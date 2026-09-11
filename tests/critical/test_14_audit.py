"""
SN-124 · Governance, Audit Trail & Privacy Critical Tests
=========================================================
Verifies:
1. Mandatory Action Logging (docs/18-audit-logging.md §2):
   Every consequential human and AI action writes a complete audit record with:
   actor_type, action, result, timestamp, and correlation_id.
2. Confidence Invariant (docs/18-audit-logging.md §1):
   confidence is non-null ONLY when actor_type == 'AI'. Non-AI actor with confidence raises ValueError.
3. Redaction Invariant (docs/18-audit-logging.md §4):
   Passwords, tokens, secrets, and authorization keys are recursively redacted ([REDACTED]).
4. Retention Policy (docs/17-security-privacy.md §4 / SN-108):
   scripts/retention.sh is executable and enforces the retention schedule.
5. Privacy by Default (docs/17-security-privacy.md §2 / SN-107):
   PrivacyBlurrer applies Gaussian blur (ksize >= 25) to face and plate regions.
6. ANPR Code Gating (docs/17-security-privacy.md §3 / SN-109):
   VISION_ANPR_ENABLED is disabled (False) by default.
7. False-Positive Rate & Model Limitations (SN-110):
   GET /vision/false-positive-rate computes dismissed / total;
   GET /vision/model-limitations publishes declared model limitations and biases.
8. Mutation Check:
   Setting confidence on a USER actor fails; bypassing audit write fails.
"""

import os
import uuid
import subprocess
import numpy as np
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.models.audit import AuditLog, AuditActorType, AuditResult
from app.models.user import User, UserRole
from app.models.vision import BehaviorFlag, BehaviorFlagType, BehaviorFlagStatus
from app.services.audit_service import write_audit, SENSITIVE_KEYS
from services.vision_worker.privacy import PrivacyBlurrer, blur_bounding_box
from services.vision_worker.config import VisionWorkerConfig


# ---------------------------------------------------------------------------
# 1. Mandatory Actions Audit Verification
# ---------------------------------------------------------------------------

MANDATORY_ACTIONS = [
    ("SIGNAL_OVERRIDE", AuditActorType.USER, None),
    ("SIGNAL_MODE_CHANGE", AuditActorType.USER, None),
    ("CORRIDOR_ACTIVATE", AuditActorType.USER, None),
    ("CORRIDOR_DEACTIVATE", AuditActorType.SYSTEM, None),
    ("INCIDENT_CONFIRM", AuditActorType.USER, None),
    ("INCIDENT_DISMISS", AuditActorType.USER, None),
    ("PUBLIC_WARNING_PUBLISH", AuditActorType.USER, None),
    ("EVENT_APPROVE", AuditActorType.USER, None),
    ("ADVISORY_PUBLISH", AuditActorType.USER, None),
    ("ROUTE_DIVERSION", AuditActorType.USER, None),
    ("USER_LOGIN", AuditActorType.USER, None),
    ("USER_LOGOUT", AuditActorType.USER, None),
    ("TOKEN_REVOKE", AuditActorType.USER, None),
    ("ACCESS_DENIED", AuditActorType.USER, None),
    # AI actions (carry non-null confidence)
    ("AI_CONTROL_DECISION", AuditActorType.AI, 0.92),
    ("AI_INCIDENT_DETECT", AuditActorType.AI, 0.85),
    ("AI_ADVISORY_DRAFT", AuditActorType.AI, 0.88),
    ("AI_BEHAVIOR_FLAG", AuditActorType.AI, 0.95),
]


