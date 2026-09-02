from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

# Assuming schemas and models are defined elsewhere in the project
# For this file to be complete, I will import them hypothetically
# from ..models import Junction, TrafficSensor, TrafficReading
# from ..schemas import JunctionCreate, JunctionUpdate, SensorCreate, TrafficReadingQuery, TrafficReadingCreate

class Junction: pass
class TrafficSensor: pass
class TrafficReading: pass
class JunctionCreate: pass
class JunctionUpdate: pass
class SensorCreate: pass
class TrafficReadingQuery: pass
class TrafficReadingCreate: pass

async def get_junctions(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Junction]:
    result = await db.execute(select(Junction).offset(skip).limit(limit))
    return result.scalars().all()

async def get_junction(db: AsyncSession, junction_id: UUID) -> Optional[Junction]:
    result = await db.execute(select(Junction).where(Junction.id == junction_id))
    return result.scalar_one_or_none()

async def create_junction(db: AsyncSession, data: JunctionCreate) -> Junction:
    junction = Junction(**data.dict())
    db.add(junction)
    await db.commit()
    await db.refresh(junction)
    return junction

async def update_junction(db: AsyncSession, junction_id: UUID, data: JunctionUpdate) -> Optional[Junction]:
    junction = await get_junction(db, junction_id)
    if junction:
        for key, value in data.dict(exclude_unset=True).items():
            setattr(junction, key, value)
        await db.commit()
        await db.refresh(junction)
    return junction

async def get_sensors(db: AsyncSession, junction_id: Optional[UUID] = None) -> List[TrafficSensor]:
    query = select(TrafficSensor)
    if junction_id:
        query = query.where(TrafficSensor.junction_id == junction_id)
    result = await db.execute(query)
    return result.scalars().all()

async def create_sensor(db: AsyncSession, data: SensorCreate) -> TrafficSensor:
    sensor = TrafficSensor(**data.dict())
    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)
    return sensor

async def get_readings(db: AsyncSession, query_params: TrafficReadingQuery) -> List[TrafficReading]:
    # Placeholder implementation based on hypothetical query params
    query = select(TrafficReading)
    if hasattr(query_params, 'junction_id') and query_params.junction_id:
        query = query.where(TrafficReading.junction_id == query_params.junction_id)
    if hasattr(query_params, 'limit') and query_params.limit:
        query = query.limit(query_params.limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_latest_readings(db: AsyncSession, junction_id: UUID) -> List[TrafficReading]:
    query = select(TrafficReading).where(TrafficReading.junction_id == junction_id).order_by(desc(TrafficReading.timestamp)).limit(10)
    result = await db.execute(query)
    return result.scalars().all()

async def create_reading(db: AsyncSession, data: TrafficReadingCreate) -> TrafficReading:
    reading = TrafficReading(**data.dict())
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading
