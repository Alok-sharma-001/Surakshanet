"""
Tier 2 Boundary & Corner Cases: Feature 5 - Token Revocation Boundaries (M1)
Logout idempotency, malformed tokens, missing bearer scheme, expired tokens.
"""

import uuid
import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(5)
def test_logout_twice_idempotency(http_client: E2EHttpClient):
    """TC-B05-01: Boundary - Calling logout twice with the same token does not crash."""
    email = f"log2_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "ValidPassword123!"
    http_client.register_user(email=email, password=pwd, name="Double Logout")
    _, token = http_client.login_user(email=email, password=pwd)
    assert token, "Login failed"

    # First logout
    res1 = http_client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 200

    # Second logout
    res2 = http_client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    # Either succeeds or returns 401 (already revoked) without 500 error
    assert res2.status_code in (200, 401), f"Unexpected status on double logout: {res2.status_code}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(5)
def test_logout_with_malformed_token_string(http_client: E2EHttpClient):
    """TC-B05-02: Boundary - Calling logout with malformed JWT returns 401."""
    res = http_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"}
    )
    assert res.status_code == 401, f"Expected 401 for malformed token, got {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(5)
def test_logout_missing_bearer_scheme(http_client: E2EHttpClient):
    """TC-B05-03: Boundary - Authorization header without 'Bearer ' prefix returns 401."""
    res = http_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert res.status_code == 401, f"Expected 401 for wrong auth scheme, got {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(5)
def test_logout_empty_bearer_token(http_client: E2EHttpClient):
    """TC-B05-04: Boundary - Authorization header with 'Bearer ' and no token returns 401."""
    res = http_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer "}
    )
    assert res.status_code == 401, f"Expected 401 for empty token, got {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(5)
def test_revoked_token_reuse_across_multiple_endpoints(http_client: E2EHttpClient):
    """TC-B05-05: Boundary - Revoked token is rejected consistently across multiple endpoints."""
    email = f"reuse_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "ValidPassword123!"
    http_client.register_user(email=email, password=pwd, name="Token Reuser")
    _, token = http_client.login_user(email=email, password=pwd)

    # Revoke
    http_client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    headers = {"Authorization": f"Bearer {token}"}
    for path in ["/api/v1/auth/me", "/api/v1/users/", "/api/v1/traffic/readings"]:
        r = http_client.get(path, headers=headers)
        assert r.status_code == 401, f"Revoked token was accepted at {path}: {r.status_code}"
