#!/usr/bin/env bash
#
# SN-140 — Phase 0 regression guard.
#
# Phase 0 removed every code path that fabricated data and served it through
# the same shape as a real measurement. Those deletions must still hold after
# the remaining phases of change, so this script is run in CI and any hit
# fails the build.
#
# Source of truth: docs/23-final-acceptance.md §3, extended with the four
# fabrication paths that section's greps did not cover.

set -uo pipefail
cd "$(dirname "$0")/.."

failed=0

# check <description> <command...>
# Fails when the command produces output. Inverted grep semantics: a hit is bad.
check() {
  local desc="$1"; shift
  local out
  out="$("$@" 2>/dev/null)"
  if [ -n "$out" ]; then
    echo "FAIL  $desc"
    echo "$out" | sed 's/^/        /'
    failed=1
  else
    echo "ok    $desc"
  fi
}

# warn <description> <command...>
# Same inverted semantics as check, but reports without failing the build.
warn() {
  local desc="$1"; shift
  local out
  out="$("$@" 2>/dev/null)"
  if [ -n "$out" ]; then
    echo "WARN  $desc ($(echo "$out" | wc -l | tr -d ' ') hits, non-blocking until Phase 8)"
    echo "$out" | sed 's/^/        /'
  else
    echo "ok    $desc"
  fi
}

echo "Phase 0 regression guard (SN-140)"
echo

# --- docs/23-final-acceptance.md §3 -----------------------------------------

check "SN-001 no fabricated training metrics" \
  grep -n "420\|14\.2\|11\.8\|22\.4" backend/app/api/ml.py

check "SN-002 no hardcoded AI narration" \
  grep -rnI --exclude-dir=.git --exclude-dir=docs --exclude-dir=scripts \
  --exclude-dir=graphify-out --exclude-dir=.claude --exclude-dir=__pycache__ --exclude-dir=.mypy_cache \
  "MARL Green Extension" .

check "SN-005 no MicroSimRunner" \
  grep -rn "MicroSimRunner" backend/

check "no mock plan restore" \
  grep -rn "mock_plan" ml/ backend/

# The §3 grep is literally `grep -rn "DEL-CP-01" backend/`, which also hits the
# routing topology table and test fixtures — legitimate seed data, not
# fabrication. The defect it exists for is an *assumed* emergency route: a
# fallback corridor that pre-empts live signals nobody asked for.
check "no assumed emergency route" \
  bash -c 'grep -rn "DEL-CP-01" backend/app/api/emergency.py'

check "SN-010 no hardcoded VMS content" \
  grep -rn "ACCIDENT CLEARED" backend/ frontend/

# Studio/ is frozen decorative 3D and is excluded by the specification.
# websocket.ts uses Math.random for reconnect backoff jitter, which is not
# data fabrication.
check "SN-004 no client-side data fabrication" \
  bash -c 'grep -rn "Math.random" frontend/dashboard/src --include=*.tsx --include=*.ts \
    | grep -v "components/Studio/" \
    | grep -v "services/websocket.ts"'

check "no decorative length assertions in tests" \
  grep -rn 'assert len("' tests/

# An assertion mixing one 2xx code with one 4xx/5xx code passes whether or
# not the feature actually works, so it tests nothing. Originally just
# "(200, 401)" (auth), but the identical anti-pattern resurfaced later as
# "(200, 429)" (rate limiting): a 429 proves nothing about whether the
# endpoint is genuinely public, so a broken-but-always-rate-limited endpoint
# would pass identically to a working one. Generalized to any 2xx paired
# with any 4xx/5xx in one status_code tuple — deliberately narrower than
# "any second number", since e.g. "(200, 201)" or "(200, 204)" pairs two
# legitimately-ambiguous *success* codes and is not this anti-pattern.
check "no decorative status-code assertions in tests" \
  grep -rnE "status_code in \(200, ?[45][0-9]{2}\)" tests/

# --- Gaps found after Phase 0 was declared complete -------------------------

# The MQTT consumer ran a 5-second ticker that invented pcu/speed/queue with
# random.uniform and published it to traffic_updates as live telemetry — the
# same defect class as MicroSimRunner, in a file the original greps missed.
check "no fabricated telemetry in the MQTT consumer" \
  grep -n "random\." backend/app/services/mqtt_consumer.py

# SN-008 made DataSource canonical. The legacy vocabulary is not a member of
# the enum and would fail the traffic_readings.source CHECK constraint.
check "no legacy source vocabulary in the backend" \
  bash -c "grep -rn \"'live'\|\\\"live\\\"\|'mock'\|\\\"mock\\\"\" backend/app/services/mqtt_consumer.py backend/app/schemas/traffic.py backend/app/models/traffic.py"

# The vision worker derived avg_speed from PCU with a random jitter — the same
# formula as the deleted MQTT ticker — and published it under source "vision".
# A detector measures counts, not speed.
check "no derived speed in the vision worker" \
  grep -n "np.random\|avg_speed.*pcu\|52\.0 -" ml/vision/rtsp_stream_worker.py

