"""007_governance

Revision ID: 007_governance
Revises: 006_incidents
Create Date: 2026-09-11 18:30:00.000000

SN-098: Add EMERGENCY_SERVICES and CITIZEN roles to userrole enum.
SN-102: AuditLog hypertable with composite PK (id, timestamp), 30-day chunks,
        and CHECK constraint that confidence is non-null only when actor_type = 'AI'.
SN-108: TimescaleDB retention policies for audit_logs, traffic_readings, control_decisions, and cv_detections.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "007_governance"
down_revision: Union[str, None] = "006_incidents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Extend userrole enum (SN-098)
    if is_postgres:
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'EMERGENCY_SERVICES'")
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'CITIZEN'")

    # 004_events_and_advisories already created a "minimal" audit_logs table
    # (single-column id PK, no model/model_version/confidence) for
    # EVENT_APPROVE/ADVISORY_PUBLISH. backend/app/models/audit.py's AuditLog
    # has since grown those AI-attribution fields and a composite (id,
    # timestamp) PK required for the TimescaleDB hypertable below — drop the
    # old table and its enum types (redefined with identical names below) so
    # the canonical governance-grade table can take its place. Recreated
    # verbatim at the end of downgrade() so migration 004's own downgrade
    # still has something to act on if the chain is downgraded past this one.
    op.drop_table("audit_logs")
    if is_postgres:
        op.execute("DROP TYPE IF EXISTS auditactortype")
        op.execute("DROP TYPE IF EXISTS auditresult")
        # Created explicitly rather than left to sa.Enum(...)'s implicit
        # checkfirst-create inside op.create_table() below: in this exact
        # drop-then-recreate-same-name-in-one-transaction sequence, that
        # implicit path raised "type auditactortype does not exist" at
        # CREATE TABLE time (verified live) — its existence check appears
        # not to see the type this same transaction just (re)dropped.
        # postgresql.ENUM(..., create_type=False) below then just references
        # these by name instead of trying to manage their lifecycle itself.
        op.execute("CREATE TYPE auditactortype AS ENUM ('USER', 'SYSTEM', 'AI')")
        op.execute("CREATE TYPE auditresult AS ENUM ('SUCCESS', 'FAILURE', 'DENIED')")

    # 2. Create audit_logs table (SN-102)
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column(
            "actor_type",
            postgresql.ENUM("USER", "SYSTEM", "AI", name="auditactortype", create_type=False) if is_postgres
            else sa.Enum("USER", "SYSTEM", "AI", name="auditactortype"),
            nullable=False,
            server_default="USER",
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            nullable=True,
        ),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(),
            nullable=True,
        ),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column(
            "result",
            postgresql.ENUM("SUCCESS", "FAILURE", "DENIED", name="auditresult", create_type=False) if is_postgres
            else sa.Enum("SUCCESS", "FAILURE", "DENIED", name="auditresult"),
            server_default="SUCCESS",
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", "timestamp"),
        sa.CheckConstraint(
            "(confidence IS NULL) OR (actor_type = 'AI')",
            name="ck_audit_logs_confidence_actor_ai",
        ),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)

    # 3. Hypertable & Retention Policies (SN-102, SN-108)
    if is_postgres:
        # Create hypertable if TimescaleDB extension is active
        op.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                ) THEN
                    PERFORM create_hypertable('audit_logs', 'timestamp', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);
                    
                    -- Add retention policies (SN-108)
                    BEGIN
                        PERFORM add_retention_policy('audit_logs', INTERVAL '1 year', if_not_exists => TRUE);
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END;
                    BEGIN
                        -- 001_initial_schema already added a 90-day retention
                        -- policy on traffic_readings; add_retention_policy's
                        -- if_not_exists => TRUE would silently no-op against
                        -- that existing policy, leaving the table at 90 days
                        -- instead of the 1 year documented in
                        -- docs/17-security-privacy.md §4 (verified live) —
                        -- remove the old policy first so the new interval
                        -- actually takes effect.
                        PERFORM remove_retention_policy('traffic_readings', if_exists => TRUE);
                        PERFORM add_retention_policy('traffic_readings', INTERVAL '1 year', if_not_exists => TRUE);
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END;
                    BEGIN
                        PERFORM add_retention_policy('control_decisions', INTERVAL '90 days', if_not_exists => TRUE);
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END;
                    BEGIN
                        PERFORM add_retention_policy('cv_detections', INTERVAL '72 hours', if_not_exists => TRUE);
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END;
                END IF;
            END $$;
        """)


