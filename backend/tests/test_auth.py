import uuid
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    uid = uuid.uuid4().hex[:8]
    email = f"newuser_{uid}@example.com"
    response = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "strongpassword123",
        "name": "New User"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["name"] == "New User"
    assert "id" in data

@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    uid = uuid.uuid4().hex[:8]
    payload = {
        "email": f"duplicate_{uid}@example.com",
        "password": "strongpassword123",
        "name": "Dupe User"
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    uid = uuid.uuid4().hex[:8]
    payload = {
        "email": f"logintest_{uid}@example.com",
        "password": "testpassword"
    }
    await client.post("/api/v1/auth/register", json={
        **payload,
        "name": "Login Test User"
    })
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    uid = uuid.uuid4().hex[:8]
    await client.post("/api/v1/auth/register", json={
        "email": f"wrongpass_{uid}@example.com",
        "password": "correctpassword",
        "name": "Wrong Pass User"
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": f"wrongpass_{uid}@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@test.com"
    assert data["name"] == "Test Admin"

@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
