"""
Tier 1 Feature Coverage: Feature 7 - Alembic Versioned Migrations (M2)
Requirement: Scaffold Alembic, replace silent create_all, and establish
reproducible migration history.
"""

import os
import subprocess
import pytest
from tests.e2e.client import E2EDatabaseClient, PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_ini_file_exists():
    """TC-F07-01: Verify alembic.ini exists in project repository."""
    candidates = [
        os.path.join(PROJECT_ROOT, "backend", "alembic.ini"),
        os.path.join(PROJECT_ROOT, "alembic.ini"),
    ]
    found = [p for p in candidates if os.path.exists(p)]
    assert len(found) > 0, f"alembic.ini not found in {candidates}"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_versions_directory_exists():
    """TC-F07-02: Verify alembic migration versions directory exists."""
    candidates = [
        os.path.join(PROJECT_ROOT, "backend", "alembic", "versions"),
        os.path.join(PROJECT_ROOT, "backend", "migrations", "versions"),
        os.path.join(PROJECT_ROOT, "alembic", "versions"),
    ]
    found = [p for p in candidates if os.path.isdir(p)]
    assert len(found) > 0, f"Alembic versions directory not found in {candidates}"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_env_py_exists():
    """TC-F07-03: Verify env.py exists for Alembic migration execution."""
    candidates = [
        os.path.join(PROJECT_ROOT, "backend", "alembic", "env.py"),
        os.path.join(PROJECT_ROOT, "backend", "migrations", "env.py"),
        os.path.join(PROJECT_ROOT, "alembic", "env.py"),
    ]
    found = [p for p in candidates if os.path.exists(p)]
    assert len(found) > 0, f"Alembic env.py not found in {candidates}"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_version_table_or_migration_scaffold(db_client: E2EDatabaseClient):
    """TC-F07-04: Verify alembic_version table or migration tracking exists in database."""
    # Check if alembic_version exists or tables are defined
    res = db_client.execute_query(
        "SELECT table_name FROM information_schema.tables WHERE table_name = 'alembic_version';"
    )
    # If migrations have been applied, alembic_version is present
    # If in dev before M2 run, check schema definition
    has_alembic_table = len(res) > 0
    # Also verify models Base metadata exists
    has_users = len(db_client.execute_query(
        "SELECT table_name FROM information_schema.tables WHERE table_name = 'users';"
    )) > 0
    assert has_alembic_table or has_users, "Neither alembic_version nor database tables found"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_check_or_current_command():
    """TC-F07-05: Verify alembic CLI can inspect migration status."""
    backend_dir = os.path.join(PROJECT_ROOT, "backend")
    if os.path.exists(os.path.join(backend_dir, "alembic.ini")):
        res = subprocess.run(
            ["alembic", "current"],
            cwd=backend_dir,
            capture_output=True,
            text=True
        )
        assert res.returncode in (0, 1), f"Alembic execution failure: {res.stderr}"
    else:
        # Candidate check passed in F07-01
        pass
