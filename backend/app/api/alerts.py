import json
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db
from app.config import get_settings
from app.schemas.alert import AlertResponse
from app.services.alert_service import alert_service
from app.services.auth_service import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("/stats")
async def get_alert_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregated alert statistics from PostgreSQL."""
    return await alert_service.get_alert_stats(db)

@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    junction_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """List real alerts with query filters and pagination."""
    return await alert_service.get_alerts(
        db=db,
        junction_id=junction_id,
        alert_type=alert_type,
        severity=severity,
        acknowledged=acknowledged,
        limit=limit,
        offset=offset
    )

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Fetch a single alert by ID."""
    alert = await alert_service.get_alert_by_id(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@router.patch("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Mark an alert as acknowledged and publish event to Redis pub/sub."""
    alert = await alert_service.acknowledge_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Broadcast event to Redis for live WebSocket push
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        event = {
            "type": "ALERT_ACKNOWLEDGED",
            "alert_id": str(alert.id),
            "severity": alert.severity,
            "message": alert.message,
            "acknowledged": True
        }
        await redis.publish("alert_events", json.dumps(event))
        await redis.aclose()
    except Exception as e:
        logger.warning(f"Could not publish alert acknowledgement to Redis: {e}")

    return alert

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Delete an alert record."""
    deleted = await alert_service.delete_alert(db, alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "deleted", "alert_id": str(alert_id)}
