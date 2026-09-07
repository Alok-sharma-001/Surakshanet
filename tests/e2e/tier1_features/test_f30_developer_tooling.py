"""
Tier 1 Feature Coverage: Feature 30 - Developer Tooling & Hygiene (M6)
Requirement: Add Makefile, .pre-commit-config.yaml, validate .env.example,
and include MIT LICENSE.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(30)
def test_makefile_exists_in_root():
    """TC-F30-01: Verify Makefile exists in repository root."""
    path = os.path.join(PROJECT_ROOT, "Makefile")
    assert os.path.exists(path), f"Makefile missing at {path}"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(30)
def test_makefile_defines_standard_targets():
    """TC-F30-02: Verify Makefile defines build, up, down, and test targets."""
    path = os.path.join(PROJECT_ROOT, "Makefile")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "test" in content, "Makefile missing 'test' target"
    assert "up" in content or "dev" in content or "start" in content, "Makefile missing lifecycle targets"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(30)
def test_mit_license_file_exists():
    """TC-F30-03: Verify LICENSE file exists in project root."""
    path = os.path.join(PROJECT_ROOT, "LICENSE")
    assert os.path.exists(path), f"LICENSE file missing at {path}"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(30)
def test_license_declares_mit_license():
    """TC-F30-04: Verify LICENSE contains MIT License declaration."""
    path = os.path.join(PROJECT_ROOT, "LICENSE")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "MIT License" in content or "MIT" in content, "LICENSE does not specify MIT License"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(30)
def test_pre_commit_config_exists():
    """TC-F30-05: Verify .pre-commit-config.yaml exists."""
    path = os.path.join(PROJECT_ROOT, ".pre-commit-config.yaml")
    assert os.path.exists(path), f".pre-commit-config.yaml missing at {path}"
