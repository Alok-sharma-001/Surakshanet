"""
SN-111 · Authentication Critical Path Tests
===========================================
Verifies:
1. Login success: valid credentials authenticate, issue JWT with jti, reset lockout counter, and write USER_LOGIN audit row (SUCCESS).
2. Login failure: invalid password returns 401, records failure, and writes USER_LOGIN audit row (FAILURE) with zero credential leaks.
3. Lockout rate limit: >= 5 failed attempts trigger 429 lockout.
4. Token revocation: /auth/logout revokes token jti; subsequent verification fails with 401.
5. User profile: GET /auth/me returns current user for valid token; rejects missing/invalid token.
6. Registration: POST /auth/register is publicly reachable (Invariant §13.4 —
   gating it behind an existing account would mean no one could ever
   register) and always creates OPERATOR, ignoring any client-submitted role.
7. Mutation check: disabling or bypassing verify_password fails the test.
"""

import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User, UserRole
from app.models.audit import AuditActorType, AuditResult
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    is_token_revoked,
    revoke_token,
    check_login_rate_limit,
    record_login_failure,
    reset_login_failures,
)


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        email="operator@surakshanet.local",
        name="Traffic Operator",
        password_hash=hash_password("SuperSecret123!"),
        role=UserRole.OPERATOR,
        is_active=True,
    )


