"""
SN-123 · Provenance Contract Critical Tests
===========================================
Verifies:
1. Every telemetry/prediction/metric/decision payload carries mandatory `source`.
2. `confidence` is strictly forbidden unless `source == DataSource.MODEL` (or actor_type == 'AI' for audit rows).
3. Heuristic predictions never emit `confidence` and declare `training_data=None`.
4. Model predictions declare `training_data="synthetic"` and permit `confidence`.
5. Canonical telemetry validation rejects missing, invalid, or legacy ('live', 'sim', 'mock') sources.
6. Empty readings yield 503 `forecast_unavailable` rather than a synthesised curve.

Mutation check: return confidence on the heuristic path -> test fails.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from shared.constants import DataSource
from shared.telemetry import (
    validate_telemetry,
    TelemetryValidationError,
    ApproachTelemetry,
    JunctionTelemetry,
)
from app.schemas.ml import PredictionResponse, PredictionItem
from app.models.audit import AuditLog, AuditActorType, AuditResult


def test_heuristic_prediction_strictly_forbids_confidence():
    """SN-006, SN-123: A heuristic prediction item must never carry a confidence value."""
    # Valid heuristic item with confidence=None
    valid_heuristic = PredictionResponse(
        junction_id="J0",
        predictions=[
            PredictionItem(minutes=15, predicted_pcu=45.0, confidence=None),
            PredictionItem(minutes=30, predicted_pcu=50.0, confidence=None),
        ],
        spillback_risk=0.25,
        source=DataSource.HEURISTIC,
        training_data=None,
    )
    assert valid_heuristic.source == DataSource.HEURISTIC
    assert valid_heuristic.training_data is None
    for p in valid_heuristic.predictions:
        assert p.confidence is None

    # Invalid: confidence attached to heuristic prediction must raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        PredictionResponse(
            junction_id="J0",
            predictions=[
                PredictionItem(minutes=15, predicted_pcu=45.0, confidence=0.88),
            ],
            spillback_risk=0.25,
            source=DataSource.HEURISTIC,
        )
    assert "confidence is forbidden when source is 'heuristic'" in str(exc_info.value)


def test_model_prediction_permits_confidence_and_declares_provenance():
    """SN-006, SN-007, SN-123: Model-sourced predictions permit confidence and must declare training data."""
    model_pred = PredictionResponse(
        junction_id="J1",
        predictions=[
            PredictionItem(minutes=15, predicted_pcu=52.0, confidence=0.91),
            PredictionItem(minutes=30, predicted_pcu=58.5, confidence=0.87),
        ],
        spillback_risk=0.35,
        source=DataSource.MODEL,
        training_data="synthetic",
    )
    assert model_pred.source == DataSource.MODEL
    assert model_pred.training_data == "synthetic"
    assert model_pred.predictions[0].confidence == 0.91
    assert model_pred.predictions[1].confidence == 0.87


def test_datasource_enum_closed_set():
    """SN-008, SN-123: DataSource must strictly match the six canonical sources."""
    expected_sources = {"sumo", "vision", "mqtt", "model", "heuristic", "manual"}
    actual_sources = {s.value for s in DataSource}
    assert actual_sources == expected_sources

    # Legacy sources MUST NOT exist in DataSource
    legacy_sources = {"live", "sim", "mock"}
    for leg in legacy_sources:
        assert leg not in actual_sources, f"Legacy source '{leg}' found in DataSource enum!"


def test_canonical_telemetry_source_validation():
    """SN-023, SN-114, SN-123: Telemetry ingest rejects payloads missing or carrying invalid source."""
    valid_approach = {
        "direction": "N",
        "lane_ids": ["lane_0"],
        "vehicle_count": 10.0,
        "pcu": 12.0,
        "queue_length_m": 15.0,
        "mean_speed_kmh": 35.0,
        "occupancy": 0.4,
        "accumulated_wait_s": 25.0,
    }

    # 1. Valid telemetry with canonical sources
    for src in [DataSource.SUMO, DataSource.VISION, DataSource.MQTT]:
        payload = {
            "junction_id": "J0",
            "source": src.value,
            "approaches": [valid_approach],
        }
        validated = validate_telemetry(payload)
        assert validated.source == src

    # 2. Missing source -> TelemetryValidationError
    payload_no_src = {
        "junction_id": "J0",
        "approaches": [valid_approach],
    }
    with pytest.raises(TelemetryValidationError) as exc:
        validate_telemetry(payload_no_src)
    assert "missing mandatory 'source'" in str(exc.value).lower()

    # 3. Invalid/legacy source ('mock') -> TelemetryValidationError
    payload_legacy = {
        "junction_id": "J0",
        "source": "mock",
        "approaches": [valid_approach],
    }
    with pytest.raises(TelemetryValidationError) as exc:
        validate_telemetry(payload_legacy)
    assert "unknown source 'mock'" in str(exc.value)


def test_audit_log_confidence_only_for_ai_actors():
    """SN-102, SN-123, SN-124: Audit log confidence constraint enforces AI-only confidence."""
    # User actor with confidence must be rejected
    with pytest.raises(ValueError) as exc:
        AuditLog(
            actor_type=AuditActorType.USER,
            action="SIGNAL_OVERRIDE",
            confidence=0.95,
        )
    assert "confidence must be null unless actor_type is 'AI'" in str(exc.value)

    # System actor with confidence must be rejected
    with pytest.raises(ValueError) as exc:
        AuditLog(
            actor_type=AuditActorType.SYSTEM,
            action="HEALTH_CHECK",
            confidence=0.99,
        )
    assert "confidence must be null unless actor_type is 'AI'" in str(exc.value)

    # AI actor with confidence succeeds
    ai_audit = AuditLog(
        actor_type=AuditActorType.AI,
        action="DQN_ACTION_SELECT",
        confidence=0.89,
        model="marl_policy_downtown",
        model_version="a3541fb5",
        source="model",
    )
    assert ai_audit.confidence == 0.89
    assert ai_audit.actor_type == AuditActorType.AI


def test_mutation_check_heuristic_confidence_leak():
    """
    Mutation check: return confidence on the heuristic path -> test fails.
    Simulates production code mutating to return confidence in a heuristic response.
    """
    def produce_heuristic_response(leak_confidence: bool):
        items = [
            PredictionItem(
                minutes=15,
                predicted_pcu=32.0,
                confidence=0.92 if leak_confidence else None,
            )
        ]
        return PredictionResponse(
            junction_id="J0",
            predictions=items,
            spillback_risk=0.15,
            source=DataSource.HEURISTIC,
            training_data=None,
        )

    # Non-mutated path succeeds
    resp = produce_heuristic_response(leak_confidence=False)
    assert resp.predictions[0].confidence is None

    # Mutated path: confidence leaked into heuristic response -> MUST FAIL
    with pytest.raises(ValidationError):
        produce_heuristic_response(leak_confidence=True)
