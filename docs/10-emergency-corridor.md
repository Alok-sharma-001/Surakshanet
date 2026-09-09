# 10 — Emergency Green Corridor

Covers **SN-039 … SN-050**. The audit found the skeleton real (API, DB persistence, Redis broadcast, SUMO forcing green) but four capabilities missing: **ETA propagation, real plan restoration, cross-street protection, clearance-time estimation**. It also found `GreenWaveController` storing the pre-emption baseline as the literal `{"mock_plan": True}` (`ml/emergency/green_wave.py:22`) and a hardcoded default route (`api/emergency.py:38`).

---

## 1. Emergency vehicle model (SN-039)

| Field | Type | Source |
|---|---|---|
| `vehicle_id` | string | dispatch system / operator |
| `vehicle_type` | `AMBULANCE` \| `FIRE` \| `POLICE` \| `VIP` | existing enum |
| `priority` | `CRITICAL` \| `HIGH` \| `MEDIUM` | existing enum |
| `origin` | lat/lon | GPS (simulated in demo, `source: "manual"` when operator-entered) |
| `destination` | lat/lon + name | operator selection |
| `route` | ordered junction IDs | **computed by A***, never defaulted |
| `current_position` | link ID + progress 0–1 | SUMO vehicle tracking |
| `route_etas` | per-junction seconds | computed, §3 |
| `status` | `ACTIVE` \| `COMPLETED` \| `CANCELLED` | existing enum |

**SN-049:** delete `EmergencyActivateRequest.get_route()`'s fallback to `["DEL-CP-01","DEL-ITO-02","DEL-ASH-04"]`. A request with neither a destination nor an explicit route returns `422`.

---

## 2. Route calculation (SN-041)

Use the existing A* in `ml/routing/routing_engine.py`. Two changes:

1. **Build the graph from the database**, not from a caller-supplied literal — junctions and edges seeded to match the SUMO network.
2. **Refresh edge weights from live telemetry** on a timer (default 10 s) via the existing `update_edge_weights`, which currently is never called with live data.

Weighting for emergency routing differs from citizen routing: emergency uses `0.7 · travel_time + 0.3 · distance` (congestion is something the corridor will *remove*, so weighting it heavily sends the vehicle the long way round). Citizen/alternative routing keeps the existing `ROUTING_WEIGHTS`. Both sets live in `shared/constants.py`.

---

## 3. ETA calculation (SN-042)

For each junction *j* on the route:

```
eta_j = Σ (link_length_i / max(current_speed_i, min_speed_floor))  for links i before j
        + Σ intersection_delay_k                                   for junctions k before j
```

- `current_speed_i` from live telemetry (`source: sumo` or `vision`).
- `min_speed_floor = 5 km/h` prevents division blow-up on a fully stopped link.
- `intersection_delay_k = 0` for junctions already pre-empted (that is the point of the corridor); otherwise half the cycle length.
- Emergency vehicles are modelled at `1.3 × link free-flow speed`, capped at the link limit — they move faster than traffic but are not teleported.

**Recompute every 2 s** while the corridor is active. ETAs are estimates and carry `source: "sumo"` (derived from measured speeds), never a confidence score.

---

## 4. Rolling activation (SN-043) — the core correction

**Do not turn every junction green at once.** That is the current behaviour and it is both unrealistic and needlessly damaging to cross traffic.

```
for each junction j in route:
    activate_at_j = eta_j − clearance_lead_s
    where clearance_lead_s = amber_s + all_red_s + queue_discharge_estimate_s
```

`queue_discharge_estimate_s = queue_length_pcu / saturation_flow_pcu_per_s` with `saturation_flow = 0.5 PCU/s/lane` — i.e. the green starts early enough to clear the standing queue *before* the vehicle arrives, not at the moment it arrives.

Junction states: `scheduled → preempted → passed → restored`. Only junctions inside the activation window are green; the rest run normally.

**Timeout guard:** if a junction has been `preempted` for more than `2 × its estimated occupancy` without a pass-through (vehicle rerouted, stuck, or lost), release it, restore the program, and log the reason. A corridor must never strand a junction on green indefinitely.

---

## 5. Signal pre-emption: capture and restore (SN-044, SN-045)

**Capture (before pre-empting):**
```python
logics = traci.trafficlight.getAllProgramLogics(tl_id)
current = traci.trafficlight.getProgram(tl_id)
phase   = traci.trafficlight.getPhase(tl_id)
captured_programs[tl_id] = {
    "program_id": current,
    "phase_index": phase,
    "logics": serialise(logics),
    "captured_at": now(),
}
```
This replaces `{"mock_plan": True}` entirely (SN-044).

