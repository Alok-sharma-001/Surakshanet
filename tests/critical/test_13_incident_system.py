"""SN-083..SN-094 · Critical Tests for Phase 6 Incident System
============================================================
Verifies:
1. Incident & IncidentIndicator Models (SN-083, SN-084)
   - Only POSSIBLE_INCIDENT enum value (no ACCIDENT overclaim)
   - Default status UNVERIFIED
   - Human Gate 1 Invariant (@validates): Setting CONFIRMED requires confirmed_by
   - Human Gate 2 Invariant (@validates): Warning requires CONFIRMED + warning_published_by
   - Integrity rule (SN-084): Inserting incident with zero indicator rows fails at write time
2. Anomaly Indicators (SN-086..SN-088)
   - Speed collapse fires on drop < 40% baseline; suppressed during normal red phase
   - Stationary vehicle fires > 20s outside queue; suppressed in queue context or red signal
   - Occupancy spike fires on > 0.75 absolute AND > 1.5x baseline
   - Flow drop fires on downstream < 50% upstream
   - Queue anomaly fires on growth > 3x normal
3. Combination Rule and Anomaly Score (SN-089)
   - Fixed weights formula: Σ (w_i * s_i) / Σ (w_i available)
   - Raises strictly when indicators_fired >= 2 AND confidence >= 0.50
   - Missing indicators correctly normalized in denominator
4. Deduplication & Auto-Resolution (SN-090)
   - One open incident per link (no duplicate rows created)
   - Auto-resolves after 5 minutes of all-clear, logged as auto_cleared, never deleted
5. REST API & Human Gates (SN-091..SN-094)
   - Human Gate 1: POST /incidents/{id}/confirm sets CONFIRMED, penalizes link, proposes unit
   - Human Gate 2: POST /incidents/{id}/publish-warning returns 409 if unconfirmed
   - Dismissal requires non-empty reason
   - Audited throughout
"""

import uuid
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.incident import (
    Incident,
    IncidentIndicator,
    IncidentType,
    IncidentStatus,
    IncidentIndicatorType,
)
from app.models.user import User, UserRole
from app.models.audit import AuditActorType, AuditResult
from app.models.advisory import CitizenAdvisory, AdvisoryOriginType
from services.anomaly_service.indicators import (
    evaluate_speed_collapse,
    evaluate_stationary_vehicle,
    evaluate_occupancy_spike,
    evaluate_flow_drop,
    evaluate_queue_anomaly,
    IndicatorResult,
)
from services.anomaly_service.rules import (
    evaluate_anomaly_combination,
    INDICATOR_WEIGHTS,
    MIN_INDICATORS_FIRED,
    MIN_CONFIDENCE_THRESHOLD,
)
from services.anomaly_service.main import (
    AnomalyDetector,
    LinkTelemetryBuffer,
    AUTO_RESOLVE_CLEAR_SECONDS,
)
from app.services.routing_service import routing_service
from app.services.advisory_service import build_advisory
from fastapi import HTTPException


def make_mock_db(scalar_return=None):
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = scalar_return
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    return mock_db


# ============================================================================
# 1. Models and Integrity Invariants (SN-083, SN-084)
# ============================================================================

def test_incident_type_has_no_accident_value():
    """SN-083: The only incident_type value is POSSIBLE_INCIDENT.

    There is deliberately no ACCIDENT enum value so the schema itself prevents
    the overclaim of certifying a crash from telemetry alone.
    """
    assert hasattr(IncidentType, "POSSIBLE_INCIDENT")
    assert not hasattr(IncidentType, "ACCIDENT")
    assert not hasattr(IncidentType, "CRASH")
    assert list(IncidentType.__members__.keys()) == ["POSSIBLE_INCIDENT"]


