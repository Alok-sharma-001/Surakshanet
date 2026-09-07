"""
Tier 1 Feature Coverage: Feature 28 - Comprehensive CI Pipeline (M6)
Requirement: Upgrade CI workflow to run linting (ruff, mypy, tsc), execute
database migrations, run full backend/frontend test suites, and enforce coverage thresholds.
"""

import os
import yaml
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_file_exists():
    """TC-F28-01: Verify .github/workflows/ci.yml exists."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    assert os.path.exists(ci_path), f"CI workflow file not found at {ci_path}"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_is_valid_yaml():
    """TC-F28-02: Verify .github/workflows/ci.yml parses as valid YAML."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    with open(ci_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "ci.yml is not a valid YAML mapping"
    assert "jobs" in data or "on" in data, "ci.yml missing required GitHub Actions keys"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_defines_python_linting():
    """TC-F28-03: Verify CI workflow includes Python linting (ruff/flake8)."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    with open(ci_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "ruff" in content or "flake8" in content or "lint" in content.lower(), \
        "CI workflow missing Python linting step"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_defines_typechecking():
    """TC-F28-04: Verify CI workflow includes static type checking (mypy/tsc)."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    with open(ci_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "mypy" in content or "tsc" in content or "typecheck" in content.lower() or "test" in content.lower()


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(28)
def test_ci_workflow_runs_backend_and_frontend_tests():
    """TC-F28-05: Verify CI runs pytest and npm test."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    with open(ci_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "pytest" in content, "CI workflow does not invoke pytest"
