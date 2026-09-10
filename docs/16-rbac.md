# 16 — Role-Based Access Control

Covers **SN-098 … SN-101, SN-112**. Current roles: `ADMIN`, `OPERATOR`, `VIEWER` (`backend/app/models/user.py:8`). The guard helper `require_role(*roles)` exists at `backend/app/services/auth_service.py:202` but **is not applied to mutating endpoints** — `signals.py::update_signal_mode`, `signals.py::override_signal_phase` and `emergency.py::activate_emergency` all use `get_optional_current_user`, meaning an anonymous caller can change signal modes and activate emergency corridors.

---

## 1. Target roles

| Role | Who | Scope |
|---|---|---|
| `ADMIN` | System administrator | Everything, including approvals, publication and audit |
| `OPERATOR` | Traffic control room | Signals, incidents, events (create/predict), corridors (view) |
| `EMERGENCY_SERVICES` | Ambulance/fire/police dispatch | Emergency incidents and corridors only |
| `VIEWER` | City administration, analysts | Read-only across operational surfaces |
| `CITIZEN` | Public | Public advisory surface only (usually unauthenticated) |

`CITIZEN` exists as a role so the public surface can later support saved routes or notifications without restructuring auth. Today `/public/*` requires no token at all.

---

## 2. Permission matrix (SN-099)

`✔` allowed · `—` denied (403) · `PUB` public, no authentication

| API group | ADMIN | OPERATOR | EMERGENCY_SERVICES | VIEWER | CITIZEN |
|---|---|---|---|---|---|
| `POST /auth/login`, `/auth/refresh` | PUB | PUB | PUB | PUB | PUB |
| `GET /auth/me` | ✔ | ✔ | ✔ | ✔ | ✔ |
| `POST /auth/register` | ✔ | — | — | — | — |
| `GET /users`, `PATCH /users/{id}` | ✔ | — | — | — | — |
| `GET /health`, `/health/deep` | PUB | PUB | PUB | PUB | PUB |
| `GET /traffic/*`, `/junctions/*` (read) | ✔ | ✔ | ✔ | ✔ | — |
| `POST/PATCH /traffic/*`, `/junctions/*` | ✔ | ✔ | — | — | — |
| `GET /signals/*` | ✔ | ✔ | ✔ | ✔ | — |
| `PATCH /signals/junctions/{id}/mode` | ✔ | ✔ | — | — | — |
| `POST /signals/junctions/{id}/override` | ✔ | ✔ | — | — | — |
| `GET /signals/junctions/{id}/decision` | ✔ | ✔ | — | ✔ | — |
| `POST /ab/run` | ✔ | ✔ | — | — | — |
| `GET /ab/runs/{id}` | ✔ | ✔ | — | ✔ | — |
| `GET /ml/*` (predict, models, status) | ✔ | ✔ | ✔ | ✔ | — |
| `POST /ml/train/*` | ✔ | — | — | — | — |
| `GET /simulation/*` | ✔ | ✔ | — | ✔ | — |
| `POST /simulation/{start,step,stop,reset}` | ✔ | ✔ | — | — | — |
| `POST /emergency/activate` | ✔ | — | ✔ | — | — |
| `POST /emergency/deactivate/{id}` | ✔ | — | ✔ | — | — |
| `GET /emergency/*` | ✔ | ✔ | ✔ | ✔ | — |
| `GET /emergency/{id}/recovery` | ✔ | ✔ | ✔ | ✔ | — |
| `POST /events` , `PATCH /events/{id}` | ✔ | ✔ | — | — | — |
| `GET /events*` | ✔ | ✔ | ✔ | ✔ | — |
| `POST /events/{id}/predict` | ✔ | ✔ | — | — | — |
| `POST /events/{id}/approve` | ✔ | — | — | — | — |
| `POST /events/{id}/publish` | ✔ | — | — | — | — |
| `GET /incidents*` | ✔ | ✔ | ✔ | ✔ | — |
| `POST /incidents/{id}/confirm`, `/dismiss` | ✔ | ✔ | — | — | — |
| `POST /incidents/{id}/escalate` | ✔ | ✔ | ✔ | — | — |
| `POST /incidents/{id}/publish-warning` | ✔ | — | — | — | — |
| `GET /vision/*` | ✔ | ✔ | ✔ | ✔ | — |
| `PATCH /vision/flags/{id}/resolve` | ✔ | ✔ | — | — | — |
| `POST /vision/zones` | ✔ | ✔ | — | — | — |
| `GET /routing/*` | ✔ | ✔ | ✔ | ✔ | — |
| `POST /routing/vms/broadcast` | ✔ | ✔ | — | — | — |
| `GET /audit*` | ✔ | — | — | — | — |
| `GET /public/*` | PUB | PUB | PUB | PUB | PUB |

**Deliberate restrictions and their reasons:**
- Only `ADMIN` publishes anything public (event publish, incident warning). Public communication is irreversible; it needs the highest authority in the system.
- Only `EMERGENCY_SERVICES` and `ADMIN` activate corridors (SN-101) — a corridor pre-empts an entire route and is an abuse vector if open to every operator.
- `EMERGENCY_SERVICES` cannot change signal modes. They request priority; they do not run the network.
- `VIEWER` (city administration) reads analytics and A/B results but changes nothing.

---

## 3. Implementation (SN-100)

Replace `Depends(get_optional_current_user)` with `Depends(require_role("ADMIN","OPERATOR"))` (etc.) on every mutating endpoint. `get_optional_current_user` remains valid **only** on `/public/*` and `/health*`.

Extend `require_role` to write a `DENIED` audit row on rejection and to return a message naming the role and the action:
```
403 {"detail": "Role OPERATOR cannot perform CORRIDOR_ACTIVATE"}
```

**Rate limits (SN-101):** signal override 10/min/user; corridor activation 5/min/user; A/B run 1 concurrent; public endpoints 60/min/IP. Reuse the Redis limiter already built for login (`auth_service.py:49`).

---

## 4. Frontend enforcement

Role-aware navigation **and** route guards — hiding a menu item is not access control. `frontend/dashboard/src/store/authStore.ts` exposes the role; `DashboardLayout` guards routes; disabled controls state *why* ("Requires ADMIN"), rather than failing silently on click.

---

## 5. Acceptance criteria (SN-112)

1. Every `—` cell in §2 returns **403** for a token of that role.
2. Every `✔` cell returns non-403 for a token of that role.
3. No mutating endpoint accepts an anonymous request — verified by calling each without a token.
4. `/public/*` succeeds with no token and exposes nothing from the protected surface (SN-113).
5. Every 403 writes an audit row with `result: DENIED`.
6. Rate limits return 429 with `retry_after_s`.
