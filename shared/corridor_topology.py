"""Canonical SUMO corridor network topology (SN-041 / docs/15-routing.md §2).

Single source of truth for junction/edge identifiers matching
`simulation/networks/corridor.{nod,edg}.xml`, shared by the routing service
(backend) and the live SUMO bridge (simulation) so the two never drift apart.
Real coordinates aligned with corridor.net.xml (J0..J3 at 300m spacing, plus
N/S cross approaches).
"""

from typing import Any, Dict, List, Optional, Tuple

CORRIDOR_JUNCTIONS: List[Dict[str, Any]] = [
    {"id": "W_entry", "name": "West Expressway Entry", "lat": 12.9177, "lon": 77.6211},
    {"id": "J0", "name": "Corridor Junction 0", "lat": 12.9177, "lon": 77.6238},
    {"id": "J1", "name": "Corridor Junction 1", "lat": 12.9177, "lon": 77.6265},
    {"id": "J2", "name": "Corridor Junction 2", "lat": 12.9177, "lon": 77.6292},
    {"id": "J3", "name": "Corridor Junction 3", "lat": 12.9177, "lon": 77.6319},
    {"id": "E_exit", "name": "East Expressway Exit / Hospital", "lat": 12.9177, "lon": 77.6346},
    {"id": "N0", "name": "North Approach 0", "lat": 12.9186, "lon": 77.6238},
    {"id": "S0", "name": "South Approach 0", "lat": 12.9168, "lon": 77.6238},
    {"id": "N1", "name": "North Approach 1", "lat": 12.9186, "lon": 77.6265},
    {"id": "S1", "name": "South Approach 1", "lat": 12.9168, "lon": 77.6265},
    {"id": "N2", "name": "North Approach 2", "lat": 12.9186, "lon": 77.6292},
    {"id": "S2", "name": "South Approach 2", "lat": 12.9168, "lon": 77.6292},
    {"id": "N3", "name": "North Approach 3", "lat": 12.9186, "lon": 77.6319},
    {"id": "S3", "name": "South Approach 3", "lat": 12.9168, "lon": 77.6319},
]