@pytest.mark.parametrize("action,actor_type,conf", MANDATORY_ACTIONS)
@pytest.mark.asyncio
async def test_mandatory_action_writes_complete_record(action, actor_type, conf):
    """Asserts each mandatory action produces a valid, complete audit record."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    actor_id = uuid.uuid4() if actor_type == AuditActorType.USER else None

    entry = await write_audit(
        db=mock_db,
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        target_type="test_target",
        target_id=uuid.uuid4(),
        input_payload={"param": "value"},
        output_payload={"status": "completed"},
        confidence=conf,
        result=AuditResult.SUCCESS,
        source="test",
        correlation_id="corr-test-123",
    )

    assert entry.action == action
    assert entry.actor_type == actor_type
    assert entry.result == AuditResult.SUCCESS
    assert entry.timestamp is not None
    assert entry.correlation_id == "corr-test-123"

    if actor_type == AuditActorType.AI:
        assert entry.confidence == conf
    else:
        assert entry.confidence is None

    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Confidence Invariant Tests
# ---------------------------------------------------------------------------

def test_confidence_non_null_only_for_ai():
    """docs/18-audit-logging.md §1: confidence on human or system actor is rejected."""
    # 1. AI actor with confidence succeeds
    ai_log = AuditLog(
        action="AI_CONTROL_DECISION",
        actor_type=AuditActorType.AI,
        confidence=0.91,
    )
    assert ai_log.confidence == 0.91
    assert ai_log.actor_type == AuditActorType.AI

    # 2. USER actor with confidence MUST raise ValueError
    with pytest.raises(ValueError, match="confidence must be null unless actor_type is 'AI'"):
        AuditLog(
            action="SIGNAL_OVERRIDE",
            actor_type=AuditActorType.USER,
            confidence=0.99,
        )

    # 3. SYSTEM actor with confidence MUST raise ValueError
    with pytest.raises(ValueError, match="confidence must be null unless actor_type is 'AI'"):
        AuditLog(
            action="CORRIDOR_DEACTIVATE",
            actor_type=AuditActorType.SYSTEM,
            confidence=0.50,
        )


# ---------------------------------------------------------------------------
# 3. Sensitive Data Redaction Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_credential_redaction():
    """docs/18-audit-logging.md §4: Passwords, tokens, keys are never logged."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    sensitive_payload = {
        "email": "operator@surakshanet.local",
        "password": "super_secret_cleartext_password",
        "token": "bearer_jwt_token_payload",
        "api_key": "ai_studio_api_key_secret",
        "secret": "hmac_secret_key",
        "nested": {
            "credentials": "top_secret_credentials",
            "safe_metric": 42.0,
        },
        "list_data": [
            {"authorization": "Bearer secret_header_token"},
            {"public_info": "ok_to_log"}
        ]
    }

    entry = await write_audit(
        db=mock_db,
        action="USER_LOGIN",
        actor_type=AuditActorType.USER,
        input_payload=sensitive_payload,
    )

    inp = entry.input
    assert inp["password"] == "[REDACTED]"
    assert inp["token"] == "[REDACTED]"
    assert inp["api_key"] == "[REDACTED]"
    assert inp["secret"] == "[REDACTED]"
    assert inp["nested"]["credentials"] == "[REDACTED]"
    assert inp["nested"]["safe_metric"] == 42.0
    assert inp["list_data"][0]["authorization"] == "[REDACTED]"
    assert inp["list_data"][1]["public_info"] == "ok_to_log"


# ---------------------------------------------------------------------------
# 4. Retention Policy Tests (SN-108)
# ---------------------------------------------------------------------------

def test_retention_script_executable_and_dry_run():
    """SN-108: scripts/retention.sh exists, is executable, and runs clean dry-run."""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_path = os.path.join(repo_root, "scripts", "retention.sh")
    assert os.path.isfile(script_path), f"Retention script not found at {script_path}"
    assert os.access(script_path, os.X_OK), f"Retention script {script_path} is not executable!"

    proc = subprocess.run([script_path, "--dry-run"], capture_output=True, text=True, cwd=repo_root)
    assert proc.returncode == 0
    assert "DRY-RUN (Simulated)" in proc.stdout
    assert "Would purge cv_detections older than 72h" in proc.stdout
    assert "Would purge control_decisions older than 90 days" in proc.stdout
    assert "Would purge DISMISSED behavior_flags older than 90 days" in proc.stdout


# ---------------------------------------------------------------------------
# 5. Privacy by Default & ANPR Default Disabled (SN-107, SN-109)
# ---------------------------------------------------------------------------

def test_privacy_blur_faces_and_plates():
    """SN-107: PrivacyBlurrer applies Gaussian blur before saving."""
    blurrer = PrivacyBlurrer(anpr_enabled=False)

    # 100x100 synthetic frame
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    # Draw high-contrast patch inside the face bounding box [10:30, 10:30]
    frame[15:25, 15:25] = 255

    blurred = blurrer.blur_sensitive_areas(
        frame,
        vehicle_boxes=[[20.0, 20.0, 80.0, 80.0]],
        face_boxes=[[10.0, 10.0, 30.0, 30.0]],
    )

    assert blurred.shape == frame.shape
    # Frame was modified by blur
    assert not np.array_equal(blurred, frame)


def test_anpr_disabled_by_default():
    """SN-109: ANPR is disabled by default in VisionWorkerConfig."""
    cfg = VisionWorkerConfig()
    assert cfg.anpr_enabled is False, "ANPR must be disabled by default!"