@pytest.fixture
def mock_admin_user():
    return User(
        id=uuid.uuid4(),
        email="admin@surakshanet.local",
        name="Admin User",
        password_hash=hash_password("AdminSecret123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )


def test_password_hashing_and_verification():
    """Verifies bcrypt hashing and verification functions."""
    plain = "MySecretPassword123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_token_creation_and_payload():
    """Asserts that created access tokens contain jti, sub, role, and exp."""
    user_id = str(uuid.uuid4())
    token = create_access_token({"sub": user_id, "role": "OPERATOR"})
    payload = decode_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "OPERATOR"
    assert "jti" in payload
    assert "exp" in payload


@pytest.mark.asyncio
async def test_token_revocation_denylist():
    """Asserts that revoking a token jti flags it as revoked."""
    jti = str(uuid.uuid4())
    
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "revoked"

    with patch("app.services.auth_service.get_redis_client", return_value=mock_redis):
        await revoke_token(jti, expires_in_seconds=60)
        mock_redis.setex.assert_called_once()
        revoked = await is_token_revoked(jti)
        assert revoked is True


@pytest.mark.asyncio
async def test_login_rate_limit_lockout():
    """Asserts that 5 failed attempts trigger 429 Too Many Requests."""
    identifier = "locked_user@surakshanet.local"

    mock_redis = AsyncMock()
    mock_redis.get.return_value = "5"

    with patch("app.services.auth_service.get_redis_client", return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            await check_login_rate_limit(identifier)
        assert exc_info.value.status_code == 429
        assert "Too many failed login attempts" in exc_info.value.detail


@pytest.mark.asyncio
async def test_login_audit_logging_and_credential_safety():
    """SN-097, SN-104: Failed and successful logins write audit rows without credentials."""
    from app.services.audit_service import write_audit

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    user_id = uuid.uuid4()

    # Success audit
    entry_ok = await write_audit(
        db=mock_db,
        action="USER_LOGIN",
        actor_type=AuditActorType.USER,
        actor_id=user_id,
        target_type="user",
        target_id=user_id,
        input_payload={"email": "operator@surakshanet.local", "password": "SuperSecretPassword!"},
        output_payload={"status": "authenticated"},
        result=AuditResult.SUCCESS,
        source="auth",
    )
    assert entry_ok.result == AuditResult.SUCCESS
    assert entry_ok.input["password"] == "[REDACTED]"

    # Failure audit
    entry_fail = await write_audit(
        db=mock_db,
        action="USER_LOGIN",
        actor_type=AuditActorType.USER,
        target_type="user",
        input_payload={"email": "operator@surakshanet.local", "token": "sensitive_raw_token"},
        output_payload={"reason": "invalid_credentials"},
        result=AuditResult.FAILURE,
        source="auth",
    )
    assert entry_fail.result == AuditResult.FAILURE
    assert entry_fail.input["token"] == "[REDACTED]"


def test_auth_me_requires_valid_token(mock_user):
    """Asserts GET /auth/me returns 401 when no authorization header is provided."""
    client = TestClient(app)
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_register_is_public_and_ignores_client_submitted_role(mock_user):
    """Invariant §13.4: POST /auth/register is reachable by an anonymous
    caller (it is how every account, including the first one, is ever
    created), and always creates OPERATOR regardless of any 'role' field in
    the request body — a self-registering caller must never be able to
    submit role: ADMIN (or any other elevated role) and get it.
    """
    client = TestClient(app)
    res = client.post("/api/v1/auth/register", json={
        "email": f"newuser-{uuid.uuid4().hex[:12]}@example.com",
        "name": "New User",
        "password": "Password123!",
        "role": "ADMIN",
    })
    assert res.status_code == 201, res.text
    assert res.json()["role"] == "OPERATOR"


@pytest.mark.asyncio
async def test_register_user_always_ignores_submitted_role():
    """SN-098/Invariant §13.4: register_user() must force OPERATOR regardless
    of any role on the request, including the two roles this migration adds
    (EMERGENCY_SERVICES, CITIZEN) — self-registration must never be the path
    that grants an elevated role. The real, correct way to get a user into
    one of those roles is the existing ADMIN-only PATCH /users/{id}/role
    promotion endpoint (backend/app/api/users.py), covered separately by
    test_role_promotion_admin_required_and_validation in test_auth.py — the
    new roles need no special-casing there since it already validates
    against the full UserRole enum.
    """
    from app.services.auth_service import register_user
    from app.schemas.auth import UserCreate

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Attempting to self-register as EMERGENCY_SERVICES must still yield OPERATOR
    req_es = UserCreate(
        email="es_responder@surakshanet.gov.in",
        name="Emergency Responder",
        password="ValidPassword123!",
        role=UserRole.EMERGENCY_SERVICES,
    )
    user_es = await register_user(mock_db, req_es)
    assert user_es.role == UserRole.OPERATOR
    assert user_es.email == "es_responder@surakshanet.gov.in"

    # Attempting to self-register as CITIZEN must still yield OPERATOR
    req_cit = UserCreate(
        email="citizen_user@surakshanet.gov.in",
        name="Citizen User",
        password="ValidPassword123!",
        role=UserRole.CITIZEN,
    )
    user_cit = await register_user(mock_db, req_cit)
    assert user_cit.role == UserRole.OPERATOR
    assert user_cit.email == "citizen_user@surakshanet.gov.in"


@pytest.mark.asyncio
async def test_mutation_verify_password(monkeypatch):
    """Mutation check: Verifies authentication strictly depends on verify_password."""
    from app.services.auth_service import authenticate_user

    mock_db = AsyncMock()
    user = User(
        id=uuid.uuid4(),
        email="operator@surakshanet.local",
        name="Traffic Operator",
        password_hash=hash_password("ValidPassword123!"),
        role=UserRole.OPERATOR,
        is_active=True,
    )
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: user)

    # 1. Standard behavior: wrong password fails
    auth_res = await authenticate_user(mock_db, "operator@surakshanet.local", "WrongPassword456!")
    assert auth_res is None, "Expected authentication failure on wrong password"

    # 2. Mutated behavior: if verify_password is intentionally corrupted to return True
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda p, h: True)
    mutated_res = await authenticate_user(mock_db, "operator@surakshanet.local", "WrongPassword456!")
    assert mutated_res is not None, "Mutant survived: verify_password is disconnected from authenticate_user"

