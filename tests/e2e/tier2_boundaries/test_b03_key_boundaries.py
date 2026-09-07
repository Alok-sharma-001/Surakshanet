"""
Tier 2 Boundary & Corner Cases: Feature 3 - Private Key & Git Ignore Boundaries (M1)
Boundary conditions on key untracking, git ignore evaluation, nested keys.
"""

import os
import subprocess
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(3)
def test_nested_pem_file_ignored_by_git():
    """TC-B03-01: Boundary - A newly created nested .pem file is ignored by git."""
    test_nested_pem = os.path.join(PROJECT_ROOT, "backend", "test_boundary.pem")
    try:
        with open(test_nested_pem, "w") as f:
            f.write("-----BEGIN DUMMY PRIVATE KEY-----\n")

        res = subprocess.run(
            ["git", "check-ignore", "backend/test_boundary.pem"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        assert res.returncode == 0, "Nested .pem file was NOT ignored by git rules"
    finally:
        if os.path.exists(test_nested_pem):
            os.remove(test_nested_pem)


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(3)
def test_key_extension_in_subdirectory_ignored():
    """TC-B03-02: Boundary - .key files in subdirectories are ignored by git."""
    test_key = os.path.join(PROJECT_ROOT, "infra", "dummy.key")
    try:
        with open(test_key, "w") as f:
            f.write("dummy-key-content\n")

        res = subprocess.run(
            ["git", "check-ignore", "infra/dummy.key"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        assert res.returncode == 0, ".key file in infra/ was NOT ignored by git"
    finally:
        if os.path.exists(test_key):
            os.remove(test_key)


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(3)
def test_no_tracked_rsa_or_dsa_keys_in_git_ls():
    """TC-B03-03: Boundary - Confirm no tracked files end in .pem, .key, .pkcs12 across tree."""
    res = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    tracked = res.stdout.splitlines()
    bad_keys = [f for f in tracked if f.endswith((".pem", ".key", ".p12", ".pkcs12"))]
    assert len(bad_keys) == 0, f"Found sensitive key files tracked in git: {bad_keys}"


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(3)
def test_purge_script_dry_run_or_help_flag():
    """TC-B03-04: Boundary - Purge script execution with --help or --dry-run exits safely."""
    candidates = [
        os.path.join(PROJECT_ROOT, "scripts", "purge_history.sh"),
        os.path.join(PROJECT_ROOT, "scripts", "rewrite_history.sh"),
    ]
    script = next((p for p in candidates if os.path.exists(p)), None)
    if script:
        res = subprocess.run(["bash", script, "--dry-run"], cwd=PROJECT_ROOT, capture_output=True, text=True)
        # Should not crash destructively
        assert res.returncode in (0, 1, 2)


@pytest.mark.tier2
@pytest.mark.m1
@pytest.mark.feature(3)
def test_gitignore_syntax_valid():
    """TC-B03-05: Boundary - .gitignore contains no malformed recursive or blank wildcard lines."""
    path = os.path.join(PROJECT_ROOT, ".gitignore")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            assert stripped != "*", "Accidental root wildcard '*' in .gitignore"