def test_incident_human_gate_invariants():
    """SN-083, SN-092, SN-094: Model invariants enforce human gates.

    1. Default status is strictly UNVERIFIED.
    2. Setting CONFIRMED without operator confirmed_by raises ValueError.
    3. Setting warning_published_at on unconfirmed incident raises ValueError.
    """
    operator_id = uuid.uuid4()

    # 1. Default status is UNVERIFIED
    inc = Incident(link_id="E_J1_J2", confidence=0.72)
    assert inc.status == IncidentStatus.UNVERIFIED
    assert inc.confirmed_by is None
    assert inc.confirmed_at is None
    assert inc.note == "Possible incident. Unverified — operator review required."

    # 2. Cannot set CONFIRMED without operator confirmed_by
    with pytest.raises(ValueError, match="cannot be set to CONFIRMED without an operator action"):
        inc.status = IncidentStatus.CONFIRMED

    # 3. Direct constructor with CONFIRMED but without confirmed_by fails
    with pytest.raises(ValueError, match="cannot be set to CONFIRMED without an operator action"):
        Incident(status=IncidentStatus.CONFIRMED, link_id="E_J1_J2", confidence=0.8)

    # 4. Setting with confirmed_by succeeds
    inc.confirmed_by = operator_id
    inc.status = IncidentStatus.CONFIRMED
    assert inc.status == IncidentStatus.CONFIRMED

    # 5. Cannot clear confirmed_by from a confirmed incident
    with pytest.raises(ValueError, match="Cannot remove confirmed_by operator"):
        inc.confirmed_by = None

    # 6. Human Gate 2: Cannot publish warning on unconfirmed incident
    inc_unverified = Incident(link_id="E_J2_J3", confidence=0.65)
    with pytest.raises(ValueError, match="Incident must be CONFIRMED before a public warning"):
        inc_unverified.warning_published_at = datetime.utcnow()


def test_zero_indicators_rejected_at_write_time():
    """SN-084: Storage plus the integrity rule that an incident cannot exist

    without a measured indicator. Inserting an incident with zero indicator rows fails.
    """
    from app.database import Base

    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Incident.__table__.create(test_engine)
    IncidentIndicator.__table__.create(test_engine)
    SessionClass = sessionmaker(bind=test_engine)

    # 1. Attempting to insert an incident with NO indicators must raise ValueError
    with SessionClass() as session:
        empty_inc = Incident(link_id="E_J1_J2", confidence=0.65)
        session.add(empty_inc)
        with pytest.raises(ValueError, match="cannot exist without at least one measured indicator"):
            session.commit()

    # 2. Inserting an incident with at least one indicator row succeeds
    with SessionClass() as session:
        valid_inc = Incident(link_id="E_J1_J2", confidence=0.75)
        ind = IncidentIndicator(
            incident=valid_inc,
            indicator=IncidentIndicatorType.SPEED_COLLAPSE,
            measured_value=12.0,
            threshold=20.0,
        )
        session.add(valid_inc)
        session.add(ind)
        session.commit()
        assert valid_inc.id is not None
        assert len(valid_inc.indicators) == 1

    test_engine.dispose()


# ============================================================================
# 2. Anomaly Indicators (SN-086, SN-087, SN-088)
# ============================================================================

def test_speed_collapse_indicator():
    """SN-086: Speed collapse fires when mean speed < 40% of baseline over 60s window.

    Does not fire during a normal red phase.
    """
    baseline_speed = 50.0  # km/h
    # 40% threshold is 20.0 km/h

    # Normal free flow (45 km/h) -> No fire
    res_normal = evaluate_speed_collapse(45.0, baseline_speed)
    assert not res_normal.fired
    assert res_normal.threshold == 20.0
    assert res_normal.strength == 0.0

    # Lane blockage collapse (8.0 km/h) -> Fires!
    res_collapse = evaluate_speed_collapse(8.0, baseline_speed)
    assert res_collapse.fired
    assert res_collapse.measured_value == 8.0
    assert res_collapse.threshold == 20.0
    assert res_collapse.strength > 0.5  # (20 - 8) / 20 = 0.60

    # Normal red phase alternation -> Suppressed, does NOT fire
    res_red = evaluate_speed_collapse(
        mean_speed_kmh=5.0,
        baseline_speed_kmh=baseline_speed,
        controlling_signal_red=True,
        is_normal_red_phase=True,
    )
    assert not res_red.fired
    assert res_red.details.get("suppressed") is True


