# Phase 2 Remediation Plan

> Execution plan for closing the gap between what `docs/CHECKLIST.md` currently
> claims for SN-023…SN-038 (`Status: COMPLETE` on every task line) and what is
> actually true by this project's own Definition of Done
> (`docs/23-final-acceptance.md §1`: implemented ∧ tested ∧ demonstrated ∧
> documented — code existing is only the first of those). The architecture
> that exists (`services/control_service/{controllers,safety,state,reward,
> ab_runner,config}.py`, `backend/app/api/ab.py`, the `002` migration,
> `shared/telemetry.py`) is genuinely honest engineering — this plan is about
> proving it, not rewriting it.

**Do not mark Phase 2 done until item 4 (run the A/B harness for real) has
produced a recorded result** — that result, whatever it says, is Phase 2's
actual deliverable. Everything else in this plan exists to make that result
trustworthy.

---

## 1. Reconcile the checklist with itself

**Problem.** Every SN-023…SN-038 task line reads `**Status** COMPLETE`, but
the phase-rollup table still reads `2 Real AI control | 0/17` and the header
total is still `31/161 — 19%` (unchanged since Phase 1 closed). The tracker
disagrees with itself, which is exactly the failure mode this project exists
to catch in the *product* — it can't be tolerated in the tracker either.

**Fix.** Do not bulk-flip the rollup to match the per-task lines. Instead,
work items 2–7 below, and only mark a task line `DONE` (not `COMPLETE` —
match the vocabulary the rest of the file uses: `NOT_STARTED · IN_PROGRESS ·
BLOCKED · TESTING · DONE`) once its own Definition-of-Done conditions are
actually satisfied. Update the phase table and header total to match the
per-task lines as each one is genuinely closed, the same way the Phase 0 and
Phase 1 status-log entries were written — one dated log line per batch, with
a note on what was actually verified.

**Check.** `grep -c "Status.*DONE" ` against the SN-023…038 block equals the
phase table's numerator equals the count folded into the header total.

---

## 2. Fix the local environment gap that's currently blocking verification

**Problem.** `.venv` has neither `torch` nor `sqlalchemy` installed, despite
both being pinned in `requirements.txt`/`backend/requirements.txt`. This is
SN-017's own acceptance criterion ("a fresh venv from requirements.txt runs
the critical test suite") going unmet in practice. Concretely, right now:

```
PYTHONPATH=... .venv/bin/python3 -m pytest tests/critical/
  -> test_15_ab_reproducibility.py fails to collect (No module named 'sqlalchemy')
  -> test_06_dqn_inference.py: 3/6 tests fail (No module named 'torch')
  -> the other 3 files: 16/16 pass
```

The 16 passing tests are real signal (see item 3) — the 4 failures are pure
environment gap, not code defects: `MarlController._load_policy()` correctly
catches the `ImportError` and reports `is_loaded=False`, which is the right
behavior, it's just not what those specific tests are asserting.

**Fix.** `pip install -r requirements.txt` (or `-r backend/requirements.txt`)
into `.venv` for real, then re-run `pytest tests/critical/` and confirm all
19 collect and the DQN tests exercise the actual PyTorch path, not the
missing-dependency path.

**Check.** `.venv/bin/python3 -c "import torch, sqlalchemy"` succeeds.
`pytest tests/critical/ -v` collects and runs all 19 tests with zero
`ModuleNotFoundError`s (failures for other reasons are then real findings —
see item 3).

---

## 3. Run `tests/critical/` for real and act on what it says

**Problem.** These five files (`test_04_telemetry_ingest.py`,
`test_05_sumo_telemetry.py`, `test_06_dqn_inference.py`,
`test_07_safety_envelope.py`, `test_15_ab_reproducibility.py`) are
well-designed — each carries an explicit "mutation check" describing what
should fail if the underlying code were faked (e.g. `test_15`'s docstring:
"hardcode the improvement to a constant -> test fails"). That's exactly the
right pattern. But per item 2, they've never actually been run to
completion, so nobody knows if they currently pass.

**Fix.** After item 2's environment fix, run the full suite and treat every
failure as a real Phase 2 finding to fix before touching the checklist:

```bash
PYTHONPATH=$(pwd):$(pwd)/backend .venv/bin/python3 -m pytest tests/critical/ -v
```

