"""
Pytest configuration and shared fixtures for Surakshanet E2E tests.
Strictly opaque-box: only external clients (HTTP, WS, MQTT, Redis, DB).
"""

import os
import uuid
import pytest
from typing import Dict, Generator

from tests.e2e.client import (
    E2EHttpClient,
    E2ERedisClient,
    E2EMqttClient,
    E2EDatabaseClient,
    DEFAULT_BACKEND_URL,
    DEFAULT_NGINX_URL,
    DEFAULT_REDIS_URL,
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_DB_URL,
)


def pytest_configure(config):
    """Register custom markers for the 4-tier E2E testing framework."""
    config.addinivalue_line("markers", "tier1: Tier 1 Feature Coverage test cases")
    config.addinivalue_line("markers", "tier2: Tier 2 Boundary & Corner Case test cases")
    config.addinivalue_line("markers", "tier3: Tier 3 Cross-Feature Combination test cases")
    config.addinivalue_line("markers", "tier4: Tier 4 Real-World Application Scenario test cases")
    config.addinivalue_line("markers", "m1: Milestone 1 Security & Authentication")
    config.addinivalue_line("markers", "m2: Milestone 2 Data Integrity & Spatial Storage")
    config.addinivalue_line("markers", "m3: Milestone 3 Architecture & Observability")
    config.addinivalue_line("markers", "m4: Milestone 4 ML & Simulation Rigor")
    config.addinivalue_line("markers", "m5: Milestone 5 Frontend Quality & UX")
    config.addinivalue_line("markers", "m6: Milestone 6 DevOps, Delivery & Documentation")
    config.addinivalue_line("markers", "feature(num): Feature Inventory index from PROJECT.md")


@pytest.fixture(scope="session")
def http_client() -> E2EHttpClient:
    """Session-scoped HTTP REST client connecting to backend."""
    return E2EHttpClient(DEFAULT_BACKEND_URL)


@pytest.fixture(scope="session")
def nginx_client() -> E2EHttpClient:
    """Session-scoped HTTP client connecting to Nginx reverse proxy."""
    return E2EHttpClient(DEFAULT_NGINX_URL)


@pytest.fixture(scope="session")
def redis_client() -> E2ERedisClient:
    """Session-scoped Redis client."""
    return E2ERedisClient(DEFAULT_REDIS_URL)


@pytest.fixture(scope="session")
def mqtt_client() -> E2EMqttClient:
    """Session-scoped MQTT client."""
    return E2EMqttClient(DEFAULT_MQTT_HOST, DEFAULT_MQTT_PORT)


@pytest.fixture(scope="session")
def db_client() -> E2EDatabaseClient:
    """Session-scoped Database client."""
    return E2EDatabaseClient(DEFAULT_DB_URL)


@pytest.fixture
def unique_email() -> str:
    """Generates a guaranteed unique email for test isolation."""
    return f"e2e_{uuid.uuid4().hex[:12]}@surakshanet.test"


@pytest.fixture
def operator_token(http_client: E2EHttpClient, unique_email: str) -> str:
    """Registers and logs in a new operator, returning Bearer JWT."""
    password = "SecureOperatorP@ss123!"
    reg_res = http_client.register_user(
        email=unique_email,
        password=password,
        name="E2E Operator",
    )
    assert reg_res.status_code in (200, 201), f"Operator registration failed: {reg_res.text}"
    login_res, token = http_client.login_user(email=unique_email, password=password)
    assert login_res.status_code == 200, f"Operator login failed: {login_res.text}"
    assert token is not None, "No access_token returned"
    return token


@pytest.fixture
def admin_token(http_client: E2EHttpClient) -> str:
    """Attempts login as seed admin; if not found, creates/promotes test admin."""
    admin_email = os.environ.get("ADMIN_EMAIL", "aloks92440@gmail.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Alok@2005")
    login_res, token = http_client.login_user(email=admin_email, password=admin_password)
    if login_res.status_code == 200 and token:
        return token

    # Fallback to test admin credentials
    test_admin_email = "admin@test.com"
    test_admin_pass = "testpassword123"
    http_client.register_user(email=test_admin_email, password=test_admin_pass, name="Admin Fallback")
    login_res, token = http_client.login_user(email=test_admin_email, password=test_admin_pass)
    if login_res.status_code == 200 and token:
        return token

    raise RuntimeError(f"Could not authenticate as admin: {login_res.text}")
