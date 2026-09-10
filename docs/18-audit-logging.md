# 18 — Audit Logging

Covers **SN-102 … SN-106**. No audit trail exists today. This is what turns "what if the AI is wrong?" from an awkward question into a strong answer: *it is constrained by the safety envelope, gated before anything public, and fully audited.*

---

## 1. Schema

`audit_logs`, defined in [05-database.md §7](05-database.md). Hypertable, 30-day chunks, 1-year retention.

Required fields on every row: `actor_type` (`USER`/`SYSTEM`/`AI`), `actor_id`, `action`, `target_type`, `target_id`, `input`, `output`, `model`, `model_version`, `confidence`, `source`, `result` (`SUCCESS`/`FAILURE`/`DENIED`), `correlation_id`, `timestamp`.

**Constraint:** `confidence` is non-null **only** when `actor_type = 'AI'`. A confidence on a human action is a category error and is rejected at write time.

---

## 2. Mandatory logged actions (SN-104)

The nine action types from the requirement, plus AI decisions:

| Action | Actor | Trigger | Notes |
|---|---|---|---|
| `SIGNAL_OVERRIDE` | USER | `POST /signals/junctions/{id}/override` | input = action + value; output = applied phase |
| `SIGNAL_MODE_CHANGE` | USER | `PATCH /signals/junctions/{id}/mode` | old and new mode in input/output |
| `CORRIDOR_ACTIVATE` | USER | `POST /emergency/activate` | route + ETAs in output |
| `CORRIDOR_DEACTIVATE` | USER or SYSTEM | manual or auto-complete | restoration verification in output |
| `INCIDENT_CONFIRM` | USER | `POST /incidents/{id}/confirm` | **human gate 1** |
| `INCIDENT_DISMISS` | USER | `POST /incidents/{id}/dismiss` | dismissal reason required |
| `PUBLIC_WARNING_PUBLISH` | USER | `POST /incidents/{id}/publish-warning` | **human gate 2, irreversible** |
| `EVENT_APPROVE` | USER | `POST /events/{id}/approve` | prediction id in input |
| `ADVISORY_PUBLISH` | USER | `POST /events/{id}/publish` | advisory content in output |
| `ROUTE_DIVERSION` | USER | diversion accepted | affected links in output |
| `USER_LOGIN` / `USER_LOGOUT` / `TOKEN_REVOKE` | USER | auth events (SN-097) | result records success/failure |
| `AI_CONTROL_DECISION` | AI | every control step | state vector, Q-values, action, clamp |
| `AI_INCIDENT_DETECT` | AI | incident created | indicators + anomaly score |
| `AI_ADVISORY_DRAFT` | AI | advisory drafted | measured basis |
| `AI_BEHAVIOR_FLAG` | AI | flag raised | evidence |
| `ACCESS_DENIED` | USER | any 403 | role and attempted action |

---

## 3. Volume management

`AI_CONTROL_DECISION` fires every control step per junction — 4 junctions × 12/min ≈ 69,000 rows/day. Handle it:

- `control_decisions` is the **detailed** store (90-day retention). `audit_logs` receives a **sampled** AI decision row: every clamp, every fallback, every mode change, plus one in twenty routine decisions.
- Sampling is documented in the audit viewer so nobody mistakes a gap for a missing decision, and the full record remains queryable in `control_decisions`.
- Never sample human actions. Every one is logged.

---

## 4. Implementation (SN-103)

`backend/app/services/audit_service.py`:

```python
async def write_audit(db, *, actor_type, actor_id, action, target_type, target_id,
                      input_data, output_data, result,
                      model=None, model_version=None, confidence=None,
                      source=None, correlation_id=None) -> None
```

- Correlation ID from the existing `backend/app/middleware/correlation.py`.
- Writes are **best-effort and non-blocking for the response**, but a write failure is logged at ERROR — a silently missing audit trail is worse than a slow request.
- Sensitive values (passwords, tokens) are never written to `input`; the helper redacts a fixed key list.
- The helper is called from the endpoint, not from a generic middleware, so `input`/`output` carry semantic content rather than raw HTTP bodies.

---

## 5. Audit viewer (SN-106)

`frontend/dashboard/src/pages/AuditPage.tsx`, route `/app/audit`, **ADMIN only** (menu hidden *and* route guarded).

Table: timestamp, actor (type + name), action, target, result, source. Filters by actor type, action, target, date range. Row expands to show `input`/`output` and, for AI rows, the model, version and confidence.

**Demo value:** after the corridor activation and the incident confirmation earlier in the demo, open this page and show those exact rows. It converts the governance claim from an assertion into an artefact.

---

## 6. Acceptance criteria (SN-124)

1. Each of the action types in §2 writes exactly one audit row when performed.
2. Every row has non-null `actor_type`, `action`, `result`, `timestamp`, `correlation_id`.
3. `confidence` is non-null only when `actor_type = 'AI'`.
4. Every 403 produces a row with `result: DENIED`.
5. Passwords and tokens never appear in `input`.
6. The viewer is inaccessible to non-ADMIN roles by both navigation and direct URL.
7. AI decision sampling is documented in the UI and the full record exists in `control_decisions`.
