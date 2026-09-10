# Phase 1 Remediation Plan

> Execution plan for the 10 findings from the Phase 1 code review (working-tree
> diff covering SN-013…SN-022). Nothing here is implemented yet — this is the
> plan to work from. Each item names the exact root cause, the fix, the files
> it touches, and how to check it actually worked. Ordered by dependency, not
> by severity: items 1–2 unblock several of the others, so do those first.

**Do not start Phase 2 before item 5 (SN-015 detectors) is done** — Phase 2's
DQN state builder reads these detectors through the REST-driven simulation
path, and today that path never loads them.

---

## 1. Stop `SystemExit` from breaking the SN-005 graceful-degradation contract

**Root cause.** `simulation/sumo_env.py` raises `SystemExit` (a `BaseException`)
when `traci` is missing. `backend/app/api/simulation.py` and
`ml/marl/train_marl.py` both wrap their import of `SumoEnvironment` in
`except ImportError: SumoEnvironment = None` — a contract `sumo_env.py` was
never asked to honor (SN-016's own file list is `main.py`,
`sumo_live_bridge.py`, `services/control_service/main.py` — **not**
`sumo_env.py`). `except ImportError` cannot catch `SystemExit`, so the
fallback is dead code, and anything importing `sumo_env` outside the three
listed entrypoints (chiefly `ml/marl/train_marl.py`, a standalone script)
crashes instead of degrading.

**Fix.** `sumo_env.py` reverts to raising a plain, informative `ImportError`
— loud (satisfies SN-013's "never silent" principle) but catchable (restores
the contract its callers already implement):

```python
# simulation/sumo_env.py
try:
    import traci
except ImportError as exc:
    raise ImportError(
        "'traci' is not importable from this interpreter "
        f"({sys.executable}). See docs/04-environment-setup.md §2 (SN-013)."
    ) from exc
```

Do not touch the behavior of `main.py`, `sumo_live_bridge.py`, or
`services/control_service/main.py` — SN-016 explicitly wants those three to
hard-exit, and that stays (see item 2 for the one caveat on `main.py`).

**Files.** `simulation/sumo_env.py` only.

**Check.** With `traci` temporarily renamed/hidden: `python -c "from
backend.app.api.simulation import SumoEnvironment"` (or just import
`app.api.simulation` inside a traci-less venv) succeeds and leaves
`SumoEnvironment = None`. `python ml/marl/train_marl.py` prints an
`ImportError`-driven message instead of an uncaught `SystemExit` traceback.

---

## 2. Deduplicate the traci-guard block into `shared/sumo_bootstrap.py`

