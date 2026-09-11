import logging
import time
from typing import Dict, List, Any, Optional, Tuple

from shared.constants import (
    EMERGENCY_CONFIG,
    SIGNAL_CONSTRAINTS,
    DataSource,
)

logger = logging.getLogger("surakshanet.green_wave")

# How far back real cross-street delay samples are kept, and how long a
# closed corridor keeps accepting samples before recovery is reported
# unresolved rather than guessed at.
SAMPLE_RETENTION_S = 180.0
RECOVERY_BASELINE_WINDOW_S = 120.0
RECOVERY_SEARCH_WINDOW_S = 600.0
RECOVERY_TOLERANCE_FACTOR = 1.10
RECOVERY_CONSECUTIVE_REQUIRED = 3


class ProgramLogicCapture:
    """Serializable capture of a junction's signal program logic (SN-044)."""

    @staticmethod
    def serialize_logics(logics: Any) -> List[Dict[str, Any]]:
        """Serializes TraCI Logic objects or dicts into JSON-compatible format."""
        if not logics:
            return []
        serialized = []
        for logic in logics:
            if isinstance(logic, dict):
                serialized.append(logic)
            else:
                subphases = []
                if hasattr(logic, "phases"):
                    for p in logic.phases:
                        subphases.append({
                            "duration": getattr(p, "duration", 30.0),
                            "state": getattr(p, "state", "rrrr"),
                            "minDur": getattr(p, "minDur", 5.0),
                            "maxDur": getattr(p, "maxDur", 60.0),
                        })
                serialized.append({
                    "programID": getattr(logic, "programID", "0"),
                    "type": getattr(logic, "type", 0),
                    "currentPhaseIndex": getattr(logic, "currentPhaseIndex", 0),
                    "phases": subphases,
                    "subParameter": getattr(logic, "subParameter", {}),
                })
        return serialized

    @staticmethod
    def deserialize_logics(serialized_logics: List[Dict[str, Any]]) -> Any:
        """Reconstructs TraCI Logic objects when traci is available, else returns the raw structure."""
        try:
            import traci
            deserialized = []
            for item in serialized_logics:
                phases = []
                for p in item.get("phases", []):
                    phases.append(
                        traci.trafficlight.Phase(
                            p.get("duration", 30.0),
                            p.get("state", "rrrr"),
                            p.get("minDur", 5.0),
                            p.get("maxDur", 60.0)
                        )
                    )
                logic = traci.trafficlight.Logic(
                    item.get("programID", "0"),
                    item.get("type", 0),
                    item.get("currentPhaseIndex", 0),
                    phases,
                    item.get("subParameter", {})
                )
                deserialized.append(logic)
            return deserialized
        except (ImportError, Exception):
            return serialized_logics


