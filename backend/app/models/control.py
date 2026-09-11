import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Float, DateTime, ForeignKey, String,
    SmallInteger, Boolean, Integer, PrimaryKeyConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class ControlDecision(Base):
    """
    Records every signal control decision made by the system (SN-024).
    TimescaleDB hypertable partitioned by 1-day chunks on timestamp.
    """
    __tablename__ = "control_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, primary_key=True, default=datetime.utcnow, nullable=False)
    junction_id = Column(UUID(as_uuid=True), ForeignKey("junctions.id"), nullable=False)
    controller = Column(String(32), nullable=False)               # 'marl' | 'webster' | 'manual'
    model_version = Column(String(64), nullable=True)             # SHA-256 of weights file
    state_vector = Column(JSONB, nullable=False)                  # 8 values with names and raw values
    q_values = Column(JSONB, nullable=True)                       # Q-values for action 0 and 1
    action = Column(SmallInteger, nullable=False)                 # 0 = extend, 1 = advance
    action_source = Column(String(32), nullable=False)            # 'policy' | 'safety_clamp' | 'operator' | 'emergency'
    clamped = Column(Boolean, default=False, nullable=False)
    clamp_reason = Column(String(64), nullable=True)              # e.g. 'min_green_not_elapsed'
    applied_phase = Column(SmallInteger, nullable=False)
    applied_duration_s = Column(Float, nullable=False)
    reward = Column(Float, nullable=True)                         # computed on subsequent step
    source = Column(String(32), nullable=False)                   # telemetry source: 'sumo' | 'vision' | etc.

    __table_args__ = (
        PrimaryKeyConstraint("id", "timestamp"),
        Index("ix_control_decisions_junction_ts", "junction_id", text("timestamp DESC")),
        Index("ix_control_decisions_controller_ts", "controller", text("timestamp DESC")),
    )


class ABRun(Base):
    """
    Stores deterministic A/B test runs comparing MARL against Webster (SN-024, SN-038).
    """
    __tablename__ = "ab_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario = Column(String(64), nullable=False)
    seed = Column(Integer, nullable=False)
    duration_s = Column(Integer, nullable=False)
    arm_a_controller = Column(String(32), default="webster", nullable=False)
    arm_b_controller = Column(String(32), default="marl", nullable=False)
    arm_a_metrics = Column(JSONB, nullable=True)
    arm_b_metrics = Column(JSONB, nullable=True)
    improvement = Column(JSONB, nullable=True)
    status = Column(String(32), default="running", nullable=False)  # 'running' | 'complete' | 'failed'
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
