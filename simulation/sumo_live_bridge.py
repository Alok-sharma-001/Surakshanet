#!/usr/bin/env python3
"""
Surakshanet - Live TraCI / SUMO to Dashboard Streaming Bridge
============================================================
Connects Eclipse SUMO simulation to Surakshanet backend via Redis Pub/Sub,
MQTT, and WebSockets.

Features:
- Launches and synchronizes with SUMO-GUI (corridor.sumocfg)
- Extracts real-time vehicle counts, average speeds, queues, and signal phases
- Streams telemetry at 2Hz-10Hz into Redis channel `traffic_updates`
- Broadcasts real-time events to frontend dashboard
- Intercepts emergency corridor activations from dashboard and forces green waves in SUMO
"""

import os
import sys
import time
import json
import socket
import logging
import argparse
import threading
import queue
from typing import Dict, Optional

logger = logging.getLogger("surakshanet.sumo_bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Ensure repo root is available for shared imports
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from shared.sumo_bootstrap import require_traci

traci = require_traci(extra_paths=[_repo_root])

from datetime import datetime, timezone
from shared.constants import (
    DataSource,
    DEMO_SEED,
    PCU_FACTORS,
    REDIS_CHANNELS,
    MQTT_JUNCTION_TELEMETRY_TOPIC,
)
from shared.telemetry import ApproachTelemetry, JunctionTelemetry, validate_telemetry
from shared.corridor_topology import route_to_edge_ids, route_edge_lengths_m
from ml.emergency.green_wave import GreenWaveController

try:
    import psycopg2
except ImportError:
    psycopg2 = None

# Cross-street delay samples are fed every 5 simulated seconds so a genuine
# pre-activation baseline (docs/10-emergency-corridor.md §7) is available the
# moment a corridor is requested, rather than only once one is already active.
DELAY_SAMPLE_INTERVAL_S = 5
DB_WRITE_THROTTLE_S = 2.0

def publish_redis_raw(channel: str, message: str, host: str = "127.0.0.1", port: int = 6379) -> bool:
    """Publishes a message to Redis using raw TCP socket (zero external pip dependencies)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((host, port))
        cmd = f"*3\r\n$7\r\nPUBLISH\r\n${len(channel)}\r\n{channel}\r\n${len(message)}\r\n{message}\r\n"
        s.sendall(cmd.encode("utf-8"))
        s.recv(1024)
        s.close()
        return True
    except Exception as e:
        return False

class SumoLiveBridge:
    def __init__(
        self,
        config_path: str,
        gui: bool = True,
        step_delay_ms: int = 100,
        redis_host: str = "127.0.0.1",
        redis_port: int = 6379,
        mqtt_host: str = "127.0.0.1",
        mqtt_port: int = 1883,
        seed: int = DEMO_SEED
    ):
        self.config_path = os.path.abspath(config_path)
        self.gui = gui
        self.step_delay_ms = step_delay_ms
        self.seed = seed
        self.redis_host = "127.0.0.1" if redis_host == "localhost" else redis_host
        self.redis_port = redis_port
        self.mqtt_host = "127.0.0.1" if mqtt_host == "localhost" else mqtt_host
        self.mqtt_port = mqtt_port

        self.is_running = False
        self.step_count = 0
        self.departed_total = 0
        self.command_queue = queue.Queue()
        self.last_cmd_seq: Dict[str, int] = {}
        self.junction_phase: Dict[str, int] = {}
        self.junction_phase_start: Dict[str, float] = {}
        self.current_controller: Dict[str, str] = {}
        self._redis_sock = None
        self.redis_password = os.environ.get("REDIS_PASSWORD", None)
        self.redis_client = None

        # Emergency corridor execution (SN-043..SN-048). This controller
        # instance is the one that actually holds live TraCI-verified state —
        # it runs in this process because this is the only process with a
        # real TraCI connection.
        self.green_wave_ctrl = GreenWaveController()
        self.corridor_vehicle: Dict[str, str] = {}          # event_id -> spawned ambulance vehicle id
        self.corridor_route_length_m: Dict[str, float] = {}  # event_id -> total route length
        self._last_db_write: Dict[str, float] = {}          # event_id -> last wall-clock write time
        self._last_delay_sample_sec = -1
        self._recovery_final_flushed: set = set()  # event_ids whose resolved recovery has been written once
        self.db_dsn = self._build_db_dsn()
        self.db_conn = None

        try:
            import redis
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                decode_responses=True,
                socket_timeout=2.0,
                retry_on_timeout=True
            )
            logger.info(f"Initialized robust redis-py client connecting to {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.debug(f"redis-py unavailable or connection pending ({e}), falling back to low-level socket")

    def publish_redis(self, channel: str, message: str) -> bool:
        """Publishes a message to Redis using redis-py or fallback socket with health reporting."""
        if self.redis_client:
            try:
                self.redis_client.publish(channel, message)
                self.redis_client.setex("simulation:bridge:heartbeat", 10, str(time.time()))
                return True
            except Exception as e:
                logger.debug(f"redis-py publish retry: {e}")

        if self._redis_sock is None:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect((self.redis_host, self.redis_port))
                if self.redis_password:
                    auth_cmd = f"*2\r\n$4\r\nAUTH\r\n${len(self.redis_password)}\r\n{self.redis_password}\r\n"
                    s.sendall(auth_cmd.encode("utf-8"))
                    s.recv(64)
                self._redis_sock = s
            except Exception:
                self._redis_sock = None
                return False

        try:
            msg_bytes = message.encode("utf-8")
            cmd = f"*3\r\n$7\r\nPUBLISH\r\n${len(channel)}\r\n{channel}\r\n${len(msg_bytes)}\r\n".encode("utf-8") + msg_bytes + b"\r\n"
            self._redis_sock.sendall(cmd)
            self._redis_sock.recv(64)
            return True
        except Exception:
            try:
                if self._redis_sock:
                    self._redis_sock.close()
            except Exception:
                pass
            self._redis_sock = None
            return False

    def _is_junction_preempted(self, junction_id: str) -> bool:
        """True while `junction_id` is currently held by an active emergency corridor.

        Precedence per docs/09-dynamic-signals.md §4: EMERGENCY_PREEMPTION
        outranks the controller. Junction-specific (not a network-wide flag)
        so junctions outside the active corridor keep running normally.
        """
        for event in self.green_wave_ctrl.active_events.values():
            for entry in event["route_etas"]:
                if entry["junction_id"] == junction_id and entry["state"] == "preempted":
                    return True
        return False

    def _build_db_dsn(self) -> Optional[str]:
        """Builds a plain psycopg2 DSN mirroring backend/app/config.py's DATABASE_URL assembly."""
        host = os.environ.get("POSTGRES_HOST", "postgres")
        if host == "localhost":
            host = "127.0.0.1"
        return (
            f"host={host} port={os.environ.get('POSTGRES_PORT', '5432')} "
            f"dbname={os.environ.get('POSTGRES_DB', 'surakshanet')} "
            f"user={os.environ.get('POSTGRES_USER', 'surakshanet')} "
            f"password={os.environ.get('POSTGRES_PASSWORD', 'surakshanet_dev')}"
        )

    def _get_db_conn(self):
        """Returns a live psycopg2 connection, reconnecting on failure.

        Used only to write back what this process actually observed via
        TraCI (captured programs, verified restorations, real delay
        samples) — the same "own-process direct write" pattern
        services/control_service/main.py uses for control_decisions.
        """
        if psycopg2 is None:
            return None
        if self.db_conn is not None:
            try:
                if self.db_conn.closed == 0:
                    return self.db_conn
            except Exception:
                pass
        try:
            self.db_conn = psycopg2.connect(self.db_dsn)
            self.db_conn.autocommit = True
            return self.db_conn
        except Exception as e:
            logger.debug(f"Emergency DB connection unavailable ({e}); corridor state stays Redis/in-memory only.")
            self.db_conn = None
            return None

    def write_emergency_event(self, event_id: str, **fields) -> None:
        """Writes real corridor state observed via TraCI back to emergency_events.

        `fields` may include route_etas, captured_programs, cross_street_max_red_s,
        clearance_time_s, status, restored_at, recovery_s, recovery_series — only
        columns that actually changed need be passed.
        """
        conn = self._get_db_conn()
        if conn is None or not fields:
            return
        set_clause = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE emergency_events SET {set_clause} WHERE id = %s",
                    values + [event_id],
                )
        except Exception as e:
            logger.warning(f"Failed to write emergency_events row for {event_id}: {e}")
            self.db_conn = None

    def start(self):
        """Launches SUMO and begins the live TraCI streaming loop."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"SUMO configuration file not found: {self.config_path}")

        binary = "sumo-gui" if self.gui else "sumo"
        cmd = [
            binary,
            "-c", self.config_path,
            "--start",
            "--quit-on-end",
            "--delay", str(self.step_delay_ms),
            "--step-length", "1.0",
            "--seed", str(self.seed),
            "--random", "false"
        ]

        logger.info(f"Starting SUMO with command: {' '.join(cmd)}")
        traci.start(cmd)
        self.is_running = True
        logger.info("✅ Connected to SUMO TraCI! Live telemetry bridge running...")

        if self.redis_client:
            try:
                self.redis_client.setex("simulation:bridge:heartbeat", 30, str(time.time()))
                self.redis_client.set("sumo:step", "0")
            except Exception:
                pass

        # Start two-way dashboard command listener (Emergency Green Waves & Signal Overrides)
        cmd_thread = threading.Thread(target=self.listen_dashboard_commands, daemon=True)
        cmd_thread.start()

        try:
            while self.is_running:
                # 1. Process all queued commands from dashboard safely in the MAIN TraCI thread
                while not self.command_queue.empty():
                    try:
                        cmd = self.command_queue.get_nowait()
                        p_type = cmd.get("type", "")
                        if p_type == "EMERGENCY_ACTIVATED":
                            logger.info("🚨 [REDIS] EMERGENCY GREEN CORRIDOR ACTIVATION COMMAND RECEIVED!")
                            self.handle_emergency_activated(cmd)
                        elif p_type == "EMERGENCY_DEACTIVATED":
                            logger.info("✅ [REDIS] EMERGENCY CORRIDOR DEACTIVATION COMMAND RECEIVED!")
                            self.handle_emergency_deactivated(cmd)
                        elif p_type == "SIGNAL_OVERRIDE":
                            action = cmd.get("action", "")
                            val = cmd.get("value", 5)
                            logger.info(f"🎛 DASHBOARD SIGNAL OVERRIDE: {action} (val={val})")
                            self.handle_signal_override(action, val)
                        elif p_type == "SET_PHASE":
                            tl_id = cmd.get("junction_id")
                            target_phase = cmd.get("phase")
                            dur_s = float(cmd.get("duration_s", 5.0))
                            seq = int(cmd.get("seq", 0))
                            ctrl = cmd.get("controller", "marl")
                            if tl_id and target_phase is not None and not self._is_junction_preempted(tl_id):
                                if seq >= self.last_cmd_seq.get(tl_id, -1):
                                    self.last_cmd_seq[tl_id] = seq
                                    self.current_controller[tl_id] = ctrl
                                    try:
                                        curr = traci.trafficlight.getPhase(tl_id)
                                        if curr != target_phase:
                                            traci.trafficlight.setPhase(tl_id, target_phase)
                                        traci.trafficlight.setPhaseDuration(tl_id, dur_s)
                                        logger.debug(f"🚦 [SET_PHASE] {tl_id} phase={target_phase} dur={dur_s}s seq={seq}")
                                    except Exception as e:
                                        logger.warning(f"Error applying SET_PHASE on {tl_id}: {e}")
                        elif p_type == "SIGNAL_MODE_CHANGED":
                            tl_id = cmd.get("junction_id")
                            mode_val = str(cmd.get("mode", "MARL")).lower()
                            if tl_id:
                                self.current_controller[tl_id] = mode_val
                    except Exception as e:
                        logger.warning(f"Error executing queued command: {e}")

                traci.simulationStep()
                self.step_count += 1
                sim_time_s = float(traci.simulation.getTime())
                should_sample_delay = (
                    int(sim_time_s) % DELAY_SAMPLE_INTERVAL_S == 0
                    and int(sim_time_s) != self._last_delay_sample_sec
                )
                if should_sample_delay:
                    self._last_delay_sample_sec = int(sim_time_s)
                if self.redis_client:
                    try:
                        self.redis_client.set("sumo:step", str(self.step_count))
                    except Exception:
                        pass

                # 2. Advance any active emergency corridors on their real rolling
                #    schedule (SN-043) — real TraCI capture/restore, never a blanket
                #    "everything green" override.
                if self.green_wave_ctrl.active_events:
                    self._step_active_corridors(sim_time_s)
                if should_sample_delay and self.green_wave_ctrl._recovery_open:
                    self._flush_open_recovery_events()

                # 1. Collect live vehicle data from TraCI
                veh_ids = traci.vehicle.getIDList()
                total_vehicles = len(veh_ids)
                
                speeds = []
                waiting_count = 0
                for v in veh_ids:
                    try:
                        spd_kmh = traci.vehicle.getSpeed(v) * 3.6
                        speeds.append(spd_kmh)
                        if spd_kmh < 5.0:
                            waiting_count += 1
                    except Exception:
                        pass

                avg_speed = round(sum(speeds) / max(1, len(speeds)), 1) if speeds else 38.5
                departed = traci.simulation.getDepartedNumber()
                self.departed_total += departed
                throughput = round(800 + (total_vehicles * 4.5) + (departed * 12), 1)

                # Determine Network Level of Service (LOS)
                if avg_speed > 35:
                    los = "A (Free Flow)"
                elif avg_speed > 26:
                    los = "B (Stable Flow)"
                elif avg_speed > 18:
                    los = "C (Fair Flow)"
                elif avg_speed > 12:
                    los = "D (Approaching Capacity)"
                else:
                    los = "F (Forced Breakdown)"

                # 2. Collect Traffic Lights & Junction canonical telemetry
                tl_ids = traci.trafficlight.getIDList()
                tl_states = {}
                junctions_stats = []
                all_dets = set(traci.lanearea.getIDList())

                for i, tl in enumerate(tl_ids):
                    try:
                        state_str = traci.trafficlight.getRedYellowGreenState(tl)
                        phase = traci.trafficlight.getPhase(tl)
                        tl_states[tl] = {"phase": phase, "state": state_str}

                        # Track phase duration
                        if tl not in self.junction_phase or self.junction_phase[tl] != phase:
                            self.junction_phase[tl] = phase
                            self.junction_phase_start[tl] = sim_time_s
                        phase_elapsed_s = max(0.0, sim_time_s - self.junction_phase_start.get(tl, sim_time_s))

                        # Build all 4 approaches (N, E, S, W) from lane-area detectors (SN-015, SN-025)
                        approaches = []
                        for dir_code in ["N", "E", "S", "W"]:
                            det_id = f"det_{tl}_{dir_code}_0"
                            if det_id in all_dets:
                                v_ids = traci.lanearea.getLastStepVehicleIDs(det_id)
                                v_count = float(len(v_ids))
                                queue_m = float(traci.lanearea.getJamLengthMeters(det_id))
                                spd = float(traci.lanearea.getLastStepMeanSpeed(det_id)) * 3.6
                                speed_kmh = max(0.0, spd) if spd >= 0.0 else 35.0
                                occ = float(traci.lanearea.getLastStepOccupancy(det_id)) / 100.0
                                occ = max(0.0, min(1.0, occ))
                                lane_id = traci.lanearea.getLaneID(det_id)

                                pcu = 0.0
                                accum_wait = 0.0
                                breakdown = {}
                                for v in v_ids:
                                    try:
                                        v_type = traci.vehicle.getTypeID(v)
                                        breakdown[v_type] = breakdown.get(v_type, 0) + 1
                                        pcu += PCU_FACTORS.get(v_type, 1.0)
                                        accum_wait += float(traci.vehicle.getAccumulatedWaitingTime(v))
                                    except Exception:
                                        pass
                                if v_count > 0 and pcu == 0.0:
                                    pcu = v_count * 1.0

                                approaches.append(ApproachTelemetry(
                                    direction=dir_code,
                                    lane_ids=[lane_id],
                                    vehicle_count=v_count,
                                    pcu=pcu,
                                    queue_length_m=queue_m,
                                    mean_speed_kmh=speed_kmh,
                                    occupancy=occ,
                                    accumulated_wait_s=accum_wait,
                                    vehicle_breakdown=breakdown
                                ))
                            else:
                                approaches.append(ApproachTelemetry(
                                    direction=dir_code,
                                    lane_ids=[],
                                    vehicle_count=0.0,
                                    pcu=0.0,
                                    queue_length_m=0.0,
                                    mean_speed_kmh=35.0,
                                    occupancy=0.0,
                                    accumulated_wait_s=0.0,
                                    vehicle_breakdown={}
                                ))

                        # Feed a real cross-street delay sample (SN-048) every ~5 sim
                        # seconds, independent of whether a corridor is active, so a
                        # genuine pre-activation baseline is already available the
                        # moment one is requested. N/S is the cross-street direction
                        # relative to the E/W corridor arterial.
                        if should_sample_delay:
                            ns_waits = [a.accumulated_wait_s for a in approaches if a.direction in ("N", "S") and a.vehicle_count > 0]
                            delay_proxy = (sum(ns_waits) / len(ns_waits)) if ns_waits else 0.0
                            self.green_wave_ctrl.ingest_delay_sample(tl, delay_proxy, t=sim_time_s)

                        # Build and validate canonical JunctionTelemetry (SN-023, SN-025)
                        jt = JunctionTelemetry(
                            junction_id=tl,
                            source=DataSource.SUMO,
                            approaches=approaches,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            sim_time_s=sim_time_s,
                            current_phase=int(phase),
                            phase_elapsed_s=round(phase_elapsed_s, 2),
                            cycle_length_s=90.0,
                            controller=self.current_controller.get(tl, "marl"),
                            total_pcu=sum(a.pcu for a in approaches),
                            seed=self.seed
                        )
                        # Ensure it validates against schema
                        validated = validate_telemetry(jt.to_dict())
                        self.publish_redis(REDIS_CHANNELS["traffic"], validated.to_json())

                        junc_queue = sum(int(a.queue_length_m / 7.5) for a in approaches)
                        moving_speeds = [a.mean_speed_kmh for a in approaches if a.vehicle_count > 0]
                        junc_avg_speed = round(sum(moving_speeds) / len(moving_speeds), 1) if moving_speeds else 35.0

                        junctions_stats.append({
                            "id": tl,
                            "index": i,
                            "queue": junc_queue,
                            "speed": junc_avg_speed,
                            "pcu": jt.total_pcu,
                            "phase": phase,
                            "signal_state": state_str,
                            "is_congested": junc_queue > 6 or junc_avg_speed < 18.0
                        })
                    except Exception as e:
                        logger.warning(f"Error extracting canonical telemetry for junction {tl}: {e}")

                # 3. Construct Live Telemetry Summary Packet
                telemetry = {
                    "type": "SIMULATION_TICK",
                    "source": DataSource.SUMO.value,
                    "step": self.step_count,
                    "sim_time": f"{int((self.step_count % 3600) // 60):02d}:{int(self.step_count % 60):02d}",
                    "total_vehicles": total_vehicles,
                    "avg_speed": avg_speed,
                    "throughput": throughput,
                    "network_los": los,
                    "queue_length": waiting_count,
                    "active_alerts": 1 if waiting_count > 8 else 0,
                    "traffic_lights": tl_states,
                    "junctions": junctions_stats,
                    "timestamp": time.time()
                }

                # 4. Stream simulation summary to REDIS_CHANNELS["simulation"]
                payload_str = json.dumps(telemetry)
                self.publish_redis(REDIS_CHANNELS["simulation"], payload_str)

                # SN-002: a periodic publisher previously emitted fake green extension
                # messages to signal_events every 15 steps, regardless of state and with
                # no model involved. The dashboard displayed that string as an AI decision.
                #
                # The bridge reports state; it does not narrate decisions. Real
                # control decisions are published by the control service once it
                # exists (Phase 2, SN-030), carrying the state vector and Q-values
                # that produced them.

                if self.step_count % 5 == 0:
                    logger.info(
                        f"[Step {self.step_count}] Vehicles: {total_vehicles} | "
                        f"Avg Speed: {avg_speed} km/h | Queue: {waiting_count} | LOS: {los}"
                    )

                time.sleep(self.step_delay_ms / 1000.0)

        except KeyboardInterrupt:
            logger.info("Stopping simulation bridge...")
        except traci.exceptions.FatalTraCIError:
            logger.info("SUMO GUI closed by user.")
        finally:
            self.stop()

    def handle_emergency_activated(self, cmd: Dict):
        """Starts real rolling pre-emption for a corridor (SN-043..SN-045).

        This is the only process with a live TraCI connection, so this is
        the only place that can genuinely capture/restore signal programs —
        `self.green_wave_ctrl` here is authoritative, unlike the API
        process's own instance, which never sees a corridor actually run.
        """
        event_id = cmd.get("event_id")
        route = cmd.get("route") or []
        if not event_id or len(route) < 2:
            logger.warning(f"Emergency activation command missing event_id/route: {cmd}")
            return

        sim_time_s = float(traci.simulation.getTime())
        edge_ids = route_to_edge_ids(route)
        amb_id = None

        if edge_ids:
            try:
                route_def_id = f"corridor_route_{event_id[:8]}"
                traci.route.add(route_def_id, edge_ids)
                amb_id = f"AMBULANCE_{event_id[:8]}"
                traci.vehicle.add(
                    vehID=amb_id,
                    routeID=route_def_id,
                    typeID="ambulance",
                    depart="now",
                    departLane="best",
                    departPos="last",
                    departSpeed="max",
                )
                traci.vehicle.setColor(amb_id, (255, 255, 255, 255))
                self.corridor_vehicle[event_id] = amb_id
                self.corridor_route_length_m[event_id] = sum(route_edge_lengths_m(route).values()) or None
                logger.info(f"🚑 [SUMO SIMULATION] Ambulance {amb_id} spawned for corridor {event_id}: {' -> '.join(route)}")
                if self.gui:
                    try:
                        traci.gui.trackVehicle("View #0", amb_id)
                        traci.gui.setZoom("View #0", 500.0)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Failed to spawn ambulance for corridor {event_id}: {e}")
        else:
            logger.warning(
                f"Corridor {event_id}: route {route} has no directly-connected SUMO edges; "
                f"activation proceeds on elapsed-time scheduling only, without a tracked vehicle."
            )

        self.green_wave_ctrl.activate(
            event_id=event_id,
            priority=cmd.get("priority", "CRITICAL"),
            vehicle_type=cmd.get("vehicle_type", "AMBULANCE"),
            route_junction_ids=route,
            vehicle_id=cmd.get("vehicle_id"),
            edge_lengths_m=route_edge_lengths_m(route),
            start_time=sim_time_s,
        )
        self.write_emergency_event(
            event_id,
            route_etas=json.dumps(self.green_wave_ctrl.active_events[event_id]["route_etas"]),
        )

    def handle_emergency_deactivated(self, cmd: Dict):
        """Requests early release of a corridor; performs the real restore+verify."""
        event_id = cmd.get("event_id")
        if not event_id or event_id not in self.green_wave_ctrl.active_events:
            return
        sim_time_s = float(traci.simulation.getTime())
        started_at = self.green_wave_ctrl.active_events[event_id]["started_at"]
        self.green_wave_ctrl.deactivate(
            event_id, end_time=sim_time_s - started_at, absolute_time=sim_time_s
        )
        self._flush_corridor_state(event_id, force=True)
        logger.info(f"✅ [SUMO SIMULATION] Corridor {event_id} deactivated on request; signals restored.")

    def _step_active_corridors(self, sim_time_s: float):
        """Advances every corridor this process is driving by one simulation step."""
        for event_id in list(self.green_wave_ctrl.active_events.keys()):
            event = self.green_wave_ctrl.active_events[event_id]
            elapsed_s = sim_time_s - event["started_at"]

            progress = None
            amb_id = self.corridor_vehicle.get(event_id)
            total_len = self.corridor_route_length_m.get(event_id)
            if amb_id and total_len:
                if amb_id in traci.vehicle.getIDList():
                    try:
                        progress = min(1.0, max(0.0, traci.vehicle.getDistance(amb_id) / total_len))
                    except Exception:
                        progress = None
                else:
                    # Vehicle already arrived (removed from the simulation) or was never inserted.
                    progress = 1.0

            self.green_wave_ctrl.step_corridor(
                event_id, elapsed_s=elapsed_s, vehicle_progress=progress, absolute_time=sim_time_s
            )
            self._flush_corridor_state(event_id)

            if event_id not in self.green_wave_ctrl.active_events:
                # step_corridor deactivated it internally (final junction passed).
                self.corridor_vehicle.pop(event_id, None)
                self.corridor_route_length_m.pop(event_id, None)
                if self.gui:
                    try:
                        traci.gui.trackVehicle("View #0", "")
                        traci.gui.setZoom("View #0", 180.0)
                    except Exception:
                        pass
                logger.info(f"✅ [SUMO SIMULATION] Corridor {event_id} completed; all junctions restored and verified.")

    def _flush_open_recovery_events(self):
        """Writes evolving post-close recovery series to the DB as real samples keep arriving.

        Flushes once more even after a corridor's recovery resolves (still_open
        flips to False the instant it resolves) — otherwise the final
        recovery_s/series never reaches the DB, since resolution and
        de-registration happen in the same instant inside green_wave.py.
        """
        for event_id, still_open in list(self.green_wave_ctrl._recovery_open.items()):
            if still_open:
                self._flush_corridor_state(event_id, force=True)
            elif event_id not in self._recovery_final_flushed:
                self._flush_corridor_state(event_id, force=True)
                self._recovery_final_flushed.add(event_id)

    def _flush_corridor_state(self, event_id: str, force: bool = False):
        """Writes the corridor's current real state to Redis (live UI) and the DB (throttled)."""
        status = self.green_wave_ctrl.get_corridor_status(event_id)
        if not status:
            return
        try:
            self.publish_redis(
                REDIS_CHANNELS["emergency"],
                json.dumps({"type": "EMERGENCY_CORRIDOR_TICK", **status}),
            )
        except Exception:
            pass

        now = time.time()
        if not force and (now - self._last_db_write.get(event_id, 0.0)) < DB_WRITE_THROTTLE_S:
            return
        self._last_db_write[event_id] = now

        event = self.green_wave_ctrl.active_events.get(event_id) or self.green_wave_ctrl.completed_events.get(event_id)
        if not event:
            return
        fields = {
            "route_etas": json.dumps(event["route_etas"]),
            "cross_street_max_red_s": event["cross_street"]["max_red_s"],
        }
        if event["status"] == "COMPLETED":
            fields["status"] = "COMPLETED"
            # Naive UTC to match emergency_events.restored_at's plain DateTime column —
            # a tz-aware value here previously caused a silent INSERT rollback
            # elsewhere in this codebase (see CLAUDE.md's 2026-09-11 Phase 2 addendum).
            fields["restored_at"] = datetime.utcnow()
            fields["recovery_s"] = event["recovery"]["recovery_s"]
            fields["recovery_series"] = json.dumps({
                "series": event["recovery"]["series"],
                "baseline_delay_s": event["recovery"]["baseline_delay_s"],
                "peak_delay_s": event["recovery"]["peak_delay_s"],
                "resolved": event["recovery"]["resolved"],
                "baseline_available": event["recovery"]["baseline_available"],
            })
        self.write_emergency_event(event_id, **fields)

    def handle_signal_override(self, action: str, value: int = 5):
        """Applies manual signal override in SUMO."""
        try:
            tl_ids = traci.trafficlight.getIDList()
            for tl in tl_ids:
                if action == "FLASH_ALL_RED":
                    curr = traci.trafficlight.getRedYellowGreenState(tl)
                    traci.trafficlight.setRedYellowGreenState(tl, "r" * len(curr))
                    logger.info(f"⚠️ SUMO Junction {tl} Flashing ALL RED")
                elif action in ["PHASE_SKIP", "FORCE_PHASE_SKIP"]:
                    p = traci.trafficlight.getPhase(tl)
                    traci.trafficlight.setPhase(tl, (p + 1) % 4)
                    logger.info(f"⏭ SUMO Junction {tl} Skipped to Phase {(p + 1) % 4}")
                elif action in ["EXTEND_GREEN", "HOLD_GREEN"]:
                    dur = traci.trafficlight.getPhaseDuration(tl)
                    traci.trafficlight.setPhaseDuration(tl, dur + value)
                    logger.info(f"⏱ SUMO Junction {tl} Green extended by +{value}s")
                elif action in ["SHORTEN_GREEN", "REDUCE_GREEN"]:
                    dur = traci.trafficlight.getPhaseDuration(tl)
                    traci.trafficlight.setPhaseDuration(tl, max(5, dur - value))
                    logger.info(f"⏱ SUMO Junction {tl} Green reduced by -{value}s")
        except Exception as e:
            logger.warning(f"Failed to apply signal override in SUMO: {e}")

    def listen_dashboard_commands(self):
        """Background thread listening for control commands, manual overrides, and emergency events."""
        sub_channels = [
            REDIS_CHANNELS["emergency"],
            REDIS_CHANNELS["signals"],
            REDIS_CHANNELS["control_commands"],
        ]
        while self.is_running:
            logger.info(f"Connecting to Redis command bus at {self.redis_host}:{self.redis_port}...")
            try:
                if self.redis_client:
                    pubsub = self.redis_client.pubsub()
                    pubsub.subscribe(*sub_channels)
                    while self.is_running:
                        try:
                            item = pubsub.get_message(timeout=0.5)
                            if item and item.get("type") == "message":
                                raw_data = item.get("data")
                                text_data = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)
                                payload = json.loads(text_data)
                                if isinstance(payload, dict) and ("type" in payload or "action" in payload):
                                    self.command_queue.put(payload)
                        except Exception:
                            pass
                else:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((self.redis_host, self.redis_port))
                    c1, c2, c3 = sub_channels[0], sub_channels[1], sub_channels[2]
                    sub_cmd = f"*4\r\n$9\r\nSUBSCRIBE\r\n${len(c1)}\r\n{c1}\r\n${len(c2)}\r\n{c2}\r\n${len(c3)}\r\n{c3}\r\n"
                    s.sendall(sub_cmd.encode("utf-8"))
                    f = s.makefile("r", encoding="utf-8", errors="ignore")
                    logger.info(f"✅ Redis Command Bus (socket): Subscribed to {', '.join(sub_channels)}")
                    while self.is_running:
                        line = f.readline()
                        if not line:
                            break
                        if line.startswith("$"):
                            length = int(line[1:].strip())
                            msg = f.read(length)
                            f.readline()
                            try:
                                payload = json.loads(msg)
                                if isinstance(payload, dict) and ("type" in payload or "action" in payload):
                                    self.command_queue.put(payload)
                            except Exception:
                                pass
            except Exception as e:
                if self.is_running:
                    logger.warning(f"Command listener reconnecting in 2s ({e})...")
                    time.sleep(2)

    def stop(self):
        """Stops TraCI simulation gracefully."""
        self.is_running = False
        try:
            traci.close()
        except Exception:
            pass
        logger.info("TraCI bridge closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Surakshanet SUMO-to-Dashboard Live Bridge")
    parser.add_argument(
        "--config",
        type=str,
        default="simulation/networks/corridor.sumocfg",
        help="Path to corridor.sumocfg"
    )
    parser.add_argument("--no-gui", action="store_true", help="Run SUMO in headless mode without GUI")
    parser.add_argument("--delay", type=int, default=50, help="Step delay in milliseconds (default: 50)")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port (default: 6379)")
    parser.add_argument("--seed", type=int, default=DEMO_SEED, help=f"Simulation seed (default: {DEMO_SEED})")
    args = parser.parse_args()

    bridge = SumoLiveBridge(
        config_path=args.config,
        gui=not args.no_gui,
        step_delay_ms=args.delay,
        redis_port=args.redis_port,
        seed=args.seed
    )
    bridge.start()
