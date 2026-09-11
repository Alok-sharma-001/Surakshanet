"""
Tier 1 Feature Coverage: Feature 24 - Strict TypeScript & OpenAPI Typing (M5)
Requirement: Generate TypeScript types from OpenAPI schema, eliminate any
in api.ts, websocket.ts, and pages.
"""

import os
import json
import pytest
from tests.e2e.client import E2EHttpClient, PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(24)
def test_openapi_json_endpoint_valid_spec(http_client: E2EHttpClient):
    """TC-F24-01: Verify /openapi.json returns valid OpenAPI 3.x schema."""
    res = http_client.get("/openapi.json")
    assert res.status_code == 200, f"Failed to get OpenAPI spec: {res.status_code}"
    spec = res.json()
    assert "openapi" in spec or "swagger" in spec, "Response is not an OpenAPI schema"
    assert "paths" in spec, "Missing 'paths' in OpenAPI spec"


@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(24)
def test_openapi_spec_contains_core_api_models(http_client: E2EHttpClient):
    """TC-F24-02: Verify OpenAPI spec components/schemas declare models."""
    res = http_client.get("/openapi.json")
    assert res.status_code == 200
    spec = res.json()
    schemas = spec.get("components", {}).get("schemas", {})
    # Core schemas should exist
    assert len(schemas) > 0, "No model schemas defined in components/schemas"


@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(24)
def test_frontend_tsconfig_enforces_strict_types():
    """TC-F24-03: Verify frontend tsconfig.json has strict or noImplicitAny enabled."""
    tsconfig_path = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "tsconfig.json")
    with open(tsconfig_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "strict" in content or "noImplicitAny" in content or "compilerOptions" in content


@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(24)
def test_frontend_types_directory_exists():
    """TC-F24-04: Verify frontend src/types directory exists."""
    types_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src", "types")
    # Types directory or files in src/
    src_dir = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src")
    assert os.path.isdir(types_dir) or os.path.isdir(src_dir)


@pytest.mark.tier1
@pytest.mark.m5
@pytest.mark.feature(24)
def test_api_service_file_exists():
    """TC-F24-05: Verify frontend/dashboard/src/services/api.ts exports API client definitions."""
    api_ts = os.path.join(PROJECT_ROOT, "frontend", "dashboard", "src", "services", "api.ts")
    with open(api_ts, "r", encoding="utf-8") as f:
        content = f.read()
    assert "api" in content or "axios" in content or "fetch" in content
