import uuid
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, delete

from app.models.alert import Alert, AlertType, AlertSeverity
from app.schemas.alert import AlertResponse

class AlertEngine:
    """Service for managing and evaluating real system alerts backed by PostgreSQL."""

    def __init__(self):
        self.thresholds = {
            "congestion": {"density": 0.8, "speed": 15.0},
            "spillback": {"risk": 0.85},
            "signal_timeout": 10.0
        }

    async def get_alerts(
        self,
        db: AsyncSession,
        junction_id: Optional[str] = None,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AlertResponse]:
        """Query alerts from PostgreSQL with optional filters and pagination."""
        if db is None:
            return []

        query = select(Alert).order_by(desc(Alert.created_at))

        if junction_id:
            try:
                j_uuid = uuid.UUID(str(junction_id))
                query = query.where(Alert.junction_id == j_uuid)
            except ValueError:
                pass

        if alert_type:
            try:
                at_enum = AlertType[alert_type.upper()]
                query = query.where(Alert.alert_type == at_enum)
            except KeyError:
                pass

        if severity:
            try:
                sev_enum = AlertSeverity[severity.upper()]
                query = query.where(Alert.severity == sev_enum)
            except KeyError:
                pass

        if acknowledged is not None:
            query = query.where(Alert.is_acknowledged == acknowledged)

        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        alerts = result.scalars().all()

        responses = []
        for a in alerts:
            at_val = a.alert_type.value if hasattr(a.alert_type, 'value') else str(a.alert_type)
            sev_val = a.severity.value if hasattr(a.severity, 'value') else str(a.severity)
            responses.append(AlertResponse(
                id=a.id,
                junction_id=a.junction_id,
                alert_type=at_val,
                severity=sev_val,
                message=a.message,
                is_acknowledged=a.is_acknowledged,
                created_at=a.created_at,
                acknowledged_at=a.acknowledged_at
            ))
        return responses

    async def get_alert_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Return counts by type, severity, and status from PostgreSQL."""
        if db is None:
            return {
                "total": 0, "active": 0, "resolved": 0,
                "by_type": {}, "by_severity": {}
            }

        result = await db.execute(select(Alert))
        alerts = result.scalars().all()

        total = len(alerts)
        active = sum(1 for a in alerts if not a.is_acknowledged)
        resolved = total - active

        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}

        for a in alerts:
            t = a.alert_type.value if hasattr(a.alert_type, 'value') else str(a.alert_type)
            s = a.severity.value if hasattr(a.severity, 'value') else str(a.severity)
            by_type[t] = by_type.get(t, 0) + 1
            by_severity[s] = by_severity.get(s, 0) + 1

        return {
            "total": total,
            "active": active,
            "resolved": resolved,
            "by_type": by_type,
            "by_severity": by_severity
        }

    async def get_alert_by_id(self, db: AsyncSession, alert_id: uuid.UUID) -> Optional[AlertResponse]:
        """Fetch a single alert by UUID."""
        if db is None:
            return None
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        a = result.scalar_one_or_none()
        if not a:
            return None

        at_val = a.alert_type.value if hasattr(a.alert_type, 'value') else str(a.alert_type)
        sev_val = a.severity.value if hasattr(a.severity, 'value') else str(a.severity)
        return AlertResponse(
            id=a.id,
            junction_id=a.junction_id,
            alert_type=at_val,
            severity=sev_val,
            message=a.message,
            is_acknowledged=a.is_acknowledged,
            created_at=a.created_at,
            acknowledged_at=a.acknowledged_at
        )

    async def acknowledge_alert(self, db: AsyncSession, alert_id: uuid.UUID) -> Optional[AlertResponse]:
        """Mark alert as acknowledged in the database."""
        if db is None:
            return None
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        a = result.scalar_one_or_none()
        if not a:
            return None

        a.is_acknowledged = True
        a.acknowledged_at = datetime.datetime.utcnow()
        db.add(a)
        await db.commit()
        await db.refresh(a)

        at_val = a.alert_type.value if hasattr(a.alert_type, 'value') else str(a.alert_type)
        sev_val = a.severity.value if hasattr(a.severity, 'value') else str(a.severity)
        return AlertResponse(
            id=a.id,
            junction_id=a.junction_id,
            alert_type=at_val,
            severity=sev_val,
            message=a.message,
            is_acknowledged=a.is_acknowledged,
            created_at=a.created_at,
            acknowledged_at=a.acknowledged_at
        )

    async def delete_alert(self, db: AsyncSession, alert_id: uuid.UUID) -> bool:
        """Delete an alert record from the database."""
        if db is None:
            return False
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        a = result.scalar_one_or_none()
        if not a:
            return False
        await db.delete(a)
        await db.commit()
        return True

alert_service = AlertEngine()
