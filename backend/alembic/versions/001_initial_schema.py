"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-06 14:15:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Enable PostGIS and TimescaleDB extensions
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis CASCADE;")
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # 2. Users Table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.Enum("ADMIN", "OPERATOR", "VIEWER", name="userrole"), nullable=False, server_default="VIEWER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 3. Junctions Table
    location_col = (
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
        if is_postgres
        else sa.Column("location", sa.String(), nullable=True)
    )
    op.create_table(
        "junctions",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        location_col,
        sa.Column("num_approaches", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("geometry", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    if is_postgres:
        op.execute("CREATE INDEX IF NOT EXISTS ix_junctions_location ON junctions USING GIST (location);")

    # 4. Traffic Sensors Table
    op.create_table(
        "traffic_sensors",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), primary_key=True, default=uuid.uuid4),
        sa.Column("junction_id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("junctions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sensor_type", sa.Enum("CAMERA", "INDUCTION", "ACOUSTIC", "GPS", name="sensortype"), nullable=False),
        sa.Column("approach_direction", sa.Enum("N", "E", "S", "W", name="approachdirection"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 5. Traffic Readings Table (Composite PK: id, timestamp)
    op.create_table(
        "traffic_readings",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("sensor_id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("traffic_sensors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("junction_id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("junctions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_count", sa.Float(), nullable=False),
        sa.Column("pcu_value", sa.Float(), nullable=False),
        sa.Column("avg_speed", sa.Float(), nullable=True),
        sa.Column("queue_length", sa.Float(), nullable=True),
        sa.Column("vehicle_breakdown", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(), nullable=True, server_default="live"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )
    op.create_index(op.f("ix_traffic_readings_timestamp"), "traffic_readings", ["timestamp"], unique=False)

    # Convert to TimescaleDB hypertable with 1-day chunk interval & 90-day retention policy
    if is_postgres:
        op.execute("SELECT create_hypertable('traffic_readings', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);")
        op.execute("SELECT add_retention_policy('traffic_readings', INTERVAL '90 days', if_not_exists => TRUE);")

    # 6. Signal Plans Table
    op.create_table(
        "signal_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), primary_key=True, default=uuid.uuid4),
        sa.Column("junction_id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("junctions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phases", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("mode", sa.Enum("MARL", "WEBSTER", "MANUAL", name="signalmode"), nullable=False, server_default="WEBSTER"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # 7. Alerts Table
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), primary_key=True, default=uuid.uuid4),
        sa.Column("junction_id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("junctions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.Enum("CONGESTION", "SPILLBACK", "SIGNAL_FAILURE", "QUEUE_OVERFLOW", name="alerttype"), nullable=False),
        sa.Column("severity", sa.Enum("INFO", "WARNING", "CRITICAL", name="alertseverity"), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
    )

    # 8. Emergency Events Table
    op.create_table(
        "emergency_events",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), primary_key=True, default=uuid.uuid4),
        sa.Column("priority", sa.Enum("CRITICAL", "HIGH", "MEDIUM", name="emergencypriority"), nullable=False),
        sa.Column("vehicle_type", sa.Enum("AMBULANCE", "FIRE", "POLICE", "VIP", name="emergencyvehicletype"), nullable=False),
        sa.Column("route", sa.JSON(), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "COMPLETED", "CANCELLED", name="emergencystatus"), nullable=False),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )

    # 9. Incidents Table
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), primary_key=True, default=uuid.uuid4),
        sa.Column("junction_id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("junctions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("incident_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        try:
            op.execute("SELECT remove_retention_policy('traffic_readings', if_exists => TRUE);")
        except Exception:
            pass

    op.drop_table("incidents")
    op.drop_table("emergency_events")
    op.drop_table("alerts")
    op.drop_table("signal_plans")
    op.drop_table("traffic_readings")
    op.drop_table("traffic_sensors")
    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_junctions_location;")
    op.drop_table("junctions")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    if is_postgres:
        for enum_name in ["userrole", "sensortype", "approachdirection", "signalmode", "alerttype", "alertseverity", "emergencypriority", "emergencyvehicletype", "emergencystatus"]:
            try:
                op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE;")
            except Exception:
                pass
