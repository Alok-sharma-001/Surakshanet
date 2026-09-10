# 08 — MARL Control Service & A/B Proof Harness

Covers **SN-030 … SN-038**. This is the project's central engineering task: the audit found a complete, trained DQN (`ml/marl/weights/marl_policy_downtown.pth`, 900 KB) that **no backend module ever loads for inference**, while the dashboard displays a hardcoded string as if it were an AI decision.

**Do not retrain and do not redesign the network.** The existing `MARLAgent` (`state_dim=8`, `action_dim=2`) is correct. What is missing is the inference path, the safety envelope, and the measurement that proves it works.

---

## 1. Control loop

```
SUMO lane-area detectors
  │ queue · speed · occupancy · accumulated wait · phase · elapsed green
  ▼
sumo_live_bridge ──── canonical telemetry ────▶ Redis: traffic_updates
                                                     │
                                                     ▼
                                          CONTROL SERVICE   every control_step_s (default 5.0)
                                            1. aggregate telemetry per junction
                                            2. build 8-dim state vector
                                            3. select controller by SignalMode
                                            4. inference  →  action
                                            5. SAFETY ENVELOPE  (hard clamp)
                                            6. emit command
                                                     │
                                                     ▼
                                          Redis: control_commands
                                                     │
                                                     ▼
                                          sumo_live_bridge → traci.trafficlight.setPhase /
                                                              setPhaseDuration
                                                     │
                                                     ▼
                                              new traffic state
                                                     │
                                       reward computed on next step, decision persisted
                                                     ▼
                             Postgres control_decisions  +  Redis control_decisions
                                                     ▼
                                          WebSocket /ws/control → UI
```

---

## 2. State vector (SN-034)

Eight dimensions, in this fixed order. **The order must match training exactly** — a permuted vector produces confident nonsense, which is worse than no model.

| # | Feature | Unit | Normalisation | Telemetry source |
|---|---|---|---|---|
| 0 | `queue_length` | PCU | `/ 50.0`, clip [0,1] | max over approaches |
| 1 | `mean_speed` | km/h | `/ 60.0`, clip [0,1] | PCU-weighted mean |
| 2 | `occupancy` | ratio | already [0,1] | max over approaches |
| 3 | `accumulated_wait` | s | `/ 300.0`, clip [0,1] | max over approaches |
| 4 | `phase_index` | int | `/ (n_phases - 1)` | `current_phase` |
| 5 | `elapsed_green` | s | `/ max_green_s`, clip [0,1] | `phase_elapsed_s` |
| 6 | `tod_sin` | — | `sin(2π · seconds_of_day / 86400)` | timestamp (IST) |
| 7 | `tod_cos` | — | `cos(2π · seconds_of_day / 86400)` | timestamp (IST) |

Normalisation constants live in `services/control_service/config.py` and are **recorded in `control_decisions.state_vector` alongside the raw values**, so a reviewer can reconstruct exactly what the network saw.

**Missing data rule:** if any approach is missing telemetry for more than `2 × control_step_s`, the junction falls back to `WEBSTER` and the reason is recorded. The policy never runs on imputed inputs.

---

## 3. Action space

Two actions, matching `action_dim=2`:

| Action | Label | Meaning |
|---|---|---|
| `0` | `extend` | hold the current phase for another `control_step_s` |
| `1` | `advance` | begin the transition to the next phase in the program |

This formulation is chosen deliberately: **the agent can never invent a phase.** It only chooses *when* to switch between the phases already defined in the SUMO network file, which makes the safety envelope simple and makes the hardware story credible (§8).

Action masking uses the existing `MARLAgent.get_valid_actions`. Inference runs greedy: `epsilon = 0.0`. Training-time exploration must never run in the demo path.

---

## 4. Reward (SN-035)

```
r_t = − ( Σ queue_t − Σ queue_{t−1} ) − λ · Σ wait_t
```
with `λ = 0.01` (in `config.py`, recorded per decision). Computed one step *after* the action so the outcome is observed, then written to the decision row.

