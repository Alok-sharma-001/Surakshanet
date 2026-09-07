"""
Tier 2 Boundary & Corner Cases: Feature 1 - Registration & Role Boundaries (M1)
Boundary limits, malformed inputs, email edge cases, role boundary inputs.
"""

import uuid
import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(1)
def test_registration_empty_password_rejected(http_client: E2EHttpClient):
    """TC-B01-01: Boundary - Registration with empty string password returns 422."""
    email = f"empty_pwd_{uuid.uuid4().hex[:6]}@test.com"
    res = http_client.register_user(email=email, password="", name="Empty Pass")
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(1)
def test_registration_malformed_email_syntax(http_client: E2EHttpClient):
    """TC-B01-02: Boundary - Registration with malformed email syntax returns 422."""
    for malformed in ["not-an-email", "@nodomain.com", "user@.com", "user space@domain.com"]:
        res = http_client.register_user(email=malformed, password="Password123!", name="Bad Email")
        assert res.status_code in (400, 422), f"Malformed email '{malformed}' accepted with {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(1)
def test_registration_duplicate_email_conflict(http_client: E2EHttpClient):
    """TC-B01-03: Boundary - Attempting to register identical email twice returns 400 or 409."""
    email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "ValidPassword123!"
    res1 = http_client.register_user(email=email, password=pwd, name="First Reg")
    assert res1.status_code in (200, 201)

    res2 = http_client.register_user(email=email, password=pwd, name="Second Reg")
    assert res2.status_code in (400, 409), f"Expected duplicate email conflict, got {res2.status_code}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(1)
def test_role_promotion_invalid_role_enum(http_client: E2EHttpClient, admin_token: str):
    """TC-B01-04: Boundary - Promoting to nonexistent role string returns 422."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = http_client.patch(
        "/api/v1/users/nonexistent-id/role",
        json_data={"role": "SUPER_OVERLORD"},
        headers=headers
    )
    assert res.status_code in (404, 422), f"Invalid role enum accepted: {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(1)
def test_registration_extreme_length_name(http_client: E2EHttpClient):
    """TC-B01-05: Boundary - Name with 500+ characters handled without server error 500."""
    long_name = "A" * 512
    email = f"long_name_{uuid.uuid4().hex[:6]}@test.com"
    res = http_client.register_user(email=email, password="Password123!", name=long_name)
    assert res.status_code in (200, 201, 422), f"Extreme length name caused crash: {res.status_code}"
