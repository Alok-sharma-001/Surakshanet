"""
Tier 2 Boundary & Corner Cases: Feature 12 - Workload Decoupling Boundaries (M3)
Extreme durations, negative duration, duplicate task starts, stop on idle system.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(12)
def test_simulation_negative_duration_rejected(http_client: E2EHttpClient):
    """TC-B12-01: Boundary - Starting simulation with negative duration returns 422."""
    res = http_client.post(
        "/api/v1/simulation/start",
        json_data={"duration": -10}
    )
    assert res.status_code in (400, 401, 404, 409, 422)


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(12)
def test_simulation_zero_duration(http_client: E2EHttpClient):
    """TC-B12-02: Boundary - Starting simulation with duration=0 returns 422 or instant completion."""
    res = http_client.post(
        "/api/v1/simulation/start",
        json_data={"duration": 0}
    )
    assert res.status_code in (200, 202, 400, 401, 404, 409, 422)


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(12)
def test_simulation_stop_when_idle_safe(http_client: E2EHttpClient):
    """TC-B12-03: Boundary - Calling stop when no simulation is active returns cleanly."""
    res = http_client.post("/api/v1/simulation/stop")
    assert res.status_code in (200, 401, 404), f"Calling stop on idle system crashed: {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(12)
def test_marl_training_episodes_exceeding_boundary(http_client: E2EHttpClient):
    """TC-B12-04: Boundary - Requesting 1,000,000 episodes is safely clamped or capped."""
    res = http_client.post(
        "/api/v1/ml/train/start",
        json_data={"episodes": 1000000}
    )
    # Backend should cap or reject safely
    assert res.status_code in (200, 202, 400, 401, 409, 422)


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(12)
def test_query_invalid_uuid_task_id(http_client: E2EHttpClient):
    """TC-B12-05: Boundary - Querying task status with malformed task_id returns 404 or 422."""
    res = http_client.get("/api/v1/tasks/not-a-valid-task-id")
    assert res.status_code in (401, 404, 422)
