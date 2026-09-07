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

@pytest.mark.asyncio
async def test_operator_registration_enforced(client: AsyncClient):
    """Ensure registration unconditionally assigns OPERATOR even if email contains 'admin'."""
    uid = uuid.uuid4().hex[:8]
    email = f"admin_candidate_{uid}@example.com"
    response = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "strongpassword123",
        "name": "Operator Candidate"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["role"] == "OPERATOR"
    assert data["role"] != "ADMIN"

@pytest.mark.asyncio
async def test_role_promotion_admin_required_and_validation(client: AsyncClient, auth_headers: dict):
    """Ensure role promotion strictly requires ADMIN and validates UserRole enum."""
    uid = uuid.uuid4().hex[:8]
    email = f"candidate_{uid}@example.com"
    password = "candidatepassword123"
    
    # 1. Register candidate user
    reg_res = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "name": "Candidate User"
    })
    assert reg_res.status_code == 201
    candidate_id = reg_res.json()["id"]

    # 2. Login as candidate (OPERATOR role)
    login_res = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    candidate_token = login_res.json()["access_token"]
    candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

    # 3. Non-admin operator cannot promote roles (403 Forbidden)
    forbidden_res = await client.patch(
        f"/api/v1/users/{candidate_id}/role?role=ADMIN",
        headers=candidate_headers
    )
    assert forbidden_res.status_code == 403

    # 4. Admin cannot promote to invalid role (400 Bad Request)
    invalid_res = await client.patch(
        f"/api/v1/users/{candidate_id}/role?role=SUPER_ROOT",
        headers=auth_headers
    )
    assert invalid_res.status_code == 400

    # 5. Admin can promote to valid role (ADMIN)
    promote_res = await client.patch(
        f"/api/v1/users/{candidate_id}/role?role=ADMIN",
        headers=auth_headers
    )
    assert promote_res.status_code == 200
    assert promote_res.json()["role"] == "ADMIN"

@pytest.mark.asyncio
async def test_logout_token_revocation(client: AsyncClient):
    """Ensure tokens are revoked on logout and subsequent requests with the token are rejected."""
    uid = uuid.uuid4().hex[:8]
    email = f"revoketest_{uid}@example.com"
    password = "testpassword123"

    await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "name": "Revoke Test User"
    })

    login_res = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Verify authenticated access works
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email

    # Logout and revoke token
    logout_res = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out"

    # Verify revoked token is rejected
    me_revoked_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_revoked_res.status_code == 401

def test_production_startup_refusal():
    """Ensure Settings refuses startup in production if default secrets are used."""
    from pydantic import ValidationError
    from app.config import Settings

    # In development, default settings pass
    dev_settings = Settings(ENVIRONMENT="development")
    assert dev_settings.ENVIRONMENT == "development"

    # In production, default JWT secret must raise ValidationError
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="your-super-secret-key-change-in-production",
            ADMIN_PASSWORD="a-secure-admin-password-2026!"
        )

    # In production, default ADMIN_PASSWORD must raise ValidationError
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a-very-secure-jwt-key-for-prod-2026!",
            ADMIN_PASSWORD="SurakshaNet@2026"
        )

    # In production, weak ADMIN_PASSWORD must raise ValidationError
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a-very-secure-jwt-key-for-prod-2026!",
            ADMIN_PASSWORD="admin"
        )

    # In production, default dev database password must raise ValidationError
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a-very-secure-jwt-key-for-prod-2026!",
            ADMIN_PASSWORD="a-strong-custom-production-password-2026",
            DATABASE_URL="postgresql+asyncpg://surakshanet:surakshanet_dev@timescaledb:5432/surakshanet"
        )

    # In production with strong secrets, startup succeeds
    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-very-secure-jwt-key-for-prod-2026!",
        ADMIN_PASSWORD="a-strong-custom-production-password-2026",
        DATABASE_URL="postgresql+asyncpg://surakshanet:a-strong-production-db-password-2026!@timescaledb:5432/surakshanet"
    )
    assert prod_settings.ENVIRONMENT == "production"

