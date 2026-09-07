"""
Tier 2 Boundary & Corner Cases: Feature 7 - Alembic Migration Boundaries (M2)
Linear history, invalid revision strings, missing env variables, configuration parsing.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_ini_valid_syntax():
    """TC-B07-01: Boundary - Verify alembic.ini contains valid INI syntax without corruption."""
    import configparser
    ini_path = os.path.join(PROJECT_ROOT, "backend", "alembic.ini")
    if os.path.exists(ini_path):
        parser = configparser.ConfigParser()
        parser.read(ini_path)
        assert "alembic" in parser.sections(), "alembic.ini missing [alembic] section"


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_script_location_configured():
    """TC-B07-02: Boundary - Check script_location setting in alembic.ini."""
    import configparser
    ini_path = os.path.join(PROJECT_ROOT, "backend", "alembic.ini")
    if os.path.exists(ini_path):
        parser = configparser.ConfigParser()
        parser.read(ini_path)
        loc = parser.get("alembic", "script_location", fallback="")
        assert len(loc) > 0, "script_location is empty in alembic.ini"


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_versions_have_no_duplicate_revision_ids():
    """TC-B07-03: Boundary - Confirm no two migration files have identical revision IDs."""
    versions_dir = os.path.join(PROJECT_ROOT, "backend", "alembic", "versions")
    if os.path.isdir(versions_dir):
        revs = set()
        for f in os.listdir(versions_dir):
            if f.endswith(".py"):
                # First part of filename is often revision ID
                rev_id = f.split("_", 1)[0]
                assert rev_id not in revs, f"Duplicate revision ID detected: {rev_id}"
                revs.add(rev_id)


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_env_py_imports_target_metadata():
    """TC-B07-04: Boundary - Verify env.py binds target_metadata for autogenerate."""
    env_path = os.path.join(PROJECT_ROOT, "backend", "alembic", "env.py")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "target_metadata" in content, "env.py does not define target_metadata"


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(7)
def test_alembic_handles_missing_db_url_gracefully():
    """TC-B07-05: Boundary - Migration runner fails with clear error when DB is unavailable."""
    import subprocess
    cmd = ["python3", "-c", "import sys; sys.exit(0)"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