# Phase 5's services/vision_worker/main.py once defaulted an approach's
# mean_speed_kmh to a plausible-looking 0.0 whenever no track had a
# resolvable speed this window (uncalibrated camera, or simply no track with
# 2+ position samples yet) — indistinguishable from a genuine "traffic
# stopped" reading, and broadcast raw to every /ws/traffic client and into
# the control-service state vector. SN-072's own acceptance line is "mean
# speed (calibrated; null when uncalibrated)".
check "no fabricated 0.0 default for unresolved vision speed" \
  grep -n "else (0\.0 if camera\.mpp is None else 0\.0)" services/vision_worker/main.py

# Phase 7's require_role() guard was once applied to POST /auth/register
# itself, meaning no one — not even the first non-seeded user — could ever
# register (a require_role dependency requires an already-authenticated
# caller of that role, and there is no way to become authenticated before
# registering). Invariant §13.4 / docs/16-rbac.md §2: registration is PUB,
# and always forces OPERATOR server-side regardless of any client-submitted
# role — never gated behind an existing account.
check "auth/register does not require an existing account to reach it" \
  grep -n 'current_user: User = Depends(require_role' backend/app/api/auth.py

# A self-registering caller must never be able to choose their own role —
# register_user() previously read UserCreate.role straight off the request
# body, letting any anonymous caller submit role: ADMIN and get it.
check "register_user() does not trust a client-submitted role" \
  grep -n 'role = getattr(user_data, "role"' backend/app/services/auth_service.py

# Unreported fields must persist as null, never as a plausible-looking default.
check "no invented defaults on the ingest path" \
  bash -c 'grep -n "data.get(.*, *[0-9]" backend/app/services/mqtt_consumer.py | grep -v "^[0-9]*: *#"' 

# SN-004's five hardcoded boxes at 88-96% confidence also lived server-side in
# VehicleDetector._simulated_detections, returned whenever ultralytics was
# missing or inference raised. Absence of a detection is reported, not filled in.
check "no synthesised detections in the detector" \
  bash -c 'grep -n "_simulated_detections\|0\.94\|0\.96\|0\.88\|0\.91" ml/vision/vehicle_detector.py'

# Generated series plotted as measured history. The frontend check above only
# catches Math.random; SimulationPage used Math.sin for a throughput curve and
# SignalControlPage for a MARL reward curve.
check "no generated series in dashboard charts" \
  bash -c 'grep -rn "Math\.\(sin\|cos\)(" frontend/dashboard/src --include=*.tsx \
    | grep -v "components/Studio/"'

# Headline result claims that no run produced.
check "no fabricated result claims in the UI" \
  bash -c 'grep -rn "24\.5%\|39\.4%\|73\.6%\|54\.2%\|96\.4%\|99\.2%\|1,492\|1,248" \
    frontend/dashboard/src --include=*.tsx | grep -v "previously read\|previously rendered\|previously seeded\|previously carried"'

# Credentials must come from the environment, never from a committed default.
check "no committed admin credentials" \
  bash -c 'grep -rn "Alok@2005\|aloks92440" backend/scripts/ tests/e2e/conftest.py'

# A missing or unrecognised source must render UNAVAILABLE. Defaulting it to a
# measured badge asserts the strongest claim on the weakest evidence.
check "SN-009 provenance badge does not default to a measured source" \
  bash -c "grep -n \"source = 'mqtt'\|config\\[normSource\\] || config\\.\" \
    frontend/dashboard/src/components/TelemetrySourceBadge.tsx"

# --- Phase 1 remediation guards --------------------------------------------

check "no SystemExit in sumo_env.py's traci import" \
  bash -c 'grep -n "raise SystemExit" simulation/sumo_env.py'

check "no duplicated traci candidate_paths outside shared/" \
  bash -c 'grep -rln "candidate_paths = \[" backend/ simulation/ services/ | grep -v shared/'

check "/health returns healthy, not ok" \
  bash -c '! grep -q "\"status\": \"healthy\"" backend/app/api/health.py && echo "FAIL"'

check "no bare except Exception around alembic migration" \
  bash -c 'grep -A 5 -B 5 "run_alembic_migrations" backend/app/database.py | grep "except Exception"'

check "simulation start passes additional_files" \
  bash -c '! grep -q "additional_files" backend/app/api/simulation.py && echo "FAIL"'

check "no blocking socket.connect in health_deep" \
  bash -c 'grep -n "s\.connect(" backend/app/api/health.py'

check "no unconditional exit 0 in mosquitto healthcheck" \
  bash -c 'grep -n "mosquitto_sub.*exit 0" infra/docker-compose*.yml'

check "start.sh does not splice JSON into a python literal" \
  bash -c 'grep -n "json.loads(.\x27\x27\x27\\\$DEEP_HEALTH" start.sh'

echo
if [ "$failed" -ne 0 ]; then
  echo "Phase 0/1 regression detected. See docs/23-final-acceptance.md §3."
  exit 1
fi
echo "All Phase 0 and Phase 1 guards pass."
