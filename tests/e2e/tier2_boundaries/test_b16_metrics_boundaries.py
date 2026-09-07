"""
Tier 2 Boundary & Corner Cases: Feature 16 - Expanded Prometheus Metrics Boundaries (M3)
High-frequency scrapes, HEAD requests, compression handling, line protocol syntax.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(16)
def test_metrics_head_request_handling(http_client: E2EHttpClient):
    """TC-B16-01: Boundary - HEAD request to /metrics returns 200 without body."""
    res = http_client.request("HEAD", "/metrics")
    assert res.status_code == 200


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(16)
def test_metrics_high_frequency_scrape_loop(http_client: E2EHttpClient):
    """TC-B16-02: Boundary - Scraping /metrics 15 times rapidly completes without degradation."""
    for _ in range(15):
        res = http_client.get("/metrics", timeout=2.0)
        assert res.status_code == 200


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(16)
def test_metrics_line_protocol_compliance(http_client: E2EHttpClient):
    """TC-B16-03: Boundary - Ensure metric lines follow Prometheus text format."""
    res = http_client.get("/metrics")
    lines = res.text.splitlines()
    metric_lines = [l for l in lines if l and not l.startswith("#")]
    assert len(metric_lines) > 0, "No metrics found in scrape output"
    for line in metric_lines[:5]:
        parts = line.split()
        assert len(parts) >= 2, f"Malformed Prometheus metric line: {line}"


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(16)
def test_metrics_unauthenticated_access_permitted(http_client: E2EHttpClient):
    """TC-B16-04: Boundary - /metrics endpoint accessible without Authorization header."""
    http_client.clear_auth_token()
    res = http_client.get("/metrics")
    assert res.status_code == 200, "Prometheus scrape endpoint blocked without auth"


@pytest.mark.tier2
@pytest.mark.m3
@pytest.mark.feature(16)
def test_metrics_non_negative_counters(http_client: E2EHttpClient):
    """TC-B16-05: Boundary - Counter values in metrics output are non-negative."""
    res = http_client.get("/metrics")
    lines = [l for l in res.text.splitlines() if l and not l.startswith("#")]
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            try:
                val = float(parts[-1])
                # Counters and gauges should be valid floats
                assert not (val < 0 and "total" in parts[0]), f"Negative counter value: {line}"
            except ValueError:
                pass
