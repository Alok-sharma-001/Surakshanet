import uuid
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, or_, and_, cast
from geoalchemy2 import Geography

from app.models.junction import Junction, TrafficSensor
from app.models.traffic import TrafficReading
from app.schemas.traffic import (
    JunctionCreate,
    JunctionUpdate,
    SensorCreate,
    TrafficReadingCreate,
)
from shared.constants import DataSource, PCU_FACTORS


def _get_dialect_name(db: AsyncSession) -> str:
    try:
        if db.bind:
            return db.bind.dialect.name
    except Exception:
        pass
    return "postgresql"


async def get_junctions(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Junction]:
    result = await db.execute(select(Junction).offset(skip).limit(limit))
    return list(result.scalars().all())


async def get_junction(db: AsyncSession, junction_id: UUID) -> Optional[Junction]:
    result = await db.execute(select(Junction).where(Junction.id == junction_id))
    return result.scalar_one_or_none()


async def create_junction(db: AsyncSession, data: JunctionCreate) -> Junction:
    junction_dict = data.model_dump()
    junction = Junction(**junction_dict)
    db.add(junction)
    await db.commit()
    await db.refresh(junction)
    return junction


async def update_junction(db: AsyncSession, junction_id: UUID, data: JunctionUpdate) -> Optional[Junction]:
    junction = await get_junction(db, junction_id)
    if not junction:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(junction, key, value)
    db.add(junction)
    await db.commit()
    await db.refresh(junction)
    return junction


async def get_sensors(
    db: AsyncSession,
    junction_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TrafficSensor]:
    query = select(TrafficSensor)
    if junction_id:
        query = query.where(TrafficSensor.junction_id == junction_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_sensor(db: AsyncSession, data: SensorCreate) -> TrafficSensor:
    raw_type = (data.sensor_type or data.type or "CAMERA").upper()
    valid_types = ["CAMERA", "INDUCTION", "ACOUSTIC", "GPS"]
    sensor_type = raw_type if raw_type in valid_types else "CAMERA"

    raw_dir = (data.approach_direction or "N").upper()
    valid_dirs = ["N", "E", "S", "W"]
    approach_direction = raw_dir if raw_dir in valid_dirs else "N"

    sensor = TrafficSensor(
        junction_id=data.junction_id,
        sensor_type=sensor_type,
        approach_direction=approach_direction,
        is_active=True,
    )
    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)
    return sensor


async def get_readings(
    db: AsyncSession,
    junction_id: Optional[UUID] = None,
    sensor_id: Optional[UUID] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TrafficReading]:
    query = select(TrafficReading)
    if junction_id:
        query = query.where(TrafficReading.junction_id == junction_id)
    if sensor_id:
        query = query.where(TrafficReading.sensor_id == sensor_id)
    if start_time:
        if start_time.tzinfo is not None:
            start_time = start_time.replace(tzinfo=None)
        query = query.where(TrafficReading.timestamp >= start_time)
    if end_time:
        if end_time.tzinfo is not None:
            end_time = end_time.replace(tzinfo=None)
        query = query.where(TrafficReading.timestamp <= end_time)

    query = query.order_by(desc(TrafficReading.timestamp)).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_latest_readings(db: AsyncSession, junction_id: UUID, limit: int = 10) -> List[TrafficReading]:
    query = (
        select(TrafficReading)
        .where(TrafficReading.junction_id == junction_id)
        .order_by(desc(TrafficReading.timestamp))
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_reading(
    db: AsyncSession,
    data: TrafficReadingCreate,
    source: Optional[str] = None
) -> TrafficReading:
    reading_dict = data.model_dump()
    j_id = reading_dict.get("junction_id")
    if not j_id:
        res = await db.execute(select(TrafficSensor).where(TrafficSensor.id == data.sensor_id))
        sensor = res.scalar_one_or_none()
        if sensor:
            j_id = sensor.junction_id
        else:
            # junction_id is a NOT NULL foreign key. Minting a fresh UUID here
            # attached the reading to a junction that does not exist.
            raise ValueError(
                f"Cannot resolve a junction for sensor {data.sensor_id}: "
                "the sensor is unknown and no junction_id was supplied"
            )

    speed = reading_dict.get("avg_speed")
    if speed is None:
        speed = reading_dict.get("average_speed")

    # pcu_value and vehicle_count are NOT NULL. Neither may be defaulted: a
    # count of 0 is a claim that the sensor saw an empty road.
    v_count = reading_dict.get("vehicle_count")
    if v_count is None:
        raise ValueError("vehicle_count is required and cannot be defaulted")

    pcu = reading_dict.get("pcu_value")
    if pcu is None:
        # Derive from the class breakdown using the IRC factors. The previous
        # `vehicle_count * 1.0` counted a bus and a bicycle as one car each,
        # producing a PCU that looked computed but was just the raw count.
        breakdown = reading_dict.get("vehicle_breakdown")
        if not breakdown:
            raise ValueError(
                "pcu_value is required when no vehicle_breakdown is supplied; "
                "it cannot be inferred from the raw vehicle count"
            )
        pcu = sum(
            float(n) * PCU_FACTORS.get(cls, 1.0)
            for cls, n in breakdown.items()
        )

    ts = reading_dict.get("timestamp")
    if ts is None:
        ts = datetime.utcnow()
    elif ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)

    raw_source = source or reading_dict.get("source") or DataSource.MQTT
    if isinstance(raw_source, DataSource):
        resolved_source = raw_source.value
    else:
        raw_str = str(raw_source).lower()
        if raw_str in [s.value for s in DataSource]:
            resolved_source = raw_str
        elif raw_str == "sim":
            # Migration shim for rows written before SN-008.
            resolved_source = DataSource.SUMO.value
        else:
            # "mock" previously mapped to HEURISTIC, which relabelled invented
            # data as a formula-based estimate. Its emitters are gone (SN-012a);
            # anything unrecognised is rejected rather than relabelled.
            raise ValueError(
                f"Unrecognised data source {raw_str!r}; "
                f"expected one of {[s.value for s in DataSource]}"
            )

    reading = TrafficReading(
        id=uuid.uuid4(),
        sensor_id=data.sensor_id,
        junction_id=j_id,
        vehicle_count=v_count,
        pcu_value=pcu,
        avg_speed=speed,
        # Nullable. An unreported queue is unknown, not empty.
        queue_length=reading_dict.get("queue_length"),
        vehicle_breakdown=reading_dict.get("vehicle_breakdown"),
        source=resolved_source,
        timestamp=ts,
    )
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading


