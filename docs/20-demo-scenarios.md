# 20 — Demo Scenarios

Covers **SN-127 … SN-134**. Five deterministic scenarios on the same corridor network (`simulation/networks/corridor.*`), switchable from the UI. **Every number shown is measured from SUMO. No scenario contains a scripted figure.**

---

## 1. Determinism (SN-127)

| Requirement | Implementation |
|---|---|
| Fixed seed | `shared/constants.py::DEMO_SEED = 42`, passed as `--seed` to every SUMO run |
| No wall-clock dependence | time-of-day features derive from simulation time, not `datetime.now()`, in demo mode |
| Fixed demand | committed route files per scenario; no runtime randomisation |
| Reproducible model | greedy inference, `epsilon = 0.0`, no online learning during demos |
| Verifiable | `make verify-determinism` runs each scenario twice and diffs the metric series |

A demo that behaves differently each rehearsal will fail on stage. Determinism is a hard requirement (R9), not a convenience.

---

## 2. Scenario A — Normal (SN-128)

**Config:** `simulation/scenarios/demo_a_normal.json` — balanced demand from `OFF_PEAK`, ~600 vehicles/hour, no events, no incidents.

**Demonstrates:** the baseline. Adaptive control operating steadily; near-symmetric splits; provenance badges showing `sumo` throughout.

**Measured outputs:** avg delay, avg queue, throughput, network LOS. **Purpose:** establishes the reference every later number is compared against. Do not skip it in the demo — a number without a baseline means nothing.

---

## 3. Scenario B — Traffic surge (SN-129)

**Config:** `demo_b_surge.json` — `EVENING_PEAK` demand with a step increase on the east approach of `J1` at t = 180 s.

**Demonstrates:**
1. Telemetry shows queue growth on the east approach.
2. The DQN extends that approach's green toward `max_green_s`.
3. `/ws/control` shows the decision with real Q-values and a reason string derived from the actual state.
4. The A/B panel shows Webster and DQN diverging live.
5. The forecaster projects the next 15 minutes (`source: model`, `training_data: synthetic`).

**Measured outputs:** the A/B improvement figure with its seed — **the project's headline number**.

**Critical:** the green extension must be an emergent consequence of the demand step, verifiable in `control_decisions`. If it is scripted, the entire demo is compromised.

---

## 4. Scenario C — Ambulance (SN-130)

**Config:** `demo_c_ambulance.json` — Scenario A demand plus an ambulance injected at `W_entry` at t = 120 s bound for a hospital node beyond `J3`.

**Demonstrates:**
1. A* computes the route on live weights.
2. Per-junction ETAs appear and update.
3. The corridor **propagates** — junctions turn green ahead of the vehicle and revert behind it.
4. Captured programs are restored and verified.
5. Cross-street max red stays under threshold; a compensating phase fires behind the vehicle if it approaches it.
6. After the corridor closes, the recovery chart shows measured cross-traffic recovery.

**Measured outputs:** ETA sequence, clearance time, cross-street max red, `recovery_s`.

**Demo line:** *"Green ahead of it, normal behind it. And here's what happened to cross traffic — recovered in four minutes. We measured that, because a corridor that paralyses the rest of the city isn't a solution."*

---

## 5. Scenario D — Rally (SN-131)

**Config:** `demo_d_rally.json` — a pre-created event: 25,000 expected, 16:00–20:00 tomorrow, affecting the `J1→J2` corridor with one closure.

**Demonstrates:**
1. Operator opens the event; derived trip counts and the stated mode-split assumptions are visible.
2. "Run prediction" executes **two** SUMO worlds at the same seed (progress driven by real step count).
3. Per-link deltas and severity bands appear from measurement.
4. Ranked alternatives with added distance/time/congestion/reason.
5. ADMIN approves → publishes → advisory created.

**Measured outputs:** per-link Δ travel time, severity counts, alternative route metrics.

**Demo line:** *"Everything so far reacted to traffic. This predicts it — before it exists."*

---

## 6. Scenario E — Incident (SN-132)

**Config:** `demo_e_incident.json` — Scenario B demand plus a lane blockage on `J1→J2` at t = 240 s (a stopped SUMO vehicle).

**Demonstrates:**
1. Indicators fire: speed collapse, stationary vehicle, occupancy spike.
2. `Possible incident — 3 of 5 indicators` appears, `UNVERIFIED`, with measured values.
3. **Nothing else happens** until the operator confirms — the human gate is visible.
4. On confirmation: routing weights update, alternatives recompute, a response unit is proposed.
5. Publishing the public warning is a **second** explicit human action.
6. Citizen view updates.
7. Network-wide delay returns toward baseline.

**Measured outputs:** indicator values vs. thresholds, anomaly score, time-to-detection, recovery series.

**Demo line:** *"It says* possible*, because a camera can flag an anomaly — it cannot certify a crash. A person confirms before this city hears anything."*

---

## 7. Scenario switcher (SN-133)

A control on the Simulation page: select scenario → `reset.sh`-equivalent state reset → start at seed 42. Shows the active scenario name, seed and elapsed simulation time. Switching mid-demo must be a single click and must complete in under 15 seconds.

---

## 8. Seed data (SN-134)

`scripts/seed_demo.py` creates:
- 4 junctions named `J0`…`J3` matching the SUMO IDs, with real Indore-area coordinates and human names (used in citizen advisories).
- 4 sensors per junction (one per approach).
- Network links matching the SUMO edges ([15-routing.md §2](15-routing.md)).
- One user per role, credentials in the run-book (not in the repository).
- One historic closed event and one resolved incident, so analytics pages are not empty.

**All seeded rows carry `source='manual'`** so they are never mistaken for measurements.

---

## 9. Acceptance criteria

1. Each scenario produces identical measured outputs across runs at the same seed (`make verify-determinism`).
2. No scenario contains a scripted numeric output — every figure traces to SUMO or the database.
3. Switching scenarios completes in under 15 s.
4. `./reset.sh && ./start.sh` returns to a known demo state in under 3 minutes.
5. Each scenario's headline behaviour is emergent from demand, not triggered by a demo-only code path.
