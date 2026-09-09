# 17 — Security, Privacy & Governance

Covers **SN-107 … SN-110**. Infrastructure security is already done and is a genuine strength: TLS/HSTS at nginx, JWT with Redis revocation denylist, bcrypt, login rate limiting, authenticated MQTT, production secret validation in `config.py`. **The gap is data governance** — which, for a surveillance-adjacent public-safety platform, is what a serious judge will probe.

---

## 1. Principles

1. **Collect the minimum.** The system needs vehicle counts and speeds. It does not need identities.
2. **Blur by default.** Any face or plate in a stored or served frame is blurred before it is written.
3. **Suspicion is not evidence.** AI flags are `UNVERIFIED` until a person resolves them, and unverified suspicion is not retained indefinitely.
4. **Every consequential action is attributable.** Operator and AI decisions alike ([18-audit-logging.md](18-audit-logging.md)).
5. **State the limits.** Documented model limitations are part of the deliverable, not an admission of weakness.

---

## 2. CCTV and personal data (SN-107)

`services/vision_worker/privacy.py` runs **before** any frame is written to disk or served:

```
frame ─▶ detect faces + plate regions ─▶ Gaussian blur (σ ≥ 15) ─▶ store
```

- Blurring is applied to the **stored** artefact, not only the displayed one. An unblurred frame must never exist on disk.
- Original frames are held in memory only for the duration of inference.
- Frame paths (`cv_detections.frame_ref`, `incidents.evidence_ref`) always point to blurred artefacts.
- A test asserts that a frame written with a detected face region has that region blurred.

---

## 3. Licence plates and ANPR (SN-109)

**ANPR is disabled by default.** `VISION_ANPR_ENABLED=false` in `.env.example`, and the code path is gated on it.

Rationale to state on the slide: plate recognition is technically easy and legally sensitive. Enabling it would require a stated legal basis, a defined retention period, and access controls beyond what a hackathon prototype can justify. **Blur by default; enable only with a documented legal basis.**

The audit's judgement: restraint here reads as maturity — one slide showing a blurred-plate pipeline earns more than a working ANPR demo.

---

## 4. Retention (SN-108)

TimescaleDB retention jobs; verify with `SELECT * FROM timescaledb_information.jobs;`

| Data | Retention | Rationale |
|---|---|---|
| Raw/blurred frames, `cv_detections` | **72 hours** | operational need only |
| `traffic_readings` (derived counts) | **1 year** | trend analysis; no personal data |
| `control_decisions` | 90 days | model behaviour audit |
| `behavior_flags` — `DISMISSED` | 90 days | do not retain disproven suspicion |
| `behavior_flags` — `CONFIRMED` | per case + 1 year | evidentiary |
| `incidents` + indicators + evidence | per case, until closure + 1 year | evidentiary |
| `audit_logs` | **1 year** | governance |
| User accounts | until deletion request | |

Purge is automated (`scripts/retention.sh`, cron) and logged. The policy is stated on a demo slide — a judge asking "how long do you keep footage?" gets a number, not an improvisation.

---

## 5. False positives (SN-110)

| Requirement | Implementation |
|---|---|
| Every AI flag starts `UNVERIFIED` | DB default, no automated path to `CONFIRMED` |
| Operator can dismiss with a reason | `PATCH /vision/flags/{id}/resolve`, audited |
| False-positive rate is tracked | `dismissed / total` per flag type, shown on the analytics page |
| The rate is reported honestly | including in the demo if asked — a system with no FP tracking is not a system that has considered being wrong |

---

## 6. Model limitations (SN-110) — stated, not hidden

Publish these in `docs/17-security-privacy.md` (here), on an analytics panel, and in the judge Q&A:

| Model | Limitation |
|---|---|
| YOLOv8n (COCO) | **No auto-rickshaw class.** Autos are detected as `car` or `motorcycle`, biasing PCU in Indian traffic. Correcting this needs a locally-labelled dataset. |
| YOLOv8n | Under-counts two-wheelers and pedestrians in dense scenes due to occlusion; recall degrades in rain, fog and at night. |
| Speed estimation | Requires per-camera calibration; uncalibrated cameras emit `null`, not a guess. |
| Forecaster (LSTM+XGB) | **Trained on synthetic data** (`train_forecaster.py:60`). It has learned its own generator, not Indian traffic. Declared as `training_data: "synthetic"` in every response. |
| DQN policy | Trained in simulation on this corridor. It has not been validated on real hardware and its transfer to another network is unproven. |
| Anomaly incident detection | Detects *anomalies*, not crashes. Confidence is an anomaly score, not a crash probability. |
| All CV behaviour flags | Measure kinematics, not intent or culpability. |

**Model bias:** the two-wheeler/auto under-detection systematically under-counts the dominant vehicle classes in Indian traffic, which would under-serve those approaches under adaptive control. Report per-class recall where measurable; state the bias where not.

---

## 7. Access control and abuse prevention

See [16-rbac.md](16-rbac.md). Specifically:
- Corridor activation restricted to `EMERGENCY_SERVICES`/`ADMIN` and rate-limited (5/min) — an unrestricted corridor is an abuse vector that can paralyse a network.
- Signal override rate-limited (10/min) and time-boxed (auto-return after 300 s).
- Public publication restricted to `ADMIN`.
- All denials audited with `result: DENIED`.

---

## 8. What the system does not do (state this plainly)

- It does not identify individuals.
- It does not determine legal violations.
- It does not detect intoxication ([14-incident-detection.md §8](14-incident-detection.md)).
- It does not control real traffic hardware today ([08-marl-control.md §8](08-marl-control.md)).
- It does not train on any real citizen's data.

---

## 9. Acceptance criteria

1. Any face/plate region in a stored frame is blurred; no unblurred frame exists on disk.
2. `VISION_ANPR_ENABLED` defaults to `false` and the gate is enforced in code.
3. Retention jobs exist for every row of §4 and are visible in `timescaledb_information.jobs`.
4. No automated path sets a `behavior_flag` or incident to `CONFIRMED`.
5. False-positive rate per flag type is computed from real resolutions and displayed.
6. The limitations table in §6 appears in the UI and in the demo materials.
7. `pytest tests/test_language_policy.py` passes (no intoxication claims anywhere).
