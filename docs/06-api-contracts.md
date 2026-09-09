# 06 — API Contracts

Base prefix `/api/v1` (`backend/app/config.py::API_PREFIX`). Auth: `Authorization: Bearer <JWT>` except where marked **PUBLIC**.

**Global response rules (R1, R2, R3):**
1. Every payload carrying a measured or derived number includes `source` from the `DataSource` enum.
2. `confidence` may appear **only** when `source == "model"`. Any other combination is a contract violation (test SN-123).
3. Unavailability is `503` with `{"status": "<subsystem>_unavailable", "reason": "<human cause>"}` — never a synthetic value.
4. Every mutating endpoint writes an `audit_logs` row (SN-104).

---

## 1. Existing endpoints (behaviour changes only)

| Endpoint | Change | Task |
|---|---|---|
| `GET /ml/predict/{junction_id}` | add `source`, `training_data`; **drop `confidence` on heuristic path** | SN-006, SN-007 |
| `GET /ml/train/status` | real state or `{"status":"unavailable","reason":...}` | SN-003 |
| `GET /ml/models` | report real weight availability incl. `training_data: "synthetic"` | SN-007 |
| `POST /ml/detect` | unchanged; now also used by the vision worker path | — |
| `GET /simulation/state` \| `/metrics` \| `/step` | `503 simulation_unavailable` when SUMO is down | SN-005 |
| `PATCH /signals/junctions/{id}/mode` | now actually changes controller behaviour; requires OPERATOR+ | SN-033, SN-100 |
| `POST /signals/junctions/{id}/override` | requires OPERATOR+, rate-limited, audited | SN-101, SN-104 |
| `POST /emergency/activate` | **hardcoded default route removed**; requires EMERGENCY_SERVICES/ADMIN | SN-049, SN-101 |
| `POST /routing/vms/broadcast` | hardcoded `"ACCIDENT CLEARED"` content removed | SN-010 |
| `GET /traffic/readings*` | `source` mandatory in every reading | SN-008 |

---

## 2. Health (Phase 1)

### `GET /health` — **PUBLIC**
`200` → `{"status":"ok","version":"1.0.0"}`

### `GET /health/deep` — **PUBLIC**
`200` → per-dependency object; see [04-environment-setup.md §6](04-environment-setup.md). `status` is `ok` only if all dependencies are `ok`, else `degraded`.

---

## 3. Control plane (Phase 2)

### `GET /signals/junctions/{junction_id}/decision` — OPERATOR+
Latest control decision. **This endpoint is the proof that the DQN is real** — it exposes the state vector and Q-values behind an observed phase change.

`200`:
```json
{
  "junction_id": "…",
  "timestamp": "2026-09-09T12:00:05Z",
  "controller": "marl",
  "model_version": "marl_policy_downtown@sha256:1f3c…",
  "state_vector": {
    "queue_length": 14.0, "mean_speed": 6.2, "occupancy": 0.61,
    "accumulated_wait": 88.0, "phase_index": 0, "elapsed_green": 22.0,
    "tod_sin": 0.5, "tod_cos": -0.86
  },
  "q_values": [3.41, 2.87],
  "action": 0,
  "action_label": "extend",
  "action_source": "policy",
  "clamped": false,
  "clamp_reason": null,
  "applied_phase": 0,
  "applied_duration_s": 5.0,
  "reason": "Q(extend)=3.41 > Q(advance)=2.87; queue 14 PCU on N approach",
  "source": "sumo"
}
```
`503` when the control service has produced no decision within `3 × control_step_s`.

### `POST /ab/run` — OPERATOR+
Request: `{"scenario":"surge","seed":42,"duration_s":900}`
`202` → `{"run_id":"…","status":"running"}`
`409` if a run is already active.

### `GET /ab/runs/{run_id}` — OPERATOR+
```json
{
  "run_id": "…", "scenario": "surge", "seed": 42, "duration_s": 900,
  "status": "complete",
  "arm_a": {"controller":"webster","avg_delay_s":42.8,"total_delay_s":51360,
            "avg_queue_pcu":18.4,"avg_wait_s":37.2,"throughput_veh_h":1180,
            "avg_travel_time_s":196.4,"vehicles_served":1200},
  "arm_b": {"controller":"marl","avg_delay_s":29.5,"total_delay_s":35400,
            "avg_queue_pcu":12.1,"avg_wait_s":24.9,"throughput_veh_h":1268,
            "avg_travel_time_s":171.0,"vehicles_served":1200},
  "improvement": {"avg_delay_pct":31.1,"avg_queue_pct":34.2,"throughput_pct":7.5},
  "formula": "(a - b) / a * 100 for cost metrics; (b - a) / a * 100 for throughput",
  "source": "sumo",
  "completed_at": "2026-09-09T12:15:00Z"
}
```
**`improvement` is absent while `status != "complete"`.** No client may compute or display an improvement figure itself.

