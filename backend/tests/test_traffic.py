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