**Root cause.** The `candidate_paths` sys.path setup plus the
`try: import traci / except ImportError: raise SystemExit(...)` guard is
copy-pasted near-verbatim across `backend/app/main.py`,
`simulation/sumo_live_bridge.py`, and `services/control_service/main.py`
(and, before item 1's fix, `simulation/sumo_env.py` too). The three copies
have already drifted — `main.py`'s candidate list is missing an
`os.path.dirname(...)` entry the other two have.

**Fix.** New module:

```python
# shared/sumo_bootstrap.py
import os
import sys


def ensure_sumo_on_path(extra_paths: list[str] | None = None) -> None:
    """Put SUMO's tools/ dir and common dist-packages locations on sys.path."""
    candidate_paths = [
        os.path.join(os.environ.get("SUMO_HOME", "/usr/share/sumo"), "tools"),
        "/usr/share/sumo/tools",
        "/usr/lib/python3/dist-packages",
        "/usr/local/share/sumo/tools",
    ]
    if extra_paths:
        candidate_paths.extend(extra_paths)
    for p in candidate_paths:
        if os.path.exists(p) and p not in sys.path:
            sys.path.insert(0, p)
    if "SUMO_HOME" not in os.environ and os.path.exists("/usr/share/sumo"):
        os.environ["SUMO_HOME"] = "/usr/share/sumo"


def require_traci(extra_paths: list[str] | None = None):
    """Import traci or hard-exit with a diagnostic. For process entrypoints
    only (main.py, sumo_live_bridge.py, control_service/main.py) — SN-016's
    three named files. Not for library modules; see sumo_env.py, which
    catches its own ImportError instead (SN-005's graceful-degradation
    contract depends on that)."""
    ensure_sumo_on_path(extra_paths)
    try:
        import traci
        return traci
    except ImportError as exc:
        raise SystemExit(
            "FATAL: 'traci' is not importable from this interpreter.\n"
            f"  interpreter: {sys.executable}\n"
            "  fix: see docs/04-environment-setup.md §2 (SN-013)"
        ) from exc
```

Each of the three entrypoints becomes:

```python
from shared.sumo_bootstrap import require_traci
traci = require_traci(extra_paths=[<file-specific repo-root path>])
```

`simulation/sumo_env.py` uses only `ensure_sumo_on_path()` (no `require_traci`,
per item 1).

**Files.** New `shared/sumo_bootstrap.py`; edits to `backend/app/main.py`,
`simulation/sumo_live_bridge.py`, `services/control_service/main.py`,
`simulation/sumo_env.py`.

**Known trade-off, not fixed here.** `backend/tests/conftest.py` imports
`app.main` unconditionally, so the whole pytest suite still aborts at
collection (not per-test) if `traci` is missing — this is what SN-016's
acceptance text literally asks for ("each process exits"), and after SN-013
`traci` is a pinned, required dependency everywhere. Flagging it so it's a
known, accepted consequence rather than a surprise — not a code change.

**Check.** `grep -rn "candidate_paths = \[" backend/ simulation/ services/`
returns only the one copy inside `shared/sumo_bootstrap.py`. All three
entrypoints still exit loudly with the same message when `traci` is hidden.

---

## 3. Restore the `/health` status string

**Root cause.** `backend/app/api/health.py`'s `/health` (liveness) now
returns `{"status": "ok"}`. `scripts/smoke_check.sh:21` and
`tests/e2e/tier1_features/test_f29_smoke_checks.py:35` both hard-check for
`"healthy"` against this exact endpoint, so both now fail against a
genuinely healthy backend.

**Fix.** Change the liveness handler's literal back to `"healthy"`:

```python
@router.get("/health")
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}
```

Leave `/health/deep`'s `"ok"`/`"degraded"` vocabulary untouched — nothing
depends on a specific string there; `start.sh` reads the `dependencies` map,
not the top-level field.

**Files.** `backend/app/api/health.py`.

**Check.** `curl -s localhost:8000/health | jq -r .status` prints `healthy`.
`bash scripts/smoke_check.sh` and
`test_f29_smoke_checks.py::test_smoke_check_verifies_health_endpoint` pass
against a running backend.

---

## 4. Stop swallowing Alembic migration failures

**Root cause.** `backend/app/database.py`'s `init_db()` wraps
`asyncio.to_thread(run_alembic_migrations)` in `except Exception as e:
logger.info(...)`, which downgrades *any* migration failure — a broken
migration, a DB connectivity blip, or (concretely, since
`backend/Dockerfile` runs `--workers 2`) two workers racing on the same
`alembic upgrade head` — to an INFO log line that guesses "already applied
or handled." `/health/deep`'s postgres check only runs `SELECT 1`, so it
reports `ok` regardless of whether the migration actually succeeded.

**Fix.** Serialize the migration with a Postgres advisory lock so concurrent
workers don't race each other into a spurious error, and let a genuine
failure propagate (fail the worker's startup, as before this diff):

```python
async def init_db() -> None:
    if "sqlite" in settings.DATABASE_URL:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        await _run_migrations_once()
    ...

_MIGRATION_LOCK_KEY = 875_501_001  # arbitrary, unique to this app

async def _run_migrations_once() -> None:
    """Guard alembic upgrade head with a Postgres advisory lock so multiple
    uvicorn workers booting concurrently don't race on the same migration —
    that race was previously masked by swallowing every exception here."""
    async with engine.connect() as conn:
        got_lock = (await conn.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _MIGRATION_LOCK_KEY}
        )).scalar()
        if not got_lock:
            logger.info("Another worker is running migrations; skipping.")
            return
        try:
            await asyncio.to_thread(run_alembic_migrations)
        finally:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": _MIGRATION_LOCK_KEY}
            )
```

No more bare `except Exception` around the migration call — a real failure
now crashes startup, which is the correct, honest behavior `/health/deep`'s
"never assumed" principle depends on.

**Files.** `backend/app/database.py`.

**Check.** Start two backend workers against a fresh DB — only one runs the
migration (log line confirms), and the app boots successfully with no
swallowed exception logged. Deliberately break a migration (e.g., a bogus
`op.execute`) and confirm startup now fails loudly instead of continuing.

---

## 5. Load the lane-area detectors on the REST-driven simulation path

**Root cause, two layers.**

1. `POST /simulation/start` builds `SumoEnvironment(net_file=req.net_file,
   route_file=req.route_file, gui=False)` with no `additional_files`, so
   `corridor.det.xml`'s 16 detectors are never passed to SUMO on this path —
   only `simulation/sumo_live_bridge.py` (which defaults to
   `-c corridor.sumocfg`) loads them. This directly contradicts SN-015's
   acceptance criterion.
2. Underlying that: `net_file`/`route_file` are bare filenames
   (`"corridor.net.xml"`) with **no directory resolution anywhere** in
   `simulation.py` or `sumo_env.py` — `SumoEnvironment.start()` passes them
   to the `sumo` subprocess as-is, relative to the backend process's CWD.
   That CWD is `/app` in the container (`WORKDIR /app` in
   `backend/Dockerfile`), not `/app/simulation/networks`, so this call was
   already broken before this diff (SUMO can't find the file) — Phase 1 just
   didn't touch this endpoint, so nobody noticed. Fixing the detector load
   means fixing path resolution at the same time, since they're the same gap.

**Fix.** Add a small shared path-resolution helper (this also removes the
duplicated candidate-path search in `health.py`, folding in the reuse
finding):

```python
# shared/paths.py
import os
from typing import Iterable, Optional

def find_existing(candidates: Iterable[str]) -> Optional[str]:
    """Return the first path in `candidates` that exists, or None."""
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

def resolve_repo_path(*parts: str) -> Optional[str]:
    """Resolve a path under the repo root, trying the container layout
    (/app/<parts>), a host checkout (repo-root-relative), and CWD-relative,
    in that order."""
    rel = os.path.join(*parts)
    candidates = [
        rel,
        os.path.join(os.getcwd(), rel),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))), rel),  # shared/ -> repo root
        os.path.join("/app", rel),
    ]
    return find_existing(candidates)
```

In `backend/app/api/simulation.py`'s `/start` handler:

```python
from shared.paths import resolve_repo_path

NET_DIR_PARTS = ("simulation", "networks")

net_path = resolve_repo_path(*NET_DIR_PARTS, req.net_file) or req.net_file
route_path = resolve_repo_path(*NET_DIR_PARTS, req.route_file) or req.route_file
det_path = resolve_repo_path(*NET_DIR_PARTS, "corridor.det.xml")

sim_instance = SumoEnvironment(
    net_file=net_path,
    route_file=route_path,
    additional_files=[det_path] if det_path else None,
    gui=False,
)
```

`backend/app/api/health.py`'s `marl_weights`/`forecast_weights` blocks
(currently two hand-rolled 4-candidate loops) become two one-line calls to
`shared.paths.find_existing(...)` with the same candidate list they already
build — pure dedup, no behavior change.

**Files.** New `shared/paths.py`; edits to `backend/app/api/simulation.py`
and `backend/app/api/health.py`.

**Check.** `POST /simulation/start` with defaults actually starts SUMO
(currently it would fail to find `corridor.net.xml` at all — confirm this is
fixed first). Then, with the simulation running, `traci.lanearea.
getJamLengthMeters("det_J0_N_0")` (or the equivalent state-builder call
Phase 2 will use) succeeds instead of raising an "unknown detector" error.

---

## 6. Stop blocking the event loop in `/health/deep`

**Root cause.** The MQTT branch of `health_deep()` (`async def`) falls back
to a plain, synchronous `socket.socket(...).connect(...)` with a 1.0s
timeout — no `await`, no executor offload. Under uvicorn's event loop this
freezes every concurrent request for up to a second, precisely when MQTT is
down (the scenario health checks exist to catch).

**Fix.**

```python
import asyncio

async def _check_mqtt_port(host: str, port: int, timeout: float = 1.0) -> None:
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=timeout
    )
    writer.close()
    await writer.wait_closed()

# in health_deep(), MQTT branch:
try:
    if mqtt_consumer.client and mqtt_consumer.client.is_connected():
        dependencies["mqtt"] = {"status": "ok"}
    else:
        await _check_mqtt_port(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT)
        dependencies["mqtt"] = {"status": "ok"}
except Exception as e:
    dependencies["mqtt"] = {"status": "error", "error": f"mqtt broker unreachable: {e}"}
```

While in this function, also worth doing (same root cause, same file, low
extra cost): run the independent checks (postgres, redis, mqtt) concurrently
via `asyncio.gather` instead of sequential `await`s, since the sumo/
control_service checks already legitimately depend on the redis client
succeeding first.

**Files.** `backend/app/api/health.py`.

**Check.** With mosquitto stopped, fire a burst of concurrent requests
against any other endpoint while polling `/health/deep` — response times for
the other endpoint should no longer show ~1s stalls correlated with the
health poll.

---

## 7. Fix the no-op mosquitto healthcheck

**Root cause.** `test: ["CMD-SHELL", "timeout 2 mosquitto_sub ... || exit
0"]` in both `infra/docker-compose.demo.yml` and `infra/docker-compose.yml`
always exits 0 regardless of whether `mosquitto_sub` succeeded, so
`depends_on: mosquitto: condition: service_healthy` never actually waits for
the broker to be ready.

**Fix.** Drop the `|| exit 0`:

```yaml
healthcheck:
  test: ["CMD-SHELL", "timeout 2 mosquitto_sub -t '$$SYS/broker/version' -C 1"]
  interval: 5s
  timeout: 5s
  retries: 10
  start_period: 5s
```

(`retries`/`start_period` give it room to come up; there's no need for the
unconditional-success escape hatch.)

**Files.** `infra/docker-compose.demo.yml`, `infra/docker-compose.yml`.

**Check.** `docker compose -f infra/docker-compose.demo.yml up -d mosquitto`
then immediately `docker inspect --format '{{.State.Health.Status}}'
surakshanet-mosquitto` in a loop — it should report `starting`/`unhealthy`
until the broker actually accepts the `mosquitto_sub` probe, not `healthy`
on the first check.

---

## 8. Escape the JSON payload spliced into `start.sh`'s Python check

**Root cause.** `start.sh` Step 8 does `json.loads('''$DEEP_HEALTH''')` —
bash-interpolating curl's raw response body directly into a Python
triple-quoted literal with no escaping. Driver error text (asyncpg/
SQLAlchemy) can contain sequences that break the literal, so exactly when a
dependency is failing, the diagnostic step can itself crash with a raw
`SyntaxError` instead of reporting which dependency is down.

**Fix.** Write the JSON to a temp file and let Python read it, instead of
interpolating it into source text:

```bash
DEEP_HEALTH_FILE="$(mktemp)"
trap 'rm -f "$DEEP_HEALTH_FILE"' EXIT
curl -s http://127.0.0.1:8000/health/deep > "$DEEP_HEALTH_FILE" 2>/dev/null || echo '{"status":"error"}' > "$DEEP_HEALTH_FILE"

HEALTH_ERR=$($PYTHON_BIN -c "
import sys, json
try:
    with open('$DEEP_HEALTH_FILE') as f:
        data = json.load(f)
    ...
")
```

(The file *path* — not its contents — is what gets interpolated, and
`mktemp`'s output is a safe, quote-free path.)

**Files.** `start.sh`.

**Check.** Manually craft a `/health/deep`-shaped JSON file whose error
string contains `'''` and a trailing backslash, point the check at it, and
confirm it now parses instead of raising `SyntaxError`.

---

## 9. Add margin to the lane-area detector boundaries

**Root cause.** 10 of 16 `laneAreaDetector` elements in
`simulation/networks/corridor.det.xml` have `pos + length` exactly equal to
the lane's compiled length in `corridor.net.xml` (e.g. `pos="4.60"
length="85.00"` against a lane length of exactly `89.60`). Zero margin means
any future regeneration of the network (different netconvert version,
edited `.nod.xml`/`.edg.xml`) that shifts junction-clipping geometry by even
a sub-centimeter breaks detector loading — a fatal SUMO error that aborts
the whole process.

**Fix.** Shave a fixed safety margin off every detector's `length` (e.g.
0.5 m), recomputed from the current `corridor.net.xml` lane lengths:

```python
# one-off script, not committed — regenerate corridor.det.xml from current
# corridor.net.xml lane lengths with a safety margin
MARGIN = 0.5
# for each <laneAreaDetector lane="X" pos="P">, set length = laneLength(X) - P - MARGIN
```

Re-run whenever `corridor.net.xml` is regenerated, so the margin is derived
from the actual compiled network rather than hand-copied numbers.

**Files.** `simulation/networks/corridor.det.xml`.

**Check.** `sumo -c simulation/networks/corridor.sumocfg --no-step-log
--end 1` (a 1-step dry run) exits 0 with no detector-related fatal error.
Re-run `netconvert` from the `.nod.xml`/`.edg.xml` sources into a scratch
net file and confirm the margin still holds against the freshly compiled
lane lengths.

---

## 10. Verify against a strengthened `check_phase0_regressions.sh`

Once items 1–9 land, add checks to `scripts/check_phase0_regressions.sh`
(it already runs in CI as `phase0-guard`; renaming it is a separate,
optional cleanup) so these ten defects can't silently return:

```bash
check "no SystemExit in sumo_env.py's traci import" \
  bash -c 'grep -n "raise SystemExit" simulation/sumo_env.py'

check "no duplicated traci candidate_paths outside shared/" \
  bash -c 'grep -rln "candidate_paths = \[" backend/ simulation/ services/ | grep -v shared/'

check "/health returns healthy, not ok" \
  bash -c '! grep -q "\"status\": \"healthy\"" backend/app/api/health.py && echo "FAIL"'

check "no bare except Exception around alembic migration" \
  bash -c 'grep -n "except Exception as e:" backend/app/database.py | grep -v pg_advisory'

check "simulation start passes additional_files" \
  bash -c 'grep -n "additional_files" backend/app/api/simulation.py'

check "no blocking socket.connect in health_deep" \
  bash -c 'grep -n "s.connect(" backend/app/api/health.py'

check "no unconditional exit 0 in mosquitto healthcheck" \
  bash -c 'grep -n "mosquitto_sub.*exit 0" infra/docker-compose*.yml'

check "start.sh does not splice JSON into a python literal" \
  bash -c 'grep -n "json.loads(.\x27\x27\x27\\\$DEEP_HEALTH" start.sh'
```

(Exact grep syntax to be finalized when each fix lands — the intent is one
guard per finding, same pattern as the Phase 0 guard.)

---

## Summary table

| # | Finding | Files | Depends on |
|---|---|---|---|
| 1 | `SystemExit` breaks SN-005 fallback | `simulation/sumo_env.py` | — |
| 2 | Traci-guard duplicated 4×| `shared/sumo_bootstrap.py` (new), `main.py`, `sumo_live_bridge.py`, `control_service/main.py`, `sumo_env.py` | 1 |
| 3 | `/health` status string regression | `backend/app/api/health.py` | — |
| 4 | Alembic failures swallowed | `backend/app/database.py` | — |
| 5 | SN-015 detectors unreachable via REST | `shared/paths.py` (new), `backend/app/api/simulation.py`, `backend/app/api/health.py` | — |
| 6 | Blocking socket in async health check | `backend/app/api/health.py` | — |
| 7 | Mosquitto healthcheck no-op | `infra/docker-compose*.yml` | — |
| 8 | Unescaped JSON in start.sh | `start.sh` | — |
| 9 | Zero-margin detector boundaries | `simulation/networks/corridor.det.xml` | — |
| 10 | Regression guard | `scripts/check_phase0_regressions.sh` | 1–9 |

Items 3, 4, 6, 7, 8, 9 are independent — any order, any subset can be
parallelized. Item 5 should land before any Phase 2 work touches the DQN
state builder. Item 2 depends on item 1 (fix the exception type before
extracting the shared helper, so the helper's `require_traci()` docstring is
accurate about what it's for).
