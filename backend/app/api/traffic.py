from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Any, List, Optional
import uuid
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models.junction import Junction, TrafficSensor
from app.models.traffic import TrafficReading
from app.schemas.traffic import (
    JunctionCreate, JunctionResponse, JunctionUpdate,
    SensorCreate, SensorResponse,
    TrafficReadingCreate, TrafficReadingResponse
)
from app.services.auth_service import get_current_user, require_role
from app.models.user import User

router = APIRouter(prefix="/traffic", tags=["traffic"])

@router.get("/junctions", response_model=List[JunctionResponse])
async def list_junctions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    result = await db.execute(select(Junction).offset(skip).limit(limit))
    return result.scalars().all()

@router.get("/junctions/{id}", response_model=JunctionResponse)
async def get_junction(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    result = await db.execute(select(Junction).where(Junction.id == id))
    junction = result.scalar_one_or_none()
    if not junction:
        raise HTTPException(status_code=404, detail="Junction not found")
    return junction

@router.post("/junctions", response_model=JunctionResponse, status_code=status.HTTP_201_CREATED)
async def create_junction(
    junction_in: JunctionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
) -> Any:
    junction = Junction(**junction_in.model_dump())
    db.add(junction)
    await db.commit()
    await db.refresh(junction)
    return junction

@router.patch("/junctions/{id}", response_model=JunctionResponse)
async def update_junction(
    id: UUID,
    junction_in: JunctionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
) -> Any:
    result = await db.execute(select(Junction).where(Junction.id == id))
    junction = result.scalar_one_or_none()
    if not junction:
        raise HTTPException(status_code=404, detail="Junction not found")
    
    update_data = junction_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(junction, field, value)
        
    db.add(junction)
    await db.commit()
    await db.refresh(junction)
    return junction

@router.get("/sensors", response_model=List[SensorResponse])
async def list_sensors(
    junction_id: Optional[UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    query = select(TrafficSensor)
    if junction_id:
        query = query.where(TrafficSensor.junction_id == junction_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/sensors", response_model=SensorResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor(
    sensor_in: SensorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
) -> Any:
    raw_type = (sensor_in.sensor_type or sensor_in.type or "CAMERA").upper()
    valid_types = ["CAMERA", "INDUCTION", "ACOUSTIC", "GPS"]
    sensor_type = raw_type if raw_type in valid_types else "CAMERA"
    
    raw_dir = (sensor_in.approach_direction or "N").upper()
    valid_dirs = ["N", "E", "S", "W"]
    approach_direction = raw_dir if raw_dir in valid_dirs else "N"

    sensor = TrafficSensor(
        junction_id=sensor_in.junction_id,
        sensor_type=sensor_type,
        approach_direction=approach_direction,
        is_active=True
    )
    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)
    
    st_val = sensor.sensor_type.value if hasattr(sensor.sensor_type, 'value') else str(sensor.sensor_type)
    ad_val = sensor.approach_direction.value if hasattr(sensor.approach_direction, 'value') else str(sensor.approach_direction)
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

@router.get("/readings", response_model=List[TrafficReadingResponse])
async def list_readings(
    junction_id: Optional[UUID] = None,
    sensor_id: Optional[UUID] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    query = select(TrafficReading)
    if junction_id:
        query = query.where(TrafficReading.junction_id == junction_id)
    if sensor_id:
        query = query.where(TrafficReading.sensor_id == sensor_id)
    if start_time:
        query = query.where(TrafficReading.timestamp >= start_time)
    if end_time:
        query = query.where(TrafficReading.timestamp <= end_time)
        
    query = query.order_by(desc(TrafficReading.timestamp)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/readings/{junction_id}", response_model=List[TrafficReadingResponse])
async def get_latest_readings(
    junction_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    query = select(TrafficReading).where(
        TrafficReading.junction_id == junction_id
    ).order_by(desc(TrafficReading.timestamp)).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/readings", response_model=TrafficReadingResponse, status_code=status.HTTP_201_CREATED)
async def create_reading(
    reading_in: TrafficReadingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) 
) -> Any:
    j_id = reading_in.junction_id
    if not j_id:
        res = await db.execute(select(TrafficSensor).where(TrafficSensor.id == reading_in.sensor_id))
        sensor = res.scalar_one_or_none()
        if sensor:
            j_id = sensor.junction_id
        else:
            j_id = uuid.uuid4()

    speed = reading_in.avg_speed if reading_in.avg_speed is not None else reading_in.average_speed
    pcu = reading_in.pcu_value if reading_in.pcu_value is not None else (reading_in.vehicle_count * 1.0)
    ts = reading_in.timestamp if reading_in.timestamp is not None else datetime.utcnow()
    if ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)

    reading = TrafficReading(
        sensor_id=reading_in.sensor_id,
        junction_id=j_id,
        vehicle_count=reading_in.vehicle_count,
        pcu_value=pcu,
        avg_speed=speed,
        queue_length=reading_in.queue_length or 0.0,
        vehicle_breakdown=reading_in.vehicle_breakdown or {},
        timestamp=ts
    )
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading
