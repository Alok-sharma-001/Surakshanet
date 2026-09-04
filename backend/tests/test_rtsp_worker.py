import pytest
import numpy as np
from ml.vision.rtsp_stream_worker import RTSPStreamWorker

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

def test_rtsp_worker_process_frame():
    """Verify frame processing, detection dispatch, PCU conversion, and telemetry schema."""
    worker = RTSPStreamWorker(
        camera_url="test_url",
        junction_id="DEL-CP-01",
        target_fps=5.0
    )
    frame = worker._generate_synthetic_frame(width=1280, height=720)
    telemetry = worker.process_frame(frame)

    assert telemetry["junction_id"] == "DEL-CP-01"
    assert "sensor_id" in telemetry
    assert "pcu_value" in telemetry
    assert telemetry["pcu_value"] >= 0.0
    assert "avg_speed" in telemetry
    assert "queue_length" in telemetry
    assert "vehicle_breakdown" in telemetry
    assert isinstance(telemetry["vehicle_count"], int)

def test_rtsp_worker_status_diagnostics():
    """Verify worker diagnostics reporting."""
    worker = RTSPStreamWorker(
        camera_url="rtsp://dummy:554/live",
        junction_id="DEL-ITO-02",
        target_fps=5.0
    )
    status = worker.get_status()
    assert status["junction_id"] == "DEL-ITO-02"
    assert status["camera_url"] == "rtsp://dummy:554/live"
    assert status["is_running"] is False
    assert status["telemetry_frames_processed"] == 0
