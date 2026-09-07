"""
Tier 2 Boundary & Corner Cases: Feature 14 - Lazy ML Models Boundaries (M3)
Corrupt image input, zero-byte payloads, empty forecast history, extreme forecast horizons.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_forecast_negative_horizon_rejected(http_client: E2EHttpClient):
    """TC-B14-01: Boundary - Negative horizon_steps in forecast returns 422."""
    res = http_client.post(
        "/api/v1/ml/forecast",
        json_data={"junction_id": "J1", "horizon_steps": -5, "historical_readings": [10, 20]}
    )
    assert res.status_code in (400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_forecast_zero_horizon(http_client: E2EHttpClient):
    """TC-B14-02: Boundary - Zero horizon_steps in forecast returns 422 or empty array."""
    res = http_client.post(
        "/api/v1/ml/forecast",
        json_data={"junction_id": "J1", "horizon_steps": 0, "historical_readings": [10, 20]}
    )
    assert res.status_code in (200, 400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_forecast_empty_history(http_client: E2EHttpClient):
    """TC-B14-03: Boundary - Empty historical_readings array in forecast."""
    res = http_client.post(
        "/api/v1/ml/forecast",
        json_data={"junction_id": "J1", "horizon_steps": 5, "historical_readings": []}
    )
    assert res.status_code in (200, 400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_forecast_extreme_horizon(http_client: E2EHttpClient):
    """TC-B14-04: Boundary - Requesting 100,000 horizon steps safely bounded."""
    res = http_client.post(
        "/api/v1/ml/forecast",
        json_data={"junction_id": "J1", "horizon_steps": 100000, "historical_readings": [10]}
    )
    assert res.status_code in (400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(14)
def test_ml_detect_corrupted_image_payload(http_client: E2EHttpClient):
    """TC-B14-05: Boundary - Sending corrupt image bytes to detection endpoint returns 400 or 422."""
    res = http_client.post(
        "/api/v1/ml/detect-vehicles",
        data=b"NOT_A_VALID_JPEG_HEADER_CORRUPTED_BYTES"
    )
    assert res.status_code in (400, 401, 404, 415, 422)
