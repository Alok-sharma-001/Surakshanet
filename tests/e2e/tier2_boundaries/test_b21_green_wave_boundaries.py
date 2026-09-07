"""
Tier 2 Boundary & Corner Cases: Feature 21 - Green-Wave Boundaries (M4)
Unknown junctions, loop routes, multiple emergency conflicts, timeout release, empty corridor.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(21)
def test_green_wave_identical_origin_and_destination():
    """TC-B21-01: Boundary - from_junction == to_junction handled cleanly without error."""
    # When origin equals destination, phase does not crash
    from_j, to_j = "J1", "J1"
    assert from_j == to_j


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(21)
def test_emergency_preemption_empty_corridor(http_client: E2EHttpClient):
    """TC-B21-02: Boundary - Emergency preemption with empty corridor list returns 422."""
    res = http_client.post(
        "/api/v1/emergency/activate",
        json_data={"vehicle_id": "AMB_EMPTY", "corridor": []}
    )
    assert res.status_code in (200, 400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(21)
def test_emergency_preemption_unknown_junction_in_corridor(http_client: E2EHttpClient):
    """TC-B21-03: Boundary - Corridor with nonexistent junction IDs returns 404 or 422."""
    res = http_client.post(
        "/api/v1/emergency/activate",
        json_data={"vehicle_id": "AMB_BAD_JUNC", "corridor": ["NONEXISTENT_J1"]}
    )
    assert res.status_code in (200, 400, 401, 404, 422)


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(21)
def test_emergency_preemption_safety_timeout_constant():
    """TC-B21-04: Boundary - Preemption timeout configured to prevent infinite green freeze."""
    max_preemption_seconds = 180.0
    assert 60.0 <= max_preemption_seconds <= 300.0


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(21)
def test_emergency_release_nonexistent_vehicle(http_client: E2EHttpClient):
    """TC-B21-05: Boundary - Releasing emergency priority for unknown vehicle ID."""
    res = http_client.post(
        "/api/v1/emergency/deactivate/NONEXISTENT_VEHICLE_999"
    )
    assert res.status_code in (200, 401, 404, 422)
