"""
SurakshaNet Autonomous Control Service (SN-030, SN-033, SN-037)
==============================================================
Main decision loop for real-time traffic signal optimization.
1. Consumes canonical telemetry from Redis (traffic_updates).
2. Builds exact 8-dimensional state representation (SN-034).
3. Routes to appropriate controller based on database signal_plans.mode (SN-033).
   - MarlController (greedy DQN inference with real weights)
   - WebsterController (flow-ratio & time-of-day fallback)
   - ManualController (operator manual override)
4. Enforces physical safety envelope and transition sequencing (SN-032).
5. Emits TraCI commands to Redis (control_commands).
6. Persists decisions to TimescaleDB (control_decisions) and streams via Redis (control_decisions).
7. Computes reward on subsequent step (SN-035).
8. Exports Prometheus observability metrics (SN-037).

Conforms strictly to docs/08-marl-control.md.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import redis.asyncio as aioredis

from app.config import get_settings
from app.models.control import ControlDecision
from app.models.junction import Junction
from app.models.signal import SignalPlan, SignalMode
try:
    from app.middleware.metrics import (
        CONTROL_DECISIONS_TOTAL,
        CONTROL_CLAMPS_TOTAL,
        CONTROL_INFERENCE_DURATION_SECONDS,
        CONTROL_STEP_LAG_SECONDS,
        CONTROL_FALLBACKS_TOTAL,
    )
except ImportError:
    from backend.app.middleware.metrics import (
        CONTROL_DECISIONS_TOTAL,
        CONTROL_CLAMPS_TOTAL,
        CONTROL_INFERENCE_DURATION_SECONDS,
        CONTROL_STEP_LAG_SECONDS,
        CONTROL_FALLBACKS_TOTAL,
    )
from shared.constants import REDIS_CHANNELS, DataSource
from shared.telemetry import validate_telemetry, resolve_junction_uuid, JunctionTelemetry, TelemetryValidationError
from services.control_service.config import ControlConfig, CONTROL_STEP_S
from services.control_service.controllers import MarlController, WebsterController, ManualController, ControllerDecision
from services.control_service.reward import RewardTracker
from services.control_service.safety import SafetyEnvelope, JunctionRuntimeState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [control_service] %(message)s"
)
logger = logging.getLogger("surakshanet.control_service")
settings = get_settings()


class ControlService:
    def __init__(self, cfg: Optional[ControlConfig] = None):
        self.cfg = cfg or ControlConfig()
        self.is_running = False
        self.engine = None
        self.async_session = None
        self.redis_client = None

        # Core controllers
        logger.info("Initializing controllers...")
        self.marl_controller = MarlController(self.cfg.weights_path)
        self.webster_controller = WebsterController()
        self.manual_controller = ManualController()
        self.safety_envelope = SafetyEnvelope(self.cfg)
        self.reward_tracker = RewardTracker(self.cfg.lambda_wait)

        # State tracking per junction
        self.junction_modes: Dict[str, SignalMode] = {}       # tl_id -> SignalMode
        self.junction_uuid_cache: Dict[str, uuid.UUID] = {}   # tl_id -> UUID
        self.last_decision_sim_time: Dict[str, float] = {}    # tl_id -> last sim_time
        self.last_decision_real_time: Dict[str, float] = {}   # tl_id -> last perf_counter
        self.last_decision_id: Dict[str, uuid.UUID] = {}      # tl_id -> previous decision UUID
        self.last_decision_ts: Dict[str, datetime] = {}       # tl_id -> previous decision timestamp
        self.cycles_since_ped: Dict[str, int] = {}            # tl_id -> cycle count
        self.cmd_seq: Dict[str, int] = {}                     # tl_id -> monotonic command sequence

        # Verification of MARL readiness
        if not self.marl_controller.is_loaded:
            logger.warning(
                "🚨 MARL policy weights are unavailable. Control service will REFUSE MARL mode "
                "and operate under Webster fallback honestly. No fake decisions will be emitted."
            )
        else:
            logger.info(f"✅ MARL Controller verified with policy hash {self.marl_controller.model_version[:16]}...")

    async def start(self):
        """Start database connections, Redis subscriptions, and background workers."""
        self.is_running = True
        logger.info("Starting SurakshaNet Autonomous Control Service...")

        # Setup database
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        # Setup Redis
        self.redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)

        # Pre-load mode cache from database
        await self._refresh_mode_cache()

        # Launch background tasks
        asyncio.create_task(self._mode_poller_loop())
        asyncio.create_task(self._traffic_telemetry_listener())
        asyncio.create_task(self._signal_events_listener())

        logger.info("Control Service fully active and listening for telemetry.")

    async def stop(self):
        """Gracefully release junctions and shut down connections."""
        self.is_running = False
        logger.info("Stopping Control Service...")

        if self.redis_client:
            await self.redis_client.close()
        if self.engine:
            await self.engine.dispose()
        logger.info("Control Service shutdown complete.")

    async def _refresh_mode_cache(self):
        """Poll database signal_plans to refresh configured junction modes (SN-033)."""
        try:
            async with self.async_session() as db:
                result = await db.execute(
                    select(SignalPlan.junction_id, SignalPlan.mode, Junction.name)
                    .join(Junction, SignalPlan.junction_id == Junction.id)
                    .where(SignalPlan.is_active.is_(True))
                )
                rows = result.all()
                for j_uuid, mode, name in rows:
                    if name:
                        self.junction_modes[name] = mode
                        self.junction_uuid_cache[name] = j_uuid
                    self.junction_modes[str(j_uuid)] = mode
                    self.junction_uuid_cache[str(j_uuid)] = j_uuid
        except Exception as e:
            logger.warning(f"Error refreshing signal mode cache from DB: {e}")

    async def _mode_poller_loop(self):
        """Periodically refresh signal mode cache every 5.0 seconds."""
        while self.is_running:
            try:
                await asyncio.sleep(self.cfg.mode_poll_interval_s if hasattr(self.cfg, "mode_poll_interval_s") else 5.0)
                await self._refresh_mode_cache()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in mode poller loop: {e}")

    async def _signal_events_listener(self):
        """Listen for real-time mode changes and emergency pre-emptions."""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(REDIS_CHANNELS["signals"])

        try:
            while self.is_running:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg:
                    await asyncio.sleep(0.05)
                    continue

                raw_data = msg.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")

                try:
                    payload = json.loads(raw_data)
                    p_type = payload.get("type")
                    if p_type == "SIGNAL_MODE_CHANGED":
                        jid = payload.get("junction_id")
                        mode_str = payload.get("mode", "").upper()
                        if jid and mode_str in SignalMode.__members__:
                            self.junction_modes[jid] = SignalMode[mode_str]
                            logger.info(f"Signal mode updated via event: {jid} -> {mode_str}")
                except Exception as e:
                    logger.warning(f"Error processing signal event: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(REDIS_CHANNELS["signals"])
            await pubsub.close()

    async def _traffic_telemetry_listener(self):
        """Listen to incoming canonical telemetry on traffic_updates and trigger decision loop."""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(REDIS_CHANNELS["traffic"])

        try:
            while self.is_running:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg:
                    await asyncio.sleep(0.02)
                    continue

                raw_data = msg.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")

                try:
                    payload = json.loads(raw_data)
                    # Filter out non-JunctionTelemetry updates if any
                    if "approaches" not in payload:
                        continue

                    telemetry = validate_telemetry(payload)
                    await self.process_telemetry_step(telemetry)
                except TelemetryValidationError as e:
                    logger.warning(f"Dropped non-canonical telemetry: {e}")
                except Exception as e:
                    logger.error(f"Error handling telemetry in control loop: {e}", exc_info=True)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(REDIS_CHANNELS["traffic"])
            await pubsub.close()

    async def process_telemetry_step(self, telemetry: JunctionTelemetry):
        """
        Processes one telemetry reading for a junction.
        Evaluates whether a control step has elapsed, and if so executes inference,
        safety envelope, command emission, and persistence.
        """
        tl_id = telemetry.junction_id
        now_sim = telemetry.sim_time_s
        now_real = time.perf_counter()

        # Determine if step interval has elapsed
        if now_sim is not None:
            last_sim = self.last_decision_sim_time.get(tl_id)
            if last_sim is not None and (now_sim - last_sim) < self.cfg.control_step_s:
                return
            step_lag = (now_sim - last_sim - self.cfg.control_step_s) if last_sim is not None else 0.0
            CONTROL_STEP_LAG_SECONDS.labels(junction=tl_id).set(max(0.0, step_lag))
            self.last_decision_sim_time[tl_id] = now_sim
        else:
            last_real = self.last_decision_real_time.get(tl_id)
            if last_real is not None and (now_real - last_real) < self.cfg.control_step_s:
                return
            step_lag = (now_real - last_real - self.cfg.control_step_s) if last_real is not None else 0.0
            CONTROL_STEP_LAG_SECONDS.labels(junction=tl_id).set(max(0.0, step_lag))
            self.last_decision_real_time[tl_id] = now_real

        # 1. Build 8-dimensional state vector (SN-034)
        from services.control_service.state import build_state_vector
        last_time = self.last_decision_sim_time.get(tl_id)
        state_result = build_state_vector(telemetry, self.cfg, last_time)

        # 2. Select controller by SignalMode and availability (SN-030, SN-031, SN-033)
        configured_mode = self.junction_modes.get(tl_id, SignalMode.MARL)
        controller_name = "webster"
        chosen_controller = self.webster_controller

        if not state_result.is_valid:
            logger.warning(f"Fallback to Webster for {tl_id}: {state_result.fallback_reason}")
            CONTROL_FALLBACKS_TOTAL.labels(reason=state_result.fallback_reason).inc()
            controller_name = "webster"
            chosen_controller = self.webster_controller
        elif configured_mode == SignalMode.MARL:
            if not self.marl_controller.is_loaded:
                CONTROL_FALLBACKS_TOTAL.labels(reason="marl_weights_unavailable").inc()
                controller_name = "webster (marl weights unavailable)"
                chosen_controller = self.webster_controller
            else:
                controller_name = "marl"
                chosen_controller = self.marl_controller
        elif configured_mode == SignalMode.MANUAL:
            controller_name = "manual"
            chosen_controller = self.manual_controller
        else:
            controller_name = "webster"
            chosen_controller = self.webster_controller

        # 3. Controller Inference
        t_start = time.perf_counter()
        decision_result: ControllerDecision = chosen_controller.select_action(
            junction_id=tl_id,
            state_vector=state_result.numpy_vector,
            current_phase=telemetry.current_phase,
            phase_elapsed_s=telemetry.phase_elapsed_s
        )
        inf_duration = time.perf_counter() - t_start
        CONTROL_INFERENCE_DURATION_SECONDS.labels(controller=chosen_controller.controller_name).observe(inf_duration)

        # 4. Mandatory Safety Envelope outside the policy (SN-032)
        ped_cycles = self.cycles_since_ped.get(tl_id, 0)
        runtime_state = JunctionRuntimeState(
            junction_id=tl_id,
            current_phase=telemetry.current_phase,
            phase_elapsed_s=telemetry.phase_elapsed_s,
            cycles_since_pedestrian_phase=ped_cycles
        )
        safety_res = self.safety_envelope.evaluate(
            action=decision_result.action,
            state=runtime_state,
            controller_name=controller_name
        )

        if safety_res.clamped:
            CONTROL_CLAMPS_TOTAL.labels(reason=safety_res.clamp_reason).inc()

        CONTROL_DECISIONS_TOTAL.labels(
            junction=tl_id,
            controller=controller_name,
            action=str(safety_res.action)
        ).inc()

        # Update pedestrian cycle tracker
        if safety_res.applied_phase != telemetry.current_phase:
            self.cycles_since_ped[tl_id] = 0
        else:
            self.cycles_since_ped[tl_id] = ped_cycles + 1

        # 5. Compute reward on subsequent step (SN-035)
        current_total_queue = sum(a.pcu for a in telemetry.approaches)
        current_total_wait = sum(a.accumulated_wait_s for a in telemetry.approaches)
        step_reward = self.reward_tracker.step(tl_id, current_total_queue, current_total_wait)

        prev_dec_id = self.last_decision_id.get(tl_id)
        prev_dec_ts = self.last_decision_ts.get(tl_id)

        # 6. Database persistence & identity resolution (SN-024)
        decision_id = uuid.uuid4()
        decision_ts = datetime.now(timezone.utc)
        self.last_decision_id[tl_id] = decision_id
        self.last_decision_ts[tl_id] = decision_ts

        j_uuid = await self._resolve_junction(tl_id)

        if j_uuid:
            try:
                async with self.async_session() as db:
                    # Update reward on previous step
                    if prev_dec_id and prev_dec_ts and step_reward is not None:
                        await db.execute(
                            update(ControlDecision)
                            .where(ControlDecision.id == prev_dec_id, ControlDecision.timestamp == prev_dec_ts)
                            .values(reward=step_reward)
                        )

                    # Persist current decision
                    decision_row = ControlDecision(
                        id=decision_id,
                        timestamp=decision_ts,
                        junction_id=j_uuid,
                        controller=controller_name,
                        model_version=decision_result.model_version,
                        state_vector=state_result.to_dict(),
                        q_values=decision_result.q_values,
                        action=safety_res.action,
                        action_source=safety_res.action_source,
                        clamped=safety_res.clamped,
                        clamp_reason=safety_res.clamp_reason,
                        applied_phase=safety_res.applied_phase,
                        applied_duration_s=safety_res.applied_duration_s,
                        reward=None,
                        source=telemetry.source.value
                    )
                    db.add(decision_row)
                    await db.commit()
            except Exception as e:
                logger.error(f"Error persisting ControlDecision for {tl_id}: {e}")

        # 7. Emit TraCI control command to Redis (control_commands)
        self.cmd_seq[tl_id] = self.cmd_seq.get(tl_id, 0) + 1
        seq = self.cmd_seq[tl_id]

        cmd_payload = {
            "type": "SET_PHASE",
            "junction_id": tl_id,
            "phase": safety_res.applied_phase,
            "duration_s": safety_res.applied_duration_s,
            "seq": seq,
            "issued_by": "control_service",
            "controller": controller_name,
            "decision_id": str(decision_id),
            "timestamp": decision_ts.isoformat()
        }
        await self.redis_client.publish(
            REDIS_CHANNELS["control_commands"],
            json.dumps(cmd_payload)
        )

        # 8. Publish to Redis for WebSocket /ws/control stream (SN-029)
        ws_event = {
            "type": "CONTROL_DECISION",
            "decision_id": str(decision_id),
            "junction_id": tl_id,
            "controller": controller_name,
            "action": safety_res.action,
            "action_label": "advance" if safety_res.action == 1 else "extend",
            "applied_phase": safety_res.applied_phase,
            "duration_s": safety_res.applied_duration_s,
            "clamped": safety_res.clamped,
            "clamp_reason": safety_res.clamp_reason,
            "q_values": decision_result.q_values,
            "model_version": decision_result.model_version,
            "timestamp": decision_ts.isoformat()
        }
        await self.redis_client.publish(
            REDIS_CHANNELS["control_decisions"],
            json.dumps(ws_event)
        )

        logger.debug(
            f"⚡ [DECISION] {tl_id} | {controller_name} | action={safety_res.action} "
            f"({'ADVANCE' if safety_res.action == 1 else 'EXTEND'}) | "
            f"clamped={safety_res.clamped} ({safety_res.clamp_reason}) | phase={safety_res.applied_phase}"
        )

    async def _resolve_junction(self, identifier: str) -> Optional[uuid.UUID]:
        """Resolves junction string identifier to database UUID."""
        if identifier in self.junction_uuid_cache:
            return self.junction_uuid_cache[identifier]

        u = resolve_junction_uuid(identifier)
        if u:
            self.junction_uuid_cache[identifier] = u
            return u

        try:
            async with self.async_session() as db:
                result = await db.execute(select(Junction).where(Junction.name.ilike(identifier)))
                j = result.scalars().first()
                if j:
                    self.junction_uuid_cache[identifier] = j.id
                    return j.id
        except Exception as e:
            logger.warning(f"Failed to resolve junction {identifier}: {e}")

        return None


async def main():
    service = ControlService()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(service.stop()))

    try:
        await service.start()
        while service.is_running:
            await asyncio.sleep(1.0)
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