# `telemetry_approach`: (junction_id, approach_direction) of the real SUMO
# traffic-light junction a vehicle arrives at via this edge, matching the
# `direction` field the live bridge publishes per approach in JunctionTelemetry
# (docs/07-telemetry.md §3). Direction is "which side the vehicle enters from"
# — an eastbound J0->J1 edge arrives at J1's WEST approach. Omitted for edges
# whose destination isn't a signalized junction (route endpoints, bypass
# roads) — those have no detector data and simply keep their free-flow speed.
CORRIDOR_EDGES: List[Dict[str, Any]] = [
    {"from": "W_entry", "to": "J0", "sumo_edge_id": "E_W_to_J0", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 100.0, "telemetry_approach": ("J0", "W")},
    {"from": "J0", "to": "W_entry", "sumo_edge_id": "E_J0_to_W", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 100.0},
    {"from": "J0", "to": "J1", "sumo_edge_id": "E_J0_to_J1", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 300.0, "telemetry_approach": ("J1", "W")},
    {"from": "J1", "to": "J0", "sumo_edge_id": "E_J1_to_J0", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 300.0, "telemetry_approach": ("J0", "E")},
    {"from": "J1", "to": "J2", "sumo_edge_id": "E_J1_to_J2", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 300.0, "telemetry_approach": ("J2", "W")},
    {"from": "J2", "to": "J1", "sumo_edge_id": "E_J2_to_J1", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 300.0, "telemetry_approach": ("J1", "E")},
    {"from": "J2", "to": "J3", "sumo_edge_id": "E_J2_to_J3", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 300.0, "telemetry_approach": ("J3", "W")},
    {"from": "J3", "to": "J2", "sumo_edge_id": "E_J3_to_J2", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 300.0, "telemetry_approach": ("J2", "E")},
    {"from": "J3", "to": "E_exit", "sumo_edge_id": "E_J3_to_E", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 100.0},
    {"from": "E_exit", "to": "J3", "sumo_edge_id": "E_E_to_J3", "free_flow_speed": 50.0, "capacity": 2000, "length_m": 100.0, "telemetry_approach": ("J3", "E")},

    {"from": "N0", "to": "J0", "sumo_edge_id": "E_N0_to_J0", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0, "telemetry_approach": ("J0", "N")},
    {"from": "J0", "to": "N0", "sumo_edge_id": "E_J0_to_N0", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0},
    {"from": "S0", "to": "J0", "sumo_edge_id": "E_S0_to_J0", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0, "telemetry_approach": ("J0", "S")},
    {"from": "J0", "to": "S0", "sumo_edge_id": "E_J0_to_S0", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0},

    {"from": "N1", "to": "J1", "sumo_edge_id": "E_N1_to_J1", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0, "telemetry_approach": ("J1", "N")},
    {"from": "J1", "to": "N1", "sumo_edge_id": "E_J1_to_N1", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0},
    {"from": "S1", "to": "J1", "sumo_edge_id": "E_S1_to_J1", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0, "telemetry_approach": ("J1", "S")},
    {"from": "J1", "to": "S1", "sumo_edge_id": "E_J1_to_S1", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0},

    {"from": "N2", "to": "J2", "sumo_edge_id": "E_N2_to_J2", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0, "telemetry_approach": ("J2", "N")},
    {"from": "J2", "to": "N2", "sumo_edge_id": "E_J2_to_N2", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0},
    {"from": "S2", "to": "J2", "sumo_edge_id": "E_S2_to_J2", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0, "telemetry_approach": ("J2", "S")},
    {"from": "J2", "to": "S2", "sumo_edge_id": "E_J2_to_S2", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0},

    {"from": "N3", "to": "J3", "sumo_edge_id": "E_N3_to_J3", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0, "telemetry_approach": ("J3", "N")},
    {"from": "J3", "to": "N3", "sumo_edge_id": "E_J3_to_N3", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0},
    {"from": "S3", "to": "J3", "sumo_edge_id": "E_S3_to_J3", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0, "telemetry_approach": ("J3", "S")},
    {"from": "J3", "to": "S3", "sumo_edge_id": "E_J3_to_S3", "free_flow_speed": 50.0, "capacity": 1000, "length_m": 100.0},

    # Parallel Northern arterial bypass (for alternative route calculation under arterial congestion)
    # — no destination here is a signalized junction, so none of these carry live telemetry.
    {"from": "N0", "to": "N1", "sumo_edge_id": "E_N0_to_N1", "free_flow_speed": 40.0, "capacity": 1500, "length_m": 300.0},
    {"from": "N1", "to": "N0", "sumo_edge_id": "E_N1_to_N0", "free_flow_speed": 40.0, "capacity": 1500, "length_m": 300.0},
    {"from": "N1", "to": "N2", "sumo_edge_id": "E_N1_to_N2", "free_flow_speed": 40.0, "capacity": 1500, "length_m": 300.0},
    {"from": "N2", "to": "N1", "sumo_edge_id": "E_N2_to_N1", "free_flow_speed": 40.0, "capacity": 1500, "length_m": 300.0},
    {"from": "N2", "to": "N3", "sumo_edge_id": "E_N2_to_N3", "free_flow_speed": 40.0, "capacity": 1500, "length_m": 300.0},
    {"from": "N3", "to": "N2", "sumo_edge_id": "E_N3_to_N2", "free_flow_speed": 40.0, "capacity": 1500, "length_m": 300.0},
    {"from": "W_entry", "to": "N0", "sumo_edge_id": "E_W_to_N0", "free_flow_speed": 40.0, "capacity": 1500, "length_m": 140.0},
    {"from": "N3", "to": "E_exit", "sumo_edge_id": "E_N3_to_E", "free_flow_speed": 40.0, "capacity": 1500, "length_m": 140.0},
]

_EDGE_ID_BY_PAIR: Dict[Tuple[str, str], str] = {
    (e["from"], e["to"]): e["sumo_edge_id"] for e in CORRIDOR_EDGES
}


_EDGE_LENGTH_BY_PAIR: Dict[Tuple[str, str], float] = {
    (e["from"], e["to"]): e["length_m"] for e in CORRIDOR_EDGES
}

_LENGTH_BY_SUMO_EDGE_ID: Dict[str, float] = {
    e["sumo_edge_id"]: e["length_m"] for e in CORRIDOR_EDGES
}

_EDGE_BY_SUMO_ID: Dict[str, Dict[str, Any]] = {
    e["sumo_edge_id"]: e for e in CORRIDOR_EDGES
}

