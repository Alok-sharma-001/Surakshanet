import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
import datetime

# Mocking SQLAlchemy Models since they are not fully defined in context
class AlertModel:
    id = "id"
    junction_id = "junction_id"
    type = "type"
    severity = "severity"
    message = "message"
    acknowledged = "acknowledged"
    created_at = "created_at"
    
class AlertResponse(BaseModel):
    id: str
    junction_id: str
    type: str
    severity: str
    message: str
    acknowledged: bool
    created_at: datetime.datetime

class AlertEngine:
    """Service for evaluating conditions and generating alerts."""
    
    def __init__(self):
        # Mock thresholds
        self.thresholds = {
            "congestion": {"density": 0.8, "speed": 15.0},
            "spillback": {"risk": 0.85},
            "signal_timeout": 10.0
        }
        
    async def evaluate_junction(self, db: AsyncSession, junction_id: str, state: Dict[str, Any]) -> List[AlertResponse]:
        """Evaluate junction state and create alerts if necessary."""
        new_alerts = []
        now = datetime.datetime.utcnow()
        
        # 1. CONGESTION Check
        densities = state.get("densities", [])
        speeds = state.get("speeds", [])
        
        is_congested = False
        for d, s in zip(densities, speeds):
            if d > self.thresholds["congestion"]["density"] and s < self.thresholds["congestion"]["speed"]:
                is_congested = True
                break
                
        if is_congested:
            new_alerts.append(self._create_alert(junction_id, "CONGESTION", "HIGH", "High congestion detected."))
            
        # 2. SPILLBACK Check
        spillback_risk = state.get("spillback_risk", 0.0)
        if spillback_risk > self.thresholds["spillback"]["risk"]:
            new_alerts.append(self._create_alert(junction_id, "SPILLBACK", "CRITICAL", "High spillback risk detected."))
            
        # 3. QUEUE OVERFLOW Check
        queue_length = state.get("queue_length", 0)
        storage_capacity = state.get("road_storage_capacity", float('inf'))
        if queue_length > storage_capacity:
            new_alerts.append(self._create_alert(junction_id, "QUEUE_OVERFLOW", "HIGH", "Queue overflow detected."))
            
        # 4. SIGNAL FAILURE Check
        last_update = state.get("last_update_time", time.time())
        if time.time() - last_update > self.thresholds["signal_timeout"]:
            new_alerts.append(self._create_alert(junction_id, "SIGNAL_FAILURE", "CRITICAL", "No state update received."))
            
        # Persist to DB (Mock logic for async DB insert)
        # for a in new_alerts:
        #    db_alert = AlertORM(**a.dict())
        #    db.add(db_alert)
        # await db.commit()
        
        return new_alerts
        
    def _create_alert(self, junction_id: str, type: str, severity: str, message: str) -> AlertResponse:
        return AlertResponse(
            id=str(uuid.uuid4()),
            junction_id=junction_id,
            type=type,
            severity=severity,
            message=message,
            acknowledged=False,
            created_at=datetime.datetime.utcnow()
        )
        
    async def get_alerts(self, db: AsyncSession, junction_id: Optional[str] = None, alert_type: Optional[str] = None, 
                         severity: Optional[str] = None, acknowledged: Optional[bool] = None, limit: int = 50) -> List[AlertResponse]:
        """Query alerts with filters."""
        # Mock DB query logic
        # stmt = select(AlertModel)
        # if junction_id: stmt = stmt.where(AlertModel.junction_id == junction_id)
        # if alert_type: stmt = stmt.where(AlertModel.type == alert_type)
        # if severity: stmt = stmt.where(AlertModel.severity == severity)
        # if acknowledged is not None: stmt = stmt.where(AlertModel.acknowledged == acknowledged)
        # stmt = stmt.limit(limit)
        # result = await db.execute(stmt)
        # return result.scalars().all()
        return []
        
    async def acknowledge_alert(self, db: AsyncSession, alert_id: uuid.UUID) -> Optional[AlertResponse]:
        """Mark alert as acknowledged."""
        # Mock update logic
        # stmt = update(AlertModel).where(AlertModel.id == alert_id).values(acknowledged=True)
        # await db.execute(stmt)
        # await db.commit()
        return None
        
    async def get_alert_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Return counts by type and severity."""
        # Mock stat aggregation
        # counts = await db.execute(select(AlertModel.type, func.count()).group_by(AlertModel.type))
        return {
            "by_type": {"CONGESTION": 0, "SPILLBACK": 0},
            "by_severity": {"CRITICAL": 0, "HIGH": 0, "LOW": 0}
        }
