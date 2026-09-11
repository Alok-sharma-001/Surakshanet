"""SN-128..SN-133: Demo scenario registry.

Loads the five demo scenario configs (demo_a_normal.json .. demo_e_incident.json,
this directory) — the single source of truth both `/simulation/start`'s
`scenario_id` resolution and `make verify-determinism` read from. Never
constructs a scenario definition inline in Python; every field a consumer
needs (route_file, seed, scripted event timings) lives in the JSON files
next to this module, so the two call sites can't drift apart.
"""
import json
import os
from typing import Dict, List, Optional

_SCENARIOS_DIR = os.path.dirname(os.path.abspath(__file__))

_SCENARIO_FILES = [
    "demo_a_normal.json",
    "demo_b_surge.json",
    "demo_c_ambulance.json",
    "demo_d_rally.json",
    "demo_e_incident.json",
]


def load_scenarios() -> Dict[str, dict]:
    """Returns {scenario_id: config_dict} for all five scenarios, keyed by
    the config's own "id" field (never the filename)."""
    scenarios: Dict[str, dict] = {}
    for filename in _SCENARIO_FILES:
        path = os.path.join(_SCENARIOS_DIR, filename)
        with open(path, "r") as f:
            config = json.load(f)
        scenarios[config["id"]] = config
    return scenarios


def get_scenario(scenario_id: str) -> Optional[dict]:
    return load_scenarios().get(scenario_id.upper())


def list_scenario_ids() -> List[str]:
    return list(load_scenarios().keys())
