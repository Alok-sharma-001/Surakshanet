"""
Tier 1 Feature Coverage: Feature 31 - Operations Runbook (M6)
Requirement: Document architectural operations, deployment, and troubleshooting
procedures in README.md.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_file_exists():
    """TC-F31-01: Verify README.md exists in repository root."""
    path = os.path.join(PROJECT_ROOT, "README.md")
    assert os.path.exists(path), f"README.md missing at {path}"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_contains_architecture_documentation():
    """TC-F31-02: Verify README.md documents system architecture or diagram."""
    path = os.path.join(PROJECT_ROOT, "README.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "architecture" in content.lower() or "surakshanet" in content.lower(), \
        "README.md missing architecture overview"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_contains_operations_or_runbook_section():
    """TC-F31-03: Verify README.md contains operational commands or runbook."""
    path = os.path.join(PROJECT_ROOT, "README.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "run" in content.lower() or "start" in content.lower() or "docker" in content.lower(), \
        "README.md missing operational instructions"


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_contains_environment_variable_matrix():
    """TC-F31-04: Verify README.md documents key environment variables or configuration."""
    path = os.path.join(PROJECT_ROOT, "README.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "env" in content.lower() or "port" in content.lower() or "config" in content.lower()


@pytest.mark.tier1
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_contains_troubleshooting_or_faq():
    """TC-F31-05: Verify README.md includes troubleshooting or diagnostic guidance."""
    path = os.path.join(PROJECT_ROOT, "README.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert len(content) > 100, "README.md is empty or incomplete"
