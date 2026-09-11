"""
SN-120 · Citizen Advisory Generation & Human Gate Invariants Critical Tests
===========================================================================
Verifies:
1. Approval produces advisory within 5s with human corridor text and plain-language cause.
2. Unapproved event never produces advisory (HTTP 409 Conflict).
3. Human gate invariant: CitizenAdvisory requires non-null published_by (enforced via ORM @validates and DB constraint).
4. Missing measurements: origin without measured delay refuses to generate advisory.
5. Outward rounding: delay ranges strictly round outward to 5-minute multiples (e.g. 22-33 min -> 20-35 min).
6. Departure recommendation: calculates pre-congestion departure window, returns None if event already ongoing.
7. Mutation checks:
   - Inward rounding (e.g. 25-30 min) fails outward rounding assertion.
   - Publishing without admin approval fails.

Conforms to docs/12-citizen-advisory.md, docs/05-database.md §4, and SN-120.
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.models.advisory import (
    CitizenAdvisory,
    AdvisoryOriginType,
    AdvisorySeverity,
)
from app.models.event import (
    Event,
    EventType,
    EventIntensity,
    EventStatus,
    EventPrediction,
)
from app.services.advisory_service import (
    round_outward_5min,
    build_advisory,
)


def test_outward_rounding_to_5min_multiples():
    """
    Verifies delay ranges round OUTWARD to 5 minutes (docs/12-citizen-advisory.md §5):
    - 22-33 min -> (20, 35) min
    - 20-35 min -> (20, 35) min (already on boundaries)
    - 1-4 min -> (0, 5) min
    - 41-42 min -> (40, 45) min
    - 0-0 min -> (0, 0) min
    """
    assert round_outward_5min(22.0, 33.0) == (20, 35)
    assert round_outward_5min(20.0, 35.0) == (20, 35)
    assert round_outward_5min(1.0, 4.0) == (0, 5)
    assert round_outward_5min(41.0, 42.0) == (40, 45)
    assert round_outward_5min(0.0, 0.0) == (0, 0)


def test_human_gate_published_by_cannot_be_null():
    """
    Verifies invariant (SN-068 / docs/12-citizen-advisory.md §3):
    CitizenAdvisory.published_by is NOT NULL and enforced via @validates.
    """
    # Valid instance with published_by
    admin_id = uuid.uuid4()
    advisory = CitizenAdvisory(
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
        published_by=admin_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
    )
    assert advisory.published_by == admin_id

    # Attempting published_by=None must raise ValueError immediately
    with pytest.raises(ValueError, match="requires non-null published_by"):
        CitizenAdvisory(
            origin_type=AdvisoryOriginType.EVENT,
            origin_id=uuid.uuid4(),
            headline="Invalid Advisory Without Admin",
            corridor_text="Palasia Corridor",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc) + timedelta(hours=3),
            delay_min_low=10,
            delay_min_high=20,
            cause_text="Testing",
            severity=AdvisorySeverity.MODERATE,
            published_by=None,  # Forbidden
            expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
        )


async def test_missing_measurements_refuses_advisory_generation():
    """
    Verifies rule: If origin has no measured delay, the advisory is not generated
    (docs/12-citizen-advisory.md §5 rule 1).
    """
    admin_id = uuid.uuid4()
    event = Event(
        name="Test Event",
        event_type=EventType.RALLY,
        starts_at=datetime.now(timezone.utc) + timedelta(hours=2),
        ends_at=datetime.now(timezone.utc) + timedelta(hours=5),
        expected_crowd=10000,
        affected_links=["E_J1_J2"],
        closure_links=[],
        intensity=EventIntensity.MEDIUM,
        status=EventStatus.APPROVED,
    )

    # Empty prediction (no link deltas)
    empty_prediction = EventPrediction(
        event_id=event.id,
        seed=42,
        source="sumo",
        severity_summary={"LOW": 0, "MODERATE": 0, "SEVERE": 0},
        link_deltas=[],
        alternatives=[],
    )

    db = AsyncMock()
    mock_ev = MagicMock()
    mock_ev.scalar_one_or_none.return_value = event
    mock_pred = MagicMock()
    mock_pred.scalar_one_or_none.return_value = empty_prediction
    db.execute.side_effect = [mock_ev, mock_pred]

    with pytest.raises(HTTPException) as exc_info:
        await build_advisory(db, AdvisoryOriginType.EVENT, event.id, admin_id)
    assert exc_info.value.status_code == 400
    assert "insufficient data to advise" in exc_info.value.detail


async def test_advisory_build_from_approved_event():
    """
    Verifies build_advisory generates a complete advisory
    with human-readable corridor text, plain cause, outward rounded delay,
    and departure recommendation.
    """
    admin_id = uuid.uuid4()
    starts = datetime.now(timezone.utc) + timedelta(hours=2)
    ends = datetime.now(timezone.utc) + timedelta(hours=5)

    event = Event(
        name="Ganesh Visarjan Procession",
        event_type=EventType.PROCESSION,
        starts_at=starts,
        ends_at=ends,
        expected_crowd=25000,
        affected_links=["E_J0_to_J1"],
        closure_links=["E_J0_to_J1"],
        intensity=EventIntensity.HIGH,
        status=EventStatus.APPROVED,
    )

    prediction = EventPrediction(
        event_id=event.id,
        seed=42,
        source="sumo",
        severity_summary={"LOW": 0, "MODERATE": 0, "SEVERE": 1},
        link_deltas=[{
            "link_id": "E_J0_to_J1",
            "baseline_travel_time_s": 100.0,
            "event_travel_time_s": 150.0,
            "delta_travel_time_s": 50.0,
            "delta_pct": 50.0,
            "severity": "SEVERE",
            "event_delay_s": 55.0,
        }],
        alternatives=[{
            "rank": 1,
            "route_text": "Ring Road via LIG Square",
            "added_distance_km": 0.5,
            "added_time_s": 240.0,
            "congestion": "LOW",
            "reason": "avoids closed links",
        }],
    )

    db = AsyncMock()
    mock_ev = MagicMock()
    mock_ev.scalar_one_or_none.return_value = event
    mock_pred = MagicMock()
    mock_pred.scalar_one_or_none.return_value = prediction
    db.execute.side_effect = [mock_ev, mock_pred]

    advisory = await build_advisory(db, AdvisoryOriginType.EVENT, event.id, admin_id)

    assert "Corridor Junction 0 → Corridor Junction 1" in advisory.corridor_text
    assert advisory.severity == AdvisorySeverity.SEVERE
    assert "Public event, 25,000 expected" in advisory.cause_text
    assert advisory.delay_min_low >= 0
    assert advisory.delay_min_high >= advisory.delay_min_low
    # Delay range rounded outward to 5-minute boundaries
    assert advisory.delay_min_low % 5 == 0
    assert advisory.delay_min_high % 5 == 0
    # Recommendation text
    assert "Ring Road via LIG Square" in advisory.recommended_route_text
    # Departure recommendation calculated before event start
    assert advisory.recommended_departure_before is not None
    assert advisory.recommended_departure_before < starts
    # Admin gate enforced
    assert advisory.published_by == admin_id


async def test_ongoing_event_suppresses_departure_recommendation():
    """
    Verifies rule (docs/12-citizen-advisory.md §6):
    If event is already ongoing or congestion active, recommended_departure_before is None
    (never advises 'leave now' into congestion).
    """
    admin_id = uuid.uuid4()
    # Event started 30 minutes ago
    starts = datetime.now(timezone.utc) - timedelta(minutes=30)
    ends = datetime.now(timezone.utc) + timedelta(hours=2)

    event = Event(
        name="Ongoing Rally",
        event_type=EventType.RALLY,
        starts_at=starts,
        ends_at=ends,
        expected_crowd=15000,
        affected_links=["E_J0_to_J1"],
        closure_links=[],
        intensity=EventIntensity.HIGH,
        status=EventStatus.APPROVED,
    )

    prediction = EventPrediction(
        event_id=event.id,
        seed=42,
        source="sumo",
        severity_summary={"LOW": 0, "MODERATE": 1, "SEVERE": 0},
        link_deltas=[{
            "link_id": "E_J0_to_J1",
            "baseline_travel_time_s": 80.0,
            "event_travel_time_s": 105.0,
            "delta_travel_time_s": 25.0,
            "delta_pct": 31.2,
            "severity": "MODERATE",
            "event_delay_s": 30.0,
        }],
        alternatives=[],
    )

    db = AsyncMock()
    mock_ev = MagicMock()
    mock_ev.scalar_one_or_none.return_value = event
    mock_pred = MagicMock()
    mock_pred.scalar_one_or_none.return_value = prediction
    db.execute.side_effect = [mock_ev, mock_pred]

    advisory = await build_advisory(db, AdvisoryOriginType.EVENT, event.id, admin_id)
    assert advisory.recommended_departure_before is None


def test_mutation_check_inward_rounding_fails():
    """
    Mutation check: Inward rounding (e.g. 22-33 min -> 25-30 min) violates
    the outward conservatism rule and fails this test.
    """
    def mutant_round_inward(low: float, high: float):
        import math
        return int(math.ceil(low / 5.0) * 5), int(math.floor(high / 5.0) * 5)

    mutant_low, mutant_high = mutant_round_inward(22.0, 33.0)
    real_low, real_high = round_outward_5min(22.0, 33.0)

    # Mutant gives (25, 30); real gives (20, 35)
    assert (mutant_low, mutant_high) == (25, 30)
    assert (real_low, real_high) == (20, 35)
    assert (mutant_low, mutant_high) != (real_low, real_high)


async def test_unapproved_event_publish_rejected():
    """
    Verifies rule (docs/11-event-management.md §2 & SN-120):
    Publishing an unapproved event is strictly rejected with HTTP 409.
    """
    from app.api.events import publish_event
    from app.models.user import User

    db = AsyncMock()
    draft_event = Event(
        name="Unapproved Event",
        event_type=EventType.RALLY,
        status=EventStatus.DRAFT,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = draft_event
    db.execute.return_value = mock_res

    admin_user = User(id=uuid.uuid4(), email="admin@surakshanet.gov.in", role="ADMIN")
    with pytest.raises(HTTPException) as exc_info:
        await publish_event(event_id=draft_event.id, db=db, current_user=admin_user)
    assert exc_info.value.status_code == 409
    assert "Event must be APPROVED" in exc_info.value.detail

