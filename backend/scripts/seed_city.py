import asyncio
import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

from app.config import get_settings
from app.models.junction import Junction, TrafficSensor, SensorType, ApproachDirection
from app.models.signal import SignalPlan, SignalMode
from app.models.traffic import TrafficReading
from app.models.alert import Alert, AlertType, AlertSeverity

settings = get_settings()

CITY_JUNCTIONS = [
    # Delhi Network
    {"name": "Connaught Place Outer Circle", "lat": 28.6315, "lon": 77.2167, "approaches": 4},
    {"name": "ITO Crossing - Vikas Marg", "lat": 28.6289, "lon": 77.2405, "approaches": 4},
    {"name": "AIIMS Flyover - Ring Road", "lat": 28.5672, "lon": 77.2100, "approaches": 4},
    {"name": "Ashram Chowk - Mathura Road", "lat": 28.5714, "lon": 77.2588, "approaches": 4},
    {"name": "Dhaula Kuan Interchange", "lat": 28.5921, "lon": 77.1565, "approaches": 4},
    {"name": "Lajpat Nagar Ring Road", "lat": 28.5700, "lon": 77.2370, "approaches": 4},
    {"name": "Kashmere Gate ISBT", "lat": 28.6675, "lon": 77.2325, "approaches": 4},
    {"name": "Hazrat Nizamuddin West", "lat": 28.5880, "lon": 77.2470, "approaches": 4},
    # Bengaluru Network
    {"name": "MG Road - Brigade Junction", "lat": 12.9756, "lon": 77.6066, "approaches": 4},
    {"name": "Silk Board Junction", "lat": 12.9177, "lon": 77.6238, "approaches": 4},
    {"name": "Indiranagar 100ft Road", "lat": 12.9719, "lon": 77.6412, "approaches": 4},
    {"name": "Koramangala Sony World Signal", "lat": 12.9352, "lon": 77.6245, "approaches": 4},
]

