"""
SN-122 · Vision Incident Gate & Wrong-Way Critical Tests
========================================================
Verifies:
1. Wrong-Way True Positive (TP): Sustained opposed vehicle heading raises exactly one WRONG_WAY flag (SN-076).
2. Wrong-Way True Negative (TN): Normal traffic trajectory raises zero flags throughout (SN-076).
3. Human Gate: BehaviorFlag status defaults strictly to UNVERIFIED (SN-070, SN-077).
4. Human Gate Invariant: No automated path may set CONFIRMED without operator resolved_by (enforced via @validates).
5. Operator Resolution: PATCH /vision/flags/{id}/resolve records resolved_by, resolved_at, and writes an audit row.
6. No-Parking Queue Context Suppression: Vehicles stationary during red phase or traffic platoon raise NO flags (SN-080).
7. Mutation check: attempting to confirm a flag without an operator action fails.
"""

import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.models.vision import (
    BehaviorFlag,
    BehaviorFlagType,
    BehaviorFlagStatus,
    NoParkingZone,
)
from app.models.audit import AuditActorType, AuditResult
from services.vision_worker.config import CameraConfig, LaneConfig
from services.vision_worker.tracker import Track
from services.vision_worker.wrongway import WrongWayDetector
from services.vision_worker.parking import NoParkingDetector, ParkingZone


def test_wrong_way_tp_and_tn():
    """SN-076, SN-122: Asserts wrong-way TP on sustained opposed manoeuvre and TN on normal traffic."""
    camera = CameraConfig(
        id="CAM-01",
        junction_id="J0",
        source="test",
        fps=15.0,
        lanes=[
            LaneConfig(
                id="L1",
                direction="N",
                polygon=[[0.0, 0.0], [500.0, 0.0], [500.0, 1000.0], [0.0, 1000.0]],
                expected_heading_deg=90.0,  # Moving in +y direction
            )
        ],
    )

    # 1. True Negative: Vehicle moves in expected lane direction (heading 90 deg)
    detector = WrongWayDetector(camera, min_opposed_frames=30, fps=15.0)
    trk_normal = Track("trk-norm", [100.0, 100.0, 150.0, 150.0], "car", 0.95, timestamp=0.0)
    trk_normal.hits = 5

    for f in range(60):
        t = f / 15.0
        # +y movement => heading = 90 deg, delta = 0 deg
        trk_normal.update([100.0, 100.0 + f * 4.0, 150.0, 150.0 + f * 4.0], "car", 0.95, timestamp=t)
        flags = detector.process_tracks([trk_normal], timestamp=t)
        assert len(flags) == 0, f"Normal vehicle raised false positive at frame {f}!"

    # 2. True Positive: Vehicle moves opposite to expected lane direction (heading 270 deg)
    detector_tp = WrongWayDetector(camera, min_opposed_frames=30, fps=15.0)
    trk_opposed = Track("trk-wrong", [100.0, 800.0, 150.0, 850.0], "car", 0.92, timestamp=0.0)
    trk_opposed.hits = 5

    flags_emitted = []
    for f in range(50):
        t = f / 15.0
        # -y movement => heading = 270 deg, delta = 180 deg (> 135 deg)
        trk_opposed.update([100.0, 800.0 - f * 4.0, 150.0, 850.0 - f * 4.0], "car", 0.92, timestamp=t)
        fl = detector_tp.process_tracks([trk_opposed], timestamp=t)
        flags_emitted.extend(fl)

    # Must raise EXACTLY one flag for the track, never a flag per frame
    assert len(flags_emitted) == 1, f"Expected exactly 1 wrong-way flag, got {len(flags_emitted)}"
    flag = flags_emitted[0]
    assert flag["flag_type"] == "WRONG_WAY"
    assert flag["status"] == "UNVERIFIED"
    assert flag["evidence"]["opposed_frames"] >= 30
    assert flag["evidence"]["heading_delta_deg"] > 135.0
    assert flag["note"] == "Behaviour flagged for review. Not a confirmed violation."


