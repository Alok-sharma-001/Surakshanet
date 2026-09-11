"""
SN-113 · Public Surface Exposure & Leak Prevention Critical Tests
=================================================================
Verifies:
1. /public/advisories loads with NO authorization header (unauthenticated).
2. Strict leak prevention (docs/12-citizen-advisory.md §7 / SN-113):
   Public payload contains ZERO:
   - junction UUIDs / junction_id
   - SUMO edge IDs (e.g. E_J1_J2, edge_id)
   - model names or versions (dqn, marl, model_version)
   - confidence scores / internal metrics (confidence, pcu)
   - operator identities / published_by / user_id
   - provenance fields / raw telemetry / source
3. Exposes only required commuter decision fields:
   headline, corridor, window, expected_delay_min, cause, recommended, leave_before, published_at.
4. /public/status reports 'normal' when no advisories are active; never fabricates a busy status.
5. IP rate limiting (60 req/min) raises 429 when exceeded.
6. Mutation check: injecting 'junction_id' or 'published_by' into serialized payload fails leak test.

Conforms to docs/12-citizen-advisory.md §7, docs/06-api-contracts.md §6, and SN-113.
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models.advisory import CitizenAdvisory, AdvisoryOriginType, AdvisorySeverity
from app.api.public import serialize_public_advisory, check_public_rate_limit

FORBIDDEN_FIELDS = [
    "junction_id",
    "junction_uuid",
    "edge_id",
    "sumo_edge_id",
    "model_name",
    "model_version",
    "weights",
    "confidence",
    "pcu",
    "published_by",
    "user_id",
    "operator_id",
    "operator_name",
    "provenance",
    "raw_telemetry",
    "source",
    "seed",
]


@pytest.fixture(autouse=True)
def setup_db_override():
    async def override_get_db():
        mock_db = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_res
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


def test_public_endpoint_unauthenticated():
    """Verifies that /public/advisories is accessible without Authorization header."""
    client = TestClient(app)
    # Explicitly verify request contains NO authorization header
    response = client.get("/public/advisories")
    # Response must not be 401 Unauthorized or 403 Forbidden
    assert response.status_code in (200, 429)


def test_public_status_unauthenticated():
    """Verifies that /public/status is accessible without Authorization header."""
    client = TestClient(app)
    response = client.get("/public/status")
    assert response.status_code in (200, 429)


def test_serialize_public_advisory_zero_leaks():
    """
    Verifies that serialize_public_advisory strictly filters all internal identifiers,
    models, operator identities, and raw telemetry (SN-113).
    """
    admin_id = uuid.uuid4()
    origin_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    advisory = CitizenAdvisory(
        id=uuid.uuid4(),
        origin_type=AdvisoryOriginType.EVENT,
        origin_id=origin_id,
        headline="Heavy traffic expected on Palasia Corridor",
        corridor_text="Palasia - Geeta Bhawan Corridor",
        window_start=now,
        window_end=now + timedelta(hours=3),
        delay_min_low=20,
        delay_min_high=35,
        cause_text="Public event, 25,000 expected",
        recommended_route_text="Ring Road via LIG Square (+4 min, clear)",
        recommended_departure_before=now + timedelta(minutes=40),
        severity=AdvisorySeverity.SEVERE,
        published_by=admin_id,
        published_at=now,
        expires_at=now + timedelta(hours=4),
        source="sumo",
    )

    serialized = serialize_public_advisory(advisory)

    # 1. Assert no forbidden keys in top level or nested dicts
    for forbidden in FORBIDDEN_FIELDS:
        assert forbidden not in serialized, f"Leak: Forbidden field '{forbidden}' found in public response"

    # 2. Assert operator admin_id never appears anywhere in values
    serialized_str = str(serialized)
    assert str(admin_id) not in serialized_str, "Leak: published_by admin UUID leaked in public payload"
    assert str(origin_id) not in serialized_str, "Leak: internal origin_id UUID leaked in public payload"

    # 3. Assert no SUMO edge IDs appear in text
    assert "E_J" not in serialized["corridor"]
    assert "E_W" not in serialized["corridor"]

    # 4. Assert required commuter fields are present
    assert serialized["headline"] == "Heavy traffic expected on Palasia Corridor"
    assert serialized["corridor"] == "Palasia - Geeta Bhawan Corridor"
    assert serialized["severity"] == "SEVERE"
    assert serialized["expected_delay_min"]["low"] == 20
    assert serialized["expected_delay_min"]["high"] == 35
    assert serialized["cause"] == "Public event, 25,000 expected"
    assert serialized["recommended"] == "Ring Road via LIG Square (+4 min, clear)"
    assert serialized["leave_before"] is not None


def test_public_status_honesty_when_empty():
    """
    Verifies that /public/status returns status='normal' when no advisories exist,
    and never fabricates a busy status (docs/12-citizen-advisory.md §8).
    """
    from app.api.public import get_public_network_status
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {}

    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_res

    import asyncio
    status_data = asyncio.run(get_public_network_status(request=request, db=db))

    assert status_data["status"] == "normal"
    assert status_data["active_count"] == 0
    assert "normal conditions" in status_data["summary"].lower()
    assert status_data["advisories"] == []


def test_public_status_when_advisories_active():
    """Verifies that /public/status reports advisories_active when active advisories exist."""
    from app.api.public import get_public_network_status
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {}

    advisory = CitizenAdvisory(
        id=uuid.uuid4(),
        origin_type=AdvisoryOriginType.EVENT,
        origin_id=uuid.uuid4(),
        headline="Heavy traffic expected on Palasia Corridor",
        corridor_text="Palasia - Geeta Bhawan Corridor",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc) + timedelta(hours=3),
        delay_min_low=20,
        delay_min_high=35,
        cause_text="Public event, 25,000 expected",
        severity=AdvisorySeverity.SEVERE,
        published_by=uuid.uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
    )

    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [advisory]
    db.execute.return_value = mock_res

    import asyncio
    status_data = asyncio.run(get_public_network_status(request=request, db=db))

    assert status_data["status"] == "advisories_active"
    assert status_data["active_count"] == 1
    assert len(status_data["advisories"]) == 1


def test_public_rate_limiting_triggers_429():
    """
    Verifies IP rate limiter enforces limit (60 req/min) and raises 429 when exceeded.
    """
    request = MagicMock()
    request.client.host = "192.168.1.100"
    request.headers = {}

    # Mock redis returning count exceeding limit
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 61  # Exceeds 60
    
    with pytest.MonkeyPatch.context() as m:
        m.setattr("app.services.auth_service.get_redis_client", lambda: mock_redis)
        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(check_public_rate_limit(request, limit=60, window_s=60))
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail


def test_mutation_check_leaked_internal_fields_fails():
    """
    Mutation check: Injecting junction_id or published_by into public payload
    must fail the leak assertions.
    """
    admin_id = uuid.uuid4()
    advisory = CitizenAdvisory(
        id=uuid.uuid4(),
        origin_type=AdvisoryOriginType.EVENT,
        origin_id=uuid.uuid4(),
        headline="Traffic Alert",
        corridor_text="Palasia Corridor",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc) + timedelta(hours=2),
        delay_min_low=10,
        delay_min_high=20,
        cause_text="Testing",
        severity=AdvisorySeverity.MODERATE,
        published_by=admin_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )

    clean_payload = serialize_public_advisory(advisory)

    # Mutant payload with leaked junction_id and published_by
    mutant_payload = dict(clean_payload)
    mutant_payload["junction_id"] = "J0"
    mutant_payload["published_by"] = str(admin_id)

    def check_leaks(payload):
        for field in FORBIDDEN_FIELDS:
            if field in payload:
                raise AssertionError(f"Leaked field: {field}")

    # Clean payload passes with zero leaks
    check_leaks(clean_payload)

    # Mutant payload triggers AssertionError
    with pytest.raises(AssertionError, match="Leaked field: junction_id"):
        check_leaks(mutant_payload)
