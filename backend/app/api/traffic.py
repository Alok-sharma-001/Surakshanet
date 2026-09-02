from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Any, List, Optional
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

@router.post("/junctions", response_model=JunctionResponse)
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

@router.post("/sensors", response_model=SensorResponse)
async def create_sensor(
    sensor_in: SensorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
) -> Any:
    sensor = TrafficSensor(**sensor_in.model_dump())
    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)
    return sensor

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

@router.post("/readings", response_model=TrafficReadingResponse)
async def create_reading(
    reading_in: TrafficReadingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) 
) -> Any:
    reading = TrafficReading(**reading_in.model_dump())
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading
