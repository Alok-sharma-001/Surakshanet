"""001b_datasource_provenance

Revision ID: 001b_datasource_provenance
Revises: 001_initial_schema
Create Date: 2026-09-10 11:00:00.000000

SN-008: TrafficReading.source defaults to the meaningless "live"; this migration
back-fills existing rows to 'mqtt', drops the 'live' default, sets nullable=False
with server_default='mqtt', and enforces an enum check constraint.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001b_datasource_provenance"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Back-fill existing rows: map 'sim' to 'sumo', and any others/NULL to 'mqtt'
    op.execute(
        "UPDATE traffic_readings SET source = 'sumo' WHERE source = 'sim';"
    )
    op.execute(
        "UPDATE traffic_readings SET source = 'mqtt' "
        "WHERE source IS NULL OR source NOT IN ('sumo', 'vision', 'mqtt', 'model', 'heuristic', 'manual');"
    )

    # 2. Alter column to NOT NULL with server_default='mqtt'
    op.alter_column(
        "traffic_readings",
        "source",
        existing_type=sa.String(),
        nullable=False,
        server_default="mqtt",
    )

    # 3. Add CHECK constraint for valid DataSource values
    op.create_check_constraint(
        "ck_traffic_readings_source",
        "traffic_readings",
        "source IN ('sumo', 'vision', 'mqtt', 'model', 'heuristic', 'manual')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_traffic_readings_source", "traffic_readings", type_="check")
    op.alter_column(
        "traffic_readings",
        "source",
        existing_type=sa.String(),
        nullable=True,
        server_default="live",
    )
