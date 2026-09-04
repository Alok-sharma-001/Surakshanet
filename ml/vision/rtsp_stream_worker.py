import os
import time
import json
import uuid
import logging
import threading
from typing import Dict, Any, Optional
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from ml.vision.vehicle_detector import VehicleDetector

logger = logging.getLogger("surakshanet.rtsp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

class RTSPStreamWorker:
    """
    Production-grade RTSP Video Stream Ingestion Worker for Physical Smart Pole Cameras.
    
    Features:
    - Threaded non-blocking frame buffer grabber (prevents RTSP queue lag)
    - Automatic exponential backoff reconnection on RTSP disconnects / network glitches
    - Real-time YOLOv8 vehicle inference with Indian IRC PCU calculation
    - Direct MQTT telemetry publishing to Mosquitto / TimescaleDB ingestion pipeline
    - Fallback synthetic frame generator for headless CI/CD & hardware emulation
    """

    def __init__(
        self,
        camera_url: str,
        junction_id: str,
        sensor_id: Optional[str] = None,
        target_fps: float = 5.0,
        mqtt_host: str = "mosquitto",
        mqtt_port: int = 1883,
        detector: Optional[VehicleDetector] = None,
        enable_synthetic_fallback: bool = True
    ):
        self.camera_url = camera_url
        self.junction_id = junction_id
        self.sensor_id = sensor_id or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{junction_id}-CAM-NORTH"))
        self.target_fps = max(0.5, min(30.0, target_fps))
        self.interval = 1.0 / self.target_fps
        self.enable_synthetic_fallback = enable_synthetic_fallback

        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_client = None

        self.detector = detector or VehicleDetector()
        
        self.is_running = False
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._grabber_thread: Optional[threading.Thread] = None
        self._inference_thread: Optional[threading.Thread] = None

        self._connected = False
        self._telemetry_count = 0
        self._last_telemetry: Optional[Dict[str, Any]] = None

    def _setup_mqtt(self) -> None:
        """Initializes and connects MQTT publisher client."""
        if mqtt is None:
            logger.warning("paho-mqtt not installed. Telemetry will be logged without MQTT publishing.")
            return

        try:
            client_id = f"rtsp-worker-{uuid.uuid4().hex[:6]}"
            self.mqtt_client = mqtt.Client(client_id=client_id)
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
            logger.info(f"RTSP Worker connected to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            logger.warning(f"Could not connect to MQTT broker ({e}). Running in offline buffering mode.")
            self.mqtt_client = None

    def _generate_synthetic_frame(self, width: int = 1280, height: int = 720) -> np.ndarray:
        """Generates a synthetic camera frame for testing when physical camera is offline."""
        frame = np.full((height, width, 3), 40, dtype=np.uint8)
        # Draw asphalt road lanes
        frame[height // 3:, :] = [70, 70, 70]
        return frame

    def _frame_grabber_loop(self) -> None:
        """Thread worker that continuously captures the newest frame from the RTSP stream."""
        backoff = 1.0
        max_backoff = 16.0

        while self.is_running:
            cap = None
            if cv2 is not None and (self.camera_url.startswith("rtsp://") or os.path.exists(self.camera_url)):
                try:
                    logger.info(f"Attempting connection to RTSP stream: {self.camera_url}...")
                    cap = cv2.VideoCapture(self.camera_url, cv2.CAP_FFMPEG if hasattr(cv2, 'CAP_FFMPEG') else cv2.CAP_ANY)
                    if cap.isOpened():
                        logger.info("RTSP stream connection established.")
                        self._connected = True
                        backoff = 1.0
                        while self.is_running:
                            ret, frame = cap.read()
                            if not ret or frame is None:
                                logger.warning("RTSP stream frame drop or stream ended.")
                                break
                            with self._frame_lock:
                                self._latest_frame = frame
                            time.sleep(0.01)  # Yield CPU
                    else:
                        logger.warning(f"Failed to open RTSP stream at {self.camera_url}")
                except Exception as e:
                    logger.error(f"RTSP grabber exception: {e}")
                finally:
                    if cap is not None:
                        cap.release()
                    self._connected = False

            if not self.is_running:
                break

            # Fallback mode if stream is unreachable or in test environment
            if self.enable_synthetic_fallback:
                synthetic_frame = self._generate_synthetic_frame()
                with self._frame_lock:
                    self._latest_frame = synthetic_frame
                time.sleep(self.interval)
            else:
                logger.info(f"Reconnecting to RTSP in {backoff:.1f}s...")
                time.sleep(backoff)
                backoff = min(max_backoff, backoff * 2.0)

    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Runs vehicle detection on a single frame and formats standard telemetry."""
        analysis = self.detector.detect_and_analyze(frame)
        
        pcu = analysis.get("total_pcu", 25.0)
        counts = analysis.get("counts", {})
        total_veh = sum(counts.values()) if isinstance(counts, dict) else int(analysis.get("vehicle_count", 15))

        # Speed and queue estimation derived from density and link capacity
        speed = round(max(10.0, 52.0 - (pcu * 0.35) + np.random.uniform(-2, 2)), 1)
        queue = round(max(0.0, (pcu - 20.0) * 1.3), 1)

        payload = {
            "sensor_id": self.sensor_id,
            "junction_id": self.junction_id,
            "timestamp": time.time(),
            "pcu_value": round(pcu, 1),
            "avg_speed": speed,
            "queue_length": queue,
            "vehicle_count": total_veh,
            "vehicle_breakdown": counts,
            "stream_source": "RTSP_LIVE" if self._connected else "RTSP_EMULATED",
            "frame_shape": list(frame.shape[:2]) if hasattr(frame, 'shape') else [720, 1280]
        }
        return payload

    def _inference_loop(self) -> None:
        """Periodic inference loop evaluating buffered frames at target FPS."""
        while self.is_running:
            start_time = time.time()
            frame = None
            with self._frame_lock:
                if self._latest_frame is not None:
                    frame = self._latest_frame.copy()

            if frame is not None:
                try:
                    telemetry = self.process_frame(frame)
                    self._last_telemetry = telemetry
                    self._telemetry_count += 1

                    # Publish to MQTT topic
                    topic = f"surakshanet/sensors/{self.sensor_id}/telemetry"
                    if self.mqtt_client is not None:
                        self.mqtt_client.publish(topic, json.dumps(telemetry))

                    if self._telemetry_count % 10 == 0:
                        logger.info(
                            f"[{self.junction_id}] Processed frame #{self._telemetry_count} -> "
                            f"{telemetry['pcu_value']} PCU, Speed: {telemetry['avg_speed']} km/h, "
                            f"Vehicles: {telemetry['vehicle_count']}"
                        )
                except Exception as e:
                    logger.error(f"Inference error in RTSP worker: {e}")

            elapsed = time.time() - start_time
            sleep_duration = max(0.01, self.interval - elapsed)
            time.sleep(sleep_duration)

    def start(self) -> None:
        """Starts the RTSP streaming and inference worker threads."""
        if self.is_running:
            return
        self.is_running = True
        self._setup_mqtt()

        self._grabber_thread = threading.Thread(target=self._frame_grabber_loop, daemon=True, name="rtsp-grabber")
        self._inference_thread = threading.Thread(target=self._inference_loop, daemon=True, name="rtsp-inference")

        self._grabber_thread.start()
        self._inference_thread.start()
        logger.info(f"RTSP Worker started for junction {self.junction_id} (target {self.target_fps} FPS)")

    def stop(self) -> None:
        """Gracefully stops all worker threads and closes network sockets."""
        self.is_running = False
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception:
                pass
        logger.info(f"RTSP Worker stopped for junction {self.junction_id}")

    def get_status(self) -> Dict[str, Any]:
        """Returns live diagnostics of the RTSP worker."""
        return {
            "junction_id": self.junction_id,
            "sensor_id": self.sensor_id,
            "camera_url": self.camera_url,
            "is_running": self.is_running,
            "connected_to_stream": self._connected,
            "telemetry_frames_processed": self._telemetry_count,
            "last_telemetry": self._last_telemetry
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Surakshanet RTSP Live Camera Ingestion Worker")
    parser.add_argument("--rtsp", type=str, default="rtsp://admin:pass@192.168.1.100:554/live", help="RTSP Camera Stream URL")
    parser.add_argument("--junction", type=str, default="DEL-CP-01", help="Junction Identifier")
    parser.add_argument("--fps", type=float, default=5.0, help="Target inference FPS")
    parser.add_argument("--mqtt-host", type=str, default="localhost", help="MQTT Broker Host")
    args = parser.parse_args()

    worker = RTSPStreamWorker(
        camera_url=args.rtsp,
        junction_id=args.junction,
        target_fps=args.fps,
        mqtt_host=args.mqtt_host
    )
    worker.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        worker.stop()
