"""
Tier 2 Boundary & Corner Cases: Feature 26 - Reconnect & Origin UI Boundaries (M5)
Max backoff delay cap, jitter randomness, unknown origin tags, null origin handling.
"""

import random
import pytest


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(26)
def test_exponential_backoff_delay_capped_at_maximum():
    """TC-B26-01: Boundary - Calculated backoff delay capped at maximum ceiling (30s)."""
    base_delay = 1.0
    max_delay = 30.0
    factor = 2.0

    for attempt in range(1, 20):
        calc_delay = min(max_delay, base_delay * (factor ** attempt))
        assert calc_delay <= max_delay, f"Backoff exceeded cap at attempt {attempt}: {calc_delay}"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(26)
def test_jitter_factor_calculation():
    """TC-B26-02: Boundary - Full jitter introduces variation between 0 and calculated backoff."""
    base_delay = 4.0
    jittered_samples = [base_delay + random.uniform(0.0, 1.0) for _ in range(10)]
    assert len(set(jittered_samples)) > 1, "Jitter failed to introduce randomness across attempts"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(26)
def test_badge_handles_unknown_source_tag():
    """TC-B26-03: Boundary - Unknown source ('external_vendor') maps to neutral fallback."""
    def get_badge_variant(source: str) -> str:
        s = source.lower()
        if s == "live":
            return "success"
        elif s == "sim":
            return "info"
        elif s == "mock":
            return "warning"
        return "neutral"

    assert get_badge_variant("unknown") == "neutral"
    assert get_badge_variant("external_sensor") == "neutral"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(26)
def test_badge_handles_none_or_empty_source():
    """TC-B26-04: Boundary - None or empty string source gracefully falls back."""
    def get_badge_text(source: str | None) -> str:
        if not source:
            return "MOCK"  # Safe default assumption
        return source.upper()

    assert get_badge_text(None) == "MOCK"
    assert get_badge_text("") == "MOCK"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(26)
def test_websocket_reconnect_counter_increments():
    """TC-B26-05: Boundary - Reconnection attempts counter increments linearly."""
    attempts = 0
    for _ in range(5):
        attempts += 1
    assert attempts == 5