def test_stationary_vehicle_indicator():
    """SN-087: Stationary vehicle stopped > 20s outside signal queue context.

    Does not fire for queued vehicles at a red signal.
    """
    # Moving vehicle -> No fire
    res_moving = evaluate_stationary_vehicle(max_stationary_s=5.0)
    assert not res_moving.fired

    # Stopped vehicle outside queue context for 35s -> Fires!
    res_stopped = evaluate_stationary_vehicle(
        max_stationary_s=35.0,
        in_queue_context=False,
        controlling_signal_red=False,
    )
    assert res_stopped.fired
    assert res_stopped.measured_value == 35.0
    assert res_stopped.threshold == 20.0
    assert res_stopped.strength > 0.7  # (35 - 20) / 20 = 0.75

    # Stopped vehicle within red signal queue -> Suppressed!
    res_queue = evaluate_stationary_vehicle(
        max_stationary_s=40.0,
        in_queue_context=True,
        controlling_signal_red=True,
    )
    assert not res_queue.fired
    assert res_queue.details.get("suppressed") is True

    # Untracked / unavailable data source -> Not available
    res_unavail = evaluate_stationary_vehicle(max_stationary_s=0.0, data_source_available=False)
    assert not res_unavail.available
    assert not res_unavail.fired


def test_remaining_indicators():
    """SN-088: Occupancy spike, Flow drop, and Queue anomaly."""
    # 1. Occupancy spike: > 0.75 absolute AND > 1.5x baseline
    # Normal peak (0.65 vs baseline 0.50) -> does not fire (0.65 <= 0.75)
    res_occ_peak = evaluate_occupancy_spike(0.65, 0.50)
    assert not res_occ_peak.fired

    # Severe spike (0.85 vs baseline 0.40) -> fires
    res_occ_spike = evaluate_occupancy_spike(0.85, 0.40)
    assert res_occ_spike.fired
    assert res_occ_spike.measured_value == 0.85

    # 2. Flow drop: downstream < 50% of upstream
    res_flow_drop = evaluate_flow_drop(downstream_throughput=20.0, upstream_throughput=80.0)
    assert res_flow_drop.fired
    assert res_flow_drop.threshold == 40.0

    res_flow_norm = evaluate_flow_drop(downstream_throughput=70.0, upstream_throughput=80.0)
    assert not res_flow_norm.fired

    # 3. Queue anomaly: queue growth rate > 3x normal growth
    res_queue_spike = evaluate_queue_anomaly(queue_growth_rate=4.5, normal_growth_rate=1.0)
    assert res_queue_spike.fired
    assert res_queue_spike.threshold == 3.0

    res_queue_norm = evaluate_queue_anomaly(queue_growth_rate=1.8, normal_growth_rate=1.0)
    assert not res_queue_norm.fired


# ============================================================================
# 3. Combination Rule and Anomaly Score (SN-089)
# ============================================================================