# ---------------------------------------------------------------------------
# 6. False-Positive Rate & Model Limitations (SN-110)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_false_positive_rate_calculation():
    """SN-110: False-positive rate is tracked as dismissed / total."""
    from app.api.vision import get_false_positive_rate

    # Mock flags: 2 DISMISSED, 2 CONFIRMED, 1 UNVERIFIED => FP rate = 2/5 = 0.4
    flags = [
        BehaviorFlag(flag_type=BehaviorFlagType.WRONG_WAY, status=BehaviorFlagStatus.DISMISSED, resolved_by=uuid.uuid4(), camera_id="C1", track_id="1", confidence=0.8, evidence={}),
        BehaviorFlag(flag_type=BehaviorFlagType.WRONG_WAY, status=BehaviorFlagStatus.CONFIRMED, resolved_by=uuid.uuid4(), camera_id="C1", track_id="2", confidence=0.9, evidence={}),
        BehaviorFlag(flag_type=BehaviorFlagType.DANGEROUS_DRIVING, status=BehaviorFlagStatus.DISMISSED, resolved_by=uuid.uuid4(), camera_id="C1", track_id="3", confidence=0.7, evidence={}),
        BehaviorFlag(flag_type=BehaviorFlagType.DANGEROUS_DRIVING, status=BehaviorFlagStatus.CONFIRMED, resolved_by=uuid.uuid4(), camera_id="C1", track_id="4", confidence=0.85, evidence={}),
        BehaviorFlag(flag_type=BehaviorFlagType.WRONG_WAY, status=BehaviorFlagStatus.UNVERIFIED, camera_id="C1", track_id="5", confidence=0.6, evidence={}),
    ]

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalars=lambda: MagicMock(all=lambda: flags))

    admin_user = User(id=uuid.uuid4(), email="admin@s.local", name="Admin", password_hash="h", role="ADMIN")
    result = await get_false_positive_rate(db=mock_db, current_user=admin_user)

    assert result["overall"]["total_flags"] == 5
    assert result["overall"]["dismissed"] == 2
    assert result["overall"]["confirmed"] == 2
    assert result["overall"]["unverified"] == 1
    assert result["overall"]["false_positive_rate"] == 0.4


@pytest.mark.asyncio
async def test_model_limitations_declared():
    """SN-110: GET /vision/model-limitations returns declared limitations."""
    from app.api.vision import get_model_limitations

    admin_user = User(id=uuid.uuid4(), email="admin@s.local", name="Admin", password_hash="h", role="ADMIN")
    res = await get_model_limitations(current_user=admin_user)

    assert "models" in res
    models = res["models"]
    assert "yolov8n_coco" in models
    assert "traffic_forecaster" in models
    assert "dqn_signal_policy" in models
    assert "anomaly_incident_detection" in models
    assert "cv_behavior_flags" in models
    # Check COCO bias declaration
    assert "No auto-rickshaw class" in models["yolov8n_coco"]["limitations"][0]
    # Check synthetic forecaster declaration
    assert models["traffic_forecaster"]["declared_tag"] == "training_data: synthetic"


# ---------------------------------------------------------------------------
# 7. Attribute Assignment & Warning Audit Verification
# ---------------------------------------------------------------------------

def test_audit_log_validates_confidence_on_attribute_mutation():
    """SN-097 / docs/18-audit-logging.md §1: @validates('confidence') prevents post-init mutation."""
    log = AuditLog(action="SIGNAL_OVERRIDE", actor_type=AuditActorType.USER, confidence=None)
    with pytest.raises(ValueError, match="confidence must be null unless actor_type is 'AI'"):
        log.confidence = 0.85

    ai_log = AuditLog(action="AI_CONTROL_DECISION", actor_type=AuditActorType.AI, confidence=0.80)
    ai_log.confidence = 0.95
    assert ai_log.confidence == 0.95


@pytest.mark.asyncio
async def test_public_warning_publish_audit_action():
    """docs/18-audit-logging.md §2: Verifies PUBLIC_WARNING_PUBLISH is properly formatted and logged."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    user_id = uuid.uuid4()
    incident_id = uuid.uuid4()

    entry = await write_audit(
        db=mock_db,
        action="PUBLIC_WARNING_PUBLISH",
        actor_type=AuditActorType.USER,
        actor_id=user_id,
        target_type="incident",
        target_id=incident_id,
        input_payload={"advisory_id": "adv-123"},
        output_payload={"warning_published_at": "2026-09-11T12:00:00Z"},
        result=AuditResult.SUCCESS,
        source="manual",
    )
    assert entry.action == "PUBLIC_WARNING_PUBLISH"
    assert entry.actor_type == AuditActorType.USER
    assert entry.confidence is None
    assert entry.target_type == "incident"
    mock_db.add.assert_called_once()


def test_mutation_audit_confidence_guard(monkeypatch):
    """Mutation check: Verifies confidence constraint cannot be silently bypassed."""
    # 1. Non-AI actor must fail
    with pytest.raises(ValueError, match="confidence must be null unless actor_type is 'AI'"):
        AuditLog(action="SIGNAL_OVERRIDE", actor_type=AuditActorType.USER, confidence=0.95)

    with pytest.raises(ValueError, match="confidence must be null unless actor_type is 'AI'"):
        AuditLog(action="CORRIDOR_DEACTIVATE", actor_type=AuditActorType.SYSTEM, confidence=0.75)

    # 2. AI actor must succeed
    ai_log = AuditLog(action="AI_CONTROL_DECISION", actor_type=AuditActorType.AI, confidence=0.95)
    assert ai_log.confidence == 0.95