async def seed_city():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Check if already seeded
        res = await db.execute(select(Junction))
        existing_junctions = res.scalars().all()
        if len(existing_junctions) >= len(CITY_JUNCTIONS):
            print(f"City already seeded with {len(existing_junctions)} junctions.")
            return

        print("Seeding smart city junctions and sensor topology...")
        created_junctions = []
        created_sensors = []

        for data in CITY_JUNCTIONS:
            junction = Junction(
                id=uuid.uuid4(),
                name=data["name"],
                latitude=data["lat"],
                longitude=data["lon"],
                num_approaches=data["approaches"],
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=14)
            )
            db.add(junction)
            created_junctions.append(junction)

            # Create 4 approach sensors per junction (N, E, S, W)
            for d in [ApproachDirection.N, ApproachDirection.E, ApproachDirection.S, ApproachDirection.W]:
                sensor = TrafficSensor(
                    id=uuid.uuid4(),
                    junction_id=junction.id,
                    sensor_type=SensorType.CAMERA if d in [ApproachDirection.N, ApproachDirection.S] else SensorType.INDUCTION,
                    approach_direction=d,
                    is_active=True,
                    created_at=datetime.utcnow() - timedelta(days=14)
                )
                db.add(sensor)
                created_sensors.append(sensor)

            # Create default MARL Signal Plan
            signal_plan = SignalPlan(
                id=uuid.uuid4(),
                junction_id=junction.id,
                name=f"{data['name']} MARL Master Plan",
                mode=SignalMode.MARL,
                phases=[
                    {"phase": 1, "name": "North-South Straight", "duration": 35, "min_green": 12, "max_green": 60},
                    {"phase": 2, "name": "North-South Left Turn", "duration": 20, "min_green": 10, "max_green": 40},
                    {"phase": 3, "name": "East-West Straight", "duration": 30, "min_green": 12, "max_green": 55},
                    {"phase": 4, "name": "East-West Left Turn", "duration": 15, "min_green": 10, "max_green": 35}
                ],
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=14)
            )
            db.add(signal_plan)

        await db.commit()
        print(f"Created {len(created_junctions)} junctions and {len(created_sensors)} sensors.")

        # Seed realistic historical traffic readings (7 days, 15m intervals)
        print("Generating 7-day realistic time-series traffic readings...")
        now = datetime.utcnow()
        readings = []

        # Generate sample historical steps over last 7 days
        for step in range(0, 7 * 24 * 4, 2):  # Every 30 mins
            point_time = now - timedelta(minutes=step * 15)
            hour = (point_time.hour + 5) % 24  # Local hour approximation

            # Peak multipliers
            is_morning_peak = 8 <= hour <= 10
            is_evening_peak = 17 <= hour <= 20
            is_night = hour < 6 or hour > 22

            if is_morning_peak:
                base_count = random.randint(45, 95)
                base_speed = random.uniform(18.0, 28.0)
            elif is_evening_peak:
                base_count = random.randint(55, 110)
                base_speed = random.uniform(14.0, 24.0)
            elif is_night:
                base_count = random.randint(5, 20)
                base_speed = random.uniform(48.0, 65.0)
            else:
                base_count = random.randint(25, 55)
                base_speed = random.uniform(32.0, 44.0)

            # Sample 4 sensors per time step
            sample_sensors = random.sample(created_sensors, min(len(created_sensors), 8))
            for sensor in sample_sensors:
                count = max(2, int(base_count * random.uniform(0.7, 1.3)))
                cars = int(count * 0.55)
                two_wheelers = int(count * 0.25)
                buses = int(count * 0.08)
                trucks = int(count * 0.05)
                autos = count - (cars + two_wheelers + buses + trucks)

                pcu = round(cars * 1.0 + two_wheelers * 0.5 + buses * 3.0 + trucks * 3.0 + autos * 1.0, 1)
                queue_len = round(max(0.0, (count - 15) * 1.8 * random.uniform(0.8, 1.2)), 1)

                reading = TrafficReading(
                    id=uuid.uuid4(),
                    timestamp=point_time,
                    sensor_id=sensor.id,
                    junction_id=sensor.junction_id,
                    vehicle_count=float(count),
                    pcu_value=pcu,
                    avg_speed=round(base_speed * random.uniform(0.85, 1.15), 1),
                    queue_length=queue_len,
                    vehicle_breakdown={
                        "car": cars,
                        "motorcycle": two_wheelers,
                        "bus": buses,
                        "truck": trucks,
                        "auto_rickshaw": max(0, autos)
                    },
                    created_at=point_time
                )
                readings.append(reading)

        # Batch insert readings
        print(f"Inserting {len(readings)} traffic reading records into TimescaleDB/Postgres...")
        batch_size = 500
        for i in range(0, len(readings), batch_size):
            db.add_all(readings[i:i + batch_size])
            await db.commit()

        # Seed active smart alerts
        ashram = next(j for j in created_junctions if "Ashram" in j.name)
        silkboard = next(j for j in created_junctions if "Silk Board" in j.name)
        ito = next(j for j in created_junctions if "ITO" in j.name)

        alerts = [
            Alert(
                id=uuid.uuid4(),
                junction_id=ashram.id,
                alert_type=AlertType.SPILLBACK,
                severity=AlertSeverity.CRITICAL,
                message="High spillback risk: Northbound queue exceeds 85% link capacity at Mathura Rd.",
                is_acknowledged=False,
                created_at=datetime.utcnow() - timedelta(minutes=4)
            ),
            Alert(
                id=uuid.uuid4(),
                junction_id=silkboard.id,
                alert_type=AlertType.CONGESTION,
                severity=AlertSeverity.WARNING,
                message="Heavy corridor congestion: Average approach speed dropped to 12 km/h.",
                is_acknowledged=False,
                created_at=datetime.utcnow() - timedelta(minutes=15)
            ),
            Alert(
                id=uuid.uuid4(),
                junction_id=ito.id,
                alert_type=AlertType.QUEUE_OVERFLOW,
                severity=AlertSeverity.WARNING,
                message="Vikas Marg queue spilling back towards Laxmi Nagar bridge.",
                is_acknowledged=True,
                created_at=datetime.utcnow() - timedelta(minutes=28),
                acknowledged_at=datetime.utcnow() - timedelta(minutes=10)
            )
        ]
        db.add_all(alerts)
        await db.commit()

        print("City topology, baseline readings, and active alerts successfully seeded!")

if __name__ == "__main__":
    asyncio.run(seed_city())
