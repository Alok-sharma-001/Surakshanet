# 14 — Incident Detection & Response

Covers **SN-083 … SN-096**. Currently the only "accident detection" in the repository is UI string labels (`LiveIncidents.tsx:26`, `AIInsightsTicker.tsx:31`, `Navbar.tsx:121`). No detector exists.

---

## 1. What is honestly buildable

**A trained crash classifier is not.** It needs a labelled collision dataset the project does not have, and crashes are rare events — a model trained on a handful of clips produces false positives on every hard brake. Building one and calling it accident detection would repeat exactly the defect this roadmap exists to remove.

**What is buildable, and is more defensible:** multi-indicator anomaly detection from telemetry the system already produces. Real ATMS automatic incident detection (AID) works this way — it is anomaly-based, not a vision classifier. So this is the *stronger* answer, not the lesser one, and it should be presented that way on stage.

---

## 2. The five indicators (SN-086 … SN-088)

All computed from canonical telemetry, per link, on a rolling window.

| # | Indicator | Measure | Default threshold | Window |
|---|---|---|---|---|
| 1 | `SPEED_COLLAPSE` | mean speed vs. 15-min rolling baseline | < 40% of baseline | 60 s |
| 2 | `STATIONARY_VEHICLE` | vehicle stopped outside a signal queue | > 20 s stationary | 60 s |
| 3 | `OCCUPANCY_SPIKE` | lane occupancy vs. baseline | > 0.75 absolute **and** > 1.5 × baseline | 60 s |
| 4 | `FLOW_DROP` | downstream link throughput | < 50% of upstream throughput | 120 s |
| 5 | `QUEUE_ANOMALY` | queue growth rate | > 3 × normal growth for this time of day | 90 s |

Indicator 2 requires the vision worker's tracking or SUMO vehicle state; when neither is available it does not fire, and the incident confidence is computed over the four indicators that can.

**Baselines are measured**, from the same link's own history at the same time of day — not typed in.

---

## 3. Combination rule and confidence (SN-089)

```
confidence = Σ (indicator_weight_i × strength_i) / Σ (indicator_weight_i for available indicators)

strength_i = clamp((measured_i − threshold_i) / threshold_i, 0, 1)

weights: SPEED_COLLAPSE 0.30 · STATIONARY_VEHICLE 0.25 · OCCUPANCY_SPIKE 0.20
         FLOW_DROP 0.15 · QUEUE_ANOMALY 0.10

incident raised when: indicators_fired >= 2  AND  confidence >= 0.50
```

**Rules:**
1. The formula is fixed and documented **before** the demo. Tuning thresholds until the demo produces a satisfying confidence is fabrication by another route.
2. `confidence` here is an anomaly score, not a probability that a crash occurred. The UI labels it "anomaly score", and the API note field says so.
3. An incident row must have at least one `incident_indicators` row with a measured value — enforced at write time ([05-database.md §6](05-database.md)).

---

## 4. Output (SN-090)

The only `incident_type` value is `POSSIBLE_INCIDENT`. **There is deliberately no `ACCIDENT` enum value** — the schema itself prevents the overclaim.

```json
{"incident_type":"POSSIBLE_INCIDENT","status":"UNVERIFIED","confidence":0.74,
 "indicators_fired":3,"indicators_total":5,
 "indicators":[{"indicator":"SPEED_COLLAPSE","measured_value":4.1,"threshold":10.0},
               {"indicator":"STATIONARY_VEHICLE","measured_value":31.0,"threshold":20.0},
               {"indicator":"OCCUPANCY_SPIKE","measured_value":0.88,"threshold":0.75}],
 "note":"Possible incident. Unverified — operator review required.",
 "source":"sumo"}
```

UI phrasing is fixed: **"Possible incident — 3 of 5 indicators"**. Never "Accident detected — 87% confidence", which is what the current mock UI displays.

---

## 5. Response state machine (SN-092 … SN-094)

```
   DETECTED ──▶ UNVERIFIED ──▶ UNDER_REVIEW ──┬──▶ CONFIRMED ──▶ RESPONDING ──▶ RESOLVED ──▶ CLOSED
   (auto)       (auto)         (operator       │    (operator)    (assisted)     (operator)   (operator)
                                opens it)      └──▶ DISMISSED
                                                    (operator)
```

