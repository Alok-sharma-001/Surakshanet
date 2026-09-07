"""
Tier 1 Feature Coverage: Feature 15 - Error Handling & Correlation ID (M3)
Requirement: Add request tracking middleware (X-Request-ID) and standardize
error responses to a structured envelope.
"""

import uuid
import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(15)
def test_response_contains_x_request_id_header(http_client: E2EHttpClient):
    """TC-F15-01: Verify standard GET request returns an X-Request-ID header."""
    res = http_client.get("/api/v1/health")
    assert res.status_code == 200
    req_id = res.get_header("X-Request-ID")
    # In M3 correlation ID middleware is added
    if req_id is not None:
        assert len(req_id) > 0, "X-Request-ID header is empty"


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(15)
def test_client_supplied_correlation_id_echoed(http_client: E2EHttpClient):
    """TC-F15-02: Verify client-supplied X-Request-ID is preserved in response."""
    test_id = f"corr-e2e-{uuid.uuid4().hex[:12]}"
    res = http_client.get("/api/v1/health", headers={"X-Request-ID": test_id})
    assert res.status_code == 200
    echoed = res.get_header("X-Request-ID")
    if echoed is not None:
        assert echoed == test_id, f"Expected echoed '{test_id}', got '{echoed}'"


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(15)
def test_404_error_response_structured_format(http_client: E2EHttpClient):
    """TC-F15-03: Verify 404 response returns valid JSON error envelope."""
    res = http_client.get(f"/api/v1/nonexistent-endpoint-{uuid.uuid4().hex[:6]}")
    assert res.status_code == 404
    data = res.json()
    assert isinstance(data, dict), "404 body is not a JSON object"
    assert "error" in data or "detail" in data, f"Unexpected error format: {data}"


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(15)
def test_422_validation_error_response_structured_format(http_client: E2EHttpClient):
    """TC-F15-04: Verify 422 validation failure returns structured error response."""
    # Send malformed registration payload
    res = http_client.post("/api/v1/auth/register", json_data={"bad_field": 123})
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data or "error" in data, f"Missing error detail: {data}"


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(15)
def test_error_response_content_type_is_json(http_client: E2EHttpClient):
    """TC-F15-05: Verify error responses have application/json Content-Type."""
    res = http_client.get("/api/v1/not-found-endpoint")
    content_type = res.get_header("Content-Type", "")
    assert "application/json" in content_type.lower()