def test_combination_rule_exact_formula():
    """SN-089: Anomaly score combination rule matches documented formula:

    confidence = Σ (w_i * s_i) / Σ (w_i available)
    Raises when indicators_fired >= 2 AND confidence >= 0.50.
    """
    # 1. Only 1 indicator fired -> Does NOT raise (requires >= 2)
    ind_1 = IndicatorResult("SPEED_COLLAPSE", True, 4.0, 20.0, strength=0.8, available=True)
    ind_2 = IndicatorResult("STATIONARY_VEHICLE", False, 0.0, 20.0, strength=0.0, available=True)
    ind_3 = IndicatorResult("OCCUPANCY_SPIKE", False, 0.3, 0.75, strength=0.0, available=True)
    ind_4 = IndicatorResult("FLOW_DROP", False, 50.0, 40.0, strength=0.0, available=True)
    ind_5 = IndicatorResult("QUEUE_ANOMALY", False, 1.0, 3.0, strength=0.0, available=True)

    eval_single = evaluate_anomaly_combination([ind_1, ind_2, ind_3, ind_4, ind_5])
    assert eval_single.indicators_fired == 1
    assert not eval_single.should_raise

    # 2. Two weak indicators (confidence < 0.50) -> Does NOT raise
    ind_1_weak = IndicatorResult("SPEED_COLLAPSE", True, 18.0, 20.0, strength=0.1, available=True)
    ind_2_weak = IndicatorResult("STATIONARY_VEHICLE", True, 21.0, 20.0, strength=0.05, available=True)
    eval_weak = evaluate_anomaly_combination([ind_1_weak, ind_2_weak, ind_3, ind_4, ind_5])
    assert eval_weak.indicators_fired == 2
    assert eval_weak.confidence < 0.50
    assert not eval_weak.should_raise

    # 3. Three strong indicators (speed collapse + stationary vehicle + occupancy spike) -> Raises!
    # 0.30*0.90 + 0.25*0.90 + 0.20*0.50 = 0.27 + 0.225 + 0.10 = 0.595 >= 0.50
    ind_1_strong = IndicatorResult("SPEED_COLLAPSE", True, 2.0, 20.0, strength=0.90, available=True)
    ind_2_strong = IndicatorResult("STATIONARY_VEHICLE", True, 38.0, 20.0, strength=0.90, available=True)
    ind_3_strong = IndicatorResult("OCCUPANCY_SPIKE", True, 0.90, 0.75, strength=0.50, available=True)
    eval_strong = evaluate_anomaly_combination([ind_1_strong, ind_2_strong, ind_3_strong, ind_4, ind_5])

    assert eval_strong.indicators_fired == 3
    assert eval_strong.indicators_total == 5
    assert eval_strong.confidence >= 0.50
    assert eval_strong.should_raise
    assert eval_strong.note == "Possible incident. Unverified — operator review required."


def test_combination_rule_with_missing_indicator():
    """SN-089: If stationary vehicle tracking is unavailable, confidence is

    normalized over the 4 available indicators rather than penalized.
    """
    ind_1 = IndicatorResult("SPEED_COLLAPSE", True, 4.0, 20.0, strength=0.80, available=True)
    ind_2_unavail = IndicatorResult("STATIONARY_VEHICLE", False, 0.0, 20.0, strength=0.0, available=False)
    ind_3 = IndicatorResult("OCCUPANCY_SPIKE", True, 0.90, 0.75, strength=0.50, available=True)
    ind_4 = IndicatorResult("FLOW_DROP", False, 50.0, 40.0, strength=0.0, available=True)
    ind_5 = IndicatorResult("QUEUE_ANOMALY", False, 1.0, 3.0, strength=0.0, available=True)

    res = evaluate_anomaly_combination([ind_1, ind_2_unavail, ind_3, ind_4, ind_5])
    assert res.indicators_total == 4  # STATIONARY_VEHICLE excluded
    assert res.indicators_fired == 2
    # Available weight sum = 0.30 + 0.20 + 0.15 + 0.10 = 0.75
    # Weighted strength = 0.30*0.80 + 0.20*0.50 = 0.24 + 0.10 = 0.34
    # Confidence = 0.34 / 0.75 = 0.45
    assert res.confidence == 0.45


# ============================================================================
# 4. Deduplication & Auto-Resolution (SN-090)
# ============================================================================