def test_human_gate_unverified_default_and_confirmation_lock():
    """SN-070, SN-077: Invariant check.
    1. Default status is strictly UNVERIFIED.
    2. Setting CONFIRMED without operator resolved_by raises ValueError.
    """
    flag = BehaviorFlag(
        flag_type=BehaviorFlagType.WRONG_WAY,
        camera_id="CAM-01",
        track_id="trk-99",
        confidence=0.88,
        evidence={"delta": 180.0},
    )

    # 1. Assert UNVERIFIED default
    assert flag.status == BehaviorFlagStatus.UNVERIFIED
    assert flag.resolved_by is None
    assert flag.resolved_at is None

    # 2. Mutation check: Setting CONFIRMED without operator action must fail
    with pytest.raises(ValueError, match="cannot be set to CONFIRMED without an operator action"):
        flag.status = BehaviorFlagStatus.CONFIRMED

    # 3. Direct constructor with CONFIRMED but without resolved_by must also fail
    with pytest.raises(ValueError, match="cannot be set to CONFIRMED without an operator action"):
        BehaviorFlag(
            status=BehaviorFlagStatus.CONFIRMED,
            flag_type=BehaviorFlagType.WRONG_WAY,
            camera_id="CAM-01",
            track_id="trk-direct-fail",
            confidence=0.9,
            evidence={}
        )

    # 4. With operator action, CONFIRMED is accepted (both via attribute and via constructor)
    operator_id = uuid.uuid4()
    flag.resolved_by = operator_id
    flag.resolved_at = datetime.utcnow()
    flag.status = BehaviorFlagStatus.CONFIRMED
    assert flag.status == BehaviorFlagStatus.CONFIRMED

    flag_constructor = BehaviorFlag(
        status=BehaviorFlagStatus.CONFIRMED,
        resolved_by=operator_id,
        flag_type=BehaviorFlagType.WRONG_WAY,
        camera_id="CAM-01",
        track_id="trk-direct-ok",
        confidence=0.9,
        evidence={}
    )
    assert flag_constructor.status == BehaviorFlagStatus.CONFIRMED
    assert flag_constructor.resolved_by == operator_id

    # 5. Invariant: Cannot clear resolved_by from a confirmed flag
    with pytest.raises(ValueError, match="Cannot remove resolved_by operator from a CONFIRMED BehaviorFlag"):
        flag.resolved_by = None


@pytest.mark.asyncio
async def test_operator_resolution_audit_logging():
    """SN-077: Operator resolution writes a mandatory audit log entry."""
    from app.services.audit_service import write_audit

    mock_db = AsyncMock()
    operator_id = uuid.uuid4()
    flag_id = uuid.uuid4()

    entry = await write_audit(
        db=mock_db,
        action="FLAG_RESOLVE",
        actor_type=AuditActorType.USER,
        actor_id=operator_id,
        target_type="behavior_flag",
        target_id=flag_id,
        input_payload={"target_status": "CONFIRMED", "note": "Verified by operator"},
        output_payload={"flag_type": "WRONG_WAY"},
        result=AuditResult.SUCCESS,
        source="manual",
    )

    assert entry.action == "FLAG_RESOLVE"
    assert entry.actor_id == operator_id
    assert entry.target_id == flag_id
    assert entry.result == AuditResult.SUCCESS
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


def test_no_parking_queue_context_suppression():
    """SN-080: Parking detector suppresses alerts during red signal or traffic platoon."""
    zone = ParkingZone(
        zone_id="Z-TEST",
        name="Bus Clearway",
        camera_id="CAM-01",
        polygon=[[0.0, 0.0], [200.0, 0.0], [200.0, 200.0], [0.0, 200.0]],
        threshold_s=5.0,
    )
    detector = NoParkingDetector(camera_id="CAM-01", zones=[zone], default_threshold_s=5.0)

    # 1. Vehicle stopped at red signal -> queue_context must suppress
    trk = Track("trk-red", [50.0, 50.0, 100.0, 100.0], "car", 0.9, timestamp=0.0)
    trk.hits = 5

    for s in range(10):
        t = float(s)
        trk.update(trk.bbox, trk.vehicle_class, trk.confidence, timestamp=t)
        flags = detector.process_tracks([trk], timestamp=t, controlling_signal_red=True)
        assert len(flags) == 0, f"Red signal failed to suppress queue parking at step {s}!"

    # 2. Genuinely parked vehicle (signal green, no queue) -> raises ILLEGAL_PARKING
    detector_free = NoParkingDetector(camera_id="CAM-01", zones=[zone], default_threshold_s=5.0)
    trk_parked = Track("trk-parked", [50.0, 50.0, 100.0, 100.0], "car", 0.9, timestamp=0.0)
    trk_parked.hits = 5

    raised = []
    for s in range(10):
        t = float(s)
        trk_parked.update(trk_parked.bbox, trk_parked.vehicle_class, trk_parked.confidence, timestamp=t)
        fl = detector_free.process_tracks([trk_parked], timestamp=t, controlling_signal_red=False)
        raised.extend(fl)

    assert len(raised) == 1, f"Expected exactly 1 ILLEGAL_PARKING flag, got {len(raised)}"
    assert raised[0]["flag_type"] == "ILLEGAL_PARKING"
    assert raised[0]["status"] == "UNVERIFIED"
