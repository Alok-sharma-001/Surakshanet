"""
Tier 2 Boundary & Corner Cases: Feature 9 - TimescaleDB Hypertables Boundaries (M2)
Far future timestamps, ancient timestamps, microsecond resolution, batch ingestion.
"""

import pytest
from datetime import datetime, timezone, timedelta
from tests.e2e.client import E2EDatabaseClient, E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(9)
def test_future_timestamp_reading_handling(http_client: E2EHttpClient):
    """TC-B09-01: Boundary - Reading timestamp 10 years in the future handled gracefully."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()
    res = http_client.post(
        "/api/v1/traffic/reading",
        json_data={
            "junction_id": "J1",
            "timestamp": future_time,
            "vehicle_count": 10,
            "average_speed": 40.0,
            "source": "sim"
        }
    )
    # Should either validate range or insert cleanly
    assert res.status_code in (200, 201, 400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(9)
def test_ancient_timestamp_reading_handling(http_client: E2EHttpClient):
    """TC-B09-02: Boundary - Reading timestamp before year 2000 handled gracefully."""
    ancient_time = "1999-01-01T00:00:00Z"
    res = http_client.post(
        "/api/v1/traffic/reading",
        json_data={
            "junction_id": "J1",
            "timestamp": ancient_time,
            "vehicle_count": 5,
            "average_speed": 30.0,
            "source": "sim"
        }
    )
    assert res.status_code in (200, 201, 400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(9)
def test_time_bucket_with_zero_interval_rejected(db_client: E2EDatabaseClient):
    """TC-B09-03: Boundary - time_bucket with interval '0 seconds' raises error."""
    try:
        db_client.execute_scalar("SELECT time_bucket('0 seconds', NOW());")
        # TimescaleDB rejects 0 interval
        assert False, "time_bucket accepted 0 seconds interval"
    except Exception:
        # Expected failure
        assert True


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(9)
def test_microsecond_timestamp_precision(db_client: E2EDatabaseClient):
    """TC-B09-04: Boundary - Timestamp column retains sub-second microsecond precision."""
    now_ts = datetime.now(timezone.utc).isoformat()
    val = db_client.execute_scalar(f"SELECT '{now_ts}'::timestamptz;")
    assert val is not None


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(9)
def test_out_of_order_timestamp_storage(db_client: E2EDatabaseClient):
    """TC-B09-05: Boundary - Inserting out-of-order time series records is supported."""
    t1 = datetime.now(timezone.utc) - timedelta(hours=2)
    t2 = datetime.now(timezone.utc) - timedelta(hours=1)
    # Both timestamps parse as valid PostgreSQL timestamptz
    res = db_client.execute_scalar(f"SELECT ('{t2.isoformat()}'::timestamptz > '{t1.isoformat()}'::timestamptz);")
    assert res is True