class GreenWaveController:
    """Emergency green-wave controller implementing rolling corridor pre-emption,

    real signal program capture/restoration/verification, cross-street starvation
    protection, and post-corridor recovery delay measurement from real samples.
    Conforms to docs/10-emergency-corridor.md (SN-039..SN-048).

    Capture/restore only do anything when called from a process holding a live
    TraCI connection (or given a test/mock `env`). Recovery measurement only
    produces a result once real delay samples have actually been fed in via
    `ingest_delay_sample` — it never invents a curve.
    """

    def __init__(
        self,
        lookahead: int = EMERGENCY_CONFIG.get("lookahead_junctions", 3),
        green_hold_s: float = EMERGENCY_CONFIG.get("green_hold_s", 30.0),
        cross_street_max_red_s: float = EMERGENCY_CONFIG.get("cross_street_max_red_s", 90.0),
    ):
        self.lookahead = lookahead
        self.green_hold_s = green_hold_s
        self.cross_street_max_red_s = cross_street_max_red_s

        self.active_events: Dict[str, Dict[str, Any]] = {}
        self.completed_events: Dict[str, Dict[str, Any]] = {}

        # Fallback inter-junction distance, used ONLY when the caller does not
        # supply real per-edge lengths (e.g. from the routing graph). Real
        # callers should pass `edge_lengths_m` to `activate`/`compute_route_etas`.
        self.default_link_length_m = 300.0

        # Continuous rolling cross-street delay samples, independent of any one
        # corridor event, keyed by junction_id -> [(t, delay_s), ...]. Fed by
        # whoever has live telemetry (normally the SUMO bridge process).
        self.delay_samples: Dict[str, List[Tuple[float, float]]] = {}
        # event_id -> True while that completed event still wants incoming
        # samples routed into its recovery series.
        self._recovery_open: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Live telemetry ingestion (real samples, not a formula)
    # ------------------------------------------------------------------

    def ingest_delay_sample(self, junction_id: str, delay_s: float, t: Optional[float] = None) -> None:
        """Records one real cross-street delay measurement for a junction.

        Called continuously by the process with live telemetry (the SUMO
        bridge), independent of whether a corridor is active, so a genuine
        pre-activation baseline is available the moment a corridor starts.
        """
        t = t if t is not None else time.time()
        buf = self.delay_samples.setdefault(junction_id, [])
        buf.append((t, delay_s))
        cutoff = t - SAMPLE_RETENTION_S
        while buf and buf[0][0] < cutoff:
            buf.pop(0)

        for event_id, still_open in list(self._recovery_open.items()):
            if not still_open:
                continue
            event = self.completed_events.get(event_id)
            if not event or junction_id not in event.get("route", []):
                continue
            self._record_recovery_sample(event, t, delay_s)

    def _baseline_for_route(self, route: List[str], now: float) -> Optional[float]:
        """Averages real samples from the last RECOVERY_BASELINE_WINDOW_S seconds."""
        cutoff = now - RECOVERY_BASELINE_WINDOW_S
        values = []
        for jid in route:
            for ts, delay_s in self.delay_samples.get(jid, []):
                if ts >= cutoff:
                    values.append(delay_s)
        if not values:
            return None
        return sum(values) / len(values)

    # ------------------------------------------------------------------
    # ETA computation (SN-042)
    # ------------------------------------------------------------------

    def compute_route_etas(
        self,
        route: List[str],
        telemetry_by_junction: Optional[Dict[str, Any]] = None,
        link_speeds: Optional[Dict[str, float]] = None,
        edge_lengths_m: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Calculates per-junction ETA from live link speeds (SN-042).

        eta_j = Σ (link_length_i / max(current_speed_i * 1.3, min_speed_floor))
                + Σ intersection_delay_k

        `edge_lengths_m` maps "{from}_{to}" -> real length in meters, sourced
        from the routing graph. Falls back to `default_link_length_m` only
        when the caller has no real topology to hand over.
        """
        min_floor_mps = EMERGENCY_CONFIG.get("min_speed_floor_kmh", 5.0) / 3.6
        speed_factor = EMERGENCY_CONFIG.get("emergency_speed_factor", 1.3)
        free_flow_speed_mps = 50.0 / 3.6

        cumulative_time_s = 0.0
        etas = []

        for idx, jid in enumerate(route):
            if idx == 0:
                transit_time_s = 100.0 / (free_flow_speed_mps * speed_factor)
                intersection_delay_s = 10.0
                cumulative_time_s += transit_time_s + intersection_delay_s
            else:
                prev_jid = route[idx - 1]
                edge_key = f"{prev_jid}_{jid}"

                speed_kmh = 45.0
                if link_speeds and edge_key in link_speeds:
                    speed_kmh = link_speeds[edge_key]
                elif telemetry_by_junction and jid in telemetry_by_junction:
                    tj = telemetry_by_junction[jid]
                    approaches = tj.get("approaches", [])
                    if approaches:
                        speed_kmh = approaches[0].get("mean_speed_kmh", 45.0)

                speed_mps = (speed_kmh / 3.6) * speed_factor
                eff_speed_mps = min(free_flow_speed_mps, max(speed_mps, min_floor_mps))

                link_length = (
                    edge_lengths_m.get(edge_key, self.default_link_length_m)
                    if edge_lengths_m
                    else self.default_link_length_m
                )
                transit_time = link_length / eff_speed_mps

                intersection_delay = 12.0
                cumulative_time_s += transit_time + intersection_delay

            queue_pcu = 0.0
            if telemetry_by_junction and jid in telemetry_by_junction:
                tj = telemetry_by_junction[jid]
                approaches = tj.get("approaches", [])
                if approaches:
                    queue_pcu = approaches[0].get("pcu", 0.0)

            sat_flow = EMERGENCY_CONFIG.get("saturation_flow_pcu_per_s", 0.5)
            queue_discharge_s = queue_pcu / sat_flow if sat_flow > 0 else 0.0

            clearance_lead_s = (
                SIGNAL_CONSTRAINTS.get("amber_s", 3)
                + SIGNAL_CONSTRAINTS.get("all_red_s", 2)
                + queue_discharge_s
            )

            eta_val = round(cumulative_time_s, 1)
            activate_at = max(0.0, round(eta_val - clearance_lead_s, 1))

            etas.append({
                "junction_id": jid,
                "eta_s": eta_val,
                "clearance_lead_s": round(clearance_lead_s, 1),
                "activate_at_s": activate_at,
                "state": "scheduled",
                "activated_at": None,
                "passed_at": None,
                "restored_at": None,
                "capture_failed": False,
                "restore_failed": False,
                "timeout_limit_s": round(eta_val + queue_discharge_s + 45.0, 1),
            })

        for i in range(1, len(etas)):
            if etas[i]["eta_s"] <= etas[i - 1]["eta_s"]:
                etas[i]["eta_s"] = round(etas[i - 1]["eta_s"] + 15.0, 1)
                etas[i]["activate_at_s"] = max(0.0, round(etas[i]["eta_s"] - etas[i]["clearance_lead_s"], 1))

        return etas

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def activate(
        self,
        event_id: str,
        priority: str,
        vehicle_type: str,
        route_junction_ids: List[str],
        origin: Optional[Dict[str, float]] = None,
        destination: Optional[Dict[str, Any]] = None,
        vehicle_id: Optional[str] = None,
        env: Any = None,
        telemetry_by_junction: Optional[Dict[str, Any]] = None,
        link_speeds: Optional[Dict[str, float]] = None,
        edge_lengths_m: Optional[Dict[str, float]] = None,
        start_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Activates a green wave corridor with rolling activation scheduling (SN-043).

        `origin`/`destination` are stored exactly as given — including None —
        never defaulted to an invented coordinate (SN-049's principle applies
        to every field, not just the route list).
        """
        now = start_time if start_time is not None else time.time()
        vid = vehicle_id or f"AMB-{event_id[:4].upper()}"

        route_etas = self.compute_route_etas(
            route_junction_ids,
            telemetry_by_junction=telemetry_by_junction,
            link_speeds=link_speeds,
            edge_lengths_m=edge_lengths_m,
        )

        final_eta = route_etas[-1]["eta_s"] if route_etas else 60.0
        final_clearance_lead = route_etas[-1]["clearance_lead_s"] if route_etas else 15.0
        clearance_time_s = round(final_eta + final_clearance_lead, 1)

        baseline_delay_s = self._baseline_for_route(route_junction_ids, now)

        event_data = {
            "id": event_id,
            "vehicle_id": vid,
            "priority": priority,
            "vehicle_type": vehicle_type,
            "route": route_junction_ids,
            "origin": origin,
            "destination": destination,
            "route_etas": route_etas,
            "current_index": 0,
            "current_position": {"link_id": f"W_{route_junction_ids[0]}", "progress": 0.0},
            "captured_programs": {},
            "cross_street": {
                "max_red_s": 0.0,
                "threshold_s": self.cross_street_max_red_s,
                "compensating_phase_inserted": False,
                "accumulated_red_per_junction": {jid: 0.0 for jid in route_junction_ids},
            },
            "clearance_time_s": clearance_time_s,
            "started_at": now,
            "elapsed_s": 0.0,
            "status": "ACTIVE",
            "restored_at": None,
            "recovery": {
                "baseline_delay_s": baseline_delay_s,
                "baseline_available": baseline_delay_s is not None,
                "peak_delay_s": baseline_delay_s,
                "recovery_s": None,
                "series": [],
                "consecutive_normal_samples": 0,
                "resolved": False,
            },
        }

        self.active_events[event_id] = event_data
        self.step_corridor(event_id, elapsed_s=0.0, env=env)

        return {
            "status": "activated",
            "event_id": event_id,
            "route": route_junction_ids,
            "route_etas": route_etas,
            "clearance_time_s": clearance_time_s,
            "activation_policy": "rolling",
            "source": DataSource.SUMO.value,
        }

    def capture_program(self, junction_id: str, env: Any = None) -> Optional[Dict[str, Any]]:
        """Captures real signal program logic from TraCI or a supplied environment (SN-044).

        Returns None when no real capture is possible — it never invents a
        plausible-looking program. A junction that cannot be safely captured
        is not pre-empted, matching the safety reasoning the pre-Phase-3 code
        already documented: pre-empting without a real plan to restore leaves
        the junction stuck.
        """
        if env is not None:
            captured = {
                "program_id": "0",
                "phase_index": 0,
                "logics": [],
                "captured_at": time.time(),
            }
            got_logics = False
            if hasattr(env, "get_program_logics"):
                logics = env.get_program_logics(junction_id)
                captured["logics"] = ProgramLogicCapture.serialize_logics(logics)
                got_logics = bool(captured["logics"])
                if captured["logics"] and "programID" in captured["logics"][0]:
                    captured["program_id"] = str(captured["logics"][0]["programID"])
            if hasattr(env, "get_program"):
                captured["program_id"] = str(env.get_program(junction_id))
            if hasattr(env, "get_phase"):
                captured["phase_index"] = int(env.get_phase(junction_id))
            if not got_logics:
                logger.warning(f"env provided for {junction_id} but returned no program logics; treating as capture failure.")
                return None
            return captured

        try:
            import traci
            logics = traci.trafficlight.getAllProgramLogics(junction_id)
            if not logics:
                logger.warning(f"TraCI returned no program logics for junction {junction_id}; capture failed.")
                return None
            current_program = traci.trafficlight.getProgram(junction_id)
            current_phase = traci.trafficlight.getPhase(junction_id)
            captured = {
                "program_id": str(current_program),
                "phase_index": int(current_phase),
                "logics": ProgramLogicCapture.serialize_logics(logics),
                "captured_at": time.time(),
            }
            logger.info(f"Captured real TraCI program for junction {junction_id}: program={current_program}")
            return captured
        except ImportError:
            logger.warning(f"No TraCI connection available; cannot capture real program for {junction_id}.")
            return None
        except Exception as e:
            logger.warning(f"TraCI capture failed for junction {junction_id}: {e}")
            return None

    def restore_and_verify_program(
        self,
        junction_id: str,
        captured_data: Dict[str, Any],
        env: Any = None
    ) -> bool:
        """Restores captured program logic and asserts exact equality (SN-045).

        Returns the real outcome. A restoration that cannot be verified is
        reported as failed — it is never assumed to have succeeded.
        """
        if not captured_data or not captured_data.get("logics"):
            logger.warning(f"No captured program for {junction_id}; cannot verify restoration.")
            return False

        if env is not None:
            if hasattr(env, "restore_program_logic"):
                ok = bool(env.restore_program_logic(junction_id, captured_data))
                if not ok:
                    logger.error(f"env restore_program_logic reported failure for {junction_id}.")
                return ok
            if hasattr(env, "restore_plan"):
                env.restore_plan(junction_id, captured_data)
                return True
            logger.warning(f"env provided for {junction_id} has no restore hook; cannot verify restoration.")
            return False

        try:
            import traci
            deserialized = ProgramLogicCapture.deserialize_logics(captured_data["logics"])
            if isinstance(deserialized, list) and deserialized and hasattr(deserialized[0], "phases"):
                traci.trafficlight.setProgramLogic(junction_id, deserialized[0])
            traci.trafficlight.setProgram(junction_id, str(captured_data["program_id"]))
            traci.trafficlight.setPhase(junction_id, int(captured_data["phase_index"]))

            readback_logics = traci.trafficlight.getAllProgramLogics(junction_id)
            readback_serialized = ProgramLogicCapture.serialize_logics(readback_logics)
            if readback_serialized == captured_data["logics"]:
                logger.info(f"Verified exact program logic restoration for junction {junction_id}.")
                return True
            logger.error(f"Program readback mismatch for junction {junction_id}; restoration NOT verified.")
            return False
        except ImportError:
            logger.warning(f"No TraCI connection available; cannot verify restoration for {junction_id}.")
            return False
        except Exception as e:
            logger.error(f"TraCI restoration failed for junction {junction_id}: {e}")
            return False

    def step_corridor(
        self,
        event_id: str,
        elapsed_s: float,
        env: Any = None,
        vehicle_progress: Optional[float] = None,
        absolute_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Periodic tick: activates/restores junctions on the rolling schedule,

        tracks cross-street red time, and feeds the recovery baseline.

        `elapsed_s` is relative to this corridor's own start (what the ETA
        schedule is expressed in). `absolute_time`, when the caller has one
        (the bridge's own simulation clock), is threaded through to
        `deactivate()` so recovery sampling — which is measured on that same
        absolute clock via `ingest_delay_sample` — isn't compared against a
        relative timestamp from a different time base.
        """
        if event_id not in self.active_events:
            return {"status": "error", "message": "Event not found"}

        event = self.active_events[event_id]
        event["elapsed_s"] = elapsed_s

        route = event["route"]
        route_etas = event["route_etas"]

        total_time = route_etas[-1]["eta_s"] if route_etas else 100.0
        norm_progress = vehicle_progress if vehicle_progress is not None else min(1.0, max(0.0, elapsed_s / total_time))

        total_junctions = len(route)
        vehicle_j_index = min(total_junctions - 1, int(norm_progress * total_junctions))
        event["current_index"] = vehicle_j_index

        current_jid = route[vehicle_j_index]
        next_jid = route[min(total_junctions - 1, vehicle_j_index + 1)]
        event["current_position"] = {
            "link_id": f"{current_jid}_{next_jid}",
            "progress": round(norm_progress, 2),
            "current_junction": current_jid,
        }

        def _finalize_passed(entry: Dict[str, Any], jid: str, t: float):
            entry["passed_at"] = t
            captured = event["captured_programs"].get(jid)
            if captured:
                ok = self.restore_and_verify_program(jid, captured, env=env)
                if ok:
                    entry["state"] = "restored"
                    entry["restored_at"] = t
                else:
                    entry["state"] = "restore_failed"
                    entry["restore_failed"] = True
                    entry["restored_at"] = t
                    logger.error(
                        f"Corridor {event_id}: junction {jid} could not be verifiably restored; "
                        f"released to control service without a confirmed match."
                    )
            else:
                # Never pre-empted (capture was unavailable) — nothing to restore.
                entry["state"] = "passed_unmanaged"

        for idx, entry in enumerate(route_etas):
            jid = entry["junction_id"]
            current_state = entry["state"]

            if idx < vehicle_j_index:
                if current_state in ("scheduled", "preempted"):
                    _finalize_passed(entry, jid, elapsed_s)
                    logger.info(f"Corridor {event_id}: junction {jid} passed ({entry['state']}).")

            elif idx == vehicle_j_index:
                if elapsed_s >= entry["eta_s"] and norm_progress > (idx / total_junctions):
                    if current_state not in ("restored", "restore_failed", "passed_unmanaged"):
                        _finalize_passed(entry, jid, elapsed_s)
                elif elapsed_s >= entry["activate_at_s"] and current_state == "scheduled":
                    self._try_preempt(event, entry, jid, elapsed_s, env)

            else:
                if elapsed_s >= entry["activate_at_s"] and current_state == "scheduled":
                    self._try_preempt(event, entry, jid, elapsed_s, env)

            if entry["state"] == "preempted":
                preempted_duration = elapsed_s - (entry["activated_at"] or elapsed_s)
                if preempted_duration > entry["timeout_limit_s"]:
                    logger.warning(
                        f"Corridor {event_id}: junction {jid} preemption timed out "
                        f"({preempted_duration}s > {entry['timeout_limit_s']}s). Releasing to normal cycle."
                    )
                    captured = event["captured_programs"].get(jid)
                    if captured:
                        ok = self.restore_and_verify_program(jid, captured, env=env)
                        entry["state"] = "restored" if ok else "restore_failed"
                        entry["restore_failed"] = not ok
                    else:
                        entry["state"] = "passed_unmanaged"
                    entry["restored_at"] = elapsed_s
                    entry["passed_at"] = entry["passed_at"] or elapsed_s
                    entry["timeout_reason"] = "occupancy_limit_exceeded"

        cross_info = event["cross_street"]
        max_accumulated_red = 0.0
        for entry in route_etas:
            jid = entry["junction_id"]
            if entry["state"] == "preempted":
                cross_info["accumulated_red_per_junction"][jid] += 2.0
                max_accumulated_red = max(max_accumulated_red, cross_info["accumulated_red_per_junction"][jid])

        cross_info["max_red_s"] = max(cross_info.get("max_red_s", 0.0), max_accumulated_red)

        if cross_info["max_red_s"] >= self.cross_street_max_red_s:
            for entry in route_etas:
                jid = entry["junction_id"]
                if entry["state"] in ("passed", "restored", "restore_failed", "passed_unmanaged"):
                    self._insert_compensating_phase(jid, env=env)
                    cross_info["compensating_phase_inserted"] = True
                    cross_info["accumulated_red_per_junction"][jid] = 0.0
                    logger.info(f"Corridor {event_id}: inserted cross-street compensating phase at passed junction {jid}.")

        terminal_states = ("restored", "restore_failed", "passed_unmanaged")
        all_passed = all(e["state"] in terminal_states for e in route_etas)
        if all_passed and event["status"] == "ACTIVE":
            logger.info(f"Corridor {event_id}: final junction passed. Deactivating and entering recovery measurement.")
            self.deactivate(event_id, env=env, end_time=elapsed_s, absolute_time=absolute_time)

        return self.get_corridor_status(event_id)

    def _try_preempt(self, event: Dict[str, Any], entry: Dict[str, Any], jid: str, elapsed_s: float, env: Any):
        captured = self.capture_program(jid, env=env)
        if captured is None:
            entry["state"] = "capture_unavailable"
            entry["capture_failed"] = True
            entry["activated_at"] = elapsed_s
            logger.warning(
                f"Corridor {event['id']}: junction {jid} cannot be safely pre-empted "
                f"(no verifiable program capture available); left on its normal cycle."
            )
            return
        event["captured_programs"][jid] = captured
        entry["state"] = "preempted"
        entry["activated_at"] = elapsed_s
        self._apply_green_preemption(jid, env=env)
        logger.info(f"Corridor {event['id']}: rolling preemption activated at {jid} (ETA: {entry['eta_s']}s).")

    def deactivate(
        self,
        event_id: str,
        env: Any = None,
        end_time: Optional[float] = None,
        absolute_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Restores any remaining junctions, sets restored_at, and opens recovery measurement (SN-045, SN-048).

        `end_time` stamps `restored_at`/entry timestamps in the corridor's own
        relative clock. `absolute_time` — the caller's real/simulation clock,
        the same one `ingest_delay_sample` timestamps samples with — is what
        recovery is measured against; it defaults to `end_time` when the
        caller has only one clock (e.g. tests, or a caller with no separate
        absolute time source).
        """
        if event_id not in self.active_events:
            return {"status": "error", "message": "Event not found"}

        event = self.active_events[event_id]
        now = end_time if end_time is not None else time.time()
        recovery_clock = absolute_time if absolute_time is not None else now

        for entry in event["route_etas"]:
            jid = entry["junction_id"]
            if entry["state"] not in ("restored", "restore_failed", "passed_unmanaged"):
                captured = event["captured_programs"].get(jid)
                if captured:
                    ok = self.restore_and_verify_program(jid, captured, env=env)
                    entry["state"] = "restored" if ok else "restore_failed"
                    entry["restore_failed"] = not ok
                else:
                    entry["state"] = "passed_unmanaged"
                entry["restored_at"] = now
                entry["passed_at"] = entry["passed_at"] or now

        event["status"] = "COMPLETED"
        event["restored_at"] = now
        event["recovery"]["closed_at"] = recovery_clock

        del self.active_events[event_id]
        self.completed_events[event_id] = event
        self._recovery_open[event_id] = True

        return {
            "status": "deactivated",
            "event_id": event_id,
            "restored_at": now,
            "recovery_s": event["recovery"]["recovery_s"],
        }

    def _record_recovery_sample(self, event: Dict[str, Any], t: float, delay_s: float) -> None:
        """Appends one real post-close sample and checks the recovery condition (SN-048).

        recovery_s is only ever set from real samples: the first point at
        which 3 consecutive real samples land within 10% of the real
        baseline. If no baseline was ever measured, recovery cannot be
        assessed and is reported as such rather than guessed.
        """
        rec = event["recovery"]
        if rec["resolved"]:
            return

        closed_at = event["recovery"].get("closed_at", t)
        elapsed = round(t - closed_at, 1)
        rec["series"].append({"t": elapsed, "delay_s": round(delay_s, 1)})
        rec["peak_delay_s"] = max(rec["peak_delay_s"] or delay_s, delay_s)

        if rec["baseline_delay_s"] is None:
            return

        tolerance = rec["baseline_delay_s"] * RECOVERY_TOLERANCE_FACTOR
        if delay_s <= tolerance:
            rec["consecutive_normal_samples"] += 1
            if rec["consecutive_normal_samples"] >= RECOVERY_CONSECUTIVE_REQUIRED:
                rec["recovery_s"] = elapsed
                rec["resolved"] = True
                self._recovery_open[event["id"]] = False
                logger.info(f"Corridor {event['id']}: cross-street delay recovered to baseline in {elapsed}s (measured).")
        else:
            rec["consecutive_normal_samples"] = 0

        if not rec["resolved"] and elapsed >= RECOVERY_SEARCH_WINDOW_S:
            rec["resolved"] = True
            rec["recovery_s"] = None
            rec["timeout"] = True
            self._recovery_open[event["id"]] = False
            logger.warning(f"Corridor {event['id']}: recovery window ({RECOVERY_SEARCH_WINDOW_S}s) exceeded without resolving.")

    def get_corridor_status(self, event_id: str) -> Dict[str, Any]:
        """Returns comprehensive rolling corridor status (SN-043 / docs/06-api-contracts.md §4)."""
        event = self.active_events.get(event_id) or self.completed_events.get(event_id)
        if not event:
            return {}

        route_etas = event["route_etas"]
        total_j = len(route_etas)
        curr_idx = event.get("current_index", 0)
        next_idx = min(total_j - 1, curr_idx + 1)
        next_junction = route_etas[next_idx]["junction_id"] if total_j > 0 else None
        next_eta = max(0, int(route_etas[next_idx]["eta_s"] - event.get("elapsed_s", 0))) if total_j > 0 else 0

        junction_list = []
        for e in route_etas:
            entry_dict = {
                "junction_id": e["junction_id"],
                "state": e["state"],
                "eta_s": e["eta_s"],
                "capture_failed": e.get("capture_failed", False),
                "restore_failed": e.get("restore_failed", False),
            }
            for key in ("activated_at", "passed_at", "restored_at"):
                if e.get(key) is not None:
                    entry_dict[key] = str(e[key])
            if e["state"] == "scheduled":
                entry_dict["activates_in_s"] = max(0, int(e["activate_at_s"] - event.get("elapsed_s", 0)))
            junction_list.append(entry_dict)

        return {
            "event_id": event["id"],
            "status": event["status"],
            "vehicle_id": event.get("vehicle_id"),
            "current_position": event.get("current_position"),
            "next_junction": next_junction,
            "next_junction_eta_s": next_eta,
            "clearance_time_s": event.get("clearance_time_s", 0.0),
            "junctions": junction_list,
            "cross_street": {
                "max_red_s": event["cross_street"]["max_red_s"],
                "threshold_s": event["cross_street"]["threshold_s"],
                "compensating_phase_inserted": event["cross_street"]["compensating_phase_inserted"],
            },
            "source": DataSource.SUMO.value,
        }

    def get_recovery(self, event_id: str) -> Tuple[int, Dict[str, Any]]:
        """Returns recovery metrics or 503 if still active (SN-048 / docs/10-emergency-corridor.md §7).

        recovery_s is None until enough real samples have actually resolved
        it — never a placeholder number.
        """
        event = self.active_events.get(event_id)
        if event and event.get("status") == "ACTIVE":
            return 503, {
                "error": "Corridor is still ACTIVE. Recovery delay can only be measured after corridor deactivation.",
                "source": DataSource.SUMO.value,
            }

        event = self.completed_events.get(event_id) or event
        if not event:
            return 404, {"error": "Emergency event not found"}

        rec = event.get("recovery", {})
        return 200, {
            "event_id": event_id,
            "recovery_s": rec.get("recovery_s"),
            "resolved": rec.get("resolved", False),
            "baseline_available": rec.get("baseline_available", False),
            "cross_street_baseline_delay_s": rec.get("baseline_delay_s"),
            "cross_street_peak_delay_s": rec.get("peak_delay_s"),
            "series": rec.get("series", []),
            "source": DataSource.SUMO.value,
        }

    def _apply_green_preemption(self, junction_id: str, env: Any = None):
        try:
            import traci
            traci.trafficlight.setPhase(junction_id, 0)
            traci.trafficlight.setPhaseDuration(junction_id, self.green_hold_s)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Failed to apply green preemption at {junction_id}: {e}")

        if env is not None and hasattr(env, "set_green_wave"):
            env.set_green_wave(junction_id, 0, self.green_hold_s)

    def _insert_compensating_phase(self, junction_id: str, env: Any = None):
        try:
            import traci
            traci.trafficlight.setPhase(junction_id, 2)
            traci.trafficlight.setPhaseDuration(junction_id, 15.0)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Failed to insert compensating phase at {junction_id}: {e}")

        if env is not None and hasattr(env, "set_phase"):
            env.set_phase(junction_id, 2, 15.0)


# Global singleton instance
green_wave_ctrl = GreenWaveController()