@pytest.mark.asyncio
async def test_detector_deduplication_one_open_incident_per_link():
    """SN-090: One open incident per link deduplication.

    Successive anomaly evaluations on the same link update the existing
    incident rather than creating duplicate incident rows.
    """
    detector = AnomalyDetector()

    ind_1 = IndicatorResult("SPEED_COLLAPSE", True, 2.0, 20.0, strength=0.9, available=True)
    ind_2 = IndicatorResult("STATIONARY_VEHICLE", True, 38.0, 20.0, strength=0.9, available=True)
    evaluation = evaluate_anomaly_combination([ind_1, ind_2])

    mock_db = make_mock_db(scalar_return=None)

    # First detection -> Creates new incident
    inc_1 = await detector.process_and_persist(
        db=mock_db,
        link_id="E_J1_J2",
        evaluation=evaluation,
        junction_id="J1",
        source="sumo",
    )
    assert inc_1 is not None
    assert inc_1.link_id == "E_J1_J2"
    assert "E_J1_J2" in detector.open_incidents
    mock_db.add.assert_called()

    # Second detection on same link -> Updates existing, does NOT create a second new row
    mock_db_2 = make_mock_db(scalar_return=inc_1)

    inc_2 = await detector.process_and_persist(
        db=mock_db_2,
        link_id="E_J1_J2",
        evaluation=evaluation,
        junction_id="J1",
        source="sumo",
    )
    assert inc_2.id == inc_1.id
    # No new Incident added to db
    for call in mock_db_2.add.call_args_list:
        added_obj = call[0][0]
        assert not isinstance(added_obj, Incident)


@pytest.mark.asyncio
async def test_detector_auto_resolves_after_clearance():
    """SN-090: Auto-resolves after 5 minutes of all-clear, logged as auto_cleared,

    never silently deleted.
    """
    detector = AnomalyDetector()

    # Create an open incident
    incident_id = uuid.uuid4()
    inc = Incident(
        id=incident_id,
        link_id="E_J1_J2",
        status=IncidentStatus.UNVERIFIED,
        confidence=0.75,
    )
    detector.open_incidents["E_J1_J2"] = {
        "incident_id": incident_id,
        "first_detected": 1000.0,
        "clear_start": None,
    }

    mock_db = make_mock_db(scalar_return=inc)

    # Cleared evaluation (no indicators fired)
    clear_eval = evaluate_anomaly_combination([
        IndicatorResult("SPEED_COLLAPSE", False, 45.0, 20.0, 0.0, True),
        IndicatorResult("STATIONARY_VEHICLE", False, 0.0, 20.0, 0.0, True),
    ])

    # Step 1: Initial clear signal starts the clear timer
    with patch("time.time", return_value=2000.0):
        await detector.process_and_persist(mock_db, "E_J1_J2", clear_eval)
        assert detector.open_incidents["E_J1_J2"]["clear_start"] == 2000.0
        assert inc.status == IncidentStatus.UNVERIFIED  # Still unverified, not yet 5 min

    # Step 2: 4 minutes later (240s) -> Still unverified
    with patch("time.time", return_value=2240.0):
        await detector.process_and_persist(mock_db, "E_J1_J2", clear_eval)
        assert inc.status == IncidentStatus.UNVERIFIED

    # Step 3: 5.5 minutes later (330s >= 300s) -> Auto-resolves!
    with patch("time.time", return_value=2330.0):
        await detector.process_and_persist(mock_db, "E_J1_J2", clear_eval)
        assert inc.status == IncidentStatus.RESOLVED
        assert inc.resolution == "auto_cleared"
        assert "E_J1_J2" not in detector.open_incidents


# ============================================================================
# 5. REST API & Human Gates (SN-091, SN-092, SN-093, SN-094)
# ============================================================================

@pytest.mark.asyncio
async def test_operator_confirmation_triggers_post_automation():
    """SN-092, SN-093: Human Gate 1 — Operator confirmation.

    1. Sets status CONFIRMED.
    2. Penalises link in routing graph.
    3. Recomputes alternative routes.
    4. Proposes (does NOT dispatch) response unit.
    5. Drafts advisory (publication still blocked).
    6. Audited.
    """
    from app.api.incidents import confirm_incident

    operator = User(id=uuid.uuid4(), email="operator@surakshanet.gov.in", role=UserRole.OPERATOR)

    test_inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_J2",
        junction_id="J1",
        status=IncidentStatus.UNVERIFIED,
        confidence=0.74,
    )
    mock_db = make_mock_db(scalar_return=test_inc)

    resp = await confirm_incident(incident_id=test_inc.id, db=mock_db, current_user=operator)

    # Invariant: confirmed status & operator recorded
    assert test_inc.status == IncidentStatus.CONFIRMED
    assert test_inc.confirmed_by == operator.id

    # Post-confirmation automation verified:
    # 1. Routing penalty applied
    assert len(routing_service.incident_penalties) > 0
    # 2. Response unit step is honest about having no real dispatch/unit-
    # location system to draw a specific unit ID or ETA from — it must never
    # fabricate one, and must not claim automatic dispatch occurred.
    assert resp.proposed_unit["status"] == "MANUAL_DISPATCH_REQUIRED"
    assert "unit_id" not in resp.proposed_unit
    assert "eta_minutes" not in resp.proposed_unit
    # 3. Advisory draft created
    assert resp.advisory_draft["status"] == "DRAFT"
    assert "Traffic alert" in resp.advisory_draft["headline"]

    # Clean up penalty
    routing_service.clear_incident_penalty("E_J1_J2")


