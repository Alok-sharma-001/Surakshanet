from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid

# Mock dependencies
async def get_db():
    yield None

class MockAuth:
    def __call__(self, required_role=None):
        return None

router = APIRouter(prefix="/alerts", tags=["alerts"])
alert_engine = None # Would be injected or imported
auth = MockAuth()

from app.services.alert_service import AlertEngine, AlertResponse
alert_service = AlertEngine()

@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    junction_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List alerts with query filters."""
    return await alert_service.get_alerts(db, junction_id, alert_type, severity, acknowledged, limit)

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single alert."""
    # Mock fetching single alert
    raise HTTPException(status_code=404, detail="Alert not found")

@router.patch("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(auth(required_role="operator"))
):
    """Acknowledge an alert."""
    alert = await alert_service.acknowledge_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@router.get("/stats")
async def get_alert_stats(db: AsyncSession = Depends(get_db)):
    """Get alert statistics."""
    return await alert_service.get_alert_stats(db)

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(auth(required_role="admin"))
):
    """Delete an alert."""
    # Mock delete logic
    return {"status": "deleted"}
