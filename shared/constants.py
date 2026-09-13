from enum import Enum
from typing import Dict, Any
import enum


class DataSource(str, enum.Enum):
    SUMO = "sumo"          # measured from microsimulation via TraCI
    VISION = "vision"      # derived from camera frames by the detector
    MQTT = "mqtt"          # reported by a physical/simulated edge device
    MODEL = "model"        # produced by a trained model (forecaster, DQN)
    HEURISTIC = "heuristic"  # produced by a formula, NOT a trained model
    MANUAL = "manual"      # entered or seeded by a human


# SN-014: Deterministic seed for reproducible simulation and A/B evaluation
DEMO_SEED: int = 42

# The live SUMO bridge (simulation/sumo_live_bridge.py) is the only process
# with a real TraCI connection to the corridor simulation. It writes a Redis
# heartbeat key with this TTL on every successful publish, and self-expires
# under SIGKILL/SIGTERM/crash — the bridge's stop() and shutdown path write
# nothing to Redis, so a TTL is the only liveness signal that actually works.
# Single source of truth for the bridge's own setex call, health.py's
# staleness check, and backend/app/services/bridge_observer.py.
BRIDGE_HEARTBEAT_TTL_S: int = 10

# How old the bridge's last received SIMULATION_TICK may be before a consumer
# must treat it as stale rather than live. The bridge publishes at least once
# per TraCI step with a 50ms floor, so even an order of magnitude slower than
# nominal it emits several ticks per second — a multi-second gap is
# unambiguous. Used by backend/app/services/bridge_observer.py.
BRIDGE_TICK_STALE_AFTER_S: float = 3.0

# SN-026: Single-source Redis channel names across all producers and subscribers
REDIS_CHANNELS: Dict[str, str] = {
    "traffic": "traffic_updates",
    "signals": "signal_events",
    "alerts": "alert_events",
    "emergency": "emergency_events",
    "simulation": "simulation_updates",
    "control_commands": "control_commands",     # control service → bridge
    "control_decisions": "control_decisions",    # control service → API/UI
    "incidents": "incident_events",
    "events": "event_events",
    "advisories": "advisory_events",
    "cv_detections": "cv_detections",
}



PCU_FACTORS: Dict[str, float] = {
    'car': 1.0,
    'motorcycle': 0.5,
    'bus': 3.0,
    'truck': 3.0,
    'auto_rickshaw': 1.0,
    'bicycle': 0.2,
    'lcv': 1.5
}


def compute_pcu(vehicle_counts: Dict[str, Any]) -> float:
    """Computes total PCU from vehicle counts using the canonical PCU_FACTORS (SN-074).
    Normalizes common class aliases so all callers (vision, SUMO, MQTT, API) produce identical results.
    """
    alias_map = {
        "cars": "car",
        "motorcycles": "motorcycle",
        "two_wheelers": "motorcycle",
        "two_wheeler": "motorcycle",
        "tw": "motorcycle",
        "bike": "motorcycle",
        "bikes": "motorcycle",
        "buses": "bus",
        "trucks": "truck",
        "auto_rickshaws": "auto_rickshaw",
        "autorickshaw": "auto_rickshaw",
        "auto_rickshaw": "auto_rickshaw",
        "auto": "auto_rickshaw",
        "autos": "auto_rickshaw",
        "bicycles": "bicycle",
        "cycle": "bicycle",
        "cycles": "bicycle",
        "lcvs": "lcv",
    }
    pcu = 0.0
    for key, count in vehicle_counts.items():
        if count is None:
            continue
        try:
            cnt = float(count)
        except (ValueError, TypeError):
            continue
        norm_key = alias_map.get(str(key).lower(), str(key).lower())
        factor = PCU_FACTORS.get(norm_key, 1.0)
        pcu += cnt * factor
    return round(pcu, 2)


SIGNAL_CONSTRAINTS: Dict[str, int] = {
    'min_green_s': 10,
    'max_green_s': 60,
    'amber_s': 3,
    'all_red_s': 2
}

ALERT_THRESHOLDS: Dict[str, float] = {
    'congestion_density_pct': 80.0,
    'congestion_speed_kmh': 15.0,
    'spillback_risk': 0.85,
    'signal_timeout_s': 10.0
}

MARL_HYPERPARAMS: Dict[str, Any] = {
    'replay_buffer_size': 10000,
    'batch_size': 32,
    'gamma': 0.99,
    'lr': 0.001,
    'epsilon_start': 1.0,
    'epsilon_end': 0.01,
    'epsilon_decay': 0.995,
    'target_update_freq': 100,
    'green_extension_s': 5
}

ROUTING_WEIGHTS: Dict[str, float] = {
    'travel_time': 0.4,
    'congestion': 0.3,
    'distance': 0.3
}

ROUTING_WEIGHTS_CITIZEN: Dict[str, float] = {
    'travel_time': 0.4,
    'congestion': 0.3,
    'distance': 0.3
}

ROUTING_WEIGHTS_EMERGENCY: Dict[str, float] = {
    'travel_time': 0.7,
    'congestion': 0.0,
    'distance': 0.3
}

EMERGENCY_CONFIG: Dict[str, Any] = {
    'lookahead_junctions': 3,
    'green_hold_s': 30,
    'cross_street_max_red_s': 90.0,
    'min_speed_floor_kmh': 5.0,
    'emergency_speed_factor': 1.3,
    'saturation_flow_pcu_per_s': 0.5,
    'amber_s': 3,
    'all_red_s': 2,
    'recovery_baseline_window_s': 120,
    'recovery_sample_interval_s': 5,
    'recovery_consecutive_samples': 3,
    'recovery_threshold_pct': 0.10,
}

class TelemetrySource(str, Enum):
    LIVE = "live"
    SIM = "sim"
    MOCK = "mock"


# MQTT Standard Telemetry Topics
MQTT_SENSOR_TELEMETRY_TOPIC: str = "surakshanet/sensors/{sensor_id}/telemetry"
MQTT_JUNCTION_TELEMETRY_TOPIC: str = "surakshanet/junctions/{junction_id}/telemetry"

