# 12 — Citizen Information System

Covers **SN-061 … SN-068**. Currently 0 files. The audit calls this the single highest impact-to-effort item in the project, because it changes SurakshaNet's identity from a police console to civic infrastructure — and because the category theme names commuters as beneficiaries while the built system serves only operators.

---

## 1. Design constraint

**A commuter must extract the decision in under three seconds.**

Everything below follows from that. Confidence intervals, model names, PCU values, junction IDs and provenance badges — all of which are mandatory on the operator surface — are **forbidden here**. Citizens get the decision, not the machinery.

---

## 2. The five questions

The page answers, in this order, without scrolling:

| Question | Rendered as |
|---|---|
| Where is traffic? | corridor in place names |
| Why? | one plain-language cause |
| How bad? | severity + delay range |
| How long? | time window |
| What should I do? | one recommended route, or a departure time |

Reference layout:

```
  ⚠  HEAVY TRAFFIC EXPECTED
     Vijay Nagar → Palasia
     Tomorrow, 4:00 PM – 8:00 PM

     Expected delay      20–35 minutes
     Cause               Public event, 25,000 expected

     Take instead        Ring Road via LIG Square  (+4 min, clear)
     Or leave before     3:20 PM
```

Nothing else on the card. No map required for comprehension (a map may sit below as optional detail).

---

## 3. Data model (SN-061)

`citizen_advisories`, schema in [05-database.md §4](05-database.md). Notes on the fields that matter most:

- `corridor_text` uses **human place names only**. A junction UUID or SUMO edge ID on this surface is a bug.
- `delay_min_low` / `delay_min_high` come from the measured Δ travel time of the originating prediction — never rounded up for effect.
- `published_by` is **NOT NULL**. Publication is always a human act (SN-068); the constraint enforces it at the database level, not just in code.
- `expires_at` is mandatory. A stale advisory is worse than none; expired advisories disappear from `/public` automatically.

---

## 4. Sources (SN-067)

Four origins, all flowing through the same advisory table so the public surface has one shape:

| `origin_type` | Trigger | Human gate |
|---|---|---|
| `EVENT` | ADMIN publishes an approved event prediction | yes — approval + publish |
| `INCIDENT` | ADMIN publishes a warning for a **CONFIRMED** incident | yes — confirm, then publish |
| `EMERGENCY` | Corridor activation on a major route | yes — publish decision |
| `FORECAST` | Forecaster predicts severe congestion | yes — operator publishes |

**No path publishes automatically.** The audit's incident-response principle applies: publishing a public warning is irreversible, and a false alarm broadcast to a city is worse than a slow response.

---

## 5. Content builder (SN-063)

`backend/app/services/advisory_service.py`

```python
def build_advisory(origin_type, origin_id) -> CitizenAdvisoryDraft:
    # 1. resolve measured numbers from the origin
    #    EVENT     -> event_predictions.link_deltas (worst affected corridor)
    #    INCIDENT  -> measured delay on the affected link
    #    EMERGENCY -> corridor route + expected clearance
    #    FORECAST  -> forecaster horizon output (source=model)
    # 2. translate link IDs -> human corridor text via junction names
    # 3. delay range from measured deltas, rounded to 5-minute granularity
    # 4. cause text from a fixed vocabulary keyed by origin type
    # 5. recommendation = top-ranked alternative, or departure advice if none
    # 6. severity band copied from the measurement, never re-derived for effect
```

**Rules:**
1. Every number traces to a measurement or a declared model output. If an origin has no measured delay, the advisory is not generated — the operator sees "insufficient data to advise".
2. Delay ranges round **outward** to 5 minutes (a measured 22–33 becomes 20–35), never inward.
3. Cause text comes from a fixed vocabulary. Free-text causes invite overclaiming.

---

## 6. Departure recommendation (SN-064)

`recommended_departure_before` = the last 15-minute bucket before the predicted congestion onset where the forecast delay is below the `LOW` threshold, minus the travel time on the recommended route.

If congestion is already active, the field is null and the UI shows only the alternative route. **Do not** invent a "leave now" instruction when leaving now is exactly the problem.

---

## 7. Public API (SN-062) — no authentication

`GET /public/advisories`, `GET /public/advisories/{id}`, `GET /public/status`. Contracts in [06-api-contracts.md §6](06-api-contracts.md).

**Exposure rules (test SN-113):**

| Must expose | Must never expose |
|---|---|
| headline, corridor text, window | junction UUIDs, SUMO edge IDs |
| delay range, cause, severity | model names, versions, confidence |
| recommended route text, leave-before | operator identities, `published_by` |
| published/expires timestamps | raw telemetry, provenance fields |

Rate limit per IP (default 60 req/min) reusing the Redis limiter already built for login. No cookies, no tracking, no personal data collected — stated on the page.

---

## 8. Public route and UI (SN-065, SN-066)

**Routing:** `/public` registered in `App.tsx` **outside** `DashboardLayout` — no sidebar, no header, no auth guard, no operator chrome. It is a separate surface that happens to share a build.

**UI requirements:**
- Loads and is readable on a phone over a slow connection; no map or chart is required for the primary read.
- Largest element is the headline; second is the delay range.
- Severity encoded by more than colour (icon + word) for accessibility.
- Empty state is honest and calm: *"No traffic advisories right now."* — never a filler advisory to make the page look active.
- No auto-refresh flicker; poll every 60 s and update in place.
- No provenance badges — this is the one surface where they are deliberately absent, because the operator has already vouched for the content by publishing it.

**Language:** plain, imperative, no jargon. "Heavy traffic expected", not "Elevated congestion probability on link E_J1_J2".

---

## 9. Operator → citizen chain (the demo beat)

```
operator approves diversion  (Events page, ADMIN)
        │  audit row: EVENT_APPROVE
        ▼
operator publishes advisory   (human gate)
        │  audit row: ADVISORY_PUBLISH, published_by set
        ▼
citizen_advisories row created
        │
        ▼  Redis advisory_events → /ws/events
GET /public/advisories  ──▶  phone shows the advisory  (< 5 s)
```

**Demo line:** *"That one click reached commuters. Not a dashboard for the control room — information for the people stuck in the traffic."*

---

## 10. Acceptance criteria

1. `/public` loads with no authentication and no token in the request.
2. An operator's approval produces a visible public advisory within 5 s.
3. The public payload contains no UUIDs, model names, confidences or operator identities (SN-113).
4. Every delay figure traces to a measured Δ from the originating prediction.
5. An unapproved event or an unconfirmed incident never produces an advisory.
6. Expired advisories disappear without intervention.
7. `published_by IS NULL` is impossible — enforced by the database constraint.
8. The empty state shows no advisory rather than a placeholder.
