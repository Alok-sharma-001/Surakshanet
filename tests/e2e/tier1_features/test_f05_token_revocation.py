"""
Tier 1 Feature Coverage: Feature 5 - Token Revocation & Logout (M1)
Requirement: Add jti to JWT claims, implement Redis-backed token blacklist,
and add POST /api/v1/auth/logout.
"""

import uuid
import pytest
from tests.e2e.client import E2EHttpClient, E2ERedisClient


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(5)
def test_jwt_contains_unique_jti_claim(http_client: E2EHttpClient):
    """TC-F05-01: Verify login access token payload contains a unique 'jti' claim."""
    email = f"jti_test_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "TokenPassword123!"
    http_client.register_user(email=email, password=pwd, name="JTI User")
    _, token = http_client.login_user(email=email, password=pwd)
    assert token, "Login failed to return token"

    # Decode without verification to inspect claims
    import jwt
    unverified = jwt.decode(token, options={"verify_signature": False})
    assert "jti" in unverified, f"JWT claims missing 'jti': {unverified.keys()}"
    assert len(str(unverified["jti"])) > 0, "jti claim is empty"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(5)
def test_logout_endpoint_succeeds_with_valid_token(http_client: E2EHttpClient):
    """TC-F05-02: Verify POST /api/v1/auth/logout returns 200 OK with valid token."""
    email = f"logout_test_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "TokenPassword123!"
    http_client.register_user(email=email, password=pwd, name="Logout User")
    _, token = http_client.login_user(email=email, password=pwd)
    assert token, "Login failed"

    res = http_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200, f"Logout failed: {res.status_code}, body: {res.text}"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(5)
def test_revoked_token_rejected_on_subsequent_request(http_client: E2EHttpClient):
    """TC-F05-03: Verify using a revoked token on protected endpoint returns 401 Unauthorized."""
    email = f"revoked_test_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "TokenPassword123!"
    http_client.register_user(email=email, password=pwd, name="Revoked User")
    _, token = http_client.login_user(email=email, password=pwd)
    assert token, "Login failed"

    # Logout to revoke
    logout_res = http_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_res.status_code == 200

    # Attempt to access protected endpoint (e.g. /api/v1/users/me)
    check_res = http_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert check_res.status_code == 401, f"Expected 401 for revoked token, got {check_res.status_code}"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(5)
def test_revoked_token_recorded_in_redis(http_client: E2EHttpClient, redis_client: E2ERedisClient):
    """TC-F05-04: Verify revoked token's jti is stored in Redis blacklist."""
    email = f"redis_rev_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "TokenPassword123!"
    http_client.register_user(email=email, password=pwd, name="Redis User")
    _, token = http_client.login_user(email=email, password=pwd)
    assert token, "Login failed"

    import jwt
    claims = jwt.decode(token, options={"verify_signature": False})
    jti = claims.get("jti")

    # Call logout
    http_client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    # Check redis keys
    matching_keys = redis_client.keys(f"*{jti}*")
    assert len(matching_keys) > 0, f"No key matching jti '{jti}' found in Redis"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(5)
def test_logout_without_token_returns_401(http_client: E2EHttpClient):
    """TC-F05-05: Verify calling logout without Bearer token returns 401."""
    res = http_client.post("/api/v1/auth/logout")
    assert res.status_code == 401, f"Expected 401 Unauthorized, got {res.status_code}"
