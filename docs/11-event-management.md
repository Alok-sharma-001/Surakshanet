# 11 — Event / Rally Traffic Management

Covers **SN-051 … SN-060**. Built from scratch: a keyword sweep of `backend/app`, `ml` and `frontend/dashboard/src` for `rally`, `event_management` and `special event` returns **0 files**.

The audit identifies this, with the citizen advisory, as the project's clearest differentiator — because every competing entry in this category demos a system that *reacts* to congestion, and this one *predicts* it.

**Key insight that keeps this cheap:** you do not need a new model. The what-if is two SUMO runs. Simulation-based prediction is also more defensible than a regression trained on data you do not have.

---

## 1. Event entity (SN-051)

Schema in [05-database.md §4](05-database.md). Operator-supplied fields:

| Field | Notes |
|---|---|
| `name` | e.g. "Ganesh Visarjan Procession" |
| `event_type` | `RALLY`, `PROCESSION`, `FESTIVAL`, `VIP_MOVEMENT`, `MARATHON`, `CONCERT`, `DEMONSTRATION`, `GOVERNMENT`, `OTHER` |
| `starts_at` / `ends_at` | with timezone; displayed IST |
| `expected_crowd` | integer — drives demand translation (§3) |
| `affected_links` | SUMO edge IDs, selected on the map |
| `closure_links` | subset that is fully closed |
| `intensity` | operator's own `LOW`/`MEDIUM`/`HIGH` estimate |

**`intensity` is the operator's judgement, not a prediction.** The system's predicted severity (§4) is computed separately and may disagree — that disagreement is useful information, not an error.

---

## 2. Status lifecycle (SN-058)

```
DRAFT ──predict──▶ PREDICTED ──approve(ADMIN)──▶ APPROVED ──publish(ADMIN)──▶ PUBLISHED
  │                     │                             │                            │
  └──────────────── CANCELLED ◀───────────────────────┘                            ▼
                                                                                CLOSED
```

Rules:
- `predict` may run repeatedly while `DRAFT`/`PREDICTED`; each run creates a new `event_predictions` row.
- `approve` requires an existing completed prediction. Approving without measured data is rejected.
- `publish` emits the citizen advisory ([12-citizen-advisory.md](12-citizen-advisory.md)) and is a **human gate**, audited (SN-068, SN-104).
- Only `PUBLISHED` events reach the public surface.

---

## 3. Demand translation (SN-054)

Convert expected crowd to additional vehicle trips using **openly stated assumptions**. These are configuration in `services/control_service/config.py`, printed in the UI next to the prediction, and quoted on stage.

```
default_mode_split = {
    "two_wheeler": 0.40,   occupancy 1.4
    "car":         0.25,   occupancy 2.1
    "auto":        0.15,   occupancy 2.5
    "bus":         0.15,   occupancy 35.0
    "walk_other":  0.05,   occupancy —  (generates no vehicle trips)
}
arrival_profile  = 60% arrive in the 90 min before start, 80% depart in the 60 min after end
```

```
vehicles_of_type = expected_crowd × mode_share × (1 / occupancy)
```

Worked example — 25,000 attendees:
`two_wheeler = 25000 × 0.40 / 1.4 ≈ 7,143` · `car = 25000 × 0.25 / 2.1 ≈ 2,976` · `auto ≈ 1,500` · `bus ≈ 107`.

These trips are injected into `affected_links` following the arrival profile, and `closure_links` are removed from the network for the event window.

**Honesty requirement:** the UI labels these assumptions as assumptions, with the numbers visible. A judge who asks "where does 7,143 come from?" must get an answer from the screen, not from memory.

---

## 4. Dual-world what-if (SN-055, SN-056)

Reuses the A/B runner from [08-marl-control.md §7](08-marl-control.md) — same two-instance machinery, different variable.

| Held identical | Differs |
|---|---|
| network, base demand profile, **seed**, duration, controller | event demand injection + link closures |

```
World A (baseline): normal demand, no closures
World B (event):    normal demand + injected event trips, closures applied
```

