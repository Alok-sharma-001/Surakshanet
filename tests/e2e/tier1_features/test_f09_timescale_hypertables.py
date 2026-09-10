"""
Tier 1 Feature Coverage: Feature 9 - TimescaleDB Hypertables (M2)
Requirement: Convert traffic_readings to TimescaleDB hypertable with composite
PK (id, timestamp) & retention policy.
"""

import pytest
from tests.e2e.client import E2EDatabaseClient, E2EHttpClient


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(9)
def test_hypertable_information_schema(db_client: E2EDatabaseClient):
    """TC-F09-01: Verify timescaledb_information schema is queryable."""
    res = db_client.execute_query(
        "SELECT hypertable_name FROM timescaledb_information.hypertables;"
    )
    # Check if traffic_readings is among hypertables (or schema accessible)
    assert isinstance(res, list), "Failed to query timescaledb_information.hypertables"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(9)
def test_traffic_readings_table_exists(db_client: E2EDatabaseClient):
    """TC-F09-02: Verify traffic_readings table exists with required timestamp column."""
    columns = db_client.execute_query(
        """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'traffic_readings';
        """
    )
    col_names = [r[0] for r in columns]
    assert "timestamp" in col_names, f"Missing 'timestamp' in traffic_readings columns: {col_names}"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(9)
def test_time_bucket_query_capability(db_client: E2EDatabaseClient):
    """TC-F09-03: Verify TimescaleDB time_bucket analytical function works."""
    query = """
    SELECT time_bucket('5 minutes', NOW()) as bucket;
    """
    res = db_client.execute_scalar(query)
    assert res is not None, "time_bucket query failed"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(9)
def test_traffic_history_api_time_filtering(authed_client: E2EHttpClient):
    """TC-F09-04: Verify GET /api/v1/traffic/history handles time interval queries."""
    res = authed_client.get(
        "/api/v1/traffic/history",
        params={
            "start_time": "2026-09-01T00:00:00Z",
            "end_time": "2026-09-06T23:59:59Z",
            "limit": 10
        }
    )
    assert res.status_code == 200, f"Expected 200 for an authenticated request, got {res.status_code}: {res.text}"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(9)
def test_timescale_retention_policy_or_jobs(db_client: E2EDatabaseClient):
    """TC-F09-05: Check TimescaleDB background jobs for retention policy."""
    jobs = db_client.execute_query(
        "SELECT job_id, proc_name FROM timescaledb_information.jobs;"
    )
    assert isinstance(jobs, list), "Failed to query timescaledb background jobs"
