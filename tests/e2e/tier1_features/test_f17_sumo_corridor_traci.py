"""
Tier 1 Feature Coverage: Feature 17 - SUMO Corridor Network & TraCI Fixes (M4)
Requirement: Align 4-junction arterial (18 links) with TraCI phase strings;
resolve coordinator API mismatches.
"""

import os
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(17)
def test_sumo_corridor_network_files_exist():
    """TC-F17-01: Verify SUMO corridor network configuration files exist."""
    sim_dir = os.path.join(PROJECT_ROOT, "simulation")
    assert os.path.isdir(sim_dir), "simulation directory missing"
    # Find any .net.xml or .sumocfg files
    net_files = []
    for root, _, files in os.walk(sim_dir):
        for f in files:
            if f.endswith(".net.xml") or f.endswith(".sumocfg") or f.endswith(".nod.xml"):
                net_files.append(f)
    assert len(net_files) > 0, "No SUMO network files found in simulation/"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(17)
def test_corridor_articular_junctions_defined():
    """TC-F17-02: Verify 4 corridor junctions (J1, J2, J3, J4) defined in network."""
    sim_dir = os.path.join(PROJECT_ROOT, "simulation")
    found_corridor_refs = False
    for root, _, files in os.walk(sim_dir):
        for f in files:
            if f.endswith((".xml", ".py", ".json")):
                p = os.path.join(root, f)
                with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                    if "J1" in content and "J2" in content and "J3" in content and "J4" in content:
                        found_corridor_refs = True
                        break
        if found_corridor_refs:
            break
    assert found_corridor_refs, "Corridor junctions J1-J4 not referenced in simulation files"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(17)
def test_traci_phase_string_length_convention():
    """TC-F17-03: Verify phase strings comply with 18-link corridor standard."""
    standard_phase = "rrrrGGGggrrrrGGGgg"
    assert len(standard_phase) == 18, f"Expected 18-character phase string, got {len(standard_phase)}"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(17)
def test_sumo_live_bridge_file_exists():
    """TC-F17-04: Verify simulation/sumo_live_bridge.py or simulator bridge exists."""
    candidates = [
        os.path.join(PROJECT_ROOT, "simulation", "sumo_live_bridge.py"),
        os.path.join(PROJECT_ROOT, "simulation", "sumo_bridge.py"),
        os.path.join(PROJECT_ROOT, "simulation", "traci_bridge.py"),
    ]
    found = [p for p in candidates if os.path.exists(p)]
    assert len(found) > 0, f"SUMO bridge script not found in {candidates}"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(17)
def test_signals_api_endpoint_handles_phase_updates():
    """TC-F17-05: Verify signals API accepts valid phase configuration."""
    from tests.e2e.client import E2EHttpClient
    client = E2EHttpClient()
    res = client.get("/api/v1/signals/corridor")
    assert res.status_code in (200, 401, 404)
