"""
SurakshaNet A/B Proof Endpoints (SN-038)
=======================================
Exposes endpoints for running and inspecting dual-arm simulation experiments:
POST /ab/run        - Trigger an A/B run (Webster vs MARL DQN)
GET  /ab/runs/{id}  - Retrieve run metrics and server-side improvement
GET  /ab/runs       - List past runs
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db, async_session_factory
from app.models.control import ABRun
from app.models.user import User
from app.models.audit import AuditActorType, AuditResult
from app.services.auth_service import require_role
from app.services.audit_service import write_audit
from services.control_service.ab_runner import (
    ABRunner,
    generate_ab_statement,
    DEMO_SEED,
)

logger = logging.getLogger("surakshanet.ab_api")
router = APIRouter(prefix="/ab", tags=["A/B Proof Harness"])


class ABRunRequest(BaseModel):
    scenario: str = Field(default="surge", description="Traffic demand scenario name")
    seed: int = Field(default=DEMO_SEED, description="Deterministic pseudo-random seed")
    duration_s: int = Field(default=900, ge=60, le=7200, description="Simulation duration in seconds")


class ABRunResponse(BaseModel):
    id: uuid.UUID
    scenario: str
    seed: int
    duration_s: int
    arm_a_controller: str
    arm_b_controller: str
    arm_a_metrics: Optional[Dict[str, Any]] = None
    arm_b_metrics: Optional[Dict[str, Any]] = None
    improvement: Optional[Dict[str, Any]] = None
    statement: Optional[str] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


async def _execute_ab_simulation(run_id: uuid.UUID, scenario: str, seed: int, duration_s: int):
    """Background task executing the dual simulation arms and updating the database."""
    runner = ABRunner()
    try:
        # Run blocking TraCI simulation in a thread pool executor
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            runner.run_ab_comparison,
            scenario,
            seed,
            duration_s
        )

        async with async_session_factory() as db:
            run_obj = await db.get(ABRun, run_id)
            if run_obj:
                run_obj.arm_a_metrics = result["arm_a_metrics"]
                run_obj.arm_b_metrics = result["arm_b_metrics"]
                run_obj.improvement = result["improvement"]
                run_obj.status = "complete"
                run_obj.completed_at = datetime.utcnow()
                db.add(run_obj)
                await db.commit()
                logger.info(f"A/B Run {run_id} completed successfully.")
    except Exception as e:
        logger.error(f"A/B Run {run_id} failed: {e}", exc_info=True)
        async with async_session_factory() as db:
            run_obj = await db.get(ABRun, run_id)
            if run_obj:
                run_obj.status = "failed"
                run_obj.completed_at = datetime.utcnow()
                db.add(run_obj)
                await db.commit()


@router.post("/run", response_model=ABRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_ab_run(
    req: ABRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", action="AB_RUN")),
):
    """
    Launch a deterministic A/B comparison run (Webster vs MARL DQN).
    Both arms run with identical seed, duration, network, and safety envelope (SN-100, SN-101, SN-104).
    Enforces max 1 concurrent A/B run.
    """
    # Enforce 1 concurrent run limit (SN-101)
    running_res = await db.execute(select(ABRun).where(ABRun.status == "running"))
    if running_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Only 1 concurrent A/B run allowed. An experiment is currently in progress. retry_after_s: 30",
            headers={"Retry-After": "30"}
        )

    run_id = uuid.uuid4()
    now = datetime.utcnow()

    run_row = ABRun(
        id=run_id,
        scenario=req.scenario,
        seed=req.seed,
        duration_s=req.duration_s,
        arm_a_controller="webster",
        arm_b_controller="marl",
        arm_a_metrics=None,
        arm_b_metrics=None,
        improvement=None,  # Rule R7: improvement absent while incomplete
        status="running",
        started_at=now,
        completed_at=None
    )
    db.add(run_row)
    await db.commit()
    await db.refresh(run_row)

    # Audit log (SN-104)
    corr_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    try:
        await write_audit(
            db=db,
            action="AB_RUN",
            actor_type=AuditActorType.USER,
            actor_id=current_user.id,
            target_type="ab_run",
            target_id=run_id,
            input_payload={"scenario": req.scenario, "seed": req.seed, "duration_s": req.duration_s},
            output_payload={"run_id": str(run_id), "status": "running"},
            result=AuditResult.SUCCESS,
            source="manual",
            correlation_id=corr_id,
        )
        await db.commit()
    except Exception:
        pass

    background_tasks.add_task(
        _execute_ab_simulation,
        run_id=run_id,
        scenario=req.scenario,
        seed=req.seed,
        duration_s=req.duration_s
    )

    return ABRunResponse(
        id=run_row.id,
        scenario=run_row.scenario,
        seed=run_row.seed,
        duration_s=run_row.duration_s,
        arm_a_controller=run_row.arm_a_controller,
        arm_b_controller=run_row.arm_b_controller,
        arm_a_metrics=None,
        arm_b_metrics=None,
        improvement=None,
        statement=None,
        status="running",
        started_at=run_row.started_at,
        completed_at=None
    )


@router.get("/runs/{run_id}", response_model=ABRunResponse)
async def get_ab_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "VIEWER")),
):
    """Retrieve an A/B run by ID. Improvement is absent until complete."""
    run_obj = await db.get(ABRun, run_id)
    if not run_obj:
        raise HTTPException(status_code=404, detail="A/B run not found")

    statement = None
    if run_obj.status == "complete" and run_obj.arm_a_metrics and run_obj.arm_b_metrics and run_obj.improvement:
        statement = generate_ab_statement(
            run_obj.scenario,
            run_obj.seed,
            run_obj.duration_s,
            run_obj.arm_a_metrics,
            run_obj.arm_b_metrics,
            run_obj.improvement
        )

    return ABRunResponse(
        id=run_obj.id,
        scenario=run_obj.scenario,
        seed=run_obj.seed,
        duration_s=run_obj.duration_s,
        arm_a_controller=run_obj.arm_a_controller,
        arm_b_controller=run_obj.arm_b_controller,
        arm_a_metrics=run_obj.arm_a_metrics,
        arm_b_metrics=run_obj.arm_b_metrics,
        improvement=run_obj.improvement if run_obj.status == "complete" else None,
        statement=statement,
        status=run_obj.status,
        started_at=run_obj.started_at,
        completed_at=run_obj.completed_at
    )


@router.get("/runs", response_model=List[ABRunResponse])
async def list_ab_runs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "VIEWER")),
):
    """List all historical A/B runs ordered by start time."""
    result = await db.execute(select(ABRun).order_by(desc(ABRun.started_at)).limit(50))
    runs = result.scalars().all()

    responses = []
    for r in runs:
        stmt = None
        if r.status == "complete" and r.arm_a_metrics and r.arm_b_metrics and r.improvement:
            stmt = generate_ab_statement(
                r.scenario,
                r.seed,
                r.duration_s,
                r.arm_a_metrics,
                r.arm_b_metrics,
                r.improvement
            )
        responses.append(ABRunResponse(
            id=r.id,
            scenario=r.scenario,
            seed=r.seed,
            duration_s=r.duration_s,
            arm_a_controller=r.arm_a_controller,
            arm_b_controller=r.arm_b_controller,
            arm_a_metrics=r.arm_a_metrics,
            arm_b_metrics=r.arm_b_metrics,
            improvement=r.improvement if r.status == "complete" else None,
            statement=stmt,
            status=r.status,
            started_at=r.started_at,
            completed_at=r.completed_at
        ))
    return responses
