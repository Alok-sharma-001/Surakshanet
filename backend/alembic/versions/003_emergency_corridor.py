"""003_emergency_corridor

Revision ID: 003_emergency_corridor
Revises: 002_control_decisions_ab_runs
Create Date: 2026-09-11 12:00:00.000000

SN-040: Extend emergency_events with corridor, ETA, program capture, and recovery fields.
Create network_links table for live routing graph (SN-041).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_emergency_corridor"
down_revision: Union[str, None] = "002_control_decisions_ab_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add corridor tracking columns to emergency_events
    op.add_column("emergency_events", sa.Column("vehicle_id", sa.String(length=64), nullable=True))
    op.add_column("emergency_events", sa.Column("origin_lat", sa.Float(), nullable=True))
    op.add_column("emergency_events", sa.Column("origin_lon", sa.Float(), nullable=True))
    op.add_column("emergency_events", sa.Column("destination_lat", sa.Float(), nullable=True))
    op.add_column("emergency_events", sa.Column("destination_lon", sa.Float(), nullable=True))
    op.add_column("emergency_events", sa.Column("destination_name", sa.String(length=128), nullable=True))
    op.add_column("emergency_events", sa.Column("route_etas", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("emergency_events", sa.Column("captured_programs", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("emergency_events", sa.Column("restored_at", sa.DateTime(), nullable=True))
    op.add_column("emergency_events", sa.Column("clearance_time_s", sa.Float(), nullable=True))
    op.add_column("emergency_events", sa.Column("cross_street_max_red_s", sa.Float(), nullable=True))
    op.add_column("emergency_events", sa.Column("recovery_s", sa.Float(), nullable=True))
    op.add_column("emergency_events", sa.Column("recovery_series", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # 2. Create network_links table for live A* routing graph
    op.create_table(
        "network_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_junction", sa.String(length=64), nullable=False),
        sa.Column("to_junction", sa.String(length=64), nullable=False),
        sa.Column("sumo_edge_id", sa.String(length=64), nullable=False),
        sa.Column("length_m", sa.Float(), nullable=False),
        sa.Column("lanes", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("free_flow_speed_kmh", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("capacity_pcu_h", sa.Float(), nullable=False, server_default="2000.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_network_links_from_to",
        "network_links",
        ["from_junction", "to_junction"],
    )


def downgrade() -> None:
    op.drop_index("ix_network_links_from_to", table_name="network_links")
    op.drop_table("network_links")

    op.drop_column("emergency_events", "recovery_series")
    op.drop_column("emergency_events", "recovery_s")
    op.drop_column("emergency_events", "cross_street_max_red_s")
    op.drop_column("emergency_events", "clearance_time_s")
    op.drop_column("emergency_events", "restored_at")
    op.drop_column("emergency_events", "captured_programs")
    op.drop_column("emergency_events", "route_etas")
    op.drop_column("emergency_events", "destination_name")
    op.drop_column("emergency_events", "destination_lon")
    op.drop_column("emergency_events", "destination_lat")
    op.drop_column("emergency_events", "origin_lon")
    op.drop_column("emergency_events", "origin_lat")
    op.drop_column("emergency_events", "vehicle_id")
