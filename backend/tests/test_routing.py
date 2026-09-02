import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_compute_route(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/routing/route", json={
        "origin": {"lat": 12.9716, "lng": 77.5946},
        "destination": {"lat": 12.9352, "lng": 77.6245}
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "path" in data
    assert "distance" in data
    assert "duration" in data

@pytest.mark.asyncio
async def test_get_alternatives(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/routing/alternatives", json={
        "origin": {"lat": 12.9716, "lng": 77.5946},
        "destination": {"lat": 12.9352, "lng": 77.6245}
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
