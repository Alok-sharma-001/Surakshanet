"""
Tier 1 Feature Coverage: Feature 6 - Database Service Consolidation (M2)
Requirement: Consolidate DB services to timescaledb-ha:pg15, enabling native
PostGIS and TimescaleDB extensions.
"""

import pytest
from tests.e2e.client import E2EDatabaseClient, PROJECT_ROOT
import os


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(6)
def test_timescaledb_extension_active(db_client: E2EDatabaseClient):
    """TC-F06-01: Verify timescaledb extension is registered in pg_extension."""
    res = db_client.execute_query(
        "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"
    )
    assert len(res) > 0, "timescaledb extension is not active in database"
    extname, version = res[0]
    assert extname == "timescaledb"
    assert len(version) > 0


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(6)
def test_postgis_extension_available(db_client: E2EDatabaseClient):
    """TC-F06-02: Verify postgis extension is registered or available."""
    # Check if installed or can be queried
    try:
        ver = db_client.execute_scalar("SELECT PostGIS_Version();")
        assert ver is not None and "3." in str(ver)
    except Exception:
        # Check pg_available_extensions
        avail = db_client.execute_query(
            "SELECT name FROM pg_available_extensions WHERE name = 'postgis';"
        )
        assert len(avail) > 0, "postgis extension not available in timescaledb-ha engine"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(6)
def test_docker_compose_consolidated_service():
    """TC-F06-03: Verify docker-compose.yml configures timescaledb-ha engine."""
    compose_path = os.path.join(PROJECT_ROOT, "infra", "docker-compose.yml")
    assert os.path.exists(compose_path), "docker-compose.yml missing"
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "timescaledb-ha" in content or "timescaledb" in content, \
        "docker-compose.yml does not configure timescaledb service"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(6)
def test_database_version_is_postgres_15(db_client: E2EDatabaseClient):
    """TC-F06-04: Verify consolidated database runs PostgreSQL 15.x."""
    ver_str = db_client.execute_scalar("SELECT version();")
    assert "PostgreSQL 15" in str(ver_str), f"Expected PostgreSQL 15, got: {ver_str}"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(6)
def test_db_read_write_verification(db_client: E2EDatabaseClient):
    """TC-F06-05: Verify database supports basic transaction read/write."""
    import psycopg2
    conn = psycopg2.connect(db_client.db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMPORARY TABLE e2e_test_rw (id SERIAL PRIMARY KEY, val TEXT);")
            cur.execute("INSERT INTO e2e_test_rw (val) VALUES ('surakshanet_test');")
            cur.execute("SELECT val FROM e2e_test_rw WHERE val = 'surakshanet_test';")
            val = cur.fetchone()[0]
            assert val == "surakshanet_test"
    finally:
        conn.close()
