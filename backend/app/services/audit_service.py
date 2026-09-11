import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog, AuditActorType, AuditResult


async def write_audit(
    db: AsyncSession,
    action: str,
    actor_type: AuditActorType = AuditActorType.USER,
    actor_id: Optional[uuid.UUID] = None,
    target_type: Optional[str] = None,
    target_id: Optional[uuid.UUID] = None,
    input_payload: Optional[Dict[str, Any]] = None,
    output_payload: Optional[Dict[str, Any]] = None,
    result: AuditResult = AuditResult.SUCCESS,
    source: str = "manual",
    correlation_id: Optional[str] = None,
) -> AuditLog:
    """Persist an audit log entry for governance and traceability."""
    audit_entry = AuditLog(
        id=uuid.uuid4(),
        timestamp=datetime.utcnow(),
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        input=input_payload,
        output=output_payload,
        result=result,
        source=source,
        correlation_id=correlation_id,
    )
    db.add(audit_entry)
    await db.flush()
    return audit_entry