**Check.** All 19 tests pass. Keep the run's output — it's the evidence
item 1's checklist update should cite.

---

## 4. Retrain the MARL policy against real SUMO (SN-012f)

**Problem, still open from Phase 0.** `ml/marl/train_marl.py` draws its
training state from `np.random.uniform(5, 40, size=8)` and its transitions
from `np.random.normal(...)` — there is no SUMO anywhere in the loop. The
weights `MarlController` loads and `ab_runner.py` would evaluate were never
trained on real traffic dynamics. This is the one gap that makes every other
piece of honest Phase 2 engineering (the safety envelope, the state builder,
the A/B harness's honest-reporting rule) moot: they'd all be correctly,
honestly measuring a policy that learned nothing about real traffic.

Two aggravators noted in Phase 0's SN-012f log, still present: the loop is
hardcoded `for ep in range(150)` while the `episodes` argument is written
into `hparams.json` as whatever the caller passed (so the recorded
hyperparameters don't describe the run that happened), and the agent is
hardcoded to `junction_id="DEL-CP-01"`.

**Fix.** Replace the synthetic rollout with a real episode loop against
`SumoEnvironment`, reading the SN-015 lane-area detectors (now correctly
loaded — see the Phase 1 plan, item 5), seeded via `DEMO_SEED`
(`shared/constants.py`). Honour the `episodes` argument for real. Take the
junction id from `services/control_service/config.py` rather than
hardcoding it.

**Check.** `python -m ml.marl.train_marl` drives an actual SUMO process
(observable via CPU/process activity, not instant completion). Two runs at
`seed=42` produce byte-identical `marl_hyperparameters.json` and matching
final-episode metrics. `hparams.json`'s `episodes` field matches how many
episodes actually ran.

---

## 5. Run the A/B harness and record a real result

**Problem.** `services/control_service/ab_runner.py` (SN-038) exists and is
architecturally sound — it drives two live TraCI runs and reports negative
results unchanged — but there is no evidence it has ever been executed. No
`ab_runs` row, no log, nothing dated after the code itself.

**Fix.** After item 4 lands (a policy trained on real SUMO — running the A/B
harness against the current `np.random`-trained weights would produce a
number, but not a *meaningful* one), actually run it:

```python
from services.control_service.ab_runner import ABRunner
result = ABRunner().run_ab_comparison(scenario="surge", seed=42, duration_s=900)
```

or via `POST /ab/run` once the backend is up. Let the result be whatever it
is — per SN-038's own rule, a result where MARL underperforms Webster is a
valid, reportable outcome, not a failure to fix by re-running until the
number looks better.

**Check.** A real row exists in `ab_runs` (or the equivalent JSON output)
with a `status: complete`, a non-null `improvement`, and a `statement` that
matches the sign of the measured delay change. Re-running at the same seed
reproduces the same arm metrics (this is what `test_15_ab_reproducibility.py`
checks — item 3 covers running it).

---

## 6. Remove the fabricated pre-audit benchmark artifacts

**Problem.** `ml/benchmarks/results/baseline_study_report.md` and
`baseline_study_results.json` assert "Status: Defensible Benchmark Verified"
and "18.38% delay reduction / 22.92% queue reduction," with no runner script
anywhere that could have produced them (`ml/benchmarks/` contains only the
`results/` subdirectory). `docs/RESEARCH_DEFENSE.md` independently asserts a
*different* set of absolute numbers (42.16s→34.41s, not 46.8s→38.2s) for
what it claims is the same study, while landing on the identical "18.38%" /
"22.92%" percentages — two independently-fabricated write-ups converging on
the same target number. Both predate the audit (last touched in commit
`3b9626f`, the pre-Phase-0 baseline) and were never cleaned up by Phase 0's
SN-012 doc-reconciliation pass. `STATUS.md` still repeats the number under a
"RESEARCH-GRADE" label; `CLAUDE.md` picked it up as fact from there.

**Fix.**
- Delete `ml/benchmarks/results/baseline_study_report.md` and
  `baseline_study_results.json`, or move them to a clearly-marked
  `ml/benchmarks/results/ARCHIVED_PRE_AUDIT_UNVERIFIED/` if history wants to
  be kept — never leave them at a path that looks like current output.
- Rewrite `docs/RESEARCH_DEFENSE.md §2` to either state plainly that no
  verified benchmark exists yet (pending item 5), or — once item 5 has
  produced a real result — cite that result's actual numbers, sourced from
  the real `ab_runs` row, not hand-typed.
- Rewrite `STATUS.md`'s "Adaptive Signal Control" row: drop the specific
  percentages until item 5 exists; the row's own "SUPERSEDED" banner already
  says `docs/01-current-state.md` is authoritative — the body should stop
  contradicting its own banner.
- Fix `docs/RESEARCH_DEFENSE.md §3`'s `live`/`sim`/`mock` vocabulary to the
  `DataSource` enum (`sumo|vision|mqtt|model|heuristic|manual`) SN-008
  introduced — it's still using the pre-Phase-0 terms.

**Check.** `grep -rn "18.38\|22.92" .` (excluding `.git`) returns nothing, or
— once item 5 has run — returns only the real, freshly-measured numbers,
traceable to an actual `ab_runs` row.

---

## 7. Verify the remaining SN-023…037 tasks against their own acceptance text

**Problem.** This plan has spot-verified SN-023 (`shared/telemetry.py`),
SN-024 (the `002` migration), SN-025 (the bridge emits `JunctionTelemetry`
via `REDIS_CHANNELS`), SN-026 (`REDIS_CHANNELS` exists), SN-029 (`/ws/control`
route exists), SN-030 (the control-service files exist), SN-036 (forecaster
honest-provenance work — largely done in Phase 0 already), SN-037 (the five
Prometheus metric names exist), and SN-038 (architecturally sound, needs
item 5). SN-027, SN-028, SN-031, SN-032, SN-033, SN-034, SN-035 have **not**
been individually re-verified in this pass — each has a specific,
checkable acceptance line in `docs/CHECKLIST.md` (e.g. SN-032: "A state that
would yield a 2s green is clamped to `min_green_s` and the clamp is
persisted"). `tests/critical/test_07_safety_envelope.py` likely already
covers SN-032 and passed in the item-3 run, which is good evidence — extend
that same "does a real test exercise this exact acceptance line" check to
the others before trusting their `COMPLETE` label.

**Fix.** For each of SN-027, 028, 031, 033, 034, 035, run its own acceptance
line as a literal check:
- SN-027: post a malformed MQTT payload, confirm it's rejected and logged
  rather than partially written.
- SN-028: `grep -rn "signal_events\|surakshanet:events:signals"` — confirm
  only one naming scheme survives.
- SN-031: exercise `MarlController`, `WebsterController`, `ManualController`
  on identical input, confirm observably different timing output.
- SN-033: flip `signal_plans.mode` via the API, confirm the control loop's
  output changes within one control step.
- SN-034: feed a fixture telemetry set through `build_state_vector`, confirm
  a deterministic, correctly-ordered 8-dim vector with recorded normalisation
  constants.
- SN-035: confirm a `control_decisions` row's `reward` column is populated
  on the step after the action, using the documented formula.

**Check.** Each item above either passes as described (mark `DONE`, cite the
exact command/test that proved it) or fails (log the gap the same way SN-012a
…k logged Phase 0's gaps, don't silently mark it done).

---

## Summary table

| # | Item | Blocks |
|---|---|---|
| 1 | Reconcile checklist rollup with per-task status | Tracking honesty only — do continuously |
| 2 | Install `torch`/`sqlalchemy` into `.venv` | 3, 5 |
| 3 | Run `tests/critical/` to completion | 1 (evidence), 7 |
| 4 | Retrain MARL against real SUMO (SN-012f) | 5 |
| 5 | Run the A/B harness, record a real result | 1 (SN-038), 6 |
| 6 | Delete/replace fabricated benchmark artifacts | Trustworthiness of any Phase 2 claim in docs |
| 7 | Verify SN-027/028/031/033/034/035 individually | 1 |

Order: 2 → 3 (cheap, immediate signal) in parallel with 6 (pure doc cleanup,
no dependencies) → 4 (the real blocker, takes the longest) → 5 → 1 and 7
close out once everything above is true. Do not let Phase 3 start on the
strength of the current `COMPLETE` labels alone — SN-039…050 (emergency
corridor) depends on the control service's mode-routing (SN-033) actually
being verified, not just present.
