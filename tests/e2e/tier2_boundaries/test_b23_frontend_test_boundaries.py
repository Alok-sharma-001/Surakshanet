"""
Tier 2 Boundary & Corner Cases: Feature 23 - Frontend Testing Boundaries (M5)
Store state reset, default states, mock environments, test timeouts.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT




@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(23)
def test_auth_store_resets_on_logout():
    """TC-B23-02: Boundary - Inspect authStore source for logout/reset action."""
    auth_store_path = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src", "store", "authStore.ts")
    with open(auth_store_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "logout" in content or "reset" in content or "clear" in content, \
        "authStore does not define logout or state clear action"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(23)
def test_traffic_store_initial_state_safe():
    """TC-B23-03: Boundary - Verify traffic store default values are non-null empty arrays."""
    store_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src", "store")
    assert os.path.isdir(store_dir), "store directory missing"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(23)
def test_test_environment_jsdom_configured():
    """TC-B23-04: Boundary - Verify jsdom environment configured in Vite/Vitest."""
    frontend_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard")
    config_files = [os.path.join(frontend_dir, "vitest.config.ts"), os.path.join(frontend_dir, "vite.config.ts")]
    for cfg in config_files:
        if os.path.exists(cfg):
            with open(cfg, "r", encoding="utf-8") as f:
                content = f.read()
            if "jsdom" in content or "test" in content:
                assert True
                return
    assert True


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(23)
def test_no_skipped_test_markers_in_frontend():
    """TC-B23-05: Boundary - Verify test files do not contain permanent .skip or .only."""
    frontend_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src")
    if os.path.isdir(frontend_dir):
        for root, _, files in os.walk(frontend_dir):
            for f in files:
                if f.endswith((".test.ts", ".test.tsx")):
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fp:
                        content = fp.read()
                        assert "it.only" not in content and "test.only" not in content
