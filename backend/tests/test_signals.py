import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_signal_plans(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/signals/plans", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_junction_signal_plan(client: AsyncClient, auth_headers: dict):
    # Test with any junction identifier
    response = await client.get("/api/v1/signals/junctions/Connaught", headers=auth_headers)
    if response.status_code == 200:
        data = response.json()
        assert "mode" in data
        assert "phases" in data

@pytest.mark.asyncio
async def test_signal_override(client: AsyncClient, auth_headers: dict):
    # Test override endpoint with fallback or known junction
    response = await client.get("/api/v1/signals/plans", headers=auth_headers)
    assert response.status_code == 200
    plans = response.json()
    if len(plans) > 0:
        j_id = plans[0]["junction_id"]
        override_res = await client.post(
            f"/api/v1/signals/junctions/{j_id}/override",
            json={"action": "PHASE_SKIP", "value": 5},
            headers=auth_headers
        )
        assert override_res.status_code == 200
        assert override_res.json()["status"] == "override_applied"
