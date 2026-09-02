"""
Traffic demand profiles for different times of day.
Used by NetworkGenerator and SUMO simulation.
"""

MORNING_PEAK = {
    'name': 'morning_peak',
    'description': 'Morning rush hour (8:00-10:00 AM)',
    'duration_s': 3600,
    'total_vehicles': 1200,
    'phases': [
        {'start': 0, 'end': 600, 'flow_pct': 0.15, 'description': 'Ramp up'},
        {'start': 600, 'end': 2400, 'flow_pct': 0.70, 'description': 'Peak flow'},
        {'start': 2400, 'end': 3600, 'flow_pct': 0.15, 'description': 'Ramp down'}
    ],
    'directional_split': {'NS': 0.6, 'EW': 0.4},  # More N-S flow in morning
    'vehicle_mix': {'car': 0.25, 'motorcycle': 0.40, 'auto_rickshaw': 0.15, 'bus': 0.10, 'truck': 0.10}
}

EVENING_PEAK = {
    'name': 'evening_peak',
    'description': 'Evening rush hour (5:00-7:00 PM)',
    'duration_s': 3600,
    'total_vehicles': 1400,
    'phases': [
        {'start': 0, 'end': 600, 'flow_pct': 0.20, 'description': 'Ramp up'},
        {'start': 600, 'end': 2400, 'flow_pct': 0.65, 'description': 'Peak flow'},
        {'start': 2400, 'end': 3600, 'flow_pct': 0.15, 'description': 'Ramp down'}
    ],
    'directional_split': {'NS': 0.4, 'EW': 0.6},  # More E-W flow in evening (reverse commute)
    'vehicle_mix': {'car': 0.30, 'motorcycle': 0.35, 'auto_rickshaw': 0.15, 'bus': 0.10, 'truck': 0.10}
}

OFF_PEAK = {
    'name': 'off_peak',
    'description': 'Off-peak hours (11:00 AM - 4:00 PM)',
    'duration_s': 3600,
    'total_vehicles': 600,
    'phases': [
        {'start': 0, 'end': 3600, 'flow_pct': 1.0, 'description': 'Uniform low flow'}
    ],
    'directional_split': {'NS': 0.5, 'EW': 0.5},
    'vehicle_mix': {'car': 0.20, 'motorcycle': 0.35, 'auto_rickshaw': 0.20, 'bus': 0.10, 'truck': 0.15}
}

NIGHT = {
    'name': 'night',
    'description': 'Night hours (11:00 PM - 5:00 AM)',
    'duration_s': 3600,
    'total_vehicles': 200,
    'phases': [
        {'start': 0, 'end': 3600, 'flow_pct': 1.0, 'description': 'Uniform low flow'}
    ],
    'directional_split': {'NS': 0.5, 'EW': 0.5},
    'vehicle_mix': {'car': 0.10, 'motorcycle': 0.10, 'auto_rickshaw': 0.05, 'bus': 0.05, 'truck': 0.70}
}

ALL_PROFILES = [MORNING_PEAK, EVENING_PEAK, OFF_PEAK, NIGHT]

def get_profile(name: str) -> dict:
    """Get profile by name."""
    for p in ALL_PROFILES:
        if p['name'] == name:
            return p
    return OFF_PEAK
