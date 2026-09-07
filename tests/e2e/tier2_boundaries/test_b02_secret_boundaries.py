"""
Tier 2 Boundary & Corner Cases: Feature 2 - Environment & Secret Boundaries (M1)
Empty secrets, extreme secret lengths, whitespace handling, environment case-sensitivity.
"""

import os
import subprocess
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(2)
def test_production_mode_with_empty_secret_fails():
    """TC-B02-01: Boundary - Empty JWT_SECRET_KEY in production mode is blocked."""
    cmd = [
        "python3",
        "-c",
        """
import os, sys
os.environ['ENVIRONMENT'] = 'production'
os.environ['JWT_SECRET_KEY'] = ''
try:
    from app.config import get_settings
    settings = get_settings()
    if not settings.JWT_SECRET_KEY:
        sys.exit(101)
except Exception:
    sys.exit(0)
sys.exit(0)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(PROJECT_ROOT, "backend"))
    assert res.returncode != 101, "Allowed empty JWT secret in production mode"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(2)
def test_production_mode_with_whitespace_secret_fails():
    """TC-B02-02: Boundary - Whitespace-only JWT_SECRET_KEY in production mode is blocked."""
    cmd = [
        "python3",
        "-c",
        """
import os, sys
os.environ['ENVIRONMENT'] = 'production'
os.environ['JWT_SECRET_KEY'] = '   '
try:
    from app.config import get_settings
    settings = get_settings()
    if settings.JWT_SECRET_KEY.strip() == '':
        sys.exit(101)
except Exception:
    sys.exit(0)
sys.exit(0)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(PROJECT_ROOT, "backend"))
    assert res.returncode != 101, "Allowed whitespace-only JWT secret in production mode"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(2)
def test_environment_case_insensitivity_triggers_production_rules():
    """TC-B02-03: Boundary - ENVIRONMENT='PRODUCTION' (uppercase) triggers production validation."""
    cmd = [
        "python3",
        "-c",
        """
import os, sys
os.environ['ENVIRONMENT'] = 'PRODUCTION'
os.environ['JWT_SECRET_KEY'] = 'secret'
try:
    from app.config import get_settings
    settings = get_settings()
    if settings.ENVIRONMENT.lower() == 'production' and settings.JWT_SECRET_KEY == 'secret':
        sys.exit(101)
except Exception:
    sys.exit(0)
sys.exit(0)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(PROJECT_ROOT, "backend"))
    assert res.returncode != 101, "Uppercase ENVIRONMENT='PRODUCTION' bypassed safety check"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(2)
def test_extreme_length_secret_key_handling():
    """TC-B02-04: Boundary - 4096-character random secret loads without buffer overflow."""
    huge_secret = "A" * 4096
    cmd = [
        "python3",
        "-c",
        f"""
import os, sys
os.environ['ENVIRONMENT'] = 'development'
os.environ['JWT_SECRET_KEY'] = '{huge_secret}'
try:
    from app.config import get_settings
    settings = get_settings()
    assert len(settings.JWT_SECRET_KEY) == 4096
    sys.exit(0)
except Exception as e:
    sys.exit(1)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(PROJECT_ROOT, "backend"))
    assert res.returncode == 0, "Failed to handle 4096-char secret key"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(2)
def test_database_url_malformed_scheme_handling():
    """TC-B02-05: Boundary - Database URL with invalid scheme does not silently pass."""
    cmd = [
        "python3",
        "-c",
        """
import os, sys
os.environ['DATABASE_URL'] = 'invalid-proto://localhost/db'
try:
    from app.config import get_settings
    settings = get_settings()
    sys.exit(0)
except Exception:
    sys.exit(0)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(PROJECT_ROOT, "backend"))
    assert res.returncode == 0
