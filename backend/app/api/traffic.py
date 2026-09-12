from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, List, Optional
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.schemas.traffic import (
    JunctionCreate, JunctionResponse, JunctionUpdate,
    SensorCreate, SensorResponse,
    TrafficReadingCreate, TrafficReadingResponse
)
from app.models.user import User

from app.services.auth_service import require_role
from app.services import traffic_service
from shared.constants import compute_pcu

router = APIRouter(prefix="/traffic", tags=["traffic"])


# ---------------------------------------------------------------------------
# Junctions - Spatial Queries (MUST be placed before /junctions/{id})
# ---------------------------------------------------------------------------


@router.get("/junctions/spatial/nearest", response_model=JunctionResponse)
async def get_nearest_junction(
    latitude: float = Query(..., description="Latitude coordinate", ge=-90.0, le=90.0),
    longitude: float = Query(..., description="Longitude coordinate", ge=-180.0, le=180.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    junction = await traffic_service.get_nearest_junction(db, latitude=latitude, longitude=longitude)
    if not junction:
        raise HTTPException(status_code=404, detail="No junction found")
    return junction


@router.get("/junctions/spatial/radius", response_model=List[JunctionResponse])
async def get_junctions_within_radius(
    latitude: float = Query(..., description="Center latitude", ge=-90.0, le=90.0),
    longitude: float = Query(..., description="Center longitude", ge=-180.0, le=180.0),
    radius_meters: float = Query(5000.0, ge=0.0, description="Radius in meters"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    return await traffic_service.get_junctions_within_radius(
        db, latitude=latitude, longitude=longitude, radius_meters=radius_meters
    )


@router.get("/junctions/spatial/bbox", response_model=List[JunctionResponse])
async def get_junctions_in_bbox(
    min_lat: float = Query(..., description="Minimum latitude"),
    min_lon: float = Query(..., description="Minimum longitude"),
    max_lat: float = Query(..., description="Maximum latitude"),
    max_lon: float = Query(..., description="Maximum longitude"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    return await traffic_service.get_junctions_in_bbox(
        db, min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon
    )


# ---------------------------------------------------------------------------
# Junctions CRUD
# ---------------------------------------------------------------------------

@router.get("/junctions", response_model=List[JunctionResponse])
async def list_junctions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    return await traffic_service.get_junctions(db, skip=skip, limit=limit)


@router.get("/junctions/{id}", response_model=JunctionResponse)
async def get_junction(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    junction = await traffic_service.get_junction(db, junction_id=id)
    if not junction:
        raise HTTPException(status_code=404, detail="Junction not found")
    return junction


@router.post("/junctions", response_model=JunctionResponse, status_code=status.HTTP_201_CREATED)
async def create_junction(
    junction_in: JunctionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
) -> Any:
    return await traffic_service.create_junction(db, data=junction_in)


@router.patch("/junctions/{id}", response_model=JunctionResponse)
async def update_junction(
    id: UUID,
    junction_in: JunctionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
) -> Any:
    junction = await traffic_service.update_junction(db, junction_id=id, data=junction_in)
    if not junction:
        raise HTTPException(status_code=404, detail="Junction not found")
    return junction


# ---------------------------------------------------------------------------
# Sensors CRUD
# ---------------------------------------------------------------------------

@router.get("/sensors", response_model=List[SensorResponse])
async def list_sensors(
    junction_id: Optional[UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    return await traffic_service.get_sensors(db, junction_id=junction_id, skip=skip, limit=limit)


@router.post("/sensors", response_model=SensorResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor(
    sensor_in: SensorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
) -> Any:
    sensor = await traffic_service.create_sensor(db, data=sensor_in)
    st_val = sensor.sensor_type.value if hasattr(sensor.sensor_type, "value") else str(sensor.sensor_type)
    ad_val = sensor.approach_direction.value if hasattr(sensor.approach_direction, "value") else str(sensor.approach_direction)
    return SensorResponse(
        id=sensor.id,
        junction_id=sensor.junction_id,
        sensor_type=st_val,
        approach_direction=ad_val,
        is_active=sensor.is_active,
        created_at=sensor.created_at,
        type=st_val.lower(),
        name=sensor_in.name or f"{st_val} Sensor"
    )


# ---------------------------------------------------------------------------
# Readings CRUD
# ---------------------------------------------------------------------------

@router.get("/readings", response_model=List[TrafficReadingResponse])
async def list_readings(
    junction_id: Optional[UUID] = None,
    sensor_id: Optional[UUID] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    return await traffic_service.get_readings(
        db,
        junction_id=junction_id,
        sensor_id=sensor_id,
        start_time=start_time,
        end_time=end_time,
        skip=skip,
        limit=limit
    )


@router.get("/readings/{junction_id}", response_model=List[TrafficReadingResponse])
async def get_latest_readings(
    junction_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    return await traffic_service.get_latest_readings(db, junction_id=junction_id, limit=limit)


@router.post("/readings", response_model=TrafficReadingResponse, status_code=status.HTTP_201_CREATED)
async def create_reading(
    reading_in: TrafficReadingCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
) -> Any:
    source = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            source = body.get("source")
    except Exception:
        pass
    try:
        return await traffic_service.create_reading(db, data=reading_in, source=source)
    except ValueError as e:
        # A reading that cannot be attributed to a junction, or that is missing
        # a NOT NULL field, is rejected rather than completed with defaults.
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/reading", response_model=TrafficReadingResponse, status_code=status.HTTP_201_CREATED)
async def create_reading_singular(
    reading_in: TrafficReadingCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
) -> Any:
    return await create_reading(reading_in, request, db, current_user)


@router.get("/history", response_model=List[TrafficReadingResponse])
async def get_traffic_history(
    junction_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    j_id = None
    if junction_id:
        try:
            j_id = UUID(junction_id)
        except Exception:
            j_id = None
    return await traffic_service.get_readings(
        db,
        junction_id=j_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )


@router.get("/latest", response_model=List[TrafficReadingResponse])
async def get_latest_traffic(
    junction_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    if junction_id:
        try:
            j_id = UUID(junction_id)
        except Exception:
            return []
        return await traffic_service.get_latest_readings(db, junction_id=j_id, limit=20)
    return await traffic_service.get_readings(db, limit=20)


@router.post("/pcu")
async def calculate_pcu(
    data: dict,
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    total_pcu = compute_pcu(data)
    return {"pcu": total_pcu, "total_pcu": total_pcu}
