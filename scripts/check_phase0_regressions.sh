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
  grep -rn --exclude-dir=.git --exclude-dir=docs --exclude-dir=scripts \
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

# Non-blocking until Phase 8. Rewriting these needs each test's real intent;
# see SN-111…SN-126. They must be zero before SN-140 sign-off.
warn "no decorative length assertions in tests" \
  grep -rn 'assert len("' tests/

warn "no decorative status-code assertions in tests" \
  grep -rn "status_code in (200, 401)" tests/

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

# A missing or unrecognised source must render UNAVAILABLE. Defaulting it to a
# measured badge asserts the strongest claim on the weakest evidence.
check "SN-009 provenance badge does not default to a measured source" \
  bash -c "grep -n \"source = 'mqtt'\|config\\[normSource\\] || config\\.\" \
    frontend/dashboard/src/components/TelemetrySourceBadge.tsx"

echo
if [ "$failed" -ne 0 ]; then
  echo "Phase 0 regression detected. See docs/23-final-acceptance.md §3."
  exit 1
fi
echo "All Phase 0 deletions hold."
