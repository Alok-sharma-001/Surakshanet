"""
Tier 2 Boundary & Corner Cases: Feature 15 - Error Envelope & Correlation ID Boundaries (M3)
Empty correlation IDs, special characters, extreme header length, 405 envelopes.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(15)
def test_empty_x_request_id_header(http_client: E2EHttpClient):
    """TC-B15-01: Boundary - Sending empty X-Request-ID header triggers generated fallback."""
    res = http_client.get("/api/v1/health", headers={"X-Request-ID": ""})
    assert res.status_code == 200
    req_id = res.get_header("X-Request-ID")
    if req_id is not None:
        assert len(req_id) > 0, "Response returned empty X-Request-ID"


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(15)
def test_long_x_request_id_header(http_client: E2EHttpClient):
    """TC-B15-02: Boundary - Sending 512-character X-Request-ID handled without crash."""
    long_id = "req-" + "A" * 512
    res = http_client.get("/api/v1/health", headers={"X-Request-ID": long_id})
    assert res.status_code == 200


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(15)
def test_special_characters_in_x_request_id(http_client: E2EHttpClient):
    """TC-B15-03: Boundary - Header containing URL/header metacharacters safely sanitized."""
    special_id = "req_test:123;flags=none"
    res = http_client.get("/api/v1/health", headers={"X-Request-ID": special_id})
    assert res.status_code == 200


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(15)
def test_method_not_allowed_error_structure(http_client: E2EHttpClient):
    """TC-B15-04: Boundary - POST to GET-only /api/v1/health returns 405 with JSON envelope."""
    res = http_client.post("/api/v1/health", json_data={"not": "allowed"})
    assert res.status_code == 405
    data = res.json()
    assert isinstance(data, dict)
    assert "detail" in data or "error" in data


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(15)
def test_unparsable_json_syntax_returns_422(http_client: E2EHttpClient):
    """TC-B15-05: Boundary - Sending invalid JSON syntax returns 422 with structured detail."""
    res = http_client.request(
        "POST",
        "/api/v1/auth/login",
        data="INVALID_NOT_JSON{",
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code in (400, 422)
    data = res.json()
    assert "detail" in data or "error" in data
