"""005_vision_tables

Revision ID: 005_vision_tables
Revises: 004_events_and_advisories
Create Date: 2026-09-11 16:00:00.000000

SN-070: Create tables for cv_detections (hypertable with 72h retention),
behavior_flags (with UNVERIFIED default and human gate), and no_parking_zones.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_vision_tables"
down_revision: Union[str, None] = "004_events_and_advisories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Create cv_detections table (Composite PK: id, timestamp)
    op.create_table(
        "cv_detections",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("track_id", sa.String(length=64), nullable=True),
        sa.Column("vehicle_class", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(), nullable=False),
        sa.Column("pcu", sa.Float(), nullable=False),
        sa.Column("frame_ref", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )
    op.create_index("ix_cv_detections_camera_id", "cv_detections", ["camera_id"])
    op.create_index("ix_cv_detections_timestamp", "cv_detections", ["timestamp"])
    op.create_index("ix_cv_detections_track_id", "cv_detections", ["track_id"])

    # Convert to TimescaleDB hypertable with 1-day chunk interval & 72-hour retention policy
    if is_postgres:
        try:
            op.execute(
                "SELECT create_hypertable('cv_detections', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);"
            )
            op.execute(
                "SELECT add_retention_policy('cv_detections', INTERVAL '72 hours', if_not_exists => TRUE);"
            )
        except Exception:
            # TimescaleDB extension might not be enabled in all environments (e.g. standard postgres unit tests)
            pass

    # 2. Create behavior_flags table
    op.create_table(
        "behavior_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), nullable=False),
        sa.Column(
            "flag_type",
            sa.Enum("WRONG_WAY", "ILLEGAL_PARKING", "DANGEROUS_DRIVING", name="behaviorflagtype"),
            nullable=False,
        ),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("track_id", sa.String(length=64), nullable=False),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("UNVERIFIED", "CONFIRMED", "DISMISSED", name="behaviorflagstatus"),
            server_default="UNVERIFIED",
            nullable=False,
        ),
        sa.Column(
            "note",
            sa.String(length=256),
            server_default="Behaviour flagged for review. Not a confirmed violation.",
            nullable=False,
        ),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("frame_ref", sa.String(length=256), nullable=True),
        sa.Column("source", sa.String(length=32), server_default="vision", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_behavior_flags_camera_id", "behavior_flags", ["camera_id"])
    op.create_index("ix_behavior_flags_status", "behavior_flags", ["status"])
    op.create_index("ix_behavior_flags_detected_at", "behavior_flags", ["detected_at"])
    op.create_index("ix_behavior_flags_flag_type", "behavior_flags", ["flag_type"])

    # 3. Create no_parking_zones table
    op.create_table(
        "no_parking_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), nullable=False),
        sa.Column("camera_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("polygon", postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(), nullable=False),
        sa.Column("active_start_time", sa.String(length=16), nullable=True),
        sa.Column("active_end_time", sa.String(length=16), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_no_parking_zones_camera_id", "no_parking_zones", ["camera_id"])


def downgrade() -> None:
    op.drop_index("ix_no_parking_zones_camera_id", table_name="no_parking_zones")
    op.drop_table("no_parking_zones")

    op.drop_index("ix_behavior_flags_flag_type", table_name="behavior_flags")
    op.drop_index("ix_behavior_flags_detected_at", table_name="behavior_flags")
    op.drop_index("ix_behavior_flags_status", table_name="behavior_flags")
    op.drop_index("ix_behavior_flags_camera_id", table_name="behavior_flags")
    op.drop_table("behavior_flags")

    op.drop_index("ix_cv_detections_track_id", table_name="cv_detections")
    op.drop_index("ix_cv_detections_timestamp", table_name="cv_detections")
    op.drop_index("ix_cv_detections_camera_id", table_name="cv_detections")
    op.drop_table("cv_detections")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_name in ["behaviorflagtype", "behaviorflagstatus"]:
            op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE;")
