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
        self.emergency_mode = False
        self.active_ambulance_id = None
        self.command_queue = queue.Queue()
        self.last_cmd_seq: Dict[str, int] = {}
        self.junction_phase: Dict[str, int] = {}
        self.junction_phase_start: Dict[str, float] = {}
        self.current_controller: Dict[str, str] = {}
        self._redis_sock = None
        self.redis_password = os.environ.get("REDIS_PASSWORD", None)
        self.redis_client = None

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
                            self.trigger_emergency_corridor()
                        elif p_type == "EMERGENCY_DEACTIVATED":
                            logger.info("✅ [REDIS] EMERGENCY CORRIDOR DEACTIVATION COMMAND RECEIVED!")
                            self.clear_emergency_corridor()
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
                            if tl_id and target_phase is not None and not self.emergency_mode:
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

                # 2. When emergency corridor is active, enforce Green wave across all corridor traffic lights
                if self.emergency_mode:
                    for tl in traci.trafficlight.getIDList():
                        try:
                            if traci.trafficlight.getPhase(tl) != 0:
                                traci.trafficlight.setPhase(tl, 0)
                            traci.trafficlight.setPhaseDuration(tl, 9999)
                        except Exception:
                            pass

                traci.simulationStep()
                self.step_count += 1
                if self.redis_client:
                    try:
                        self.redis_client.set("sumo:step", str(self.step_count))
                    except Exception:
                        pass

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
                sim_time_s = float(traci.simulation.getTime())

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

    def trigger_emergency_corridor(self):
        """Spawns an ambulance and locks all corridor traffic lights to continuous GREEN."""
        self.emergency_mode = True
        try:
            # 1. Spawn a high-priority Ambulance in SUMO
            amb_id = f"AMBULANCE_{int(time.time()) % 10000}"
            self.active_ambulance_id = amb_id
            traci.vehicle.add(
                vehID=amb_id,
                routeID="r_WE",
                typeID="ambulance",
                depart="now",
                departLane="best",
                departPos="last",
                departSpeed="max"
            )
            traci.vehicle.setColor(amb_id, (255, 255, 255, 255))
            logger.info(f"🚑 [SUMO SIMULATION] AMBULANCE SPAWNED! (ID: {amb_id}) Route: West-to-East Main Corridor")
            
            # Automatically lock SUMO-GUI camera onto the ambulance so user sees it live!
            if self.gui:
                try:
                    traci.gui.trackVehicle("View #0", amb_id)
                    traci.gui.setZoom("View #0", 500.0)
                    logger.info("🎥 [SUMO-GUI] Camera locked onto Ambulance!")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to spawn ambulance vehicle: {e}")

        # 2. Pre-empt all traffic lights to Phase 0 (West-East Green)
        for tl in traci.trafficlight.getIDList():
            try:
                traci.trafficlight.setPhase(tl, 0)
                traci.trafficlight.setPhaseDuration(tl, 9999)
            except Exception:
                pass
        logger.info("🟢 [SUMO SIMULATION] ALL 4 CORRIDOR INTERSECTIONS FORCED TO GREEN (PHASE 0 HOLD)")

    def clear_emergency_corridor(self):
        """Restores normal signal cycles and resets camera view."""
        self.emergency_mode = False
        self.active_ambulance_id = None
        for tl in traci.trafficlight.getIDList():
            try:
                traci.trafficlight.setProgram(tl, "0")
                traci.trafficlight.setPhase(tl, 0)
                traci.trafficlight.setPhaseDuration(tl, 10)
            except Exception:
                pass

        if self.gui:
            try:
                traci.gui.trackVehicle("View #0", "")
                traci.gui.setOffset("View #0", 450.0, 0.0)
                traci.gui.setZoom("View #0", 180.0)
            except Exception:
                pass

        logger.info("✅ [SUMO SIMULATION] Emergency cleared. Restored signals to standard dynamic cycles.")

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