---

## 4. Emergency corridor (Phase 3)

### `POST /emergency/activate` — EMERGENCY_SERVICES, ADMIN
```json
{"vehicle_id":"AMB-07","vehicle_type":"AMBULANCE","priority":"CRITICAL",
 "origin":{"lat":22.7196,"lon":75.8577},
 "destination":{"lat":22.7532,"lon":75.8937,"name":"District Hospital"}}
```
`route_junction_ids` is **optional**; when omitted the route is computed by A* on live weights. There is no default route (SN-049) — a request with neither a destination nor an explicit route is `422`.

`201`:
```json
{"event_id":"…","route":["J0","J1","J2","J3"],
 "route_etas":[{"junction_id":"J0","eta_s":24},{"junction_id":"J1","eta_s":61},
               {"junction_id":"J2","eta_s":98},{"junction_id":"J3","eta_s":140}],
 "clearance_time_s":168,"activation_policy":"rolling","source":"sumo"}
```

### `GET /emergency/{event_id}/corridor` — EMERGENCY_SERVICES, OPERATOR+
```json
{"event_id":"…","status":"ACTIVE","current_position":{"link_id":"J1_J2","progress":0.4},
 "next_junction":"J2","next_junction_eta_s":18,
 "junctions":[{"junction_id":"J0","state":"restored","activated_at":"…","passed_at":"…"},
              {"junction_id":"J1","state":"restored"},
              {"junction_id":"J2","state":"preempted","activated_at":"…"},
              {"junction_id":"J3","state":"scheduled","activates_in_s":22}],
 "cross_street":{"max_red_s":74,"threshold_s":90,"compensating_phase_inserted":false},
 "source":"sumo"}
```

### `GET /emergency/{event_id}/recovery` — OPERATOR+
Available only after the corridor closes. `503` while `status == "ACTIVE"`.
```json
{"event_id":"…","recovery_s":238,
 "cross_street_baseline_delay_s":19.4,"cross_street_peak_delay_s":58.1,
 "returned_to_baseline_at":"…","series":[{"t":0,"delay_s":58.1}, …],
 "source":"sumo"}
```

---

## 5. Events (Phase 4)

| Endpoint | Role | Purpose |
|---|---|---|
| `POST /events` | OPERATOR, ADMIN | create (status `DRAFT`) |
| `GET /events` | OPERATOR, ADMIN, EMERGENCY_SERVICES | list |
| `PATCH /events/{id}` | OPERATOR, ADMIN | edit while `DRAFT` |
| `POST /events/{id}/predict` | OPERATOR, ADMIN | run dual-world what-if → `PREDICTED` |
| `GET /events/{id}/prediction` | OPERATOR, ADMIN | measured results |
| `POST /events/{id}/approve` | ADMIN | → `APPROVED` |
| `POST /events/{id}/publish` | ADMIN | → `PUBLISHED`, emits advisory |

`GET /events/{id}/prediction` `200`:
```json
{"event_id":"…","seed":42,"status":"complete",
 "link_deltas":[{"link_id":"E_J1_J2","baseline_travel_time_s":42.1,
                 "event_travel_time_s":71.8,"delta_pct":70.5,"severity":"SEVERE"}],
 "severity_summary":{"SEVERE":2,"MODERATE":3,"LOW":6},
 "alternatives":[{"rank":1,"route_text":"Ring Road via LIG Square",
                  "added_distance_km":1.8,"added_time_s":240,
                  "congestion":"LOW","reason":"avoids both SEVERE links"}],
 "source":"sumo","computed_at":"…"}
```
`202` with `{"status":"running"}` while the two SUMO worlds execute. **No severity is returned before both worlds complete.**

---

## 6. Public / citizen (Phase 4) — **PUBLIC, no auth**

Rate-limited per IP. Exposes **no** junction UUIDs, model internals, operator identities or raw telemetry (SN-113).

### `GET /public/advisories`
```json
{"advisories":[
  {"id":"…","severity":"SEVERE",
   "headline":"Heavy traffic expected: Vijay Nagar → Palasia",
   "window":{"start":"2026-09-10T16:00:00+05:30","end":"2026-09-10T20:00:00+05:30"},
   "expected_delay_min":{"low":20,"high":35},
   "cause":"Public event, 25,000 expected",
   "recommended":"Ring Road via LIG Square (+4 min, clear)",
   "leave_before":"2026-09-10T15:20:00+05:30",
   "published_at":"…"}],
 "generated_at":"…"}
```
Field names are deliberately plain. There is no `source`, no `confidence`, no `model_version` on this surface — citizens get the decision, not the machinery.

### `GET /public/status`
Current corridor-level conditions in plain language; `{"advisories":[], "status":"normal"}` when nothing is active. **Never fabricates an advisory to look busy.**

