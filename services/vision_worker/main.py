import os
import sys
import time
import json
import math
import logging
import threading
import asyncio
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

# Ensure repo root is available
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import redis
except ImportError:
    redis = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from shared.constants import DataSource, REDIS_CHANNELS, compute_pcu
from shared.telemetry import ApproachTelemetry, JunctionTelemetry, validate_telemetry
from shared.exceptions import VisionUnavailable
from ml.vision.vehicle_detector import VehicleDetector

from services.vision_worker.config import VisionWorkerConfig, CameraConfig, LaneConfig
from services.vision_worker.tracker import VehicleTracker, Track
from services.vision_worker.wrongway import WrongWayDetector
from services.vision_worker.parking import NoParkingDetector, ParkingZone
from services.vision_worker.behavior import RashDrivingDetector
from services.vision_worker.privacy import PrivacyBlurrer

logger = logging.getLogger("surakshanet.vision.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class VisionWorker:
    """Production Computer Vision Telemetry & Behaviour Analysis Worker (SN-069).
    
    Responsibilities:
    1. Ingestion: File/Loop/RTSP video decode at 15 fps.
    2. Inference & Tracking: YOLOv8 vehicle detection (every 3rd frame) + IoU/centroid tracking.
    3. Failure Behavior (SN-073): Explicit unavailable status; no synthetic telemetry under failures.
    4. Telemetry Emission (SN-072): Emits canonical JunctionTelemetry with source=DataSource.VISION.
    5. Behaviour Analysis: Wrong-way (SN-076), No-parking (SN-080), Rash-driving (SN-081).
    6. Privacy: Blurs face and plate regions before storage (SN-107, SN-109).
    """

    def __init__(
        self,
        config: Optional[VisionWorkerConfig] = None,
        config_path: Optional[str] = None,
        detector: Optional[VehicleDetector] = None,
        enable_synthetic_fallback: bool = False,
    ):
        self.config = config or VisionWorkerConfig.load(config_path)
        self.enable_synthetic_fallback = enable_synthetic_fallback

        # Status attributes (SN-073)
        self.is_running = False
        self._healthy = False
        self._unavailable_reason: Optional[str] = "Worker not started"
        self._current_fps: float = 0.0
        self._frames_processed: int = 0
        self._frames_dropped: int = 0
        self._last_frame_time: float = 0.0

        # Shared detector (CPU/GPU)
        try:
            self.detector = detector or VehicleDetector()
        except Exception as e:
            self.detector = None
            self._unavailable_reason = f"Model load failure: {e}"
            logger.error(f"Failed to initialize VehicleDetector: {e}")

        # Per-camera components
        self.trackers: Dict[str, VehicleTracker] = {}
        self.wrongway_detectors: Dict[str, WrongWayDetector] = {}
        self.parking_detectors: Dict[str, NoParkingDetector] = {}
        self.behavior_detectors: Dict[str, RashDrivingDetector] = {}
        self.privacy_blurrers: Dict[str, PrivacyBlurrer] = {}

        for cam_id, cam_cfg in self.config.cameras.items():
            self.trackers[cam_id] = VehicleTracker(max_age=15, min_hits=3)
            self.wrongway_detectors[cam_id] = WrongWayDetector(cam_cfg, fps=cam_cfg.fps)
            self.parking_detectors[cam_id] = NoParkingDetector(cam_id)
            self.behavior_detectors[cam_id] = RashDrivingDetector(cam_cfg)
            self.privacy_blurrers[cam_id] = PrivacyBlurrer(anpr_enabled=self.config.anpr_enabled)

        # Redis connection
        self.redis_client = None
        self._setup_redis()

        # In-memory latest state for API polling
        self._latest_detections: Dict[str, Dict[str, Any]] = {}
        self._worker_thread: Optional[threading.Thread] = None

        # Operator-drawn restricted zones (SN-079/SN-080): load once at
        # startup so a freshly-drawn zone doesn't require a worker restart to
        # take effect; refreshed periodically in _stream_loop.
        self.db_conn = None
        self._last_zone_refresh: float = 0.0
        self._refresh_zones()

    def _build_db_dsn(self) -> Optional[str]:
        """Builds a plain psycopg2 DSN mirroring backend/app/config.py's DATABASE_URL assembly."""
        host = os.environ.get("POSTGRES_HOST", "postgres")
        if host == "localhost":
            host = "127.0.0.1"
        return (
            f"host={host} port={os.environ.get('POSTGRES_PORT', '5432')} "
            f"dbname={os.environ.get('POSTGRES_DB', 'surakshanet')} "
            f"user={os.environ.get('POSTGRES_USER', 'surakshanet')} "
            f"password={os.environ.get('POSTGRES_PASSWORD', 'surakshanet_dev')}"
        )

    def _get_db_conn(self):
        """Returns a live psycopg2 connection, reconnecting on failure.

        Used only to read back operator-drawn no_parking_zones rows (SN-079)
        so the running NoParkingDetector (SN-080) actually sees them — the
        same "own-process direct DB access" pattern
        simulation/sumo_live_bridge.py uses for emergency_events.
        """
        if psycopg2 is None:
            return None
        if self.db_conn is not None:
            try:
                if self.db_conn.closed == 0:
                    return self.db_conn
            except Exception:
                pass
        try:
            self.db_conn = psycopg2.connect(self._build_db_dsn())
            self.db_conn.autocommit = True
            return self.db_conn
        except Exception as e:
            logger.debug(f"No-parking zone DB connection unavailable ({e}); zones stay whatever was last loaded.")
            self.db_conn = None
            return None

    def _refresh_zones(self):
        """Reloads no_parking_zones from Postgres into each camera's detector."""
        conn = self._get_db_conn()
        if conn is None:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, camera_id, name, polygon, active_start_time, active_end_time "
                    "FROM no_parking_zones"
                )
                rows = cur.fetchall()
        except Exception as e:
            logger.warning(f"Could not query no_parking_zones: {e}")
            return

        by_camera: Dict[str, List[ParkingZone]] = {cam_id: [] for cam_id in self.config.cameras}
        for zone_id, camera_id, name, polygon, start_t, end_t in rows:
            if camera_id not in by_camera:
                continue
            by_camera[camera_id].append(ParkingZone(
                zone_id=str(zone_id),
                name=name,
                camera_id=camera_id,
                polygon=polygon,
                active_start_time=start_t,
                active_end_time=end_t,
            ))

        for cam_id, zones in by_camera.items():
            if cam_id in self.parking_detectors:
                self.parking_detectors[cam_id].set_zones(zones)
        self._last_zone_refresh = time.time()

    def _setup_redis(self):
        if redis is None:
            logger.warning("redis-py not installed. PubSub broadcasting disabled.")
            return
        try:
            url = self.config.redis_url
            if "@redis:" in url or "redis://redis:" in url:
                url = url.replace("redis://redis:6379", "redis://127.0.0.1:6379")
            self.redis_client = redis.from_url(url, decode_responses=False)
            self.redis_client.ping()
            logger.info("Vision Worker connected to Redis successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis ({e}). Telemetry will run in local mode.")
            self.redis_client = None

    def get_status(self) -> Dict[str, Any]:
        """Returns live diagnostics of the vision worker (SN-073)."""
        now = time.time()
        # Stale frame check: if no frame processed in > 5s while running
        is_stale = self.is_running and (now - self._last_frame_time > 5.0)
        status_str = "healthy" if (self.is_running and self._healthy and not is_stale) else "unavailable"
        reason = self._unavailable_reason if status_str == "unavailable" else None
        if is_stale and status_str == "unavailable" and not reason:
            reason = "frame timeout / stream stalled"

        return {
            "status": status_str,
            "worker_running": self.is_running,
            "reason": reason,
            "fps": round(self._current_fps, 1) if status_str == "healthy" else None,
            "frames_processed": self._frames_processed,
            "frames_dropped": self._frames_dropped,
            "cameras": list(self.config.cameras.keys()),
            "anpr_enabled": self.config.anpr_enabled,
        }

    def _update_redis_status(self):
        """Persists heartbeat status to Redis with short TTL (5s)."""
        if self.redis_client:
            try:
                status_payload = json.dumps(self.get_status())
                self.redis_client.set("vision_worker:status", status_payload, ex=6)
            except Exception:
                pass

    def _build_approach_telemetry(self, camera: CameraConfig, tracks: List[Track], window_s: float) -> List[ApproachTelemetry]:
        """Aggregates tracked vehicles per approach over the window into canonical telemetry (SN-072)."""
        approaches: List[ApproachTelemetry] = []

        # Group lanes by direction ("N", "E", "S", "W")
        direction_lanes: Dict[str, List[LaneConfig]] = {}
        for lane in camera.lanes:
            direction_lanes.setdefault(lane.direction, []).append(lane)

        # Fallback if no lanes declared: synthesize default single approach
        if not direction_lanes:
            direction_lanes["N"] = [LaneConfig(id="L0", direction="N", polygon=[[0, 0], [1280, 0], [1280, 720], [0, 720]], expected_heading_deg=0.0)]

        for dir_code, lanes in direction_lanes.items():
            lane_ids = [l.id for l in lanes]
            matching_tracks = []
            for t in tracks:
                cx, cy = t.centroid
                for l in lanes:
                    if l.contains_point(cx, cy):
                        matching_tracks.append(t)
                        break

            v_count = float(len(matching_tracks))
            breakdown: Dict[str, int] = {}
            speeds_kmh = []
            stationary_count = 0
            accum_wait = 0.0
            total_bbox_area = 0.0

            for t in matching_tracks:
                v_cls = t.vehicle_class
                breakdown[v_cls] = breakdown.get(v_cls, 0) + 1
                sp = t.get_speed_kmh(camera.mpp, window_s=1.0)
                if sp is not None:
                    speeds_kmh.append(sp)

                disp = t.get_displacement(last_n=10)
                if disp < 15.0:
                    stationary_count += 1
                    accum_wait += window_s

                bw = t.bbox[2] - t.bbox[0]
                bh = t.bbox[3] - t.bbox[1]
                total_bbox_area += (bw * bh)

            # PCU using canonical shared calculation (SN-074)
            pcu = compute_pcu(breakdown) if breakdown else (v_count * 1.0)

            # Mean speed from calibrated tracks (SN-072). None whenever no track in
            # this window has a resolvable speed — uncalibrated camera, or simply no
            # track yet has 2+ position samples inside the window. Never a fabricated
            # 0.0, which would be indistinguishable from a real "traffic stopped" reading.
            mean_speed = round(float(np.mean(speeds_kmh)), 1) if speeds_kmh else None

            # Occupancy: ratio of vehicle bbox area to lane polygon area
            total_lane_area = sum(l.area for l in lanes)
            occ = round(min(1.0, max(0.0, total_bbox_area / max(1.0, total_lane_area))), 3)

            # Queue length in metres (stationary tracks * 5.5m vehicle space)
            queue_m = round(stationary_count * 5.5, 1)

            approaches.append(ApproachTelemetry(
                direction=dir_code,
                lane_ids=lane_ids,
                vehicle_count=v_count,
                pcu=pcu,
                queue_length_m=queue_m,
                mean_speed_kmh=mean_speed,
                occupancy=occ,
                accumulated_wait_s=accum_wait,
                vehicle_breakdown=breakdown,
            ))

        return approaches

    def process_frame_for_camera(
        self,
        cam_id: str,
        frame: np.ndarray,
        timestamp: float,
        run_detector: bool = True
    ) -> Tuple[List[Track], List[Dict[str, Any]]]:
        """Runs detection (if interval), updates tracker, evaluates behavior detectors,
        and returns active tracks and newly flagged behavior events.
        """
        camera = self.config.cameras[cam_id]
        tracker = self.trackers[cam_id]
        raw_detections = []

        if run_detector:
            if not self.detector or not self.detector.model_loaded:
                raise VisionUnavailable("YOLO detector weights not loaded")
            analysis = self.detector.detect_and_analyze(frame)
            raw_detections = analysis.get("detections", [])
            # Tracking update on detection frame (SN-071)
            active_tracks = tracker.update(raw_detections, timestamp=timestamp, is_detection_frame=True)
        else:
            # Tracking fills the gaps between detector runs (SN-071)
            active_tracks = tracker.update(None, timestamp=timestamp, is_detection_frame=False)

        # Behaviour analysis (SN-076, SN-080, SN-081)
        flags = []
        # 1. Wrong-way detection
        ww_flags = self.wrongway_detectors[cam_id].process_tracks(active_tracks, timestamp)
        flags.extend(ww_flags)

        # 2. No-parking detection (with queue context)
        np_flags = self.parking_detectors[cam_id].process_tracks(active_tracks, timestamp)
        flags.extend(np_flags)

        # 3. Rash driving proxies
        rd_flags = self.behavior_detectors[cam_id].process_tracks(active_tracks, timestamp)
        flags.extend(rd_flags)

        return active_tracks, flags

    def _publish_telemetry(self, camera: CameraConfig, approaches: List[ApproachTelemetry], timestamp: float):
        """Builds validated JunctionTelemetry and publishes to Redis (SN-072)."""
        jt = JunctionTelemetry(
            junction_id=camera.junction_id,
            source=DataSource.VISION,
            approaches=approaches,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp)),
            schema_version="1.0"
        )
        validated = validate_telemetry(jt.to_dict())

        if self.redis_client:
            try:
                ch = REDIS_CHANNELS["traffic"]
                self.redis_client.publish(ch, validated.to_json())
            except Exception as e:
                logger.error(f"Failed to publish vision telemetry to Redis: {e}")

    def _publish_detections_and_flags(self, cam_id: str, tracks: List[Track], flags: List[Dict[str, Any]], frame_shape: Tuple[int, int]):
        """Publishes real-time detection boxes and raises behavior alerts."""
        h, w = frame_shape
        boxes = []
        counts = {"cars": 0, "buses": 0, "bikes": 0, "pedestrians": 0}

        color_map = {
            "car": "#e5584d",
            "bus": "#1e293b",
            "truck": "#334155",
            "motorcycle": "#d97706",
            "auto_rickshaw": "#059669",
            "bicycle": "#10b981",
        }

        for t in tracks:
            bx1, by1, bx2, by2 = t.bbox
            v_cls = t.vehicle_class
            if v_cls in ("car", "lcv"):
                counts["cars"] += 1
            elif v_cls in ("bus", "truck"):
                counts["buses"] += 1
            elif v_cls in ("motorcycle", "bicycle", "auto_rickshaw"):
                counts["bikes"] += 1

            boxes.append({
                "id": t.track_id,
                "label": f"{v_cls.upper()} [{t.track_id}]",
                "confidence": round(t.confidence * 100.0, 1),
                "color": color_map.get(v_cls, "#e5584d"),
                "top": round((by1 / h) * 100.0, 1),
                "left": round((bx1 / w) * 100.0, 1),
                "width": round(((bx2 - bx1) / w) * 100.0, 1),
                "height": round(((by2 - by1) / h) * 100.0, 1),
                # Real values for durable cv_detections persistence (SN-078
                # acceptance: "every box traces to a cv_detections row") —
                # kept alongside the frontend's normalized-% fields above,
                # which stay unchanged.
                "vehicle_class": v_cls,
                "raw_bbox": [round(bx1, 1), round(by1, 1), round(bx2, 1), round(by2, 1)],
                "pcu": compute_pcu({v_cls: 1}),
            })

        detection_payload = {
            "camera_id": cam_id,
            "fps": round(self._current_fps, 1),
            "detections": boxes,
            "counts": counts,
            "timestamp": time.time(),
        }
        self._latest_detections[cam_id] = detection_payload

        if self.redis_client:
            try:
                # 1. Update latest detections in Redis key and pubsub
                self.redis_client.set(f"vision_worker:detections:{cam_id}", json.dumps(detection_payload), ex=5)
                self.redis_client.publish(REDIS_CHANNELS["cv_detections"], json.dumps(detection_payload))

                # 2. Publish flags to alerts channel and persist
                for flag in flags:
                    self.redis_client.publish(REDIS_CHANNELS["alerts"], json.dumps(flag))
            except Exception:
                pass

    def run_on_clip(self, clip_path: str, max_frames: Optional[int] = None, camera_id: str = "CAM-01") -> List[Dict[str, Any]]:
        """Synchronous run on a fixture video clip for offline testing and verification (SN-121)."""
        if not os.path.exists(clip_path):
            raise FileNotFoundError(f"Fixture clip not found at {clip_path}")

        if cv2 is None:
            raise RuntimeError("OpenCV (cv2) required for clip processing")

        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video clip {clip_path}")

        camera = self.config.cameras.get(camera_id)
        if not camera:
            camera = CameraConfig(id=camera_id, junction_id="J0", source=clip_path, fps=15.0)

        emitted_telemetry = []
        frame_idx = 0
        window_start = time.time()
        current_ts = window_start

        try:
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                frame_idx += 1
                current_ts += (1.0 / camera.fps)

                # Detection every 3rd frame
                do_detect = (frame_idx % self.config.detect_interval == 1)
                tracks, flags = self.process_frame_for_camera(camera_id, frame, current_ts, run_detector=do_detect)

                # Aggregate telemetry every 2.0 seconds
                if (current_ts - window_start) >= self.config.aggregation_window_s:
                    approaches = self._build_approach_telemetry(camera, tracks, self.config.aggregation_window_s)
                    self._publish_telemetry(camera, approaches, current_ts)
                    emitted_telemetry.append({
                        "timestamp": current_ts,
                        "approaches": [a.to_dict() for a in approaches],
                        "tracks_count": len(tracks)
                    })
                    window_start = current_ts

                if max_frames and frame_idx >= max_frames:
                    break
        finally:
            cap.release()

        return emitted_telemetry

    def _stream_loop(self):
        """Main non-blocking ingestion and inference loop."""
        logger.info("Vision Worker stream loop started.")
        self.is_running = True
        self._healthy = False

        # Pick primary camera
        cam_id = list(self.config.cameras.keys())[0] if self.config.cameras else "CAM-01"
        camera = self.config.cameras.get(cam_id)
        if not camera or not camera.source:
            self._unavailable_reason = "no video source configured"
            self._healthy = False
            self._update_redis_status()
            logger.warning("No video source configured. Worker entering unavailable state.")
            return

        source = camera.source
        target_fps = self.config.decode_fps
        frame_interval = 1.0 / target_fps
        window_start_time = time.time()
        fps_timer = time.time()
        fps_frame_count = 0

        while self.is_running:
            # Check source accessibility
            cap = None
            if cv2 is not None:
                try:
                    if os.path.exists(source) or source.startswith("rtsp://") or source.startswith("http://"):
                        cap = cv2.VideoCapture(source)
                    else:
                        self._unavailable_reason = f"video source not accessible: {source}"
                        self._healthy = False
                        self._update_redis_status()
                        time.sleep(1.0)
                        continue
                except Exception as e:
                    self._unavailable_reason = f"decode error: {e}"
                    self._healthy = False
                    self._update_redis_status()
                    time.sleep(1.0)
                    continue

            if cap is None or not cap.isOpened():
                if self.enable_synthetic_fallback:
                    # Synthetic generator for headless CI testing only
                    self._healthy = True
                    self._unavailable_reason = None
                else:
                    self._unavailable_reason = "failed to open video source"
                    self._healthy = False
                    self._update_redis_status()
                    time.sleep(1.0)
                    continue
            else:
                self._healthy = True
                self._unavailable_reason = None

            frame_idx = 0
            while self.is_running:
                loop_start = time.time()
                frame = None

                if cap is not None and cap.isOpened():
                    ret, raw_frame = cap.read()
                    if not ret or raw_frame is None:
                        # Looping file mode
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, raw_frame = cap.read()
                        if not ret:
                            self._unavailable_reason = "decode error: EOF or corrupted stream"
                            self._healthy = False
                            break
                    frame = raw_frame
                elif self.enable_synthetic_fallback:
                    frame = np.full((720, 1280, 3), 40, dtype=np.uint8)

                if frame is None:
                    break

                self._frames_processed += 1
                self._last_frame_time = time.time()
                frame_idx += 1
                now_ts = time.time()

                # Calculate FPS
                fps_frame_count += 1
                if now_ts - fps_timer >= 1.0:
                    self._current_fps = fps_frame_count / (now_ts - fps_timer)
                    fps_frame_count = 0
                    fps_timer = now_ts

                # Periodically pick up newly drawn/edited no-parking zones (SN-079/080)
                if now_ts - self._last_zone_refresh >= 30.0:
                    self._refresh_zones()

                # Process frame (detect every 3rd frame)
                try:
                    do_detect = (frame_idx % self.config.detect_interval == 1)
                    tracks, flags = self.process_frame_for_camera(cam_id, frame, now_ts, run_detector=do_detect)
                    self._publish_detections_and_flags(cam_id, tracks, flags, frame.shape[:2])

                    # 2-second telemetry aggregation window (SN-072)
                    if now_ts - window_start_time >= self.config.aggregation_window_s:
                        approaches = self._build_approach_telemetry(camera, tracks, self.config.aggregation_window_s)
                        self._publish_telemetry(camera, approaches, now_ts)
                        window_start_time = now_ts
                except VisionUnavailable as e:
                    self._unavailable_reason = str(e)
                    self._healthy = False
                except Exception as e:
                    logger.error(f"Error in vision worker processing loop: {e}")

                self._update_redis_status()

                # Timing and frame backlog management (SN-073)
                elapsed = time.time() - loop_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    # Drop frame count on backlog
                    self._frames_dropped += 1

            if cap is not None:
                cap.release()

        self._healthy = False
        self._unavailable_reason = "worker stopped"
        self._update_redis_status()
        logger.info("Vision Worker stream loop ended.")

    def start(self):
        """Starts worker thread."""
        if self.is_running:
            return
        self.is_running = True
        self._worker_thread = threading.Thread(target=self._stream_loop, daemon=True, name="vision-worker")
        self._worker_thread.start()
        logger.info("Vision Worker service started.")

    def stop(self):
        """Gracefully stops worker."""
        self.is_running = False
        self._healthy = False
        self._unavailable_reason = "worker stopped"
        self._update_redis_status()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        logger.info("Vision Worker service stopped.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SurakshaNet Vision Worker")
    parser.add_argument("--config", type=str, default=None, help="Path to cameras.yaml")
    parser.add_argument("--source", type=str, default=None, help="Video stream or file source")
    parser.add_argument("--camera", type=str, default="CAM-01", help="Camera identifier")
    args = parser.parse_args()

    worker = VisionWorker(config_path=args.config)
    if args.source and args.camera in worker.config.cameras:
        worker.config.cameras[args.camera].source = args.source

    worker.start()
    try:
        while True:
            time.sleep(1)
            status = worker.get_status()
            logger.info(f"Worker status: {status['status']} (FPS: {status['fps']})")
    except KeyboardInterrupt:
        worker.stop()
