"""
Tier 1 Feature Coverage: Feature 3 - Private Key Remediation (M1)
Requirement: Untrack surakshanet-key.pem from Git index, update .gitignore,
provide standalone history rewrite script.
"""

import os
import subprocess
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(3)
def test_surakshanet_key_untracked_in_git():
    """TC-F03-01: Verify surakshanet-key.pem is NOT tracked in git index."""
    res = subprocess.run(
        ["git", "ls-files", "surakshanet-key.pem"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    tracked_files = res.stdout.strip()
    assert tracked_files == "", f"surakshanet-key.pem is still tracked in git: {tracked_files}"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(3)
def test_gitignore_ignores_pem_and_key_extensions():
    """TC-F03-02: Verify .gitignore contains *.pem and *.key rules."""
    path = os.path.join(PROJECT_ROOT, ".gitignore")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "*.pem" in content, "*.pem pattern missing in .gitignore"
    assert "*.key" in content, "*.key pattern missing in .gitignore"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(3)
def test_gitignore_ignores_nginx_certs():
    """TC-F03-03: Verify .gitignore covers certificate paths."""
    path = os.path.join(PROJECT_ROOT, ".gitignore")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    has_cert_rule = (
        "infra/nginx/certs" in content
        or "*.crt" in content
        or "*.pem" in content
    )
    assert has_cert_rule, "No certificate path ignore rule in .gitignore"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(3)
def test_history_purge_script_exists():
    """TC-F03-04: Verify history rewrite script exists in scripts/ directory."""
    candidates = [
        os.path.join(PROJECT_ROOT, "scripts", "purge_history.sh"),
        os.path.join(PROJECT_ROOT, "scripts", "rewrite_history.sh"),
        os.path.join(PROJECT_ROOT, "scripts", "clean_secrets.sh"),
    ]
    found = [p for p in candidates if os.path.exists(p)]
    assert len(found) > 0, f"No history rewrite script found in {candidates}"


@pytest.mark.tier1
@pytest.mark.m1
@pytest.mark.feature(3)
def test_history_purge_script_contains_target_secret_identifiers():
    """TC-F03-05: Verify purge script explicitly targets sensitive key files."""
    candidates = [
        os.path.join(PROJECT_ROOT, "scripts", "purge_history.sh"),
        os.path.join(PROJECT_ROOT, "scripts", "rewrite_history.sh"),
        os.path.join(PROJECT_ROOT, "scripts", "clean_secrets.sh"),
    ]
    script_path = next((p for p in candidates if os.path.exists(p)), None)
    assert script_path is not None, "Purge script not found"

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "surakshanet-key.pem" in content or "filter-repo" in content or "bfg" in content, \
        "Purge script does not reference target secrets or git filter tooling"
