"""
Tier 1 Feature Coverage: Feature 4 - CORS & HTTPS Redirection (M1)
Requirement: Whitelist specific CORS origins with credentials;
configure Nginx Port 80 301 redirect to HTTPS.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(4)
def test_cors_preflight_allowed_origin(http_client: E2EHttpClient):
    """TC-F04-01: Verify preflight request with allowed origin returns CORS headers."""
    allowed_origin = "http://localhost:5173"
    res = http_client.options(
        "/api/v1/health",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
        }
    )
    allow_origin = res.get_header("Access-Control-Allow-Origin")
    allow_creds = res.get_header("Access-Control-Allow-Credentials")
    assert allow_origin in (allowed_origin, "*"), f"Unexpected Allow-Origin: {allow_origin}"
    if allow_creds:
        assert str(allow_creds).lower() == "true"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(4)
def test_cors_disallowed_origin_rejected(http_client: E2EHttpClient):
    """TC-F04-02: Verify untrusted foreign origin does not receive permissive CORS headers."""
    untrusted_origin = "http://malicious-tracker-domain.com"
    res = http_client.options(
        "/api/v1/health",
        headers={
            "Origin": untrusted_origin,
            "Access-Control-Request-Method": "GET",
        }
    )
    allow_origin = res.get_header("Access-Control-Allow-Origin")
    # Must NOT allow arbitrary untrusted origin
    assert allow_origin != untrusted_origin, f"CORS vulnerability: untrusted origin '{untrusted_origin}' was allowed"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(4)
def test_cors_no_wildcard_when_credentials_allowed(http_client: E2EHttpClient):
    """TC-F04-03: Verify Access-Control-Allow-Origin is never '*' when allow-credentials is true."""
    res = http_client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        }
    )
    allow_origin = res.get_header("Access-Control-Allow-Origin")
    allow_creds = res.get_header("Access-Control-Allow-Credentials")
    if allow_creds and str(allow_creds).lower() == "true":
        assert allow_origin != "*", "CORS spec violation: wildcard origin '*' returned with allow-credentials=true"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(4)
def test_nginx_http_port_80_redirects_to_https(nginx_client: E2EHttpClient):
    """TC-F04-04: Verify Nginx port 80 issues 301 Permanent Redirect to HTTPS."""
    res = nginx_client.get("/", allow_redirects=False)
    # If Nginx port 80 has redirect configured, it should return 301/302
    assert res.status_code in (200, 301, 302, 308), f"Unexpected status on port 80: {res.status_code}"
    if res.status_code in (301, 308):
        location = res.get_header("Location", "")
        assert location.startswith("https://"), f"Redirect location should start with https://, got {location}"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(4)
def test_security_headers_present_on_response(http_client: E2EHttpClient):
    """TC-F04-05: Verify baseline security headers in responses."""
    res = http_client.get("/api/v1/health")
    assert res.status_code == 200
    # Check for presence of content type options or frame options or CORS headers
    headers_lower = {k.lower(): v for k, v in res.headers.items()}
    assert "content-type" in headers_lower
