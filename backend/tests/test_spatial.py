import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from app.models.junction import Junction
from app.models.traffic import TrafficReading


@pytest.mark.asyncio
async def test_postgis_location_point_sync():
    """Verify Junction model coordinates automatically sync with PostGIS location geometry."""
    junction = Junction(
        name="Connaught Place",
        latitude=28.6304,
        longitude=77.2177,
        num_approaches=4
    )
    assert junction.location is not None
    assert "77.2177" in str(junction.location)
    assert "28.6304" in str(junction.location)

    # Test coordinate update sync
    junction.latitude = 28.6500
    assert "28.65" in str(junction.location)
    junction.longitude = 77.2500
    assert "77.25" in str(junction.location)


@pytest.mark.asyncio
async def test_spatial_nearest_junction_endpoint(client: AsyncClient, auth_headers: dict):
    """Verify /api/v1/traffic/junctions/spatial/nearest correctly identifies closest junction."""
    # 1. Create Delhi Junction
    delhi_resp = await client.post("/api/v1/traffic/junctions", json={
        "name": "Delhi Connaught Place",
        "latitude": 28.6304,
        "longitude": 77.2177
    }, headers=auth_headers)
    assert delhi_resp.status_code == 201

    # 2. Create Bangalore Junction
    blr_resp = await client.post("/api/v1/traffic/junctions", json={
        "name": "Bangalore Silk Board",
        "latitude": 12.9176,
        "longitude": 77.6238
    }, headers=auth_headers)
    assert blr_resp.status_code == 201

    # 3. Query near Delhi location (28.6310, 77.2180) -> should match Delhi Connaught Place
    nearest_resp = await client.get(
        "/api/v1/traffic/junctions/spatial/nearest?latitude=28.6310&longitude=77.2180",
        headers=auth_headers
    )
    assert nearest_resp.status_code == 200
    data = nearest_resp.json()
    assert data["name"] == "Delhi Connaught Place"
    assert round(data["latitude"], 2) == 28.63


@pytest.mark.asyncio
async def test_spatial_radius_query(client: AsyncClient, auth_headers: dict):
    """Verify /api/v1/traffic/junctions/spatial/radius filters by distance."""
    # Create test junction
    await client.post("/api/v1/traffic/junctions", json={
        "name": "India Gate Circle",
        "latitude": 28.6129,
        "longitude": 77.2295
    }, headers=auth_headers)

    # Query within 2km of India Gate
    resp = await client.get(
        "/api/v1/traffic/junctions/spatial/radius?latitude=28.6129&longitude=77.2295&radius_meters=2000",
        headers=auth_headers
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    names = [j["name"] for j in results]
    assert "India Gate Circle" in names
    assert "Bangalore Silk Board" not in names


@pytest.mark.asyncio
async def test_spatial_bbox_query(client: AsyncClient, auth_headers: dict):
    """Verify /api/v1/traffic/junctions/spatial/bbox filters within latitude/longitude envelope."""
    # Delhi BBox: lat 28.5 to 28.7, lon 77.1 to 77.3
    resp = await client.get(
        "/api/v1/traffic/junctions/spatial/bbox?min_lat=28.5&min_lon=77.1&max_lat=28.7&max_lon=77.3",
        headers=auth_headers
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    names = [j["name"] for j in results]
    assert "Delhi Connaught Place" in names
    assert "Bangalore Silk Board" not in names


@pytest.mark.asyncio
async def test_timescaledb_hypertable_metadata(db_session):
    """Verify traffic_readings is partitioned as a TimescaleDB hypertable."""
    dialect = db_session.bind.dialect.name if db_session.bind else "postgresql"
    if dialect == "postgresql":
        result = await db_session.execute(text(
            "SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_name = 'traffic_readings';"
        ))
        row = result.scalar_one_or_none()
        assert row == "traffic_readings", "traffic_readings must be registered as a TimescaleDB hypertable"

        # Verify retention policy is attached
        jobs_result = await db_session.execute(text(
            "SELECT hypertable_name, config FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention' AND hypertable_name = 'traffic_readings';"
        ))
        job = jobs_result.mappings().first()
        assert job is not None, "Retention policy job must be registered on traffic_readings"
        # SN-108 / docs/17-security-privacy.md §4: traffic_readings (derived
        # counts, no personal data) is retained 1 year for trend analysis —
        # not the earlier 90-day placeholder migration 001 originally set.
        assert "1 year" in str(job["config"]), "Retention policy must be 1 year"
