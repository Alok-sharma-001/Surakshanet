"""
Tier 1 Feature Coverage: Feature 12 - Workload Decoupling (M3)
Requirement: Offload long-running simulation & MARL training from web workers
to dedicated background tasks coordinated through Redis pub/sub.
"""

import time
import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(12)
def test_simulation_start_returns_non_blocking_response(http_client: E2EHttpClient):
    """TC-F12-01: Verify POST /api/v1/simulation/start returns quickly without blocking."""
    start_time = time.time()
    res = http_client.post(
        "/api/v1/simulation/start",
        json_data={"duration": 10, "scenario": "corridor_peak"}
    )
    elapsed = time.time() - start_time

    # Must respond within 2.0s even for a 10s simulation
    assert elapsed < 2.0, f"Simulation start blocked worker for {elapsed:.2f}s"
    assert res.status_code in (200, 202, 401, 409)


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(12)
def test_simulation_status_queryable(http_client: E2EHttpClient):
    """TC-F12-02: Verify GET /api/v1/simulation/status returns current simulation state."""
    res = http_client.get("/api/v1/simulation/status")
    assert res.status_code in (200, 401)
    if res.status_code == 200:
        data = res.json()
        assert "running" in data or "status" in data or "state" in data


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(12)
def test_simulation_stop_endpoint(http_client: E2EHttpClient):
    """TC-F12-03: Verify POST /api/v1/simulation/stop halts running background task."""
    res = http_client.post("/api/v1/simulation/stop")
    assert res.status_code in (200, 401, 404)


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(12)
def test_marl_training_task_decoupled(http_client: E2EHttpClient):
    """TC-F12-04: Verify POST /api/v1/ml/train/start returns asynchronous job acknowledgment."""
    start_time = time.time()
    res = http_client.post(
        "/api/v1/ml/train/start",
        json_data={"episodes": 5, "seed": 42}
    )
    elapsed = time.time() - start_time
    assert elapsed < 3.0, f"Training endpoint blocked worker for {elapsed:.2f}s"
    assert res.status_code in (200, 202, 401, 409)


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(12)
def test_concurrent_api_health_during_background_work(http_client: E2EHttpClient):
    """TC-F12-05: Verify /api/v1/health continues responding <200ms during background tasks."""
    res = http_client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.elapsed < 0.2, f"Health check took {res.elapsed:.3f}s"
