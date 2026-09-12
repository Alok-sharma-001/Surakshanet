import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog, AuditActorType, AuditResult

logger = logging.getLogger("surakshanet.audit")

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "api_key",
    "credentials",
    "jwt",
    "client_secret",
}


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redacts sensitive credentials, tokens, and secrets from audit payloads."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_sensitive_data(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        if data.strip().lower().startswith("bearer "):
            return "Bearer [REDACTED]"
        return data
    return data


async def write_audit(
    db: AsyncSession,
    action: str,
    actor_type: Union[AuditActorType, str] = AuditActorType.USER,
    actor_id: Optional[Union[uuid.UUID, str]] = None,
    target_type: Optional[str] = None,
    target_id: Optional[Union[uuid.UUID, str]] = None,
    input_data: Optional[Dict[str, Any]] = None,
    input_payload: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    output_payload: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    model_version: Optional[str] = None,
    confidence: Optional[float] = None,
    result: Union[AuditResult, str] = AuditResult.SUCCESS,
    source: str = "manual",
    correlation_id: Optional[str] = None,
) -> Optional[AuditLog]:
    """Persist an audit log entry for governance and traceability (SN-103).

    Invariants:
    - actor_type, action, result are mandatory.
    - confidence is non-null ONLY when actor_type == 'AI'.
    - sensitive parameters (password, token, etc.) are strictly redacted from input/output.
    - correlation_id is stamped from correlation middleware or newly generated.
    """
    if not action:
        raise ValueError("Audit 'action' is required.")

    # Normalize actor_type
    if isinstance(actor_type, str):
        try:
            actor_type = AuditActorType(actor_type.upper())
        except ValueError:
            raise ValueError(f"Invalid actor_type '{actor_type}'. Must be USER, SYSTEM, or AI.")

    # Normalize result
    if isinstance(result, str):
        try:
            result = AuditResult(result.upper())
        except ValueError:
            raise ValueError(f"Invalid result '{result}'. Must be SUCCESS, FAILURE, or DENIED.")

    # Enforce confidence constraint
    if confidence is not None:
        if actor_type != AuditActorType.AI:
            raise ValueError("Confidence can only be non-null when actor_type is 'AI'.")
        try:
            confidence = float(confidence)
        except (ValueError, TypeError):
            raise ValueError("Confidence must be a valid float value.")

    # Normalize UUIDs
    parsed_actor_id = None
    if actor_id:
        try:
            parsed_actor_id = uuid.UUID(str(actor_id))
        except ValueError:
            parsed_actor_id = None

    parsed_target_id = None
    if target_id:
        try:
            parsed_target_id = uuid.UUID(str(target_id))
        except ValueError:
            parsed_target_id = None

    raw_input = input_data if input_data is not None else input_payload
    raw_output = output_data if output_data is not None else output_payload

    cleaned_input = redact_sensitive_data(raw_input) if raw_input is not None else None
    cleaned_output = redact_sensitive_data(raw_output) if raw_output is not None else None

    # Correlation ID default
    corr_id = correlation_id or str(uuid.uuid4())

    try:
        audit_entry = AuditLog(
            id=uuid.uuid4(),
            # Naive UTC, matching AuditLog.timestamp's DateTime (no timezone)
            # column — asyncpg rejects a tz-aware value against a naive
            # column (the same defect class documented in CLAUDE.md §13
            # edge case 10, now its fourth occurrence in this project).
            timestamp=datetime.utcnow(),
            actor_type=actor_type,
            actor_id=parsed_actor_id,
            action=action,
            target_type=target_type,
            target_id=parsed_target_id,
            input=cleaned_input,
            output=cleaned_output,
            model=model,
            model_version=model_version,
            confidence=confidence,
            result=result,
            source=source,
            correlation_id=corr_id,
        )
        db.add(audit_entry)
        await db.flush()
        return audit_entry
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"[Audit] Failed to write audit record for action '{action}': {e}", exc_info=True)
        return None
