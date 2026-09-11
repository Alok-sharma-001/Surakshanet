"""006_incidents

Revision ID: 006_incidents
Revises: 005_vision_tables
Create Date: 2026-09-11 17:00:00.000000

SN-084: Create tables for incidents and incident_indicators.
Enforces the integrity rule that an incident cannot exist without at least one
measured indicator row (deferred constraint trigger in Postgres).
Downgrade cleanly drops tables, indexes, triggers, and enum types.
"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006_incidents"
down_revision: Union[str, None] = "005_vision_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 001_initial_schema already created a generic "incidents" table (plain
    # String columns: severity/title/description/location) as early Phase 0/1
    # scaffolding — it was never backed by any SQLAlchemy model and nothing
    # in the app ever reads or writes it (confirmed via grep). SN-083's real
    # Incident model supersedes it; drop the orphaned table first so the real
    # one below can be created under the same name. Recreated verbatim in
    # downgrade() so migration 001's own downgrade (which drops "incidents")
    # still has a table to drop if something downgrades past this one.
    op.drop_table("incidents")

    # 1. Create incidents table
    op.create_table(
        "incidents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "incident_type",
            sa.Enum("POSSIBLE_INCIDENT", name="incidenttype"),
            server_default="POSSIBLE_INCIDENT",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "DETECTED",
                "UNVERIFIED",
                "UNDER_REVIEW",
                "CONFIRMED",
                "DISMISSED",
                "RESPONDING",
                "RESOLVED",
                "CLOSED",
                name="incidentstatus",
            ),
            server_default="UNVERIFIED",
            nullable=False,
        ),
        sa.Column("link_id", sa.String(length=64), nullable=False),
        sa.Column("junction_id", sa.String(length=64), nullable=True),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("indicators_fired", sa.Integer(), server_default="1", nullable=False),
        sa.Column("indicators_total", sa.Integer(), server_default="5", nullable=False),
        sa.Column("evidence_ref", sa.String(length=256), nullable=True),
        sa.Column(
            "confirmed_by",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("resolution", sa.String(length=256), nullable=True),
        sa.Column("warning_published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "warning_published_by",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=32), server_default="sumo", nullable=False),
        sa.Column(
            "note",
            sa.String(length=256),
            server_default="Possible incident. Unverified — operator review required.",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_link_id", "incidents", ["link_id"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_detected_at", "incidents", ["detected_at"])
    op.create_index("ix_incidents_junction_id", "incidents", ["junction_id"])

    # 2. Create incident_indicators table
    op.create_table(
        "incident_indicators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "indicator",
            sa.Enum(
                "SPEED_COLLAPSE",
                "STATIONARY_VEHICLE",
                "OCCUPANCY_SPIKE",
                "FLOW_DROP",
                "QUEUE_ANOMALY",
                name="incidentindicatortype",
            ),
            nullable=False,
        ),
        sa.Column("measured_value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("fired_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_indicators_incident_id", "incident_indicators", ["incident_id"])
    op.create_index("ix_incident_indicators_indicator", "incident_indicators", ["indicator"])

    # 3. Add deferred constraint trigger on Postgres enforcing non-zero indicator rows (SN-084)
    if is_postgres:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION check_incident_has_indicators()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM incident_indicators WHERE incident_id = NEW.id) THEN
                    RAISE EXCEPTION 'Incident % cannot exist without at least one measured indicator row.', NEW.id;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        # asyncpg's extended query protocol rejects multiple commands in one
        # prepared statement — each DDL statement needs its own op.execute().
        op.execute("DROP TRIGGER IF EXISTS trg_check_incident_indicators ON incidents;")
        op.execute(
            """
            CREATE CONSTRAINT TRIGGER trg_check_incident_indicators
            AFTER INSERT OR UPDATE ON incidents
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW
            EXECUTE FUNCTION check_incident_has_indicators();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS trg_check_incident_indicators ON incidents;")
        op.execute("DROP FUNCTION IF EXISTS check_incident_has_indicators();")

    op.drop_index("ix_incident_indicators_indicator", table_name="incident_indicators")
    op.drop_index("ix_incident_indicators_incident_id", table_name="incident_indicators")
    op.drop_table("incident_indicators")

    op.drop_index("ix_incidents_junction_id", table_name="incidents")
    op.drop_index("ix_incidents_detected_at", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_link_id", table_name="incidents")
    op.drop_table("incidents")

    if is_postgres:
        for enum_name in ["incidentindicatortype", "incidentstatus", "incidenttype"]:
            op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE;")

    # Recreate 001_initial_schema's original orphaned "incidents" table
    # verbatim, so migration 001's own downgrade (which drops "incidents")
    # still has a table to drop if the chain is downgraded past this one.
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
