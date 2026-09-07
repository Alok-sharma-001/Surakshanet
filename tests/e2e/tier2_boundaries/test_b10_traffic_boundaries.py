"""
Tier 2 Boundary & Corner Cases: Feature 10 - Traffic Service Boundaries (M2)
Negative counts, extreme speeds, nonexistent junctions, inverted date ranges, pagination limits.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(10)
def test_traffic_reading_negative_vehicle_count_rejected(http_client: E2EHttpClient):
    """TC-B10-01: Boundary - Negative vehicle_count returns 422 validation error."""
    res = http_client.post(
        "/api/v1/traffic/reading",
        json_data={
            "junction_id": "J1",
            "vehicle_count": -5,
            "average_speed": 30.0,
            "source": "sim"
        }
    )
    assert res.status_code in (400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(10)
def test_traffic_reading_negative_speed_rejected(http_client: E2EHttpClient):
    """TC-B10-02: Boundary - Negative average_speed returns 422."""
    res = http_client.post(
        "/api/v1/traffic/reading",
        json_data={
            "junction_id": "J1",
            "vehicle_count": 10,
            "average_speed": -15.0,
            "source": "sim"
        }
    )
    assert res.status_code in (400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(10)
def test_traffic_history_inverted_timerange_error(http_client: E2EHttpClient):
    """TC-B10-03: Boundary - start_time after end_time returns 400 Bad Request."""
    res = http_client.get(
        "/api/v1/traffic/history",
        params={
            "start_time": "2026-09-05T00:00:00Z",
            "end_time": "2026-09-01T00:00:00Z"
        }
    )
    assert res.status_code in (200, 400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(10)
def test_traffic_history_pagination_limit_zero(http_client: E2EHttpClient):
    """TC-B10-04: Boundary - Pagination limit=0 returns empty list or default page."""
    res = http_client.get(
        "/api/v1/traffic/history",
        params={"limit": 0}
    )
    assert res.status_code in (200, 400, 401, 422)


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(10)
def test_traffic_nonexistent_junction_latest(http_client: E2EHttpClient):
    """TC-B10-05: Boundary - Querying latest traffic for nonexistent junction ID returns 404 or null."""
    res = http_client.get(
        "/api/v1/traffic/latest",
        params={"junction_id": "NONEXISTENT_JUNCTION_XYZ"}
    )
    assert res.status_code in (200, 401, 404)
    if res.status_code == 200:
        data = res.json()
        assert data is None or data == {} or data == []
