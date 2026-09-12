import asyncio
import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

from app.config import get_settings
from app.database import async_session_maker
from app.models.junction import Junction, TrafficSensor, SensorType, ApproachDirection
from app.models.signal import SignalPlan, SignalMode
from app.models.traffic import TrafficReading
from app.models.alert import Alert, AlertType, AlertSeverity
from app.models.network import NetworkLink
from shared.corridor_topology import CORRIDOR_JUNCTIONS, CORRIDOR_EDGES

settings = get_settings()

# These 12 junctions are decorative spatial-query demo data (nearest-junction
# lookups, map display) — they are NOT part of the real, signalized 4-junction
# SUMO corridor (W_entry/J0-J3/E_exit/N0-N3/S0-S3, seeded separately by
# scripts/seed_demo.py from shared/corridor_topology.py). Deliberately, no
# NetworkLink rows connect them to anything: A* routing between them will
# correctly find no path, because none exists to fabricate. A test that
# expects a real computed route between two of these should use the real
# corridor's coordinates instead (see backend/tests/test_antigravity.py) —
# that is the fix that was actually needed the one time this was mistaken
# for a routing bug, not adding fake connectivity here.
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
    async with async_session_maker() as db:
        # Check which of these specific decorative junctions already exist,
        # matched by name — not a total row count. A count-based check is
        # vulnerable to any other seeding process (e.g. seed_demo.py's real
        # corridor junctions) changing the total, or to row counts
        # fluctuating across repeated test/reset cycles for reasons
        # unrelated to this function; either can make the count dip below
        # len(CITY_JUNCTIONS) again and cause a second run to silently
        # duplicate every decorative junction (found live: 9 duplicate rows
        # of "Bangalore Silk Board" on the demo Postgres from exactly this).
        city_names = [data["name"] for data in CITY_JUNCTIONS]
        res = await db.execute(select(Junction).where(Junction.name.in_(city_names)))
        existing_by_name = {j.name for j in res.scalars().all()}
        remaining = [data for data in CITY_JUNCTIONS if data["name"] not in existing_by_name]
        if not remaining:
            print(f"City already seeded: all {len(CITY_JUNCTIONS)} decorative junctions present.")
            return
        if existing_by_name:
            print(f"{len(existing_by_name)}/{len(CITY_JUNCTIONS)} decorative junctions already seeded; adding the {len(remaining)} missing one(s).")

        print("Seeding smart city junctions and sensor topology...")
        created_junctions = []
        created_sensors = []

        for data in remaining:
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

        # Seed the real SUMO corridor junctions (SN-041) — distinct from the
        # decorative CITY_JUNCTIONS above. RoutingService.initialize_from_db()
        # builds graph nodes keyed by Junction.name, and network_links below
        # references junction ids like "J0"/"W_entry" — without these rows,
        # a DB-built graph would share zero node names with its own edges.
        res_corridor = await db.execute(
            select(Junction).where(Junction.name.in_([j["id"] for j in CORRIDOR_JUNCTIONS]))
        )
        existing_corridor = {j.name for j in res_corridor.scalars().all()}
        if len(existing_corridor) < len(CORRIDOR_JUNCTIONS):
            print("Seeding real SUMO corridor junctions for the routing graph...")
            corridor_junctions = [
                Junction(
                    id=uuid.uuid4(),
                    name=cj["id"],
                    latitude=cj["lat"],
                    longitude=cj["lon"],
                    num_approaches=4,
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
                for cj in CORRIDOR_JUNCTIONS
                if cj["id"] not in existing_corridor
            ]
            db.add_all(corridor_junctions)
            await db.commit()
            print(f"Created {len(corridor_junctions)} corridor junctions ({', '.join(j.name for j in corridor_junctions)}).")

        # Seed network links for A* routing (SN-041)
        res_links = await db.execute(select(NetworkLink))
        existing_links = res_links.scalars().all()
        if len(existing_links) == 0:
            print("Seeding corridor network links for A* routing...")
            links = [
                NetworkLink(
                    id=uuid.uuid4(),
                    from_junction=edge["from"],
                    to_junction=edge["to"],
                    sumo_edge_id=edge["sumo_edge_id"],
                    length_m=edge.get("length_m", 300.0),
                    lanes=2,
                    free_flow_speed_kmh=edge.get("free_flow_speed", 50.0),
                    capacity_pcu_h=edge.get("capacity", 2000.0),
                    created_at=datetime.utcnow()
                )
                for edge in CORRIDOR_EDGES
            ]
            db.add_all(links)
            await db.commit()
            print(f"Created {len(links)} network links for routing engine.")

        print("City topology, baseline readings, active alerts, corridor junctions, and network links successfully seeded!")

if __name__ == "__main__":
    asyncio.run(seed_city())
