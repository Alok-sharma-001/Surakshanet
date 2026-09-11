"""004_events_and_advisories

Revision ID: 004_events_and_advisories
Revises: 003_emergency_corridor
Create Date: 2026-09-11 14:00:00.000000

SN-052: Create tables for events, event_predictions, and citizen_advisories.
Enforces published_by NOT NULL constraint on citizen_advisories (human gate).
Creates minimal audit_logs table for EVENT_APPROVE and ADVISORY_PUBLISH actions.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_events_and_advisories"
down_revision: Union[str, None] = "003_emergency_corridor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create events table
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("expected_crowd", sa.Integer(), nullable=True),
        sa.Column("affected_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("closure_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("intensity", sa.String(length=16), server_default="MEDIUM", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_status", "events", ["status"])

    # 2. Create event_predictions table
    op.create_table(
        "event_predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("baseline_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("link_deltas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("severity_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("alternatives", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="sumo", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_predictions_event_id", "event_predictions", ["event_id"])

    # 3. Create citizen_advisories table (published_by NOT NULL enforces human gate at DB level)
    op.create_table(
        "citizen_advisories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("origin_type", sa.String(length=32), nullable=False),
        sa.Column("origin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("headline", sa.String(length=120), nullable=False),
        sa.Column("corridor_text", sa.String(length=256), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("delay_min_low", sa.Integer(), nullable=False),
        sa.Column("delay_min_high", sa.Integer(), nullable=False),
        sa.Column("cause_text", sa.String(length=256), nullable=False),
        sa.Column("recommended_route_text", sa.String(length=256), nullable=False),
        sa.Column("recommended_departure_before", sa.DateTime(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="sumo", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_citizen_advisories_expires_at", "citizen_advisories", ["expires_at"])
    op.create_index("ix_citizen_advisories_origin", "citizen_advisories", ["origin_type", "origin_id"])

    # 4. Create minimal audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_type", sa.String(length=16), server_default="USER", nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("result", sa.String(length=16), server_default="SUCCESS", nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_citizen_advisories_origin", table_name="citizen_advisories")
    op.drop_index("ix_citizen_advisories_expires_at", table_name="citizen_advisories")
    op.drop_table("citizen_advisories")

    op.drop_index("ix_event_predictions_event_id", table_name="event_predictions")
    op.drop_table("event_predictions")

    op.drop_index("ix_events_status", table_name="events")
    op.drop_table("events")