---

## 7. Vision (Phase 5)

| Endpoint | Role | Notes |
|---|---|---|
| `GET /vision/status` | OPERATOR+ | source, fps, frames processed, or `unavailable` + reason |
| `GET /vision/detections/latest?camera_id=` | OPERATOR+ | real detections only |
| `GET /vision/flags?status=UNVERIFIED` | OPERATOR+ | behaviour flags |
| `PATCH /vision/flags/{id}/resolve` | OPERATOR+ | `{"status":"CONFIRMED"\|"DISMISSED","note":"…"}` — audited |
| `POST /vision/zones` | OPERATOR, ADMIN | restricted polygon for no-parking |

`GET /vision/status` when idle:
```json
{"status":"unavailable","reason":"no video source configured","source":"vision"}
```

Flag payload:
```json
{"id":"…","flag_type":"WRONG_WAY","status":"UNVERIFIED",
 "camera_id":"CAM-01","track_id":"t-4192","detected_at":"…","confidence":0.91,
 "evidence":{"motion_heading_deg":274,"lane_heading_deg":94,
             "opposed_frames":38,"sustained_s":3.8},
 "note":"Behaviour flagged for review. Not a confirmed violation.",
 "source":"vision"}
```
The `note` field is mandatory on every behaviour flag (SN-082).

---

## 8. Incidents (Phase 6)

| Endpoint | Role | Notes |
|---|---|---|
| `GET /incidents` | OPERATOR+, EMERGENCY_SERVICES | |
| `GET /incidents/{id}` | OPERATOR+ | includes fired indicators with measured values |
| `POST /incidents/{id}/confirm` | OPERATOR, ADMIN | **human gate 1** |
| `POST /incidents/{id}/dismiss` | OPERATOR, ADMIN | |
| `POST /incidents/{id}/escalate` | OPERATOR, ADMIN | notifies EMERGENCY_SERVICES |
| `POST /incidents/{id}/publish-warning` | ADMIN | **human gate 2 — irreversible** |

```json
{"id":"…","incident_type":"POSSIBLE_INCIDENT","status":"UNVERIFIED",
 "link_id":"E_J1_J2","detected_at":"…","confidence":0.74,
 "indicators":[
   {"indicator":"SPEED_COLLAPSE","measured_value":4.1,"threshold":10.0},
   {"indicator":"STATIONARY_VEHICLE","measured_value":31.0,"threshold":20.0},
   {"indicator":"OCCUPANCY_SPIKE","measured_value":0.88,"threshold":0.75}],
 "indicators_fired":3,"indicators_total":5,
 "evidence_ref":"frames/blurred/…jpg",
 "note":"Possible incident. Unverified — operator review required.",
 "source":"sumo"}
```
`POST /incidents/{id}/publish-warning` returns `409` unless `status == "CONFIRMED"` — automation may never reach the public without a human.

---

## 9. Audit (Phase 7)

`GET /audit` — **ADMIN only**. Filters: `actor_type`, `action`, `target_id`, `from`, `to`. Paginated, ordered by timestamp desc.
`GET /audit/{id}` — single entry with full `input`/`output`.

---

## 10. WebSocket channels

| Path | Payload | Phase |
|---|---|---|
| `/ws/traffic` | canonical telemetry (with `source`) | existing |
| `/ws/signals` | phase changes, mode changes | existing |
| `/ws/alerts` | alerts | existing |
| `/ws/emergency` | corridor state transitions | existing |
| `/ws/training` | real training progress or `unavailable` | SN-003 |
| `/ws/control` | control decisions as they are made | SN-029 |
| `/ws/incidents` | incident created / status changed | SN-091 |
| `/ws/events` | event status changes | SN-062 |

All messages: `{"type":"…","timestamp":"…","payload":{…},"source":"…"}`. Heartbeat `ping`/`pong` as already implemented in `websocket_routes.py`.

---

## 11. Error contract

| Code | Meaning | Body |
|---|---|---|
| 400 | Malformed request | `{"detail":"…"}` |
| 401 | Missing/invalid token | `{"detail":"Not authenticated"}` |
| 403 | Role denied | `{"detail":"Role OPERATOR cannot perform CORRIDOR_ACTIVATE"}` |
| 404 | Not found | |
| 409 | State conflict (e.g. warning before confirmation) | `{"detail":"Incident must be CONFIRMED before a public warning"}` |
| 422 | Validation failure | FastAPI default |
| 429 | Rate limit | `{"detail":"…","retry_after_s":n}` |
| 503 | Subsystem unavailable | `{"status":"simulation_unavailable","reason":"TraCI connection refused"}` |

**503 is a first-class, correct response in this system.** Returning a plausible number instead of a 503 is the defect this project is correcting.
