"""
Tier 1 Feature Coverage: Feature 2 - Environment & Secret Safety (M1)
Requirement: Move admin credentials & secrets to env; block startup with default
secrets in ENVIRONMENT=production.
"""

import os
import subprocess
import pytest
from tests.e2e.client import PROJECT_ROOT



@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(2)
def test_env_example_contains_mandatory_security_keys():
    """TC-F02-02: Verify required environment variable keys are declared."""
    path = os.path.join(PROJECT_ROOT, ".env.example")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    required_keys = [
        "JWT_SECRET_KEY",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "REDIS_URL",
        "ENVIRONMENT",
    ]
    for key in required_keys:
        assert key in content, f"Missing key '{key}' in .env.example"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(2)
def test_env_example_contains_no_exposed_production_passwords():
    """TC-F02-03: Verify .env.example does not leak default production credentials."""
    path = os.path.join(PROJECT_ROOT, ".env.example")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line_clean = line.strip()
        if line_clean.startswith("ADMIN_PASSWORD="):
            val = line_clean.split("=", 1)[1].strip().strip('"').strip("'")
            assert val != "Alok@2005", "Exposed hardcoded password Alok@2005 in .env.example"
        if line_clean.startswith("JWT_SECRET_KEY="):
            val = line_clean.split("=", 1)[1].strip().strip('"').strip("'")
            # Should be placeholder
            assert len(val) == 0 or "change" in val.lower() or "generate" in val.lower() or "your" in val.lower()


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(2)
def test_production_mode_blocks_default_jwt_secret():
    """TC-F02-04: Test that backend configuration rejects default secret when ENVIRONMENT=production."""
    cmd = [
        "python3",
        "-c",
        """
import os, sys
os.environ['ENVIRONMENT'] = 'production'
os.environ['JWT_SECRET_KEY'] = 'secret'
try:
    from app.config import get_settings
    settings = get_settings()
    # If it allowed default secret in production, fail test
    if settings.JWT_SECRET_KEY == 'secret' and settings.ENVIRONMENT.lower() == 'production':
        sys.exit(101)
except Exception:
    # Expected validation exception in production
    sys.exit(0)
sys.exit(0)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(PROJECT_ROOT, "backend"))
    assert res.returncode != 101, "Backend failed to block default JWT_SECRET_KEY in production mode"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(2)
def test_production_mode_blocks_default_admin_credentials():
    """TC-F02-05: Test that backend configuration rejects default admin password in production."""
    cmd = [
        "python3",
        "-c",
        """
import os, sys
os.environ['ENVIRONMENT'] = 'production'
os.environ['ADMIN_PASSWORD'] = 'Alok@2005'
try:
    from app.config import get_settings
    settings = get_settings()
    if getattr(settings, 'ADMIN_PASSWORD', None) == 'Alok@2005' and settings.ENVIRONMENT.lower() == 'production':
        sys.exit(102)
except Exception:
    sys.exit(0)
sys.exit(0)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(PROJECT_ROOT, "backend"))
    assert res.returncode != 102, "Backend failed to block default ADMIN_PASSWORD in production mode"
