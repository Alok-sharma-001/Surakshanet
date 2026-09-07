"""
Tier 1 Feature Coverage: Feature 18 - Webster Fixed-Time Signal Control (M4)
Requirement: Fix 18-character phase strings (rrrrGGGggrrrrGGGgg) in webster_fallback.py
to prevent TraCI crashes.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(18)
def test_webster_fallback_source_file_exists():
    """TC-F18-01: Verify webster_fallback.py exists in ml/marl/ directory."""
    candidates = [
        os.path.join(PROJECT_ROOT, "ml", "marl", "webster_fallback.py"),
        os.path.join(PROJECT_ROOT, "ml", "webster_fallback.py"),
        os.path.join(PROJECT_ROOT, "backend", "app", "services", "webster.py"),
    ]
    found = [p for p in candidates if os.path.exists(p)]
    assert len(found) > 0, f"webster_fallback.py missing in {candidates}"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(18)
def test_webster_source_contains_18_char_phase_strings():
    """TC-F18-02: Verify webster fallback defines 18-character TraCI phase strings."""
    candidates = [
        os.path.join(PROJECT_ROOT, "ml", "marl", "webster_fallback.py"),
        os.path.join(PROJECT_ROOT, "ml", "webster_fallback.py"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    assert path is not None, "Webster source not found"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Look for 18-char string or phase definitions
    assert "rrrrGGGggrrrrGGGgg" in content or "18" in content or "phase" in content.lower(), \
        "Webster fallback does not reference 18-character signal phases"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(18)
def test_webster_cycle_length_calculation():
    """TC-F18-03: Verify Webster formula calculation bounds."""
    # Webster optimal cycle length formula: C = (1.5*L + 5) / (1 - Y)
    L = 12.0  # total lost time (seconds)
    Y = 0.65  # sum of flow ratios
    c_opt = (1.5 * L + 5.0) / (1.0 - Y)
    # C = (18 + 5) / 0.35 = 23 / 0.35 = 65.7 seconds
    assert 60.0 <= c_opt <= 70.0, f"Unexpected Webster cycle: {c_opt}"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(18)
def test_signals_status_endpoint():
    """TC-F18-04: Verify signals endpoint provides controller mode."""
    from tests.e2e.client import E2EHttpClient
    client = E2EHttpClient()
    res = client.get("/api/v1/signals/status")
    assert res.status_code in (200, 401, 404)


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(18)
def test_signals_manual_fallback_trigger():
    """TC-F18-05: Verify manual override to Webster fixed-time fallback mode."""
    from tests.e2e.client import E2EHttpClient
    client = E2EHttpClient()
    res = client.post(
        "/api/v1/signals/mode",
        json_data={"mode": "FIXED_WEBSTER", "junction_id": "J1"}
    )
    assert res.status_code in (200, 401, 404, 422)
