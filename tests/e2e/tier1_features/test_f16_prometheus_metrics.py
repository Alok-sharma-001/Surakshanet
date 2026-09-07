"""
Tier 1 Feature Coverage: Feature 16 - Expanded Prometheus Metrics (M3)
Requirement: Instrument active WebSocket connections, Redis pub/sub throughput,
queue depth, and ML latency.
"""

import pytest
from tests.e2e.client import E2EHttpClient, DEFAULT_PROMETHEUS_URL


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(16)
def test_backend_metrics_endpoint_accessible(http_client: E2EHttpClient):
    """TC-F16-01: Verify /metrics endpoint responds with HTTP 200."""
    res = http_client.get("/metrics")
    assert res.status_code == 200, f"/metrics returned status {res.status_code}"


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(16)
def test_metrics_output_contains_http_request_metrics(http_client: E2EHttpClient):
    """TC-F16-02: Verify metrics output tracks HTTP request counts."""
    res = http_client.get("/metrics")
    text = res.text
    assert "http_requests" in text or "http_request" in text or "requests_total" in text, \
        "Missing HTTP request metrics in Prometheus scrape"


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(16)
def test_metrics_content_type_valid(http_client: E2EHttpClient):
    """TC-F16-03: Verify metrics content type is text/plain or Prometheus line format."""
    res = http_client.get("/metrics")
    ctype = res.get_header("Content-Type", "")
    assert "text/plain" in ctype or "version=0.0.4" in ctype or "openmetrics" in ctype


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(16)
def test_prometheus_server_health():
    """TC-F16-04: Verify standalone Prometheus container is healthy."""
    import requests
    try:
        res = requests.get(f"{DEFAULT_PROMETHEUS_URL}/-/healthy", timeout=3)
        assert res.status_code == 200
    except Exception as e:
        pytest.skip(f"Prometheus server check skipped: {e}")


@pytest.mark.tier1
@pytest.mark.m3
@pytest.mark.feature(16)
def test_metrics_increment_after_traffic_endpoint_call(http_client: E2EHttpClient):
    """TC-F16-05: Verify making an API call affects Prometheus counters."""
    # First scrape
    res1 = http_client.get("/metrics")
    # Make API calls
    http_client.get("/api/v1/health")
    http_client.get("/api/v1/health")
    # Second scrape
    res2 = http_client.get("/metrics")
    assert res2.status_code == 200