**Stage phrasing:** "the agent is paid to shrink the queue and penalised for making anyone wait." Judges understand that in one sentence; avoid explaining it as a discounted return.

Reward is **recorded, not acted on** at demo time — the policy is fixed. Online learning is explicitly out of scope: a policy that changes during a demo is not reproducible, and reproducibility is a hard requirement (R9).

---

## 5. Safety envelope (SN-032) — mandatory

Applied to **every** action from every controller, after inference, before any TraCI command. The policy has no path around it.

```python
def apply_safety_envelope(action, junction_state, cfg) -> SafetyResult:
    # 1. minimum green
    if action == ADVANCE and junction_state.phase_elapsed_s < cfg.min_green_s:
        return clamp(EXTEND, "min_green_not_elapsed")
    # 2. maximum green
    if action == EXTEND and junction_state.phase_elapsed_s >= cfg.max_green_s:
        return clamp(ADVANCE, "max_green_exceeded")
    # 3. amber + all-red are inserted by the transition sequencer, never skippable
    # 4. pedestrian service guarantee
    if junction_state.cycles_since_pedestrian_phase >= cfg.max_cycles_without_ped:
        return clamp(ADVANCE_TO_PEDESTRIAN, "pedestrian_service_due")
    # 5. emergency pre-emption outranks the policy entirely
    if junction_state.emergency_preemption_active:
        return override(EMERGENCY_PHASE, "emergency_corridor")
    return allow(action)
```

Defaults from `shared/constants.py::SIGNAL_CONSTRAINTS` (`min_green_s=10`, `max_green_s=60`, `amber_s=3`, `all_red_s=2`) plus `max_cycles_without_ped=2`.

**Every clamp is recorded** with `clamped=true` and a `clamp_reason`. Test SN-117 crafts a state that would produce a 2-second green and asserts the clamp fires and is persisted.

Transition sequencing: `green → amber(3s) → all-red(2s) → next green`. The sequencer owns this; no controller may set a green phase directly after another green.

---

## 6. Control service specification (SN-030 … SN-033)

**Location:** `services/control_service/`
```
main.py         lifecycle, Redis subscribe, decision loop
controllers.py  MarlController · WebsterController · ManualController
safety.py       safety envelope + transition sequencer
state.py        telemetry → 8-dim vector
reward.py       reward computation
config.py       constants, normalisation, control_step_s
```

**Lifecycle**
1. Import guard for `traci` (SN-016) — fail loudly with the interpreter path.
2. Load `ml/marl/weights/marl_policy_downtown.pth`; compute a SHA-256 of the file → `model_version`. **If the load fails, do not start in MARL mode**: log, refuse `MARL`, and report `controller: "webster (marl weights unavailable)"` through `/health/deep`. Silent pretence is forbidden (R1).
3. Subscribe to `REDIS_CHANNELS["traffic"]`.
4. Poll `signal_plans.mode` per junction every 5 s (cached).
5. Run the decision loop at `control_step_s`.
6. On shutdown, release all junctions to their base program.

**Inference frequency:** `control_step_s = 5.0` simulation seconds by default. Rationale: shorter steps produce phase churn that is unreadable on screen; longer steps make the agent look unresponsive during the demo.

**Action validation before emission:** phase index within range; duration within `[min_green_s, max_green_s]`; junction currently under this service's authority (not pre-empted by a corridor); command sequence number monotonic.

**TraCI command format** on `control_commands`:
```json
{"type":"SET_PHASE","junction_id":"J1","phase":2,"duration_s":5.0,
 "seq":10482,"issued_by":"control_service","controller":"marl",
 "decision_id":"…","timestamp":"…"}
```
The bridge executes commands it receives and rejects any with a stale `seq`.

**Error handling**

| Failure | Behaviour |
|---|---|
| Telemetry gap > `2 × control_step_s` | fall back to `WEBSTER`, record reason |
| Inference exception | fall back to `WEBSTER`, log with the state vector |
| TraCI command rejected | log, retry once, then release the junction to its base program |
| Redis disconnect | exponential backoff reconnect; **do not** issue commands while blind |
| Weights missing | refuse MARL mode entirely (above) |