# ---------------------------------------------------------------------------
# Spatial Queries (PostGIS with SQLite Dialect Fallback)
# ---------------------------------------------------------------------------

async def get_nearest_junction(
    db: AsyncSession,
    latitude: float,
    longitude: float
) -> Optional[Junction]:
    """
    Find the nearest junction using PostGIS ST_Distance (with spatial index)
    when on PostgreSQL, or Euclidean distance fallback when on SQLite.
    """
    dialect = _get_dialect_name(db)
    if dialect == "postgresql":
        try:
            point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
            query = (
                select(Junction)
                .where(Junction.location.is_not(None))
                .order_by(func.ST_Distance(cast(Junction.location, Geography), cast(point, Geography)))
                .limit(1)
            )
            result = await db.execute(query)
            junction = result.scalar_one_or_none()
            if junction:
                return junction
        except Exception:
            pass

    # Fallback (SQLite or if location column is unpopulated)
    query = (
        select(Junction)
        .order_by(
            (Junction.latitude - latitude) * (Junction.latitude - latitude) +
            (Junction.longitude - longitude) * (Junction.longitude - longitude)
        )
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_junctions_within_radius(
    db: AsyncSession,
    latitude: float,
    longitude: float,
    radius_meters: float = 5000.0
) -> List[Junction]:
    """
    Query junctions within radius_meters using ST_DWithin on PostgreSQL/PostGIS,
    or degree distance fallback on SQLite.
    """
    dialect = _get_dialect_name(db)
    if dialect == "postgresql":
        try:
            point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
            query = (
                select(Junction)
                .where(
                    or_(
                        func.ST_DWithin(
                            cast(Junction.location, Geography),
                            cast(point, Geography),
                            radius_meters
                        ),
                        and_(
                            Junction.location.is_(None),
                            ((Junction.latitude - latitude) * (Junction.latitude - latitude) +
                             (Junction.longitude - longitude) * (Junction.longitude - longitude))
                            <= (radius_meters / 111000.0) * (radius_meters / 111000.0)
                        )
                    )
                )
                .order_by(
                    func.ST_Distance(
                        cast(func.coalesce(Junction.location, point), Geography),
                        cast(point, Geography)
                    )
                )
            )
            result = await db.execute(query)
            return list(result.scalars().all())
        except Exception:
            pass

    # SQLite fallback
    deg_radius = radius_meters / 111000.0
    query = (
        select(Junction)
        .where(
            ((Junction.latitude - latitude) * (Junction.latitude - latitude) +
             (Junction.longitude - longitude) * (Junction.longitude - longitude))
            <= (deg_radius * deg_radius)
        )
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_junctions_in_bbox(
    db: AsyncSession,
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float
) -> List[Junction]:
    """
    Query junctions within a bounding box using ST_MakeEnvelope on PostGIS
    or coordinate comparisons on SQLite.
    """
    dialect = _get_dialect_name(db)
    if dialect == "postgresql":
        try:
            envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            query = (
                select(Junction)
                .where(
                    or_(
                        func.ST_Within(Junction.location, envelope),
                        and_(
                            Junction.latitude >= min_lat,
                            Junction.latitude <= max_lat,
                            Junction.longitude >= min_lon,
                            Junction.longitude <= max_lon,
                        )
                    )
                )
            )
            result = await db.execute(query)
            return list(result.scalars().all())
        except Exception:
            pass

    # SQLite fallback
    query = (
        select(Junction)
        .where(
            and_(
                Junction.latitude >= min_lat,
                Junction.latitude <= max_lat,
                Junction.longitude >= min_lon,
                Junction.longitude <= max_lon,
            )
        )
    )
    result = await db.execute(query)
    return list(result.scalars().all())