# The single arterial chain (W_entry - J0 - J1 - J2 - J3 - E_exit) — used to
# find a real "immediately upstream" edge for FLOW_DROP (SN-088), rather than
# deriving one from the same sample being evaluated.
_ARTERIAL_SEQUENCE: List[str] = ["W_entry", "J0", "J1", "J2", "J3", "E_exit"]


def edge_length_m_for_sumo_id(sumo_edge_id: str) -> Optional[float]:
    """Real edge length in meters for a SUMO edge id, or None if it isn't a known corridor edge."""
    return _LENGTH_BY_SUMO_EDGE_ID.get(sumo_edge_id)


def upstream_edge_for_sumo_id(sumo_edge_id: str) -> Optional[str]:
    """Real SUMO edge id immediately upstream of the given arterial edge (the
    edge feeding traffic into its 'from' junction along the single W_entry -
    J0 - J1 - J2 - J3 - E_exit chain), or None if this edge isn't part of
    that chain or has no predecessor (e.g. the corridor's own entry edge).

    Used by the anomaly service's FLOW_DROP indicator (SN-088) so "upstream
    throughput" is a real measurement of a different, actual link — never
    derived from the same sample being evaluated.
    """
    edge = _EDGE_BY_SUMO_ID.get(sumo_edge_id)
    if not edge:
        return None
    frm = edge["from"]
    if frm not in _ARTERIAL_SEQUENCE:
        return None
    idx = _ARTERIAL_SEQUENCE.index(frm)
    if idx == 0:
        return None
    prev_junction = _ARTERIAL_SEQUENCE[idx - 1]
    return _EDGE_ID_BY_PAIR.get((prev_junction, frm))


def edge_id_for(from_junction: str, to_junction: str) -> Optional[str]:
    """Real SUMO edge id for a junction pair, or None if they aren't directly connected."""
    return _EDGE_ID_BY_PAIR.get((from_junction, to_junction))


def edge_length_m_for(from_junction: str, to_junction: str) -> Optional[float]:
    """Real edge length in meters for a junction pair, or None if not directly connected."""
    return _EDGE_LENGTH_BY_PAIR.get((from_junction, to_junction))


def route_edge_lengths_m(route_junction_ids: List[str]) -> Dict[str, float]:
    """Maps '{from}_{to}' -> real length in meters for each consecutive hop on the route."""
    lengths = {}
    for i in range(len(route_junction_ids) - 1):
        u, v = route_junction_ids[i], route_junction_ids[i + 1]
        length = edge_length_m_for(u, v)
        if length is not None:
            lengths[f"{u}_{v}"] = length
    return lengths


_TELEMETRY_APPROACH_BY_SUMO_EDGE_ID: Dict[str, Tuple[str, str]] = {
    e["sumo_edge_id"]: e["telemetry_approach"] for e in CORRIDOR_EDGES if "telemetry_approach" in e
}

_SUMO_EDGE_ID_BY_TELEMETRY_APPROACH: Dict[Tuple[str, str], str] = {
    e["telemetry_approach"]: e["sumo_edge_id"] for e in CORRIDOR_EDGES if "telemetry_approach" in e
}


def telemetry_approach_for_edge(sumo_edge_id: str) -> Optional[Tuple[str, str]]:
    """(junction_id, approach_direction) whose live telemetry describes this edge, or None.

    None for edges whose destination isn't a signalized junction — those have
    no detector data and are never a source of live congestion, honestly.
    """
    return _TELEMETRY_APPROACH_BY_SUMO_EDGE_ID.get(sumo_edge_id)


def edge_for_telemetry_approach(junction_id: str, direction: str) -> Optional[str]:
    """Real SUMO edge ID whose approach is (junction_id, direction), or None."""
    return _SUMO_EDGE_ID_BY_TELEMETRY_APPROACH.get((junction_id, direction))


def route_to_edge_ids(route_junction_ids: List[str]) -> Optional[List[str]]:
    """Maps a sequence of junction ids to the real consecutive SUMO edge ids.

    Returns None if any consecutive pair isn't a direct edge in the topology
    — callers must not guess at an edge id that doesn't exist.
    """
    edges = []
    for i in range(len(route_junction_ids) - 1):
        eid = edge_id_for(route_junction_ids[i], route_junction_ids[i + 1])
        if eid is None:
            return None
        edges.append(eid)
    return edges