**Logging:** one structured line per decision — junction, controller, state, action, clamp, latency. Correlation ID propagated from `middleware/correlation.py`.

**Metrics (SN-037):** `control_decisions_total{junction,controller,action}`, `control_clamps_total{reason}`, `control_inference_duration_seconds` (histogram), `control_step_lag_seconds` (gauge), `control_fallbacks_total{reason}`. Registered alongside the existing collectors in `backend/app/middleware/metrics.py`.

---

## 7. A/B proof harness (SN-038) — the project's primary evidence

**Purpose:** produce one number the team did not choose. The audit identifies this as the single highest-impact addition available.

**Design:** two SUMO instances, identical in every respect except the controller.

| Held identical | Differs |
|---|---|
| network file, route file, demand profile | controller: Webster fixed-time vs DQN |
| **seed** (`DEMO_SEED = 42`) | |
| duration, step length, detectors | |
| safety envelope (both arms use it) | |

Both arms run the **same safety envelope** — otherwise the comparison measures the envelope, not the policy. This is a correctness requirement, not a nicety.

**Metrics collected from SUMO (never computed by the frontend):**
`avg_delay_s`, `total_delay_s`, `avg_queue_pcu`, `avg_wait_s`, `throughput_veh_h`, `avg_travel_time_s`, `vehicles_served`.

**Improvement formula (SN-038, exact):**

```
cost metrics   (delay, queue, wait, travel time):
    improvement_pct = (arm_a - arm_b) / arm_a * 100

benefit metrics (throughput, vehicles served):
    improvement_pct = (arm_b - arm_a) / arm_a * 100

where arm_a = Webster baseline, arm_b = DQN
```

**Reporting rules — non-negotiable (R7):**
1. The number is computed server-side from `ab_runs` and stored; the client only displays it.
2. `improvement` is absent until `status == "complete"`.
3. The seed is displayed next to the number. A percentage without its seed is not a result.
4. **If the DQN performs worse, that is reported unchanged.** A negative improvement is a finding, not a bug — and a team that shows it has more credibility than one whose numbers are always favourable. If it is consistently worse, the correct response is to say so and present Webster as the operating controller.
5. The generated statement takes the form: `AI reduced average delay by 31.1% vs fixed-time under Scenario "surge" (seed 42, 900 s, 1200 vehicles).` It is emitted only when the measured data supports it.

**Acceptance (SN-125):** running the same A/B twice at the same seed produces identical metrics for both arms; changing the seed changes the improvement figure.

---

## 8. Path to real hardware (for the judge question, not for implementation)

Not implemented — documented so the claim stays honest.

The control service emits **phase-change intents**, not voltages. Real deployment adds an adapter speaking the controller's protocol (NTCIP 1202, or a vendor serial/API layer inside an ATCS cabinet). **The cabinet's own conflict monitor is retained as the ultimate safety authority** — it can physically refuse an unsafe request regardless of what the software asks for.

Deployment path: shadow mode (log intents, change nothing) → single-junction supervised pilot → corridor rollout.

The honest one-line answer: *"We emit intents; the cabinet keeps veto power."*

---

## 9. Definition of done for this document

| # | Criterion | Verified by |
|---|---|---|
| 1 | A junction visibly changes phase behaviour because of DQN inference | Gate 2, manual + SN-116 |
| 2 | `control_decisions` row exists for every observed change, with state vector and Q-values | SN-116 |
| 3 | Safety envelope clamps an unsafe action and records it | SN-117 |
| 4 | Mode switch MARL ⇄ WEBSTER changes observable timing | SN-116 |
| 5 | A/B improvement computed from SUMO output by the documented formula | SN-125 |
| 6 | `grep -rn "MARL Green Extension" .` returns nothing | SN-002, SN-140 |
| 7 | Missing weights → refuses MARL, does not pretend | SN-116 |
