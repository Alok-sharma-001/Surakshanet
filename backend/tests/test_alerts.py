import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/alerts/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_alert_stats(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/alerts/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "active" in data
    assert "resolved" in data
