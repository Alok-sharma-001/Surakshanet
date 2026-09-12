# 24 — Drunk-Driving Detection: Policy and Boundary

Covers **SN-096, SN-144**. This document exists because the original project brief asked for
"drunk driving detection," and the honest answer is that this system does not do that, cannot do
that from a camera, and is built deliberately so that no part of it can be mistaken for doing that.

---

## 1. The scientific boundary

There is no visual signature of blood alcohol content. A camera measures pixels — position,
motion, shape. Intoxication is a physiological/chemical state (blood alcohol concentration)
that has no reliable, camera-observable proxy validated for legal or operational use. Weaving,
erratic speed, and unsafe headway are real, measurable driving behaviours, and this system does
measure them — but they are not proof of intoxication. A driver reaching for a dropped phone,
avoiding a pothole, or driving a poorly-aligned vehicle can produce the same kinematic signature
as an intoxicated one. Treating a matching pattern as proof of intoxication would be a false
claim this system does not make.

## 2. The legal boundary

No jurisdiction accepts camera video as a substitute for a calibrated breathalyser or blood test
in establishing intoxication. Any system that reported "drunk driver detected" from CCTV alone
would be making a claim with no evidentiary standing, and would put an operator in the position
of publishing or acting on an accusation this project cannot support. That is a legal exposure
this project explicitly declines to create.

## 3. What this system actually does

`services/vision_worker/behavior.py` computes real, measured kinematic proxies — acceleration
variance, heading oscillation ("weaving"), and following-distance/headway — and raises a
`DANGEROUS_DRIVING` behavior flag when those measured values cross a documented threshold
(SN-081). That flag is persisted as `BehaviorFlag` with status `UNVERIFIED` (SN-077) and routed
to a human operator for review, exactly like every other AI-raised suspicion in this project
(Invariant: AI flags for review, a person confirms). The flag's own language never claims
intoxication, guilt, or a confirmed violation — see `frontend/dashboard` copy and every backend
response for `DANGEROUS_DRIVING` events.

The intended real-world path stays entirely human at the point of legal consequence: a
`DANGEROUS_DRIVING` flag reaches a patrol unit, an officer makes the stop, and — if intoxication
is actually suspected — a calibrated breathalyser or blood test produces the real measurement. AI
narrows *where* to look. It never determines the offence, and it never will inside this codebase.

## 4. Enforcement

This is not just a design intention — it is enforced mechanically:

- `tests/test_language_policy.py::test_repo_language_policy_compliance` walks the entire
  repository (code, docs, UI copy) and fails the build if any of a documented list of forbidden
  phrases appears outside an explicit prohibition statement — phrases that would claim this
  system detects intoxication or a DUI condition, phrased any of the ways a developer might
  reasonably write "the system flags an [xyz] driver" for that specific condition. It also
  forbids AI-originated guilt claims generally — language that would state a traffic violation
  or offence as confirmed, or a driver's guilt as established, by AI output alone — the same
  human-gate principle applied to language, not just to database status transitions.
- `test_language_policy_detects_mutation` is a real self-test proving the scanner actually fires
  on a deliberately reintroduced violation, rather than being a check that always passes.
- `scripts/check_phase0_regressions.sh` runs the same suite as part of CI, so a regression here
  fails the build, not just a code review.

## 5. What this means for the roadmap

"Camera-based drunk-driving detection" is explicitly **declined** as an original-brief
requirement (SN-144), for the scientific and legal reasons above — not deferred, not partially
built, not a future milestone. If a future deployment wants to correlate a `DANGEROUS_DRIVING`
flag with an eventual breathalyser result for research purposes, that is a distinct, much larger
system (chain of custody, consent, jurisdiction-specific evidentiary rules) outside this
project's scope, and would need its own explicit policy review before any code is written.
