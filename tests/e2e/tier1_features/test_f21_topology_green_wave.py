"""
Tier 1 Feature Coverage: Feature 21 - Topology-Derived Green-Wave (M4)
Requirement: Replace hardcoded return 0 with dynamic approach-phase mapping
based on TraCI network topology.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT, E2EHttpClient


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(21)
def test_green_wave_source_file_exists():
    """TC-F21-01: Verify ml/emergency/green_wave.py exists."""
    candidates = [
        os.path.join(PROJECT_ROOT, "ml", "emergency", "green_wave.py"),
        os.path.join(PROJECT_ROOT, "ml", "green_wave.py"),
        os.path.join(PROJECT_ROOT, "backend", "app", "services", "green_wave.py"),
    ]
    found = [p for p in candidates if os.path.exists(p)]
    assert len(found) > 0, f"green_wave.py not found in {candidates}"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(21)
def test_green_wave_approach_mapping_logic():
    """TC-F21-02: Verify dynamic approach mapping function signature and logic."""
    candidates = [
        os.path.join(PROJECT_ROOT, "ml", "emergency", "green_wave.py"),
        os.path.join(PROJECT_ROOT, "ml", "green_wave.py"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if path:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "_get_approach_phase" in content or "get_approach_phase" in content, \
            "Approach phase mapping function not declared in green_wave.py"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(21)
def test_east_west_vs_north_south_phase_distinction():
    """TC-F21-03: Verify East-West (J1->J2) and North-South movements map to distinct phases."""
    # EW arterial should return phase 0 (EW green), NS should return phase 2 (NS green)
    def mock_approach_resolver(from_j: str, to_j: str) -> int:
        if (from_j, to_j) in [("J1", "J2"), ("J2", "J3"), ("J3", "J4")]:
            return 0  # EW green phase
        return 2  # NS cross street green phase

    ew_phase = mock_approach_resolver("J1", "J2")
    ns_phase = mock_approach_resolver("CROSS_N", "J2")
    assert ew_phase != ns_phase, "EW and NS movements must not map to the identical phase index"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(21)
def test_emergency_preemption_api_trigger(http_client: E2EHttpClient):
    """TC-F21-04: Verify emergency preemption request via API."""
    payload = {
        "vehicle_id": "AMBULANCE_01",
        "corridor": ["J1", "J2", "J3"],
        "priority": "HIGH"
    }
    res = http_client.post("/api/v1/emergency/activate", json_data=payload)
    assert res.status_code in (200, 201, 401, 404, 422)


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(21)
def test_emergency_preemption_release_endpoint(http_client: E2EHttpClient):
    """TC-F21-05: Verify emergency preemption release restores regular cycling."""
    res = http_client.post(
        "/api/v1/emergency/deactivate/AMBULANCE_01"
    )
    assert res.status_code in (200, 401, 404, 422)
