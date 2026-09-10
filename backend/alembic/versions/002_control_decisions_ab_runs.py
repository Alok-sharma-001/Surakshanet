"""002_control_decisions_ab_runs

Revision ID: 002_control_decisions_ab_runs
Revises: 001b_datasource_provenance
Create Date: 2026-09-10 15:00:00.000000

SN-024: Create control_decisions hypertable (1-day chunks) and ab_runs table
for Phase 2 real AI control loop and A/B proof harness.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_control_decisions_ab_runs"
down_revision: Union[str, None] = "001b_datasource_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create control_decisions table
    op.create_table(
        "control_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("junction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("controller", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("state_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("q_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("action", sa.SmallInteger(), nullable=False),
        sa.Column("action_source", sa.String(length=32), nullable=False),
        sa.Column("clamped", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("clamp_reason", sa.String(length=64), nullable=True),
        sa.Column("applied_phase", sa.SmallInteger(), nullable=False),
        sa.Column("applied_duration_s", sa.Float(), nullable=False),
        sa.Column("reward", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["junction_id"], ["junctions.id"]),
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )

    # 2. Turn control_decisions into TimescaleDB hypertable partitioned by 1-day chunks
    op.execute(
        "SELECT create_hypertable('control_decisions', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);"
    )

    # 3. Create indexes
    op.create_index(
        "ix_control_decisions_junction_ts",
        "control_decisions",
        ["junction_id", sa.text("timestamp DESC")],
    )
    op.create_index(
        "ix_control_decisions_controller_ts",
        "control_decisions",
        ["controller", sa.text("timestamp DESC")],
    )

    # 4. Create ab_runs table
    op.create_table(
        "ab_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("arm_a_controller", sa.String(length=32), nullable=False, server_default="webster"),
        sa.Column("arm_b_controller", sa.String(length=32), nullable=False, server_default="marl"),
        sa.Column("arm_a_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("arm_b_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("improvement", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ab_runs")
    op.drop_index("ix_control_decisions_controller_ts", table_name="control_decisions")
    op.drop_index("ix_control_decisions_junction_ts", table_name="control_decisions")
    op.drop_table("control_decisions")
