# 24 — Frontend Requirements

Covers **SN-004, SN-005, SN-009, SN-119 … SN-126** and the frontend obligations of every feature phase.

> **Preserve the existing SurakshaNet visual language.** This is not a redesign. React 18 + TS + Vite + Zustand + Leaflet + Recharts + Tailwind stay. Do not add decorative effects, and do not extend `components/Studio/` — the audit and the original brief both warn against exactly that, and the repo already contains a Three.js sphere with ten `Math.random()` calls.

---

## 1. The core change

**The frontend becomes a visualisation of actual backend state.** Today it partly generates its own: `hooks/useTrafficSimulationEngine.ts` produces telemetry *in the browser* from templated event strings, and seven components run `Math.random()` loops. With the backend stopped, numbers keep moving — which is the most visible form of the defect this project is correcting.

| File | Current | Required |
|---|---|---|
| `hooks/useTrafficSimulationEngine.ts` | generates telemetry client-side | **delete**; replace with a WebSocket subscription hook |
| `components/CommandCenter/ComputerVisionFeed.tsx` | 5 random boxes, fake FPS/confidence | real detections or "No video source" (SN-004) |
| `pages/TrafficMapPage.tsx` | 5 `Math.random()` call sites | backend state only (SN-119) |
| `pages/SignalControlPage.tsx` | 4 `Math.random()` call sites | real control decisions |
| `components/CommandCenter/CityTrafficCanvas.tsx` | 2 call sites | real telemetry |
| `pages/{Simulation,Emergency,Analytics,Emissions,EdgeDevices}Page.tsx` | random/mock data | backend state or unavailable |
| `pages/RoutingPage.tsx:43` | hardcoded `"ACCIDENT CLEARED"` | real VMS state (SN-010) |
| `components/Studio/*` | decorative 3D | **frozen** — no changes, no extensions |

`Math.random()` remains acceptable **only** inside `components/Studio/` (decorative, non-data) and for React key generation.

---

## 2. Provenance badges (SN-009)

Extend `components/TelemetrySourceBadge.tsx` to cover all six `DataSource` values with distinct treatment:

| Source | Treatment |
|---|---|
| `sumo` / `vision` / `mqtt` | one visual family — "measured" |
| `model` | distinct from measured — "predicted" |
| `heuristic` | **distinct from both**, value prefixed "est." — never styled like a measurement (R3) |
| `manual` | distinct — "entered" |

**Hard rules:**
1. Every numeric panel renders a badge.
2. A panel with no `source` renders the unavailable state, not a number.
3. Heuristic values never share typography with measured or model values.

---

## 3. Unavailable states

Every data surface needs one, and it must be visually calm and explicit rather than an error scream:

```
┌─────────────────────────────┐
│  Simulation unavailable     │
│  TraCI connection refused   │
│  [ Retry ]                  │
└─────────────────────────────┘
```

Required on: simulation panels (SN-005), CV feed (SN-004), control decision panel, A/B panel, forecast panel, vision flags, and every map layer. Backend down → every panel shows disconnected. **No panel may continue animating.**

---

## 4. Page-by-page requirements

### Command Center (`/command`, `CommandCenterPage.tsx`)
Live map with traffic density, signal states, incidents, emergency vehicles, road closures, events, congestion zones — all from backend state, each layer badged. KPI row: active incidents, average congestion, emergency vehicles active, junctions under adaptive control, roads affected, estimated delays. AI alerts ticker showing **real** alerts from `/ws/alerts` and `/ws/incidents` — the current `AIInsightsTicker.tsx` templated strings are deleted.

### Signal panel (`/app/signals`, `SignalControlPage.tsx`)
Per junction: current phase and remaining green, controller mode (`MARL`/`WEBSTER`/`MANUAL`), **the AI decision with its reason string**, whether the safety envelope clamped it, queue and accumulated wait per approach. Mode switch control (OPERATOR+). Live from `/ws/control` and `GET /signals/junctions/{id}/decision`.

The decision display is the frontend's most important addition — it is where a judge sees that the model is real.

### A/B panel (new, `ABComparisonPanel.tsx`)
Split view, two live metric series (Webster left, DQN right), identical axes. Seed displayed prominently. Improvement figure appears **only** when the run completes, and comes from the API — the client never computes it. A negative improvement renders unchanged.

### Emergency panel (`/app/emergency`, `EmergencyPage.tsx`)
Vehicle, destination, route polyline, per-junction ETA, junction states colour-coded (`scheduled`/`preempted`/`passed`/`restored`), next junction with countdown, corridor status, cross-traffic impact, recovery chart after close. **The corridor must visibly propagate**, not render as a static list.

### Event panel (`/app/events`, new)
Create form with derived trip counts and visible assumptions; map link selection; prediction progress driven by real step count; per-link delta table with severity bands and a legend stating the thresholds; ranked alternatives; approve/publish (ADMIN) with an advisory preview.

### Citizen view (`/public`, new)
Outside `DashboardLayout` — no sidebar, no header, no auth. See [12-citizen-advisory.md §8](12-citizen-advisory.md). Three-second read; no badges, no jargon, no map required for comprehension; honest empty state.

### Incidents (`AlertsPage.tsx`, `LiveIncidents.tsx`)
Cards showing which indicators fired with measured values vs. thresholds; `UNVERIFIED` badge; confirm/dismiss/escalate; publish-warning marked distinctly as irreversible. Phrasing fixed at "Possible incident — N of 5 indicators".

### Audit (`/app/audit`, new)
ADMIN only, route-guarded as well as menu-hidden. See [18-audit-logging.md §5](18-audit-logging.md).

---

## 5. State management

| Store | Contents |
|---|---|
| `authStore.ts` (existing) | token, user, role — role drives guards |
| `trafficStore.ts` (existing) | junctions, latest telemetry, **with `source` per value** |
| `controlStore.ts` (new) | latest decision per junction, controller modes |
| `incidentStore.ts` (new) | open incidents, flags |
| `eventStore.ts` (new) | events, predictions |

WebSocket subscriptions feed the stores; components read from stores. **No component fetches on a timer to simulate liveness.**

---

## 6. Role-aware UI

Hiding a menu item is not access control ([16-rbac.md §4](16-rbac.md)). Requirements: menu filtered by role; routes guarded; disabled controls state *why* ("Requires ADMIN"); a 403 from the API shows the returned reason rather than a generic error.

---

## 7. Acceptance criteria

1. With the backend stopped, **no page displays moving traffic numbers**.
2. `grep -rn "Math.random" frontend/dashboard/src --include=*.tsx | grep -v "components/Studio/"` returns nothing.
3. `useTrafficSimulationEngine.ts` is deleted.
4. Every numeric panel shows a provenance badge.
5. Heuristic values are visually distinct from model and measured values.
6. Every data surface has an unavailable state that renders correctly.
7. The signal panel shows a real decision with its reason for an observed phase change.
8. The A/B improvement figure comes from the API, never client arithmetic.
9. `/public` loads with no token and no operator chrome.
10. `components/Studio/` is unchanged.