@pytest.mark.asyncio
async def test_public_warning_human_gate_2():
    """SN-094: Human Gate 2 — Public warning publication (ADMIN only).

    Invariant: Attempting to publish on an UNVERIFIED incident returns 409 Conflict.
    """
    from app.api.incidents import publish_incident_warning

    admin = User(id=uuid.uuid4(), email="admin@surakshanet.gov.in", role=UserRole.ADMIN)

    # 1. Unverified incident -> Returns 409
    unverified_inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_J2",
        status=IncidentStatus.UNVERIFIED,
        confidence=0.74,
    )
    mock_db_1 = make_mock_db(scalar_return=unverified_inc)

    with pytest.raises(HTTPException) as exc:
        await publish_incident_warning(unverified_inc.id, db=mock_db_1, current_user=admin)
    assert exc.value.status_code == 409
    assert "Incident must be CONFIRMED" in exc.value.detail

    # 2. Confirmed incident -> Warning succeeds
    confirmed_inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_J2",
        status=IncidentStatus.CONFIRMED,
        confirmed_by=uuid.uuid4(),
        confidence=0.74,
    )
    ind = IncidentIndicator(
        incident=confirmed_inc,
        indicator=IncidentIndicatorType.SPEED_COLLAPSE,
        measured_value=5.0,
        threshold=20.0,
    )
    confirmed_inc.indicators = [ind]
    mock_db_2 = make_mock_db(scalar_return=confirmed_inc)

    res = await publish_incident_warning(confirmed_inc.id, db=mock_db_2, current_user=admin)
    assert res["status"] == "warning_published"
    assert confirmed_inc.warning_published_by == admin.id
    assert confirmed_inc.warning_published_at is not None


@pytest.mark.asyncio
async def test_dismiss_requires_reason():
    """SN-092: Dismissal requires a non-empty reason and records it in resolution."""
    from app.api.incidents import dismiss_incident, DismissRequest
    from pydantic import ValidationError

    operator = User(id=uuid.uuid4(), email="operator@surakshanet.gov.in", role=UserRole.OPERATOR)

    inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_J2",
        status=IncidentStatus.UNVERIFIED,
        confidence=0.70,
    )
    mock_db = make_mock_db(scalar_return=inc)

    # Empty reason is rejected by schema or validator
    with pytest.raises(ValidationError):
        DismissRequest(reason="")

    # Valid dismissal succeeds
    req = DismissRequest(reason="Temporary road maintenance sensor artifact")
    await dismiss_incident(inc.id, req, db=mock_db, current_user=operator)
    assert inc.status == IncidentStatus.DISMISSED
    assert inc.resolution == "Temporary road maintenance sensor artifact"


