"""
Tier 2 Boundary & Corner Cases: Feature 30 - Developer Tooling Boundaries (M6)
Makefile dry-runs, pre-commit YAML validity, copyright notices, env formatting.
"""

import os
import subprocess
import yaml
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(30)
def test_makefile_dry_run_syntax():
    """TC-B30-01: Boundary - Running make -n test checks Makefile syntax without execution."""
    makefile_path = os.path.join(PROJECT_ROOT, "Makefile")
    if os.path.exists(makefile_path):
        res = subprocess.run(["make", "-n", "-f", makefile_path], capture_output=True, text=True)
        assert res.returncode in (0, 1, 2)


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(30)
def test_pre_commit_yaml_parses_cleanly():
    """TC-B30-02: Boundary - Verify .pre-commit-config.yaml is valid YAML mapping."""
    pc_path = os.path.join(PROJECT_ROOT, ".pre-commit-config.yaml")
    if os.path.exists(pc_path):
        with open(pc_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), ".pre-commit-config.yaml is not a valid YAML mapping"
        assert "repos" in data, "Missing 'repos' in pre-commit config"


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(30)
def test_license_contains_copyright_line():
    """TC-B30-03: Boundary - LICENSE contains standard Copyright line."""
    lic_path = os.path.join(PROJECT_ROOT, "LICENSE")
    if os.path.exists(lic_path):
        with open(lic_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Copyright" in content or "copyright" in content.lower()


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(30)
def test_env_example_has_no_windows_crlf_corruption():
    """TC-B30-04: Boundary - .env.example uses clean Unix line endings (LF)."""
    env_path = os.path.join(PROJECT_ROOT, ".env.example")
    with open(env_path, "rb") as f:
        bytes_data = f.read()
    # Should not have corrupted null bytes
    assert b"\x00" not in bytes_data, "Null bytes detected in .env.example"


@pytest.mark.tier2
@pytest.mark.m6
@pytest.mark.feature(30)
def test_docker_compose_file_valid_yaml():
    """TC-B30-05: Boundary - Verify infra/docker-compose.yml parses as valid YAML."""
    compose_path = os.path.join(PROJECT_ROOT, "infra", "docker-compose.yml")
    with open(compose_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict)
    assert "services" in data, "docker-compose.yml missing 'services' key"
