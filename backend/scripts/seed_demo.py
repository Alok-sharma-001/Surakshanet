"""SN-134: Seeds a complete, coherent demo dataset.

Ensures the four real corridor junctions (J0..J3, real Indore coordinates
and human names via shared/corridor_topology.py — see that file's header
comment for the sourcing of those coordinates) exist with sensors and
network links, one user per role, one historic closed event, and one
resolved incident — so analytics/incidents/events pages never read as
empty/unfinished during a demo walkthrough before any live simulation has
run.

Every row this script creates carries source='manual' wherever the model has
a source column (Invariant §13.3 / SN-134): seeded data must never be
mistaken for something a sensor or detector actually measured. Idempotent —
safe to run multiple times and safe to run before or after seed_city.py /
seed_admin.py.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from sqlalchemy import select

from app.database import async_session_maker, init_db
from app.models.junction import Junction, TrafficSensor, SensorType, ApproachDirection
from app.models.network import NetworkLink
from app.models.user import User, UserRole
from app.models.event import Event, EventType, EventIntensity, EventStatus
from app.models.incident import Incident, IncidentIndicator, IncidentIndicatorType, IncidentStatus
from app.services.auth_service import hash_password
from shared.corridor_topology import CORRIDOR_JUNCTIONS, CORRIDOR_EDGES

# The four real, signalized corridor junctions (SN-134 asks for these four
# specifically — not the full 14-node corridor incl. cross-street spurs and
# expressway entry/exit that seed_city.py already seeds for routing).
DEMO_JUNCTION_IDS = ["J0", "J1", "J2", "J3"]

DEMO_USERS = [
    {"email": "operator@surakshanet.local", "name": "Demo Operator", "role": UserRole.OPERATOR},
    {"email": "emergency@surakshanet.local", "name": "Demo Emergency Dispatch", "role": UserRole.EMERGENCY_SERVICES},
    {"email": "viewer@surakshanet.local", "name": "Demo City Analyst", "role": UserRole.VIEWER},
    {"email": "citizen@surakshanet.local", "name": "Demo Citizen", "role": UserRole.CITIZEN},
]
DEMO_USER_PASSWORD = "SurakshaNetDemo@2026"


async def seed_corridor_junctions_and_sensors(db) -> dict:
    """Ensures J0..J3 exist with real coordinates/names and 4 sensors each.

    Returns {sumo_id: Junction} for the four demo junctions.
    """
    by_sumo_id = {j["id"]: j for j in CORRIDOR_JUNCTIONS}
    result: dict = {}

    res = await db.execute(select(Junction).where(Junction.name.in_(DEMO_JUNCTION_IDS)))
    existing = {j.name: j for j in res.scalars().all()}

    for sumo_id in DEMO_JUNCTION_IDS:
        spec = by_sumo_id[sumo_id]

        if sumo_id in existing:
            # Sync coordinates to the current CORRIDOR_JUNCTIONS source of
            # truth even if the row predates this script — an earlier
            # seed_city.py run (or an earlier version of this script) may
            # have created it with stale/synthetic coordinates, and an
            # idempotency check that only asked "does a row with this name
            # exist" would silently leave those wrong forever.
            junction = existing[sumo_id]
            if junction.latitude != spec["lat"] or junction.longitude != spec["lon"]:
                junction.latitude = spec["lat"]
                junction.longitude = spec["lon"]
                print(f"  Updated junction {sumo_id} coordinates to {spec['lat']:.5f}, {spec['lon']:.5f} ({spec['name']})")
            result[sumo_id] = junction
            continue

        junction = Junction(
            id=uuid.uuid4(),
            name=sumo_id,
            latitude=spec["lat"],
            longitude=spec["lon"],
            num_approaches=4,
            is_active=True,
            created_at=datetime.utcnow() - timedelta(days=14),
        )
        db.add(junction)
        await db.flush()
        result[sumo_id] = junction
        print(f"  Created junction {sumo_id} ({spec['name']}) at {spec['lat']:.5f}, {spec['lon']:.5f}")

        for d in [ApproachDirection.N, ApproachDirection.E, ApproachDirection.S, ApproachDirection.W]:
            db.add(TrafficSensor(
                id=uuid.uuid4(),
                junction_id=junction.id,
                sensor_type=SensorType.CAMERA if d in (ApproachDirection.N, ApproachDirection.S) else SensorType.INDUCTION,
                approach_direction=d,
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=14),
            ))

    await db.commit()
    return result


async def seed_network_links(db):
    """Ensures network_links rows exist for every CORRIDOR_EDGES entry
    touching the four demo junctions (real SUMO edge ids/lengths, no
    invented distances)."""
    res = await db.execute(select(NetworkLink))
    existing = {(l.from_junction, l.to_junction) for l in res.scalars().all()}

    created = 0
    for e in CORRIDOR_EDGES:
        if e["from"] not in DEMO_JUNCTION_IDS and e["to"] not in DEMO_JUNCTION_IDS:
            continue
        key = (e["from"], e["to"])
        if key in existing:
            continue
        db.add(NetworkLink(
            id=uuid.uuid4(),
            from_junction=e["from"],
            to_junction=e["to"],
            sumo_edge_id=e["sumo_edge_id"],
            length_m=e["length_m"],
            lanes=2,
            free_flow_speed_kmh=e["free_flow_speed"],
            capacity_pcu_h=float(e["capacity"]),
            created_at=datetime.utcnow() - timedelta(days=14),
        ))
        created += 1
    if created:
        await db.commit()
    print(f"  Network links: {created} created, {len(existing)} already present")


async def seed_demo_users(db):
    """One user per non-ADMIN role (seed_admin.py already covers ADMIN)."""
    for spec in DEMO_USERS:
        res = await db.execute(select(User).where(User.email == spec["email"]))
        if res.scalar_one_or_none():
            print(f"  User already seeded: {spec['email']} ({spec['role'].value})")
            continue
        db.add(User(
            id=uuid.uuid4(),
            email=spec["email"],
            password_hash=hash_password(DEMO_USER_PASSWORD),
            name=spec["name"],
            role=spec["role"],
            is_active=True,
            created_at=datetime.utcnow() - timedelta(days=14),
        ))
        print(f"  Created user: {spec['email']} ({spec['role'].value})")
    await db.commit()


async def seed_historic_event(db, admin_id):
    """One historic, already-closed event — CLOSED status, source of demand
    already applied, so the Events page never reads as empty on first load.
    """
    res = await db.execute(select(Event).where(Event.name == "Rangpanchami Procession (historic, seeded)"))
    if res.scalar_one_or_none():
        print("  Historic event already seeded")
        return

    starts = datetime.utcnow() - timedelta(days=10)
    db.add(Event(
        id=uuid.uuid4(),
        name="Rangpanchami Procession (historic, seeded)",
        event_type=EventType.PROCESSION,
        starts_at=starts,
        ends_at=starts + timedelta(hours=3),
        expected_crowd=18000,
        affected_links=["E_J1_to_J2", "E_J2_to_J1"],
        closure_links=[],
        intensity=EventIntensity.HIGH,
        status=EventStatus.CLOSED,
        created_by=admin_id,
        approved_by=admin_id,
        created_at=starts - timedelta(days=2),
        approved_at=starts - timedelta(days=1),
        published_at=starts - timedelta(hours=6),
    ))
    await db.commit()
    print("  Created historic closed event: Rangpanchami Procession")


async def seed_resolved_incident(db, admin_id):
    """One resolved incident with a real measured indicator row (the
    write-time DB trigger rejects an incident with zero indicators), so the
    Incidents page shows real history before any live anomaly has fired.
    source='manual' — this is seeded demo history, not something the
    anomaly service actually detected.
    """
    res = await db.execute(select(Incident).where(Incident.link_id == "E_J2_to_J3", Incident.source == "manual"))
    if res.scalar_one_or_none():
        print("  Resolved demo incident already seeded")
        return

    detected = datetime.utcnow() - timedelta(days=3, hours=2)
    incident = Incident(
        id=uuid.uuid4(),
        link_id="E_J2_to_J3",
        junction_id="J3",
        detected_at=detected,
        confidence=0.62,
        indicators_fired=2,
        indicators_total=5,
        source="manual",
        note="Possible incident. Unverified — operator review required.",
        created_at=detected,
        updated_at=detected + timedelta(minutes=14),
    )
    incident.indicators.append(IncidentIndicator(
        id=uuid.uuid4(),
        indicator=IncidentIndicatorType.SPEED_COLLAPSE,
        measured_value=8.2,
        threshold=20.0,
        fired_at=detected,
    ))
    incident.indicators.append(IncidentIndicator(
        id=uuid.uuid4(),
        indicator=IncidentIndicatorType.STATIONARY_VEHICLE,
        measured_value=34.0,
        threshold=20.0,
        fired_at=detected,
    ))
    db.add(incident)
    await db.flush()

    # Confirm then resolve, in order, so the @validates human-gate
    # invariants are satisfied exactly as a real operator resolution would.
    incident.confirmed_by = admin_id
    incident.confirmed_at = detected + timedelta(minutes=3)
    incident.status = IncidentStatus.CONFIRMED
    await db.flush()

    incident.status = IncidentStatus.RESOLVED
    incident.resolution = "Stalled auto-rickshaw cleared by patrol; lane reopened."
    incident.updated_at = detected + timedelta(minutes=14)

    await db.commit()
    print("  Created resolved demo incident on E_J2_to_J3 (2/5 indicators, confirmed then resolved)")


async def main():
    print("Ensuring database tables exist...")
    await init_db()

    async with async_session_maker() as db:
        from sqlalchemy import select as _select
        from app.models.user import User as _User, UserRole as _UserRole
        admin_res = await db.execute(_select(_User).where(_User.role == _UserRole.ADMIN))
        admin = admin_res.scalars().first()
        if not admin:
            print("No ADMIN user found — run scripts/seed_admin.py first.")
            return
        admin_id = admin.id

        print("Seeding real corridor junctions (J0..J3) and sensors...")
        await seed_corridor_junctions_and_sensors(db)

        print("Seeding network links...")
        await seed_network_links(db)

        print("Seeding demo users (one per non-ADMIN role)...")
        await seed_demo_users(db)

        print("Seeding historic closed event...")
        await seed_historic_event(db, admin_id)

        print("Seeding resolved incident...")
        await seed_resolved_incident(db, admin_id)

    print("Demo dataset seeded.")
    print(f"Demo user password (all four roles): {DEMO_USER_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