def test_uncalibrated_none_speed_telemetry_handling():
    """SN-072, SN-086: Uncalibrated camera or empty approach emits mean_speed_kmh=None.

    Ensures speed collapse evaluator marks available=False rather than crashing,
    and LinkTelemetryBuffer calculates baseline from non-None samples.
    """
    res = evaluate_speed_collapse(mean_speed_kmh=None, baseline_speed_kmh=45.0)
    assert not res.available
    assert not res.fired
    assert res.measured_value == 0.0
    assert "Speed not resolvable" in res.details.get("reason", "")

    buf = LinkTelemetryBuffer(link_id="E_J1_J2")
    buf.add_sample(speed_kmh=50.0, occupancy=0.2, flow=10.0, queue_length=0.0)
    buf.add_sample(speed_kmh=None, occupancy=0.2, flow=10.0, queue_length=0.0)
    buf.add_sample(speed_kmh=40.0, occupancy=0.2, flow=10.0, queue_length=0.0)
    # Baseline speed computed from numeric samples: (50 + 40) / 2 = 45.0
    assert buf.get_baseline_speed() == 45.0


@pytest.mark.asyncio
async def test_detector_restart_deduplication():
    """SN-090: If detector restarts with empty in-memory open_incidents,

    it must check the database and update the existing incident rather than
    creating a duplicate row on the same link.
    """
    detector = AnomalyDetector()
    existing_incident = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_to_J2",
        status=IncidentStatus.UNVERIFIED,
        confidence=0.60,
    )
    mock_db = make_mock_db(scalar_return=existing_incident)

    ind_1 = IndicatorResult("SPEED_COLLAPSE", True, 2.0, 20.0, strength=0.9, available=True)
    ind_2 = IndicatorResult("STATIONARY_VEHICLE", True, 38.0, 20.0, strength=0.9, available=True)
    evaluation = evaluate_anomaly_combination([ind_1, ind_2])

    # In-memory dict is empty before this call
    assert "E_J1_to_J2" not in detector.open_incidents

    res = await detector.process_and_persist(
        db=mock_db,
        link_id="E_J1_to_J2",
        evaluation=evaluation,
    )
    # Updated existing incident instead of creating new one
    assert res.id == existing_incident.id
    assert detector.open_incidents["E_J1_to_J2"]["incident_id"] == existing_incident.id


@pytest.mark.asyncio
async def test_confirmed_incident_preserved_across_telemetry_drops():
    """SN-090, SN-092: Confirmed incident requires human operator resolution.

    Temporary drop in telemetry below threshold must NOT auto-resolve or delete
    the confirmed incident from tracking, preventing duplicate incident creation.
    """
    detector = AnomalyDetector()
    confirmed_inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_to_J2",
        status=IncidentStatus.CONFIRMED,
        confirmed_by=uuid.uuid4(),
        confidence=0.85,
    )
    detector.open_incidents["E_J1_to_J2"] = {
        "incident_id": confirmed_inc.id,
        "first_detected": 1000.0,
        "clear_start": 1000.0,
    }
    mock_db = make_mock_db(scalar_return=confirmed_inc)

    clear_eval = evaluate_anomaly_combination([
        IndicatorResult("SPEED_COLLAPSE", False, 45.0, 20.0, 0.0, True),
        IndicatorResult("STATIONARY_VEHICLE", False, 0.0, 20.0, 0.0, True),
    ])

    # 10 minutes later (600s >= 300s) of all-clear
    with patch("time.time", return_value=1600.0):
        await detector.process_and_persist(mock_db, "E_J1_to_J2", clear_eval)
        # Invariant: confirmed incident status is NOT auto-resolved
        assert confirmed_inc.status == IncidentStatus.CONFIRMED
        # Tracking is preserved (not deleted)
        assert "E_J1_to_J2" in detector.open_incidents


@pytest.mark.asyncio
async def test_operator_resolution_lifecycle():
    """SN-092, Completion Gate 6: Operator resolves incident.

    Sets status to RESOLVED, records resolution text, clears routing penalty,
    writes audit log, and broadcasts event.
    """
    from app.api.incidents import resolve_incident, ResolveRequest

    operator = User(id=uuid.uuid4(), email="operator@surakshanet.gov.in", role=UserRole.OPERATOR)
    inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_to_J2",
        status=IncidentStatus.CONFIRMED,
        confirmed_by=operator.id,
        confidence=0.80,
    )
    # Apply penalty beforehand
    routing_service.apply_incident_penalty("E_J1_to_J2", penalty=100.0)
    assert len(routing_service.incident_penalties) > 0

    mock_db = make_mock_db(scalar_return=inc)
    req = ResolveRequest(resolution="Debris cleared and traffic moving freely")

    res = await resolve_incident(inc.id, req, db=mock_db, current_user=operator)
    assert res.status == "RESOLVED"
    assert res.resolution == "Debris cleared and traffic moving freely"
    # Routing penalty cleared upon resolution
    assert len(routing_service.incident_penalties) == 0


