import pytest
import numpy as np
from ml.vision.rtsp_stream_worker import RTSPStreamWorker
from ml.vision.vehicle_detector import VehicleDetector
from shared.exceptions import VisionUnavailable

def test_rtsp_worker_frame_generation():
    """Verify synthetic frame generation and dimensions."""
    worker = RTSPStreamWorker(
        camera_url="test_url",
        junction_id="DEL-CP-01",
        target_fps=10.0,
        enable_synthetic_fallback=True
    )
    frame = worker._generate_synthetic_frame(width=640, height=360)
    assert frame is not None
    assert frame.shape == (360, 640, 3)

def test_rtsp_worker_refuses_to_fabricate_without_a_model():
    """With no YOLO weights loaded, the worker must report unavailability.

    It previously returned five hardcoded boxes at 88-96% confidence and a
    speed derived from PCU with a random jitter, all published under
    source "vision" — indistinguishable downstream from a real camera.
    """
    worker = RTSPStreamWorker(
        camera_url="test_url",
        junction_id="DEL-CP-01",
        target_fps=5.0
    )
    frame = worker._generate_synthetic_frame(width=1280, height=720)

    if worker.detector.model_loaded:
        pytest.skip("YOLO weights present; this test covers the absent-model path")

    with pytest.raises(VisionUnavailable):
        worker.process_frame(frame)


@pytest.mark.skipif(
    not VehicleDetector().model_loaded,
    reason="YOLO weights not installed on this runner"
)
def test_rtsp_worker_telemetry_contract():
    """With a real model, the payload declares what it actually measured."""
    worker = RTSPStreamWorker(
        camera_url="test_url",
        junction_id="DEL-CP-01",
        target_fps=5.0
    )
    frame = worker._generate_synthetic_frame(width=1280, height=720)
    telemetry = worker.process_frame(frame)

    assert telemetry["junction_id"] == "DEL-CP-01"
    assert "sensor_id" in telemetry
    assert telemetry["pcu_value"] >= 0.0
    # A single frame carries no displacement, so the detector cannot measure
    # speed, and it does not measure queue length either.
    assert telemetry["avg_speed"] is None
    assert telemetry["queue_length"] is None
    assert telemetry["source"] == "vision"
    assert "vehicle_breakdown" in telemetry
    assert isinstance(telemetry["vehicle_count"], int)
