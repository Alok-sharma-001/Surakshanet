# 15 — Routing Engine

Covers **SN-041, SN-063, SN-064, SN-010**. The audit's finding: `ml/routing/routing_engine.py` contains a genuine A* with haversine distance and congestion-weighted edges — but `update_edge_weights()` is never called with live data and the graph is never built from the database, so routes never change in response to traffic.

---

## 1. Current state

Working: `build_graph()`, `update_edge_weights()`, `find_route()` (A*), haversine, congestion factor from density/capacity, weight `0.4·travel_time + 0.3·congestion + 0.3·distance` from `shared/constants.py::ROUTING_WEIGHTS`.

Not working: nothing feeds it. Endpoints `POST /routing/route`, `/routing/alternatives`, `GET /routing/congestion` operate on a graph that is empty or stale. `api/routing.py:54` and `RoutingPage.tsx:43` contain a hardcoded `"ACCIDENT CLEARED"` VMS message (removed by SN-010).

---

## 2. Graph construction (SN-041)

`backend/app/services/routing_service.py` (new) owns a singleton graph.

**Build** on startup and on demand:
- Nodes: `junctions` rows (id, name, lat, lon).
- Edges: a new `network_links` seed matching the SUMO network — `from_junction`, `to_junction`, `sumo_edge_id`, `length_m`, `lanes`, `free_flow_speed_kmh`, `capacity_pcu_h`.

The mapping from SUMO edge IDs to database links is what lets live telemetry update the right edge. Seeded by `scripts/seed_demo.py` (SN-134) so the corridor `J0→J1→J2→J3` and its N/S approaches are represented exactly once.

**Refresh** every 10 s from the latest telemetry per link: current speed, density, and — after Phase 6 — an incident penalty on blocked links.

```python
routing_engine.update_edge_weights({
    "J1-J2": {"speed": 12.4, "density": 640.0, "source": "sumo"},
    ...
})
```

**Staleness rule:** an edge whose telemetry is older than 60 s reverts to its free-flow weight and is marked `stale: true` in the response. A route computed on stale data says so; it does not silently present old conditions as current.

---

## 3. Two weight profiles

| Profile | Weights | Used by |
|---|---|---|
| `citizen` | `0.4 travel_time + 0.3 congestion + 0.3 distance` (existing `ROUTING_WEIGHTS`) | alternatives, advisories |
| `emergency` | `0.7 travel_time + 0.3 distance` — **congestion deliberately excluded** | corridor routing |

The emergency profile excludes congestion because the corridor *removes* it. Weighting congestion for an emergency vehicle routes it the long way around traffic the system is about to clear. Both profiles live in `shared/constants.py`.

---

## 4. Alternatives (SN-063)

`POST /routing/alternatives` returns up to 3 routes, each with `route_text` (human place names), `distance_km`, `travel_time_s`, `added_time_s` vs. the primary, worst-link congestion band, and a `reason`.

Diversity: successive alternatives are computed with a penalty applied to edges already used by higher-ranked routes, so three near-identical paths are not returned as three options.

**Honest empty case:** when no alternative improves on the affected route, return an empty list with `"advice": "no better alternative — consider delayed departure"`. This feeds the departure recommendation in [12-citizen-advisory.md §6](12-citizen-advisory.md). Inventing a third-best route to fill the table is forbidden.

---

## 5. VMS (SN-010)

Variable-message-sign endpoints stay, with all hardcoded content removed. Messages are composed from real state (active incidents, corridors, published advisories) or the endpoint returns an empty active set. A VMS broadcast is a public communication and is audited like one.

---

## 6. Acceptance criteria

1. Congesting a link in SUMO changes the route returned by `POST /routing/route` within one refresh interval (SN-041 test).
2. The emergency profile and the citizen profile return measurably different routes under congestion.
3. An edge with stale telemetry is flagged `stale: true`, not silently used.
4. `grep -rn "ACCIDENT CLEARED" backend/ frontend/` returns nothing.
5. Alternatives are diverse — no two returned routes share more than 70% of their edges.
6. When no better alternative exists, the response says so rather than returning a worse route as a recommendation.