**Measured per link:** travel time, delay, queue length, throughput. Then:

```
delta_pct = (event_travel_time − baseline_travel_time) / baseline_travel_time × 100
```

**Severity bands (fixed, documented, never tuned per demo):**

| Band | Δ travel time |
|---|---|
| `LOW` | < 15% |
| `MODERATE` | 15 – 40% |
| `SEVERE` | > 40% |

Secondary roads that become congested appear naturally in the per-link results — no separate "secondary effect" model is needed, and claiming one would be inventing a mechanism.

**Rules:**
1. No severity is assigned before both worlds complete. The API returns `202 {"status":"running"}` until then.
2. Both worlds record their seed; a prediction whose worlds used different seeds is invalid and rejected.
3. `event_predictions.source` is always `sumo`. Any other value means the prediction was not measured and must not be stored.

---

## 5. Alternative route engine (SN-057)

For each `SEVERE` or `MODERATE` link, compute alternatives with the existing A* over the **event world's** weights (`ml/routing/routing_engine.py`), excluding closed links.

Each ranked alternative reports:

| Field | Source |
|---|---|
| `route_text` | human place names, from junction names |
| `added_distance_km` | A* path length − baseline path length |
| `added_time_s` | measured in the event world |
| `congestion` | severity band of the worst link on the alternative |
| `reason` | e.g. "avoids both SEVERE links on the Palasia corridor" |

Ranking: lowest `added_time_s`, tie-broken by congestion band then added distance. If no alternative is better than the affected route, the honest output is *"no better alternative — advise delayed departure"*, which feeds the departure recommendation in [12-citizen-advisory.md](12-citizen-advisory.md).

---

## 6. Event dashboard (SN-059)

New page `frontend/dashboard/src/pages/EventsPage.tsx`, route `/app/events`, roles OPERATOR/ADMIN.

**Create flow**
1. Name, type, start/end (IST picker).
2. Expected crowd → the derived trip counts appear immediately, with the assumptions shown.
3. Select affected links on the Leaflet map (click edges); mark closures distinctly.
4. Operator intensity estimate.
5. Save as `DRAFT`.

**Predict flow**
6. "Run prediction" → progress indicator while both worlds run (this takes real time; do not fake a progress bar — drive it from the runner's step count).
7. Results: per-link table with baseline vs event travel time and Δ%, colour-coded by band; severity summary; map overlay.
8. Ranked alternatives table.

**Approve / publish flow**
9. ADMIN approves the diversion.
10. Advisory preview — exactly what citizens will see.
11. Publish → advisory goes live; audit row written.

**Constraints:** no numeric value on this page may originate in the browser. The severity colours encode measured bands, and the legend states the thresholds.

---

## 7. Sequence

```
operator creates event (DRAFT)
   │
   ▼ POST /events/{id}/predict
   ├── translate crowd → trips (assumptions recorded)
   ├── World A: baseline SUMO run, seed 42
   ├── World B: event SUMO run,    seed 42
   ├── per-link deltas → severity bands
   ├── A* alternatives on event-world weights
   └── persist event_predictions (source=sumo)
   │
   ▼ operator reviews measured results
   ▼ ADMIN approves           → APPROVED   (audited)
   ▼ ADMIN publishes advisory → PUBLISHED  (audited, human gate)
   │
   ▼ GET /public/advisories   → citizen sees it
```

---

## 8. Acceptance criteria

1. Creating an event and running the prediction executes **two** SUMO runs with the same seed (verifiable in logs and in `event_predictions.seed`).
2. Every reported severity traces to a measured Δ% from those runs.
3. Alternatives come from A* on live-weighted edges and report added distance, added time, congestion and reason.
4. Approving without a completed prediction is rejected (409).
5. Publishing creates exactly one `citizen_advisories` row with `published_by` set to the approving admin.
6. An unapproved event never appears on `/public`.
7. Demand assumptions are visible in the UI and match `config.py`.
8. Re-running the prediction at the same seed produces identical deltas.
