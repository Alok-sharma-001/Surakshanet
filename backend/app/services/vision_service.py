"""Persists real-time vision-worker output that nothing else durably stores.

services/vision_worker/{wrongway,parking,behavior}.py compute WRONG_WAY,
ILLEGAL_PARKING, and DANGEROUS_DRIVING flags and publish them on
REDIS_CHANNELS["alerts"]; services/vision_worker/main.py publishes per-frame
detection boxes on REDIS_CHANNELS["cv_detections"]. Both publishes are for
live operator notification only — neither worker path writes to Postgres.
This module is the missing other half: it persists flags as real
BehaviorFlag rows (so GET /vision/flags and the human-gate resolve endpoint
have something real to operate on) and detections as real CVDetection rows
(so SN-078's "every box traces to a cv_detections row" is actually true),
instead of those tables sitting wired to endpoints that nothing ever writes
into.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger("surakshanet.services.vision")


async def persist_behavior_flag(payload: Dict[str, Any]) -> None:
    """Writes one vision-worker flag payload to the behavior_flags table.

    Silently ignores payloads without a recognized flag_type (e.g. a future,
    unrelated publisher on the same channel) rather than fabricating a type.
    """
    flag_type_raw = payload.get("flag_type")
    if not flag_type_raw:
        return

    from app.database import async_session_maker
    from app.models.vision import BehaviorFlag, BehaviorFlagType

    try:
        flag_type = BehaviorFlagType(flag_type_raw)
    except ValueError:
        logger.debug(f"Ignoring alert payload with unrecognized flag_type: {flag_type_raw!r}")
        return

    try:
        async with async_session_maker() as db:
            flag = BehaviorFlag(
                flag_type=flag_type,
                camera_id=str(payload.get("camera_id", "")),
                track_id=str(payload.get("track_id", "")),
                evidence=payload.get("evidence", {}),
                confidence=float(payload.get("confidence", 0.0)),
                note=payload.get("note", "Behaviour flagged for review. Not a confirmed violation."),
                source=payload.get("source", "vision"),
            )
            db.add(flag)
            await db.flush()

            # Audit AI behavior flag per SN-104 & SN-105
            try:
                from app.services.audit_service import write_audit
                from app.models.audit import AuditActorType, AuditResult
                await write_audit(
                    db=db,
                    action="AI_BEHAVIOR_FLAG",
                    actor_type=AuditActorType.AI,
                    actor_id=None,
                    target_type="behavior_flag",
                    target_id=flag.id,
                    input_payload={"camera_id": flag.camera_id, "track_id": flag.track_id},
                    output_payload={"flag_type": flag.flag_type.value, "evidence": flag.evidence},
                    model="vision_detector",
                    model_version="1.0.0",
                    confidence=float(flag.confidence),
                    result=AuditResult.SUCCESS,
                    source=flag.source or "vision",
                )
            except Exception as audit_err:
                logger.warning(f"Failed to log AI_BEHAVIOR_FLAG audit: {audit_err}")

            await db.commit()
    except Exception as e:
        logger.error(f"Failed to persist behavior flag ({flag_type_raw}): {e}")


async def persist_cv_detections(payload: Dict[str, Any]) -> None:
    """Writes one vision-worker detection-frame payload to cv_detections.

    One row per detected/tracked vehicle box in the frame. Payload boxes
    without the real vehicle_class/raw_bbox/pcu fields (older shape, or a
    payload from something other than main.py's _publish_detections_and_flags)
    are skipped rather than persisted with guessed values.
    """
    camera_id = payload.get("camera_id")
    boxes = payload.get("detections")
    if not camera_id or not boxes:
        return

    ts = datetime.utcfromtimestamp(payload["timestamp"]) if payload.get("timestamp") else datetime.utcnow()

    from app.database import async_session_maker
    from app.models.vision import CVDetection

    try:
        async with async_session_maker() as db:
            wrote_any = False
            for box in boxes:
                if "vehicle_class" not in box or "raw_bbox" not in box:
                    continue
                db.add(CVDetection(
                    id=uuid.uuid4(),
                    timestamp=ts,
                    camera_id=str(camera_id),
                    track_id=str(box.get("id")) if box.get("id") is not None else None,
                    vehicle_class=str(box["vehicle_class"]),
                    confidence=float(box.get("confidence", 0.0)) / 100.0,
                    bbox=box["raw_bbox"],
                    pcu=float(box.get("pcu", 0.0)),
                ))
                wrote_any = True
            if wrote_any:
                await db.commit()
    except Exception as e:
        logger.error(f"Failed to persist cv_detections for camera {camera_id}: {e}")
