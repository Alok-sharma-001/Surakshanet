# 09 — Dynamic Signal System: State Machine, I/O, Edge Cases

Covers the production-shaped signal system built around the real DQN from [08-marl-control.md](08-marl-control.md). Where that document specifies the *learning* component, this one specifies the *signal engineering* around it: what goes in, what comes out, and what happens at every boundary.

---

## 1. Inputs

| Input | Unit | Origin | Required for |
|---|---|---|---|
| Vehicle counts (per approach) | veh | telemetry | state, reward |
| PCU (per approach) | PCU | shared PCU function | state dim 0 |
| Queue length | m / PCU | detectors | state dim 0, reward |
| Mean speed | km/h | detectors | state dim 1 |
| Lane occupancy | 0–1 | detectors | state dim 2 |
| Accumulated waiting time | s | detectors | state dim 3, reward |
| Current signal phase | index | TraCI | state dim 4, sequencing |
| Elapsed green | s | control service clock | state dim 5, safety |
| Time of day | IST | system clock | state dims 6–7 |
| Emergency status | bool | `emergency_events` | pre-emption override |
| Event status | enum | `events` | operator context, demand injection |
| Pedestrian demand | bool/count | detectors (where present) | pedestrian guarantee |

Where pedestrian detection is unavailable, the pedestrian phase is served on a **fixed guarantee** (`max_cycles_without_ped`), not skipped. Absence of a sensor never becomes absence of a phase.

---

## 2. Processing pipeline

```
aggregate telemetry  →  construct state  →  select controller  →  run policy
   →  apply safety envelope  →  sequence transition  →  execute phase action
   →  observe outcome  →  compute reward  →  persist decision  →  publish
```

Each stage is a pure function where possible so the whole pipeline is testable without SUMO (SN-116 uses recorded telemetry fixtures).

---

## 3. Outputs

Every control step emits one decision record containing:

| Field | Meaning |
|---|---|
| `applied_phase` | phase index now active |
| `applied_duration_s` | green duration granted this step |
| `action` / `action_label` | `0 extend` / `1 advance` |
| `action_source` | `policy` \| `safety_clamp` \| `operator` \| `emergency` |
| `reason` | human-readable, e.g. `Q(extend)=3.41 > Q(advance)=2.87; queue 14 PCU on N approach` |
| `controller` | `marl` \| `webster` \| `manual` |
| `model_version` | weights hash (null for non-model controllers) |
| `q_values` | null for non-model controllers |
| `clamped` / `clamp_reason` | safety envelope outcome |
| `source` | provenance of the input telemetry |
| `reward` | filled in on the following step |

**The `reason` string is generated from the actual decision inputs.** It may never be a template with invented content — that is precisely the defect removed in SN-002.

---

## 4. Signal state machine

```
            ┌──────────────────────────────────────────────┐
            │                   STARTUP                    │
            │  load program from SUMO, adopt base plan     │
            └───────────────────┬──────────────────────────┘
                                ▼
                        ┌───────────────┐
              ┌────────▶│  GREEN_ACTIVE │◀────────┐
              │         └───────┬───────┘         │
              │    action=extend│action=advance   │
              │    (min_green   │(min_green met)  │
              │     enforced)   ▼                 │
              │         ┌───────────────┐         │
              │         │    AMBER      │ 3 s fixed, not skippable
              │         └───────┬───────┘         │
              │                 ▼                 │
              │         ┌───────────────┐         │
              │         │   ALL_RED     │ 2 s fixed, not skippable
              │         └───────┬───────┘         │
              │                 ▼                 │
              │         ┌───────────────┐         │
              └─────────│  PHASE_SWITCH │─────────┘
                        └───────┬───────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌──────────────────┐    ┌──────────────────┐
│ PEDESTRIAN    │     │ EMERGENCY_       │    │ MANUAL_OVERRIDE  │
│ SERVICE       │     │ PREEMPTION       │    │ (operator)       │
│ (guaranteed)  │     │ (outranks all)   │    │ time-boxed       │
└───────┬───────┘     └────────┬─────────┘    └────────┬─────────┘
        │                      │                       │
        └──────────────────────┴───────────────────────┘
                               ▼
                        ┌─────────────┐
                        │  DEGRADED   │  telemetry loss / TraCI error
                        │  → WEBSTER  │  falls back, records reason
                        └─────────────┘
                               │
                        ┌─────────────┐
                        │ FLASH_ALL_  │  operator-invoked failsafe only
                        │ RED         │
                        └─────────────┘
```