**Automation colour code (the audit's principle):**

| Stage | Colour | Automation |
|---|---|---|
| Sensor / telemetry ingest | 🟢 green | automatic |
| Anomaly detection | 🟢 green | automatic |
| Confidence + classification | 🟢 green | automatic |
| Control-room alert | 🟢 green | automatic |
| **Operator verification** | 🔴 **red** | **human gate 1 — blocks everything downstream** |
| Dispatch nearest unit | 🟡 amber | assisted — system proposes, operator confirms |
| Route optimisation / rerouting | 🟡 amber | automatic but reversible |
| **Public warning** | 🔴 **red** | **human gate 2 — irreversible** |
| Signal re-timing around the incident | 🟡 amber | automatic but reversible |
| Resolve & close | 🔴 red | human |
| Analytics + audit | 🟢 green | automatic |

**Why these two gates specifically:**
- **Confirmation** gates everything downstream, so a false positive cannot cascade into unnecessary diversions.
- **Publishing a public warning is irreversible.** A false alarm broadcast to a city is worse than a slow response.

`POST /incidents/{id}/publish-warning` returns `409` unless `status == "CONFIRMED"`. Automation may never reach the public without a human.

**Demo line:** *"It says* possible*, because a camera can flag an anomaly — it cannot certify a crash. A person confirms before this city hears anything."*

---

## 6. Post-confirmation automation (SN-093)

On `CONFIRMED`:
1. Affected link marked in the routing graph; A* weights updated → alternatives recomputed automatically.
2. Nearest response unit proposed from junction proximity — **proposed, not dispatched**.
3. Signal re-timing around the incident applied through the control service (reversible; recorded as `action_source: "incident"`).
4. Advisory **draft** created — publication still requires human gate 2.

Every one of these writes an audit row with `actor_type: SYSTEM` and the confirming operator as the causing actor.

---

## 7. Anomaly service (SN-085)

**Location:** `services/anomaly_service/{main,indicators,rules}.py`

Subscribes to `REDIS_CHANNELS["traffic"]`; maintains rolling per-link baselines in Redis; evaluates indicators each window; creates incidents; publishes to `REDIS_CHANNELS["incidents"]` → `/ws/incidents`.

**Deduplication:** one open incident per link. Further indicator fires update the existing incident's indicator list rather than creating duplicates. An incident auto-transitions to `RESOLVED` if all indicators clear for 5 minutes **and** no operator has confirmed it — logged as `auto_cleared`, never silently deleted.

---

## 8. Drunk driving (SN-095, SN-096) — explicit prohibition

> ### DO NOT IMPLEMENT CAMERA-BASED DRUNK-DRIVING DETECTION.

**There is no visual signature of blood alcohol content.** A traffic camera cannot detect intoxication. Any claim otherwise will be dismantled by a knowledgeable judge in one question, and it would be false regardless of whether anyone asks.

**The correct architecture, which is the answer to give:**

```
AI flags anomalous driving behaviour        ← what the system does (weaving, erratic speed)
        │                                     behavior_flags, DANGEROUS_DRIVING, UNVERIFIED
        ▼
Alert routed to nearest patrol              ← assisted dispatch
        │
        ▼
Officer stops the vehicle                   ← human authority
        │
        ▼
Calibrated breathalyser test                ← the actual measurement
        │
        ▼
Confirmed case with admissible evidence     ← legal determination, by a person
```

**AI narrows where to look. It never determines the offence.**

**SN-096 enforcement — `tests/test_language_policy.py`:** greps the entire repository (code, docs, UI strings, comments) and **fails** on any construction claiming intoxication detection from cameras/AI/CV. Forbidden patterns include `drunk detection`, `intoxication detect`, `alcohol.*camera`, `DUI detect`. The workflow above is the only permitted treatment of the subject.

Presenting this limitation deliberately is a scoring opportunity: it demonstrates you understand the difference between what a model outputs and what a court accepts — which most teams in this category will not.

---

## 9. Acceptance criteria

1. Blocking a lane in SUMO raises an incident within 60 s listing the indicators that fired with measured values and thresholds.
2. No rerouting, dispatch or public warning occurs before operator confirmation.
3. `POST /incidents/{id}/publish-warning` on an unconfirmed incident returns 409.
4. No `incidents` row exists without at least one `incident_indicators` row.
5. The UI never renders "accident detected" as a determination.
6. `pytest tests/test_language_policy.py` passes.
7. Every state transition writes an audit row naming the actor.
8. A cleared anomaly auto-resolves and is logged, not deleted.
