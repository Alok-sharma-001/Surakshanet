import pytest
import time
from ml.routing.routing_engine import RoutingEngine
from app.services.routing_service import RoutingService, CORRIDOR_JUNCTIONS, CORRIDOR_EDGES


def test_routing_engine_profiles():
    """Verify emergency profile excludes congestion while citizen profile weights congestion (SN-041)."""
    engine = RoutingEngine()
    engine.build_graph(CORRIDOR_JUNCTIONS, CORRIDOR_EDGES)

    # In free-flow, both profiles find arterial path W_entry -> J0 -> J1 -> J2 -> J3 -> E_exit
    route_citizen = engine.find_route_between_nodes("W_entry", "E_exit", profile="citizen")
    route_emergency = engine.find_route_between_nodes("W_entry", "E_exit", profile="emergency")

    assert route_citizen["path"] == ["W_entry", "J0", "J1", "J2", "J3", "E_exit"]
    assert route_emergency["path"] == ["W_entry", "J0", "J1", "J2", "J3", "E_exit"]

    # Congest arterial link J1 -> J2 heavily (speed drops to 5 km/h, density 1800 pcu)
    now = time.time()
    traffic_data = {
        "J1-J2": {"speed": 5.0, "density": 1800.0, "source": "sumo", "timestamp": now},
        "J1_J2": {"speed": 5.0, "density": 1800.0, "source": "sumo", "timestamp": now},
        "E_J1_to_J2": {"speed": 5.0, "density": 1800.0, "source": "sumo", "timestamp": now},
    }
    engine.update_edge_weights(traffic_data, current_time=now)

    # Citizen profile: diverted around the heavy congestion via parallel northern bypass (N1 -> N2)
    rerouted_citizen = engine.find_route_between_nodes("W_entry", "E_exit", profile="citizen")

    # Congesting the link changes citizen route!
    assert "J1-J2" not in list(zip(rerouted_citizen["path"][:-1], rerouted_citizen["path"][1:]))
    assert rerouted_citizen["path"] != route_citizen["path"]

    # Emergency profile: deliberate exclusion of congestion (corridor will clear it!)
    # Remains on arterial path or weights differently
    rerouted_emergency = engine.find_route_between_nodes("W_entry", "E_exit", profile="emergency")
    assert rerouted_emergency["path"] == ["W_entry", "J0", "J1", "J2", "J3", "E_exit"]


def test_routing_edge_staleness_detection():
    """Verify edges older than 60s revert to free-flow and flag stale: true (SN-041)."""
    engine = RoutingEngine()
    engine.build_graph(CORRIDOR_JUNCTIONS, CORRIDOR_EDGES)

    # Telemetry timestamped 90s ago
    past_time = time.time() - 90.0
    stale_traffic = {
        "J0-J1": {"speed": 8.0, "density": 1400.0, "source": "sumo", "timestamp": past_time}
    }
    engine.update_edge_weights(stale_traffic, current_time=time.time())

    assert engine.graph["J0"]["J1"]["stale"] is True
    assert engine.graph["J0"]["J1"]["current_speed"] == engine.graph["J0"]["J1"]["free_flow_speed"]

    # Route using this edge reports stale: true
    res = engine.find_route_between_nodes("J0", "J1", profile="citizen")
    assert res["stale"] is True


def test_alternatives_diversity_and_honest_empty():
    """Verify alternative routes are diverse (< 70% edge overlap) and honest empty advice (SN-041/063)."""
    engine = RoutingEngine()
    engine.build_graph(CORRIDOR_JUNCTIONS, CORRIDOR_EDGES)

    # Find alternatives between W_entry and E_exit
    w_coords = (12.9177, 77.6211)
    e_coords = (12.9177, 77.6346)

    res = engine.find_alternatives(w_coords, e_coords, num_routes=2, profile="citizen")
    assert "primary" in res
    assert "advice" in res

    primary_path = res["primary"]["path"]
    primary_edges = set(zip(primary_path[:-1], primary_path[1:]))

    for alt in res["alternatives"]:
        alt_path = alt["path"]
        alt_edges = set(zip(alt_path[:-1], alt_path[1:]))
        overlap = len(alt_edges & primary_edges) / max(len(primary_edges), 1)
        assert overlap <= 0.70, f"Alternative shares {overlap*100}% of edges with primary (max 70% allowed)"


def test_live_junction_telemetry_reroutes_within_one_refresh():
    """SN-041's literal acceptance criterion: congesting a link (via real JunctionTelemetry,

    not a synthetic edge-keyed dict) changes the returned route within one refresh interval.
    Exercises the actual caller that was previously missing: build_traffic_data_from_junction_telemetry
    -> update_live_telemetry, fed from a JunctionTelemetry-shaped payload as the live bridge
    publishes it (approaches keyed by compass direction, not by edge id).
    """
    service = RoutingService()  # fresh instance — do not disturb the process-wide singleton

    baseline = service.find_route_between_nodes("W_entry", "E_exit", profile="citizen")
    assert baseline["path"] == ["W_entry", "J0", "J1", "J2", "J3", "E_exit"]

    # A real JunctionTelemetry payload for J2, heavily congested on its WEST approach
    # (that's where a vehicle arrives via the J1->J2 edge, per corridor_topology's
    # telemetry_approach mapping) — exactly what the SUMO bridge publishes per step.
    congested_telemetry = {
        "J2": {
            "junction_id": "J2",
            "source": "sumo",
            "approaches": [
                {"direction": "W", "mean_speed_kmh": 4.0, "pcu": 45.0, "vehicle_count": 30},
                {"direction": "E", "mean_speed_kmh": 40.0, "pcu": 2.0, "vehicle_count": 1},
                {"direction": "N", "mean_speed_kmh": 40.0, "pcu": 0.0, "vehicle_count": 0},
                {"direction": "S", "mean_speed_kmh": 40.0, "pcu": 0.0, "vehicle_count": 0},
            ],
        }
    }

    # One refresh interval: translate + apply, exactly what periodic_routing_refresh does on its cadence.
    traffic_data = service.build_traffic_data_from_junction_telemetry(congested_telemetry)
    assert "E_J1_to_J2" in traffic_data, "The J1->J2 edge must be identified from J2's WEST approach telemetry"
    assert traffic_data["E_J1_to_J2"]["speed"] == 4.0

    service.update_live_telemetry(traffic_data)

    rerouted = service.find_route_between_nodes("W_entry", "E_exit", profile="citizen")
    assert rerouted["path"] != baseline["path"], "Congesting J1->J2 must change the citizen route"
    assert ("J1", "J2") not in list(zip(rerouted["path"][:-1], rerouted["path"][1:]))


def test_record_junction_telemetry_populates_the_live_cache():
    """The Redis-fed cache (routing_telemetry.record_junction_telemetry) actually stores what it's given,

    and periodic_routing_refresh's translation step can read it straight back out (SN-041).
    """
    from app.services import routing_telemetry

    payload = {
        "junction_id": "J1",
        "source": "sumo",
        "approaches": [{"direction": "W", "mean_speed_kmh": 12.0, "pcu": 20.0}],
    }
    routing_telemetry.record_junction_telemetry(payload)

    cached = routing_telemetry._latest_junction_telemetry.get("J1")
    assert cached is not None
    assert cached["approaches"][0]["mean_speed_kmh"] == 12.0
    assert "_received_at" in cached, "cache entries must be timestamped for staleness handling"
