# 19 — Testing Rebuild

Covers **SN-111 … SN-126**. The audit's finding: 443 assertions across ~5,700 lines, of which **104 assert only that a file exists**. One representative "cross-feature integration test" asserts `len("rrrrGGGggrrrrGGGgg") == 18` — a tautology over a string literal defined two lines above. API tests assert `status_code in (200, 401)`, which passes whether authentication works or is completely broken.

**Effective coverage ≈ 25%.** The instruction for this phase is explicit: *do not optimise for test count*. Test count may — and probably should — go **down**.

---

## 1. What gets deleted

| Pattern | Where | Why |
|---|---|---|
| `os.path.exists(...)` as the only assertion | `tests/e2e/tier1_features/` | proves a file exists, not that it works |
| `assert len("<literal>") == N` | `tests/e2e/tier3_combinations/` | tautology over a value defined in the test |
| `assert status_code in (200, 401)` | `tests/e2e/tier2_*` | passes when the feature is broken |
| Tests asserting on hardcoded values removed in Phase 0 | various | testing fabrications |

Delete the file rather than weakening the assertion. A deleted decorative test is progress; a retained one is a false signal.

---

## 2. The 15 critical paths

Location `tests/critical/`. Each file **must document its mutation check**: the specific one-line change to production code that makes this test fail. A test without a demonstrated failure mode is not evidence.

| ID | File | Path under test | Mutation check |
|---|---|---|---|
| SN-111 | `test_01_auth.py` | login success/failure, rate-limit lockout, token revocation, `/auth/me` | disable `verify_password` → test fails |
| SN-112 | `test_02_rbac.py` | every `—` cell in the permission matrix returns 403 | remove one `require_role` → test fails |
| SN-113 | `test_03_public_exposure.py` | `/public/*` needs no auth **and** leaks no UUIDs/models/operators | add `junction_id` to the public payload → test fails |
| SN-114 | `test_04_telemetry_ingest.py` | valid MQTT payload persists with `source='mqtt'`; malformed is rejected | remove schema validation → test fails |
| SN-115 | `test_05_sumo_telemetry.py` | SUMO run at fixed seed produces identical metric series twice | drop `--seed` → test fails |
| SN-116 | `test_06_dqn_inference.py` | real policy load, deterministic greedy action from a fixture state; missing weights → refuses MARL | stub the policy to a constant → test fails |
| SN-117 | `test_07_safety_envelope.py` | a state that would yield a 2 s green is clamped to `min_green_s` and recorded | raise `min_green_s` to 0 → test fails |
| SN-118 | `test_08_emergency_corridor.py` | ETA-ordered activation; program captured and **restored identically**; recovery measured | restore a default program instead of the captured one → test fails |
| SN-119 | `test_09_event_whatif.py` | two SUMO worlds, same seed, per-link deltas, severity from measurement | reuse one world's metrics for both → test fails |
| SN-120 | `test_10_citizen_advisory.py` | approval → advisory within 5 s; unapproved event yields none | allow publish without approval → test fails |
| SN-121 | `test_11_vision_pipeline.py` | worker on a fixture clip writes readings with `source='vision'`; PCU matches SUMO path | revert to the duplicate PCU table → test fails |
| SN-122 | `test_12_incident_gate.py` | incident from indicators; warning before confirmation returns 409; wrong-way TP and TN | allow publish-warning on UNVERIFIED → test fails |
| SN-123 | `test_13_provenance.py` | every payload carries `source`; `confidence` only when `source == 'model'` | return `confidence` on the heuristic path → test fails |
| SN-124 | `test_14_audit.py` | each mandatory action writes exactly one complete row; 403 writes `DENIED` | remove one `write_audit` call → test fails |
| SN-125 | `test_15_ab_reproducibility.py` | same seed → identical arm metrics; different seed → different improvement; formula matches spec | hardcode the improvement → test fails |
| SN-126 | `test_16_startup.py` | `start.sh` reaches all-green; missing dependency fails with a named cause | stop Redis → test asserts the named failure |

*(16 files for 15 paths — startup smoke is separated because it runs against a live stack.)*

---

## 3. Test infrastructure

| Layer | Approach |
|---|---|
| Unit / pure functions | pytest, no external services (state builder, safety envelope, reward, PCU, severity bands) |
| Integration | pytest + testcontainers or a compose-backed fixture: real Postgres, real Redis |
| SUMO tests | real `sumo` binary, headless, short scenarios (60–120 s), fixed seed |
| Vision tests | a 10-second fixture clip committed to the repo, including one wrong-way manoeuvre |
| API tests | `httpx.AsyncClient` against the real app with a seeded DB |
| Frontend | vitest for the provenance badge and role guards |

**Rules:**
1. No test mocks the thing it is meant to prove. A DQN inference test that stubs the policy proves nothing.
2. Fixed seeds everywhere; no test may be flaky by design.
3. Tests that require SUMO are marked `@pytest.mark.sumo` and skipped with a **loud** message if the binary is absent — never silently passed.
4. Assertions are on **behaviour and values**, never on file existence or literal lengths.

---

## 4. Commands

```bash
make test-critical      # the 15 paths — must be green before any demo
make test-unit          # fast, no services
make test-integration   # requires infrastructure
make test-sumo          # requires the SUMO binary
make test-frontend      # vitest
```

`make test-critical` must complete in under 5 minutes; anything slower will not be run often enough to matter.

---

## 5. CI

`.github/workflows/` runs unit + integration + frontend on every push, and the SUMO suite on a schedule. **The build fails if any critical-path test fails** — no allowances, no continue-on-error.

---

## 6. Acceptance criteria (Gate 8)

1. All 16 files exist and pass.
2. For three randomly chosen tests, applying the documented mutation makes the test fail. This is verified by a reviewer, not asserted.
3. `grep -rn 'assert len("' tests/` returns nothing.
4. `grep -rn "status_code in (200, 401)" tests/` returns nothing.
5. `grep -rln "os.path.exists" tests/ | wc -l` is 0 for assertion-only usage.
6. Test count may decrease; effective coverage of the 15 paths is 100%.
7. CI is green.
