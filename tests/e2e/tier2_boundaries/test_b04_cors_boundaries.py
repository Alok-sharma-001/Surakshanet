"""
Tier 2 Boundary & Corner Cases: Feature 4 - CORS & HTTPS Boundaries (M1)
Origin spoofing, null origins, query preservation on redirect, method boundaries.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(4)
def test_cors_subdomain_spoofing_rejected(http_client: E2EHttpClient):
    """TC-B04-01: Boundary - Origin 'http://localhost:5173.evil.com' is not granted access."""
    spoofed = "http://localhost:5173.evil.com"
    res = http_client.options(
        "/api/v1/health",
        headers={"Origin": spoofed, "Access-Control-Request-Method": "GET"}
    )
    allow_origin = res.get_header("Access-Control-Allow-Origin")
    assert allow_origin != spoofed, f"Subdomain spoofing origin '{spoofed}' was accepted"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(4)
def test_cors_null_origin_handling(http_client: E2EHttpClient):
    """TC-B04-02: Boundary - Origin 'null' (sandboxed document) does not grant credentials."""
    res = http_client.options(
        "/api/v1/health",
        headers={"Origin": "null", "Access-Control-Request-Method": "GET"}
    )
    allow_origin = res.get_header("Access-Control-Allow-Origin")
    allow_creds = res.get_header("Access-Control-Allow-Credentials")
    if allow_origin == "null":
        assert allow_creds != "true", "Null origin granted credentials=true"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(4)
def test_cors_custom_headers_in_preflight(http_client: E2EHttpClient):
    """TC-B04-03: Boundary - Preflight with custom headers X-Request-ID and Authorization."""
    res = http_client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Request-ID, Authorization, Content-Type"
        }
    )
    allowed_headers = res.get_header("Access-Control-Allow-Headers", "")
    assert res.status_code == 200


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(4)
def test_nginx_redirect_preserves_query_string(nginx_client: E2EHttpClient):
    """TC-B04-04: Boundary - Port 80 redirect preserves query arguments."""
    res = nginx_client.get("/api/v1/traffic?junction_id=J1&limit=5", allow_redirects=False)
    if res.status_code in (301, 302, 308):
        loc = res.get_header("Location", "")
        assert "junction_id=J1" in loc, f"Query params lost in redirect: {loc}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(4)
def test_trace_method_disallowed(http_client: E2EHttpClient):
    """TC-B04-05: Boundary - TRACE method is disabled/rejected (405 Method Not Allowed)."""
    res = http_client.request("TRACE", "/api/v1/health")
    assert res.status_code in (405, 403, 400), f"TRACE method should be disallowed, got {res.status_code}"
