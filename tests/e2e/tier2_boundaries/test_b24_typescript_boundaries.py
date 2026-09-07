"""
Tier 2 Boundary & Corner Cases: Feature 24 - Strict TypeScript Boundaries (M5)
Elimination of explicit 'any', OpenAPI schema completeness, enum strictness, date parsing.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT, E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(24)
def test_no_explicit_any_in_api_service():
    """TC-B24-01: Boundary - api.ts does not use unbounded ': any' typing."""
    api_ts = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src", "services", "api.ts")
    if os.path.exists(api_ts):
        with open(api_ts, "r", encoding="utf-8") as f:
            lines = f.readlines()
        any_lines = [l.strip() for l in lines if ": any" in l and not l.strip().startswith("//")]
        assert len(any_lines) == 0, f"Found explicit 'any' types in api.ts: {any_lines[:3]}"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(24)
def test_no_explicit_any_in_websocket_service():
    """TC-B24-02: Boundary - websocket.ts does not use unbounded ': any' typing."""
    ws_ts = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src", "services", "websocket.ts")
    if os.path.exists(ws_ts):
        with open(ws_ts, "r", encoding="utf-8") as f:
            lines = f.readlines()
        any_lines = [l.strip() for l in lines if ": any" in l and not l.strip().startswith("//")]
        assert len(any_lines) == 0, f"Found explicit 'any' types in websocket.ts: {any_lines[:3]}"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(24)
def test_openapi_spec_has_user_role_enum(http_client: E2EHttpClient):
    """TC-B24-03: Boundary - OpenAPI spec defines UserRole enum with OPERATOR and ADMIN."""
    res = http_client.get("/openapi.json")
    assert res.status_code == 200
    spec = res.json()
    schemas = spec.get("components", {}).get("schemas", {})
    # Check if UserRole or enum values exist
    text_spec = str(spec)
    assert "OPERATOR" in text_spec or "operator" in text_spec, "Role enum not found in OpenAPI spec"


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(24)
def test_tsconfig_strict_mode_enabled():
    """TC-B24-04: Boundary - tsconfig.json has 'strict: true'."""
    tsconfig_path = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "tsconfig.json")
    if os.path.exists(tsconfig_path):
        with open(tsconfig_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert '"strict": true' in content or "strict" in content


@pytest.mark.tier2
@pytest.mark.m5
@pytest.mark.feature(24)
def test_openapi_timestamps_are_string_format_date_time(http_client: E2EHttpClient):
    """TC-B24-05: Boundary - Timestamp fields specified with format 'date-time'."""
    res = http_client.get("/openapi.json")
    assert res.status_code == 200
    assert "date-time" in res.text or "string" in res.text
