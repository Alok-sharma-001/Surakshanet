# 23 — Definition of Done & Final Completion Gate

Covers **SN-139 … SN-150**.

---

## 1. Definition of Done (Part 27)

A feature is **not** complete because:
- the UI exists
- the API exists
- a model exists
- the code compiles
- a test passes

A feature is complete **only when all ten of the following are true**:

| # | Condition | How it is verified |
|---|---|---|
| 1 | **Backend works** | endpoint returns real data from real computation |
| 2 | **Frontend displays real output** | no client-side generation; panel shows backend state |
| 3 | **Data flows end-to-end** | traceable from source through to display |
| 4 | **Error handling exists** | the failure path returns an honest unavailable state, never a fabricated value |
| 5 | **Provenance exists** | every value carries `source`; heuristics are visually distinct |
| 6 | **Tests pass** | including the documented mutation check |
| 7 | **Demo scenario works** | the feature appears in at least one of Scenarios A–E |
| 8 | **Documentation updated** | this `docs/` set and `README.md` describe actual behaviour |
| 9 | **No fake values remain** | grep checks pass |
| 10 | **Acceptance criteria satisfied** | the feature's own criteria in its document |

A feature failing any one condition is `IN_PROGRESS`, not `DONE`.

---

## 2. Final completion matrix (Part 28)

**No row may be marked complete unless all five columns are true.**

| Requirement | Implemented | Integrated | Tested | Demonstrated | Documented |
|---|---|---|---|---|---|
| Dynamic traffic signals | ☐ | ☐ | ☐ | ☐ | ☐ |
| Real DQN inference | ☐ | ☐ | ☐ | ☐ | ☐ |
| Safety envelope | ☐ | ☐ | ☐ | ☐ | ☐ |
| Fixed-time vs AI comparison | ☐ | ☐ | ☐ | ☐ | ☐ |
| Emergency green corridor | ☐ | ☐ | ☐ | ☐ | ☐ |
| Per-junction ETA | ☐ | ☐ | ☐ | ☐ | ☐ |
| Signal program restoration | ☐ | ☐ | ☐ | ☐ | ☐ |
| Cross-traffic recovery | ☐ | ☐ | ☐ | ☐ | ☐ |
| Rally / event prediction | ☐ | ☐ | ☐ | ☐ | ☐ |
| Alternative routes | ☐ | ☐ | ☐ | ☐ | ☐ |
| Citizen advisory | ☐ | ☐ | ☐ | ☐ | ☐ |
| Accident anomaly detection | ☐ | ☐ | ☐ | ☐ | ☐ |
| Wrong-way detection | ☐ | ☐ | ☐ | ☐ | ☐ |
| No-parking detection | ☐ | ☐ | ☐ | ☐ | ☐ |
| Dangerous-driving flags | ☐ | ☐ | ☐ | ☐ | ☐ |
| Drunk-driving limitation (correct handling) | ☐ | ☐ | ☐ | ☐ | ☐ |
| Real CV pipeline | ☐ | ☐ | ☐ | ☐ | ☐ |
| RBAC (5 roles) | ☐ | ☐ | ☐ | ☐ | ☐ |
| Audit logs | ☐ | ☐ | ☐ | ☐ | ☐ |
| Privacy (blur, retention, ANPR off) | ☐ | ☐ | ☐ | ☐ | ☐ |
| Data provenance | ☐ | ☐ | ☐ | ☐ | ☐ |
| Deterministic simulation | ☐ | ☐ | ☐ | ☐ | ☐ |
| Testing (15 critical paths) | ☐ | ☐ | ☐ | ☐ | ☐ |
| One-command deployment | ☐ | ☐ | ☐ | ☐ | ☐ |
| Demo fallback video | ☐ | ☐ | ☐ | ☐ | ☐ |
| Documentation accuracy | ☐ | ☐ | ☐ | ☐ | ☐ |

**Column meanings** — a column is true only if:
- **Implemented** — the code exists and does the thing (not a stub, not a mock).
- **Integrated** — it is connected to the rest of the system; no isolated feature ([02-system-architecture.md §3](02-system-architecture.md)).
- **Tested** — a critical-path test covers it and fails under its documented mutation.
- **Demonstrated** — it appears in at least one demo scenario and was observed working in a rehearsal.
- **Documented** — described accurately in `docs/` **and** in `README.md`.

---

## 3. Regression greps (SN-140)

Phase 0's deletions must still hold at the end. Run as part of final acceptance:

