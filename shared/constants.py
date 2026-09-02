from typing import Dict, Any

PCU_FACTORS: Dict[str, float] = {
    'car': 1.0,
    'motorcycle': 0.5,
    'bus': 3.0,
    'truck': 3.0,
    'auto_rickshaw': 1.0,
    'bicycle': 0.2,
    'lcv': 1.5
}

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

EMERGENCY_CONFIG: Dict[str, Any] = {
    'lookahead_junctions': 3,
    'green_hold_s': 30
}
