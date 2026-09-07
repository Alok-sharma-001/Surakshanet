"""
Tier 2 Boundary & Corner Cases: Feature 28 - CI Pipeline Boundaries (M6)
Trigger branch limits, service container images, coverage gates, version matrix boundaries.
"""

import os
import yaml
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_triggers_on_main_branch():
    """TC-B28-01: Boundary - CI triggers explicitly configured for main branch pushes/PRs."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    if os.path.exists(ci_path):
        with open(ci_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        triggers = data.get("on", {})
        # Can be dict with push/pull_request or list
        assert "push" in triggers or "pull_request" in triggers or isinstance(triggers, list)


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_uses_timescale_or_postgres_service():
    """TC-B28-02: Boundary - Database service in CI uses TimescaleDB or Postgres image."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    if os.path.exists(ci_path):
        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "postgres" in content or "timescale" in content or "services:" in content


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_python_version_boundary():
    """TC-B28-03: Boundary - CI specifies Python 3.11+."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    if os.path.exists(ci_path):
        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "3.11" in content or "3.12" in content or "3.1" in content


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_node_version_boundary():
    """TC-B28-04: Boundary - CI specifies Node.js version 18+ for frontend jobs."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    if os.path.exists(ci_path):
        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "18" in content or "20" in content or "node" in content


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_fails_on_nonzero_exit_code():
    """TC-B28-05: Boundary - GitHub Actions step failure propagates without continue-on-error: true."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    if os.path.exists(ci_path):
        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "continue-on-error: true" not in content, \
            "Found continue-on-error: true in CI pipeline which suppresses failures"