```bash
# fabricated training metrics
grep -n "420\|14\.2\|11\.8\|22\.4" backend/app/api/ml.py

# hardcoded AI narration
grep -rn "MARL Green Extension" .

# fake simulation
grep -rn "MicroSimRunner" backend/

# mock plan restore
grep -rn "mock_plan" ml/ backend/

# hardcoded emergency route
grep -rn "DEL-CP-01" backend/

# hardcoded VMS content
grep -rn "ACCIDENT CLEARED" backend/ frontend/

# client-side data fabrication (Studio/ is frozen and excluded)
grep -rn "Math.random" frontend/dashboard/src --include=*.tsx | grep -v "components/Studio/"

# decorative tests
grep -rn 'assert len("' tests/
grep -rn "status_code in (200, 401)" tests/
```

**Every one of these must return no results.** Any hit is a Phase 0 regression and blocks sign-off.

---

## 4. Audit-finding resolution (SN-143)

Each finding from the original audit maps to tasks. **None may be unresolved at sign-off.**

| Audit finding | Resolving tasks | Status |
|---|---|---|
| MARL trained but never inferenced | SN-030 … SN-038 | ☐ |
| Hardcoded training status (episode 420) | SN-001, SN-003 | ☐ |
| Fake CV bounding boxes | SN-004, SN-078 | ☐ |
| `MicroSimRunner` RNG as simulation | SN-005 | ☐ |
| Heuristic forecast with confidence 0.92 | SN-006, SN-007 | ☐ |
| `{"mock_plan": True}` restore | SN-044, SN-045 | ☐ |
| Hardcoded emergency route | SN-049 | ☐ |
| Tautological E2E tests | SN-111 … SN-126 | ☐ |
| Event/rally management missing | SN-051 … SN-060 | ☐ |
| Citizen advisory missing | SN-061 … SN-068 | ☐ |
| Incident detection missing | SN-083 … SN-094 | ☐ |
| Wrong-way / no-parking / rash missing | SN-075 … SN-082 | ☐ |
| Drunk-driving policy absent | SN-095, SN-096 | ☐ |
| RBAC only 3 roles, guards not enforced | SN-098 … SN-101 | ☐ |
| Audit logging absent | SN-102 … SN-106 | ☐ |
| Privacy/governance absent | SN-107 … SN-110 | ☐ |
| Provenance absent | SN-008 … SN-010 | ☐ |
| `traci` missing from venv | SN-013 | ☐ |
| Multi-process bring-up fragility | SN-018 … SN-022 | ☐ |
| README overclaims vs. code | SN-011, SN-012, SN-147 | ☐ |
| Client-side fake telemetry | SN-119 … SN-126 | ☐ |
| Routing graph not fed live data | SN-041 | ☐ |
| Webster never invoked | SN-031, SN-033 | ☐ |
| Redis channel naming drift | SN-028 | ☐ |
| Duplicate PCU table | SN-074 | ☐ |

---

## 5. Forbidden-addition check (SN-148)

Confirm nothing on the do-not-build list was added:

- [ ] No new Three.js / decorative 3D (`components/Studio/` unchanged in scope)
- [ ] ANPR flag still defaults to `false`
- [ ] No camera-based drunk-driving claim anywhere (`test_language_policy.py` passes)
- [ ] No feature outside this roadmap
- [ ] Test file count did not grow for its own sake

---

## 6. Performance sanity (SN-145)

| Metric | Target | Measured |
|---|---|---|
| Control loop inference latency | p95 < 50 ms | ☐ |
| Control step lag | < 1 s behind sim time | ☐ |
| API p95 (read endpoints) | < 300 ms | ☐ |
| WebSocket fanout | 20 concurrent clients, no drops | ☐ |
| A/B run (900 s scenario) | completes < 3 min wall clock | ☐ |
| What-if (two worlds) | completes < 4 min wall clock | ☐ |
| `start.sh` cold start | < 3 min to all-green | ☐ |

---

## 7. Final completion percentage (SN-149)

```
completion_pct = (tasks with status DONE) / 150 × 100
```

Report it from `CHECKLIST.md` — do not estimate it. Alongside it, report the final matrix: rows fully complete / 26.

Baseline for comparison: **42%** at audit time (commit `84f8f6c`).

---

## 8. Sign-off (SN-150)

Sign-off requires **all** of:

1. Every row in §2 has all five columns true, or carries a written and accepted justification.
2. Every grep in §3 returns nothing.
3. Every audit finding in §4 is resolved.
4. Every box in §5 is checked.
5. Every target in §6 is met or has an accepted exception.
6. `make test-critical` is green.
7. `make verify-determinism` is green.
8. Three consecutive full demo rehearsals produced identical measured outputs.
9. `README.md` describes only what exists.
10. The backup video is recorded and playable offline.

**If a requirement is not met, say so explicitly in the sign-off rather than marking it complete.** An honest 88% with a named gap is a stronger position — with judges and with the team — than a claimed 100% that a source inspection disproves. That principle is the reason this roadmap exists.
