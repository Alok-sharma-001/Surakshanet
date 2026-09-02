import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_model_health(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/ml/models/health", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded", "offline"]

@pytest.mark.asyncio
async def test_predict_junction(client: AsyncClient, auth_headers: dict):
    # This might return 404 or a fallback prediction if not trained
    junction_id = "test-junction-123"
    response = await client.get(f"/api/v1/ml/predict/{junction_id}", headers=auth_headers)
    # We accept 200 (predicted) or 400/404 (model not trained for junction)
    assert response.status_code in [200, 400, 404]

@pytest.mark.asyncio
async def test_training_status(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/ml/train/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "is_training" in data
    assert "last_trained" in data
