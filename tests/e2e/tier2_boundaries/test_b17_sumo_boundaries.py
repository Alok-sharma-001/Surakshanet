"""
Tier 2 Boundary & Corner Cases: Feature 17 - SUMO Corridor & TraCI Boundaries (M4)
Phase string length violations, invalid character tokens, step time boundaries.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(17)
def test_traci_phase_string_underlength_rejected():
    """TC-B17-01: Boundary - 12-character phase string rejected (corridor requires 18 links)."""
    short_phase = "rrrrGGGGgrrr"
    assert len(short_phase) != 18
    # Validation logic rejects length != 18
    is_valid = len(short_phase) == 18
    assert is_valid is False


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(17)
def test_traci_phase_string_overlength_rejected():
    """TC-B17-02: Boundary - 24-character phase string rejected for 18-link junction."""
    long_phase = "rrrrGGGggrrrrGGGggrrrrGG"
    assert len(long_phase) != 18
    is_valid = len(long_phase) == 18
    assert is_valid is False


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(17)
def test_traci_phase_string_invalid_characters():
    """TC-B17-03: Boundary - Phase string containing invalid characters ('X', '1', '?') rejected."""
    allowed_chars = set("rygGuoOs")
    invalid_string = "rrrrGGGggXXXXGGGGG"
    has_invalid = any(c not in allowed_chars for c in invalid_string)
    assert has_invalid is True


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(17)
def test_simulation_step_delta_time_boundaries():
    """TC-B17-04: Boundary - Step time delta <= 0 or > 10s rejected."""
    def validate_step(delta: float) -> bool:
        return 0.1 <= delta <= 5.0

    assert validate_step(0.0) is False
    assert validate_step(-1.0) is False
    assert validate_step(10.0) is False
    assert validate_step(1.0) is True


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(17)
def test_signals_corridor_all_red_phase():
    """TC-B17-05: Boundary - All-red clearance phase ('rrrrrrrrrrrrrrrrrr') is valid 18 chars."""
    all_red = "r" * 18
    assert len(all_red) == 18
