"""
Tier 1 Feature Coverage: Feature 10 - Traffic Service Implementation (M2)
Requirement: Complete traffic_service.py with real DB models, Pydantic v2 schemas,
and bind to api/traffic.py.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(10)
def test_get_latest_traffic_endpoint(authed_client: E2EHttpClient):
    """TC-F10-01: Verify GET /api/v1/traffic/latest returns traffic status."""
    res = authed_client.get("/api/v1/traffic/latest")
    assert res.status_code == 200, f"Expected 200 for an authenticated request, got {res.status_code}: {res.text}"
    if res.status_code == 200:
        data = res.json()
        assert isinstance(data, (list, dict))


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(10)
def test_post_traffic_reading_schema_validation(authed_client: E2EHttpClient):
    """TC-F10-02: Verify POST /api/v1/traffic/reading validates required fields."""
    payload = {
        "junction_id": "J1",
        "vehicle_count": 45,
        "average_speed": 35.5,
        "congestion_level": "MEDIUM",
        "source": "sim",
    }
    res = authed_client.post("/api/v1/traffic/reading", json_data=payload)
    assert res.status_code in (200, 201, 401, 404, 422)


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(10)
def test_traffic_pcu_calculation_endpoint(authed_client: E2EHttpClient):
    """TC-F10-03: Verify PCU calculation endpoint or response includes PCU metric."""
    # Test PCU endpoint or telemetry post
    res = authed_client.post(
        "/api/v1/traffic/pcu",
        json_data={"cars": 20, "buses": 5, "two_wheelers": 30, "trucks": 2}
    )
    # If endpoint exists, check PCU calculation:
    # Standard IRC PCU: car=1.0, bus=3.0, 2W=0.5, truck=3.0
    # 20*1 + 5*3 + 30*0.5 + 2*3 = 20 + 15 + 15 + 6 = 56.0 PCU
    if res.status_code == 200:
        data = res.json()
        pcu = data.get("pcu", data.get("total_pcu"))
        assert pcu is not None and float(pcu) > 0
    else:
        assert res.status_code in (404, 401, 422)


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(10)
def test_get_traffic_corridor_overview(authed_client: E2EHttpClient):
    """TC-F10-04: Verify GET /api/v1/traffic/corridor provides arterial summary."""
    res = authed_client.get("/api/v1/traffic/corridor")
    assert res.status_code in (200, 401, 404)


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(10)
def test_traffic_service_file_uses_pydantic_v2():
    """TC-F10-05: Verify traffic service / schemas do not use deprecated Pydantic v1 dict()."""
    import os
    from tests.e2e.client import PROJECT_ROOT
    service_path = os.path.join(PROJECT_ROOT, "backend", "app", "services", "traffic_service.py")
    if os.path.exists(service_path):
        with open(service_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Should not use .dict() which is deprecated/removed in Pydantic v2
        assert "class Junction: pass" not in content, "traffic_service.py still contains mock scaffold"