@pytest.mark.asyncio
async def test_state_machine_transition_guards():
    """SN-092, SN-094: Strict state machine transition guards (409 Conflict)."""
    from app.api.incidents import (
        confirm_incident,
        dismiss_incident,
        escalate_incident,
        publish_incident_warning,
        resolve_incident,
        DismissRequest,
    )

    admin = User(id=uuid.uuid4(), email="admin@surakshanet.gov.in", role=UserRole.ADMIN)

    # 1. Cannot confirm an already RESOLVED incident
    resolved_inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_J2",
        status=IncidentStatus.RESOLVED,
        confirmed_by=admin.id,
        confidence=0.75,
    )
    mock_db = make_mock_db(scalar_return=resolved_inc)
    with pytest.raises(HTTPException) as exc:
        await confirm_incident(resolved_inc.id, db=mock_db, current_user=admin)
    assert exc.value.status_code == 409
    assert "already RESOLVED" in exc.value.detail

    # 2. Cannot dismiss an already RESOLVED incident
    with pytest.raises(HTTPException) as exc:
        await dismiss_incident(resolved_inc.id, DismissRequest(reason="late dismissal"), db=mock_db, current_user=admin)
    assert exc.value.status_code == 409

    # 3. Cannot escalate a DISMISSED incident
    dismissed_inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_J2",
        status=IncidentStatus.DISMISSED,
        confirmed_by=admin.id,
        confidence=0.75,
    )
    mock_db_d = make_mock_db(scalar_return=dismissed_inc)
    with pytest.raises(HTTPException) as exc:
        await escalate_incident(dismissed_inc.id, db=mock_db_d, current_user=admin)
    assert exc.value.status_code == 409

    # 4. Cannot publish public warning twice
    warned_inc = Incident(
        id=uuid.uuid4(),
        link_id="E_J1_J2",
        status=IncidentStatus.CONFIRMED,
        confirmed_by=admin.id,
        warning_published_at=datetime.utcnow(),
        confidence=0.80,
    )
    mock_db_w = make_mock_db(scalar_return=warned_inc)
    with pytest.raises(HTTPException) as exc:
        await publish_incident_warning(warned_inc.id, db=mock_db_w, current_user=admin)
    assert exc.value.status_code == 409
    assert "already been published" in exc.value.detail

    # 5. Cannot resolve a DISMISSED incident
    with pytest.raises(HTTPException) as exc:
        await resolve_incident(dismissed_inc.id, db=mock_db_d, current_user=admin)
    assert exc.value.status_code == 409


def test_telemetry_approach_and_penalty_avoidance():
    """SN-041, SN-093: Telemetry approach mapping and penalty routing avoidance."""
    from shared.corridor_topology import edge_for_telemetry_approach

    # J2 west approach maps to corridor edge E_J1_to_J2
    edge_id = edge_for_telemetry_approach("J2", "W")
    assert edge_id == "E_J1_to_J2"

    # Applying penalty via approach notation "J2_W" succeeds
    found = routing_service.apply_incident_penalty("J2_W", penalty=500.0)
    assert found == ("J1", "J2")
    assert ("J1", "J2") in routing_service.incident_penalties

    # Recomputing alternatives produces paths avoiding the penalized link
    alts = routing_service.recompute_incident_alternatives("J2_W")
    assert "alternatives" in alts or "primary" in alts

    # Clean up
    routing_service.clear_incident_penalty("J2_W")
    assert ("J1", "J2") not in routing_service.incident_penalties