**Restore (after pass-through):**
```python
traci.trafficlight.setProgramLogic(tl_id, deserialise(captured["logics"]))
traci.trafficlight.setProgram(tl_id, captured["program_id"])
```
Then **verify**: read the program back and compare against the captured copy. A mismatch is logged as an error and the junction is released to the control service, which re-adopts the base program. `emergency_events.status` may not become `COMPLETED` until `restored_at` is set and every junction verifies (see [05-database.md §3](05-database.md)).

Pre-emption is requested *through* the control service (which owns signal authority) and outranks the policy in the precedence order defined in [09-dynamic-signals.md §4](09-dynamic-signals.md). Amber and all-red are still observed on entry into pre-emption — a corridor never cuts a green directly to red on a conflicting approach.

---

## 6. Cross-street protection (SN-046)

Track accumulated red time per conflicting approach for the corridor's duration.

```
if approach.continuous_red_s > cross_street_max_red_s (default 90):
    insert compensating phase behind the emergency vehicle
    (only at junctions already in `passed` state — never ahead of the vehicle)
    record cross_street_max_red_s on the event
```

The constraint "only behind the vehicle" matters: inserting a compensating phase ahead of the ambulance defeats the corridor. Behind it, the phase costs nothing and prevents starvation.

**This is the answer to the sharpest question a judge will ask** — *"what about everyone else?"* — and §7 measures it.

---

## 7. Clearance time and recovery (SN-047, SN-048)

**Clearance time** = ETA at the final junction + queue-discharge time at that junction. Displayed as a live countdown.

**Recovery measurement** (after the corridor closes):
1. Baseline cross-street delay is sampled for 120 s *before* activation.
2. During and after the corridor, cross-street delay is sampled every 5 s.
3. `recovery_s` = time from corridor close until measured delay returns within **10%** of baseline for three consecutive samples.
4. The full series is stored and rendered as a chart.

`GET /emergency/{id}/recovery` returns `503` while the corridor is active — a recovery figure before recovery has happened would be fabricated.

**Demo line:** *"cross-traffic delay recovered in 4 minutes — we measured it, because a corridor that paralyses the rest of the city isn't a solution."*

---

## 8. Dashboard requirements (SN-050)

`frontend/dashboard/src/pages/EmergencyPage.tsx` must show, all from backend state:

| Element | Detail |
|---|---|
| Vehicle | id, type, priority |
| Destination | name + marker |
| Route | polyline on the Leaflet map |
| Per-junction ETA | seconds, updating |
| Junction states | `scheduled` / `preempted` / `passed` / `restored`, colour-coded |
| Next junction | highlighted, with countdown |
| Corridor status | active / closing / closed |
| Cross-traffic impact | current max red, threshold, whether a compensating phase fired |
| Recovery | chart after close, with the measured `recovery_s` |

**Visual requirement:** the corridor must *propagate* — junctions turn green ahead of the vehicle marker and revert behind it. A static list of green intersections reads as a mock; a travelling wave reads as a system.

---

## 9. Sequence

```
operator/dispatch  POST /emergency/activate {vehicle, origin, destination}
        │
        ▼  A* on live weights → route
        ▼  per-junction ETA
        ▼  activation schedule (ETA − clearance_lead)
        │
   ┌────┴─────────────────────────────────────────────┐
   │ loop every 2 s while ACTIVE:                     │
   │   update position from SUMO                      │
   │   recompute ETAs                                 │
   │   capture program + pre-empt junctions entering  │
   │     the activation window                        │
   │   restore junctions the vehicle has passed       │
   │   monitor cross-street red time                  │
   │   publish corridor state → /ws/emergency         │
   └────┬─────────────────────────────────────────────┘
        ▼  final junction passed
        ▼  restore all, verify, set restored_at
        ▼  measure recovery until baseline
        ▼  status = COMPLETED, audit row written
```

---

## 10. Acceptance criteria

1. Junctions activate in ETA order with measurable spacing — never simultaneously (SN-118).
2. After pass-through, `getAllProgramLogics()` matches the captured program exactly.
3. No conflicting approach exceeds `cross_street_max_red_s` without a compensating phase.
4. Recovery time is measured from telemetry and displayed; it is unavailable (503) while active.
5. `grep -rn "mock_plan" ml/ backend/` returns nothing.
6. `grep -rn "DEL-CP-01" backend/` returns nothing.
7. Two runs of Scenario C at the same seed produce the same ETA sequence and the same recovery figure.
8. The corridor visibly propagates ahead of the vehicle and reverts behind it.
