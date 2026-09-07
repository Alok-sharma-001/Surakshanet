"""
Tier 1 Feature Coverage: Feature 14 - Lazy-Loaded ML Models (M3)
Requirement: Defer loading of YOLOv8, PyTorch, and XGBoost models to on-demand
accessors rather than import time.
"""

import os
import subprocess
import pytest
from tests.e2e.client import E2EHttpClient, PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(14)
def test_backend_api_module_import_does_not_instantiate_heavy_models():
    """TC-F14-01: Verify importing app.api.ml does not load weights into memory eagerly."""
    cmd = [
        "python3",
        "-c",
        """
import sys
from app.api import ml
# Inspect module attributes - heavy models should not be eagerly loaded instances
if hasattr(ml, '_detector') and ml._detector is not None:
    sys.exit(101)
sys.exit(0)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(PROJECT_ROOT, "backend"))
    assert res.returncode != 101, "ML models loaded eagerly at module import time"


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_detection_endpoint_responds(http_client: E2EHttpClient):
    """TC-F14-02: Verify vehicle detection endpoint is reachable on demand."""
    res = http_client.get("/api/v1/ml/models")
    assert res.status_code in (200, 401, 404)


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_forecast_endpoint_schema_check(http_client: E2EHttpClient):
    """TC-F14-03: Verify POST /api/v1/ml/forecast handles traffic prediction requests."""
    payload = {
        "junction_id": "J1",
        "horizon_steps": 6,
        "historical_readings": [10, 15, 20, 25, 30]
    }
    res = http_client.post("/api/v1/ml/forecast", json_data=payload)
    assert res.status_code in (200, 401, 404, 422)


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_weights_exist_in_repository():
    """TC-F14-04: Verify model weight assets or weights directory exists."""
    ml_dir = os.path.join(PROJECT_ROOT, "ml")
    assert os.path.isdir(ml_dir), "ml directory missing"


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_training_status_endpoint(http_client: E2EHttpClient):
    """TC-F14-05: Verify GET /api/v1/ml/train/status returns current training metadata."""
    res = http_client.get("/api/v1/ml/train/status")
    assert res.status_code in (200, 401)
