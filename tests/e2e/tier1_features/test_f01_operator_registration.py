"""
Tier 1 Feature Coverage: Feature 1 - Operator-Only Registration (M1)
Requirement: Restrict self-registration to OPERATOR role unconditionally;
require explicit administrative action for promotion.
"""

import uuid
import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(1)
def test_registration_standard_user_assigned_operator(http_client: E2EHttpClient):
    """TC-F01-01: Verify registering normal email assigns OPERATOR role."""
    email = f"operator_{uuid.uuid4().hex[:8]}@example.com"
    res = http_client.register_user(email=email, name="Standard Operator")
    assert res.status_code in (200, 201), f"Unexpected status: {res.status_code}, body: {res.text}"
    data = res.json()
    role = str(data.get("role", "")).lower()
    assert role == "operator", f"Expected role 'operator', got '{role}'"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(1)
def test_registration_admin_keyword_in_email_assigned_operator(http_client: E2EHttpClient):
    """TC-F01-02: Verify registering with 'admin' in email STILL assigns OPERATOR role."""
    email = f"admin_attempt_{uuid.uuid4().hex[:8]}@surakshanet.org"
    res = http_client.register_user(email=email, name="Admin Attempter")
    assert res.status_code in (200, 201), f"Registration failed: {res.text}"
    data = res.json()
    role = str(data.get("role", "")).lower()
    assert role == "operator", f"Security violation: 'admin' email assigned '{role}' instead of 'operator'"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(1)
def test_registration_case_insensitive_admin_assigned_operator(http_client: E2EHttpClient):
    """TC-F01-03: Verify uppercase 'ADMINISTRATOR' email pattern assigns OPERATOR role."""
    email = f"SYSADMIN_{uuid.uuid4().hex[:8]}@CORP.COM"
    res = http_client.register_user(email=email, name="Sysadmin User")
    assert res.status_code in (200, 201), f"Registration failed: {res.text}"
    data = res.json()
    role = str(data.get("role", "")).lower()
    assert role == "operator", f"Case-insensitive admin check failed: got '{role}'"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(1)
def test_operator_cannot_promote_user_role(http_client: E2EHttpClient):
    """TC-F01-04: Verify unprivileged operator cannot promote user role (HTTP 403)."""
    # 1. Register operator A
    email_a = f"op_a_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "StrongPassword123!"
    http_client.register_user(email=email_a, password=pwd, name="Operator A")
    _, token_a = http_client.login_user(email_a, pwd)
    assert token_a, "Failed operator login"

    # 2. Register operator B
    email_b = f"op_b_{uuid.uuid4().hex[:8]}@test.com"
    res_b = http_client.register_user(email=email_b, password=pwd, name="Operator B")
    user_b_id = res_b.json().get("id")

    # 3. Operator A attempts to promote Operator B to ADMIN
    headers = {"Authorization": f"Bearer {token_a}"}
    patch_res = http_client.patch(
        f"/api/v1/users/{user_b_id}/role",
        json_data={"role": "ADMIN"},
        headers=headers
    )
    assert patch_res.status_code in (401, 403), f"Expected 403 Forbidden, got {patch_res.status_code}"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(1)
def test_registration_explicit_role_override_in_payload_ignored(http_client: E2EHttpClient):
    """TC-F01-05: Verify passing role='ADMIN' in registration payload is ignored/rejected."""
    email = f"role_exploit_{uuid.uuid4().hex[:8]}@test.com"
    res = http_client.register_user(
        email=email,
        name="Exploit Attempter",
        role="ADMIN"
    )
    if res.status_code in (200, 201):
        data = res.json()
        role = str(data.get("role", "")).lower()
        assert role == "operator", f"Payload injection granted role '{role}' instead of 'operator'"
    else:
        # Alternatively rejected with 422 if schema prohibits role field
        assert res.status_code == 422, f"Expected 422 or sanitized role, got {res.status_code}"
