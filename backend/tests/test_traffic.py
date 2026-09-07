import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_junction(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/traffic/junctions", json={
        "name": "Main St & 1st Ave",
        "latitude": 40.7128,
        "longitude": -74.0060
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Main St & 1st Ave"

@pytest.mark.asyncio
async def test_list_junctions(client: AsyncClient, auth_headers: dict):
    # Ensure at least one junction exists
    await client.post("/api/v1/traffic/junctions", json={
        "name": "Junction 1",
        "latitude": 0.0,
        "longitude": 0.0
    }, headers=auth_headers)
    
    response = await client.get("/api/v1/traffic/junctions", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) > 0

@pytest.mark.asyncio
async def test_get_junction(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/traffic/junctions", json={
        "name": "Junction 2",
        "latitude": 1.0,
        "longitude": 1.0
    }, headers=auth_headers)
    junction_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/traffic/junctions/{junction_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Junction 2"

@pytest.mark.asyncio
async def test_create_sensor(client: AsyncClient, auth_headers: dict):
    j_resp = await client.post("/api/v1/traffic/junctions", json={
        "name": "Sensor Junction",
        "latitude": 2.0,
        "longitude": 2.0
    }, headers=auth_headers)
    junction_id = j_resp.json()["id"]

    s_resp = await client.post("/api/v1/traffic/sensors", json={
        "junction_id": junction_id,
        "type": "camera",
        "name": "North Cam"
    }, headers=auth_headers)
    assert s_resp.status_code == 201
    assert s_resp.json()["type"] == "camera"

@pytest.mark.asyncio
async def test_create_reading(client: AsyncClient, auth_headers: dict):
    j_resp = await client.post("/api/v1/traffic/junctions", json={
        "name": "Reading Junction",
        "latitude": 3.0,
        "longitude": 3.0
    }, headers=auth_headers)
    junction_id = j_resp.json()["id"]

    s_resp = await client.post("/api/v1/traffic/sensors", json={
        "junction_id": junction_id,
        "type": "radar",
        "name": "Speed Radar"
    }, headers=auth_headers)
    sensor_id = s_resp.json()["id"]

    r_resp = await client.post("/api/v1/traffic/readings", json={
        "sensor_id": sensor_id,
        "vehicle_count": 10,
        "average_speed": 45.5,
        "timestamp": "2023-10-01T12:00:00Z"
    }, headers=auth_headers)
    assert r_resp.status_code == 201
    assert r_resp.json()["vehicle_count"] == 10

@pytest.mark.asyncio
async def test_list_readings(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/traffic/readings", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_update_junction(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/traffic/junctions", json={
        "name": "Original Junction",
        "latitude": 12.9716,
        "longitude": 77.5946
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    j_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/v1/traffic/junctions/{j_id}", json={
        "name": "Updated Junction Name",
        "latitude": 12.9800
    }, headers=auth_headers)
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Updated Junction Name"
    assert data["latitude"] == 12.9800


@pytest.mark.asyncio
async def test_traffic_reading_composite_pk_and_source(client: AsyncClient, auth_headers: dict, db_session):
    from sqlalchemy import select
    from app.models.traffic import TrafficReading

    # Verify TrafficReading has composite primary key (id, timestamp)
    pk_cols = [c.name for c in TrafficReading.__table__.primary_key.columns]
    assert "id" in pk_cols
    assert "timestamp" in pk_cols

    # Create junction and sensor
    j_resp = await client.post("/api/v1/traffic/junctions", json={
        "name": "Source Test Junction",
        "latitude": 28.6139,
        "longitude": 77.2090
    }, headers=auth_headers)
    j_id = j_resp.json()["id"]

    s_resp = await client.post("/api/v1/traffic/sensors", json={
        "junction_id": j_id,
        "type": "camera",
        "name": "Source Cam"
    }, headers=auth_headers)
    s_id = s_resp.json()["id"]

    # 1. Reading with source="sim"
    r_resp1 = await client.post("/api/v1/traffic/readings", json={
        "sensor_id": s_id,
        "vehicle_count": 42,
        "pcu_value": 35.5,
        "source": "sim",
        "timestamp": "2026-09-06T12:00:00Z"
    }, headers=auth_headers)
    assert r_resp1.status_code == 201
    r_id1 = r_resp1.json()["id"]

    # Check source in DB
    result1 = await db_session.execute(select(TrafficReading).where(TrafficReading.id == r_id1))
    db_reading1 = result1.scalar_one_or_none()
    assert db_reading1 is not None
    assert db_reading1.source == "sim"

    # 2. Reading default source="live"
    r_resp2 = await client.post("/api/v1/traffic/readings", json={
        "sensor_id": s_id,
        "vehicle_count": 15,
        "pcu_value": 15.0,
        "timestamp": "2026-09-06T12:05:00Z"
    }, headers=auth_headers)
    assert r_resp2.status_code == 201
    r_id2 = r_resp2.json()["id"]

    result2 = await db_session.execute(select(TrafficReading).where(TrafficReading.id == r_id2))
    db_reading2 = result2.scalar_one_or_none()
    assert db_reading2 is not None
    assert db_reading2.source == "live"


@pytest.mark.asyncio
async def test_mqtt_topic_standardization():
    from shared.constants import MQTT_SENSOR_TELEMETRY_TOPIC, MQTT_JUNCTION_TELEMETRY_TOPIC
    sensor_topic = MQTT_SENSOR_TELEMETRY_TOPIC.format(sensor_id="SEN-101")
    junction_topic = MQTT_JUNCTION_TELEMETRY_TOPIC.format(junction_id="JUNC-202")
    assert sensor_topic == "surakshanet/sensors/SEN-101/telemetry"
    assert junction_topic == "surakshanet/junctions/JUNC-202/telemetry"