def downgrade() -> None:
    """
    Downgrades migration 007 cleanly.
    
    PostgreSQL Enum Downgrade Procedure (SN-098):
    Postgres cannot drop enum values directly. To revert 'userrole' from
    ('ADMIN', 'OPERATOR', 'EMERGENCY_SERVICES', 'VIEWER', 'CITIZEN') back to
    ('ADMIN', 'OPERATOR', 'VIEWER'):
    1. Reassign any existing users with EMERGENCY_SERVICES or CITIZEN to VIEWER.
    2. CREATE TYPE userrole_old AS ENUM ('ADMIN', 'OPERATOR', 'VIEWER');
    3. ALTER TABLE users ALTER COLUMN role TYPE userrole_old USING role::text::userrole_old;
    4. DROP TYPE userrole;
    5. ALTER TYPE userrole_old RENAME TO userrole;
    """
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Drop retention policies if timescaledb active
    if is_postgres:
        op.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                    BEGIN
                        PERFORM remove_retention_policy('audit_logs', if_exists => TRUE);
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END;
                END IF;
            END $$;
        """)

    # 2. Drop audit_logs table
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")

    if is_postgres:
        op.execute("DROP TYPE IF EXISTS auditactortype")
        op.execute("DROP TYPE IF EXISTS auditresult")

        # 3. Revert userrole enum back to original 3 roles
        op.execute("""
            DO $$
            BEGIN
                -- Reassign any accounts using new roles to VIEWER
                UPDATE users SET role = 'VIEWER' WHERE role::text IN ('EMERGENCY_SERVICES', 'CITIZEN');

                CREATE TYPE userrole_downgrade AS ENUM ('ADMIN', 'OPERATOR', 'VIEWER');
                ALTER TABLE users ALTER COLUMN role DROP DEFAULT;
                ALTER TABLE users ALTER COLUMN role TYPE userrole_downgrade USING role::text::userrole_downgrade;
                ALTER TABLE users ALTER COLUMN role SET DEFAULT 'VIEWER'::userrole_downgrade;
                DROP TYPE userrole;
                ALTER TYPE userrole_downgrade RENAME TO userrole;
            EXCEPTION WHEN OTHERS THEN
                -- In case table does not exist or already downgraded
                NULL;
            END $$;
        """)

    # Recreate 004_events_and_advisories's original minimal audit_logs table
    # (and its enum types) verbatim, so that migration's own downgrade still
    # has something to act on if the chain is downgraded past this one.
    if is_postgres:
        # Explicit CREATE TYPE + create_type=False below — see the matching
        # comment in upgrade() for why sa.Enum(...)'s implicit checkfirst
        # create doesn't reliably see a type this same transaction just
        # dropped (verified live).
        op.execute("CREATE TYPE auditactortype AS ENUM ('USER', 'SYSTEM', 'AI')")
        op.execute("CREATE TYPE auditresult AS ENUM ('SUCCESS', 'FAILURE', 'DENIED')")
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), nullable=False),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "actor_type",
            postgresql.ENUM("USER", "SYSTEM", "AI", name="auditactortype", create_type=False) if is_postgres
            else sa.Enum("USER", "SYSTEM", "AI", name="auditactortype"),
            server_default="USER",
            nullable=False,
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column(
            "result",
            postgresql.ENUM("SUCCESS", "FAILURE", "DENIED", name="auditresult", create_type=False) if is_postgres
            else sa.Enum("SUCCESS", "FAILURE", "DENIED", name="auditresult"),
            server_default="SUCCESS",
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
