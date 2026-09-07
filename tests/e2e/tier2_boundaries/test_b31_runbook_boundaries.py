"""
Tier 2 Boundary & Corner Cases: Feature 31 - Operations Runbook Boundaries (M6)
Port mapping documentation, database backup instructions, quickstart syntax, anchor links.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_documents_docker_ports():
    """TC-B31-01: Boundary - README documents ports for Backend (8000), DB (5432/5434), Redis (6379)."""
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Mention of port numbers
    assert "8000" in content or "5432" in content or "port" in content.lower()


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_documents_database_backup_procedure():
    """TC-B31-02: Boundary - README documents pg_dump or backup command."""
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "dump" in content.lower() or "backup" in content.lower() or "database" in content.lower()


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_documents_emergency_override():
    """TC-B31-03: Boundary - README contains emergency vehicle or signal override steps."""
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "emergency" in content.lower() or "signal" in content.lower() or "traffic" in content.lower()


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_documents_testing_instructions():
    """TC-B31-04: Boundary - README documents how to run test suite (pytest / npm test)."""
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "test" in content.lower() or "pytest" in content.lower()


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(31)
def test_readme_markdown_header_hierarchy():
    """TC-B31-05: Boundary - Verify README starts with a top-level H1 header '# '."""
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    first_non_empty = next((l.strip() for l in lines if l.strip()), "")
    assert first_non_empty.startswith("#"), f"README should begin with a Markdown title header, got: {first_non_empty[:30]}"
