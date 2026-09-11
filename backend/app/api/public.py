import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.advisory import CitizenAdvisory

logger = logging.getLogger("surakshanet.api.public")
router = APIRouter(prefix="/public", tags=["Public"])


async def check_public_rate_limit(request: Request, limit: int = 60, window_s: int = 60) -> None:
    """
    IP rate limiter for public unauthenticated endpoints (60 req/min).
    Reuses Redis rate limiting; fails open if Redis is unreachable.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    # Honor reverse-proxy headers if present
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    try:
        from app.services.auth_service import get_redis_client
        redis = get_redis_client()
        key = f"rate_limit:public:{client_ip}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_s)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait a minute before retrying.",
            )
    except HTTPException:
        raise
    except Exception:
        # Fail open on Redis connectivity issue — do not block citizen access
        pass


def serialize_public_advisory(advisory: CitizenAdvisory) -> Dict[str, Any]:
    """
    Serializes CitizenAdvisory for public commuter view.
    CRITICAL INVARIANT (SN-113, docs/12-citizen-advisory.md §7):
    MUST EXPOSE: headline, corridor_text, window, delay range, cause, recommended route, leave_before, published_at.
    MUST NEVER EXPOSE: junction UUIDs, SUMO edge IDs, model names, confidence, operator identities, published_by, provenance fields.
    """
    rec_text = advisory.recommended_route_text
    leave_before_str = advisory.recommended_departure_before.isoformat() if advisory.recommended_departure_before else None
    pub_at_str = advisory.published_at.isoformat() if advisory.published_at else datetime.now(timezone.utc).isoformat()

    return {
        "id": str(advisory.id),
        "severity": advisory.severity.value if hasattr(advisory.severity, "value") else str(advisory.severity),
        "headline": advisory.headline,
        "corridor": advisory.corridor_text,
        "window": {
            "start": advisory.window_start.isoformat(),
            "end": advisory.window_end.isoformat(),
        },
        "expected_delay_min": {
            "low": advisory.delay_min_low,
            "high": advisory.delay_min_high,
        },
        "cause": advisory.cause_text,
        "recommended": rec_text,
        "leave_before": leave_before_str,
        "published_at": pub_at_str,
    }


@router.get("/advisories")
async def get_public_advisories(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Public unauthenticated endpoint returning active citizen traffic advisories.
    Rate-limited per IP; excludes all internal UUIDs, models, and operator identities.
    """
    await check_public_rate_limit(request)

    now = datetime.now(timezone.utc)
    stmt = (
        select(CitizenAdvisory)
        .where(CitizenAdvisory.expires_at > now)
        .order_by(desc(CitizenAdvisory.published_at))
    )
    result = await db.execute(stmt)
    advisories = result.scalars().all()

    serialized = [serialize_public_advisory(a) for a in advisories]
    return {
        "advisories": serialized,
        "generated_at": now.isoformat(),
    }


@router.get("/advisories/{advisory_id}")
async def get_public_advisory_by_id(
    advisory_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public detail for a single active citizen advisory."""
    await check_public_rate_limit(request)

    now = datetime.now(timezone.utc)
    stmt = select(CitizenAdvisory).where(
        CitizenAdvisory.id == advisory_id,
        CitizenAdvisory.expires_at > now,
    )
    result = await db.execute(stmt)
    advisory = result.scalar_one_or_none()
    if not advisory:
        raise HTTPException(status_code=404, detail="Advisory not found or expired")

    return serialize_public_advisory(advisory)


@router.get("/status")
async def get_public_network_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Plain-language corridor condition summary.
    Returns 'normal' when nothing active. Never fabricates a busy status.
    """
    await check_public_rate_limit(request)

    now = datetime.now(timezone.utc)
    stmt = select(CitizenAdvisory).where(CitizenAdvisory.expires_at > now)
    result = await db.execute(stmt)
    active = result.scalars().all()

    if not active:
        return {
            "status": "normal",
            "active_count": 0,
            "summary": "All major corridors are operating under normal conditions.",
            "advisories": [],
            "generated_at": now.isoformat(),
        }

    return {
        "status": "advisories_active",
        "active_count": len(active),
        "summary": f"{len(active)} active traffic advisories in effect across city corridors.",
        "advisories": [serialize_public_advisory(a) for a in active],
        "generated_at": now.isoformat(),
    }