**Precedence (highest first):** `FLASH_ALL_RED` → `EMERGENCY_PREEMPTION` → safety envelope clamps → `MANUAL_OVERRIDE` → `PEDESTRIAN_SERVICE` guarantee → controller action.

The policy sits at the bottom of this list by design. That ordering is the answer to "what happens if the AI is wrong?".

---

## 5. Controller modes

| Mode | Selected by | Behaviour | When used |
|---|---|---|---|
| `MARL` | `signal_plans.mode` | DQN greedy inference + envelope | adaptive operation, A/B arm B |
| `WEBSTER` | `signal_plans.mode` | Webster optimal cycle & splits, recomputed every 5 min | baseline, A/B arm A, all fallbacks |
| `MANUAL` | `signal_plans.mode` | operator commands only; no automatic phase changes | maintenance, incidents |

Mode changes take effect within one control step and are audited. A mode change during an active emergency corridor is queued until the corridor releases the junction.

---

## 6. Edge cases — all must be handled explicitly

| # | Situation | Required behaviour |
|---|---|---|
| 1 | Telemetry gap > 2 control steps | fall back to `WEBSTER`, record `reason`, surface in `/health/deep` |
| 2 | All approaches empty | serve minimum green, rotate normally; **do not** hold one phase indefinitely |
| 3 | Single approach saturated, others empty | policy may extend up to `max_green_s`; hard stop there |
| 4 | Two junctions both saturated (spillback risk) | downstream junction keeps authority; upstream is gated at `max_green_s` — documented as a known limitation, not coordinated optimisation |
| 5 | Emergency corridor arrives mid-phase | complete `amber + all-red`, then pre-empt; never cut a green to red directly |
| 6 | Emergency corridor releases junction | resume the **captured** program, not a fresh default (see [10-emergency-corridor.md](10-emergency-corridor.md)) |
| 7 | Operator override during MARL | override wins, time-boxed (default 300 s), then auto-return with an audit row |
| 8 | Pedestrian phase due while policy wants extend | pedestrian guarantee wins, clamp recorded |
| 9 | Weights missing / corrupt | refuse MARL, run Webster, report honestly |
| 10 | Clock skew / DST | all internal time is UTC; IST conversion only for the time-of-day features and UI |
| 11 | SUMO restarts | control service detects step reset, re-adopts base programs, resets elapsed timers |
| 12 | Duplicate/stale command (`seq` regression) | bridge rejects; control service logs and resynchronises |
| 13 | Junction not in the network file | command rejected; junction marked unmanaged |
| 14 | Simultaneous corridor + incident on the same junction | corridor outranks incident rerouting; both are logged |
| 15 | Control step overruns its budget | skip one step rather than queue; record `control_step_lag_seconds` |

Cases 3 and 4 are the honest limits of a per-junction agent. State them plainly rather than implying network-wide coordination the system does not perform.

---

## 7. Demonstrating the four traffic regimes

The audit is explicit: **do not script these.** Drive them from SUMO demand so the behaviour is emergent, then let the observed timings speak.

| Regime | Demand setup | Expected emergent behaviour |
|---|---|---|
| Balanced | even flows all approaches | near-symmetric splits, cycle near Webster optimum |
| Heavy on one approach | step increase east approach | that approach's green visibly grows toward `max_green_s` |
| Low traffic | off-peak profile | greens shrink toward `min_green_s`, cycle shortens |
| Saturation | demand above capacity | cycle lengthens, `max_green_s` clamps fire, gating on the upstream junction |

All four fall out of one policy. That is a stronger claim than four hand-coded modes, and it is verifiable by reading `control_decisions`.

---

## 8. Acceptance criteria

1. Every phase change in SUMO has a corresponding `control_decisions` row within one control step.
2. Switching `MARL ⇄ WEBSTER` produces observably different timing on the same demand.
3. All 15 edge cases in §6 have either a test or a documented, reviewed handler.
4. Amber and all-red are never skipped, under any precedence path.
5. The pedestrian guarantee fires within `max_cycles_without_ped` in every scenario run.
6. No `reason` string contains content not derived from that decision's inputs.
