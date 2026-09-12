#!/usr/bin/env bash
# ==============================================================================
# SurakshaNet Orchestrated Startup Script (SN-018)
# Conforms to docs/04-environment-setup.md §5 and docs/21-deployment.md §3
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PROFILE="demo"
NO_FRONTEND=false
FOREGROUND=false
DEMO_SEED=42
STEP_TIMEOUT=90

# Ensure localhost and 127.0.0.1 bypass proxy
export no_proxy="localhost,127.0.0.1,0.0.0.0,${no_proxy:-}"
export NO_PROXY="localhost,127.0.0.1,0.0.0.0,${NO_PROXY:-}"

# Parse CLI flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --no-frontend)
            NO_FRONTEND=true
            shift
            ;;
        --foreground|-f)
            FOREGROUND=true
            shift
            ;;
        --seed)
            DEMO_SEED="$2"
            shift 2
            ;;
        --timeout)
            STEP_TIMEOUT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: ./start.sh [--profile demo|dev] [--no-frontend] [--seed 42] [--timeout 90]" >&2
            exit 1
            ;;
    esac
done

# Initialize logging
mkdir -p logs
LOGFILE="logs/startup-$(date +%s).log"
exec > >(tee -a "$LOGFILE") 2>&1

COMPOSE_FILE="infra/docker-compose.demo.yml"
if [[ "$PROFILE" == "dev" ]]; then
    COMPOSE_FILE="infra/docker-compose.yml"
fi

# Detect Python interpreter (prefer virtualenv unless overridden)
if [[ -z "${PYTHON_BIN:-}" ]]; then
    PYTHON_BIN="python3"
    if [[ -f ".venv/bin/python3" ]]; then
        PYTHON_BIN=".venv/bin/python3"
    fi
fi

report_failure() {
    local step_num="$1"
    local step_name="$2"
    local cause="$3"
    local detail="$4"
    local fix="$5"
    echo ""
    printf "[%s/10] %-30s FAILED\n" "$step_num" "$step_name"
    printf "       cause:  %s\n" "$cause"
    printf "       detail: %s\n" "$detail"
    printf "       fix:    %s\n" "$fix"
    exit 1
}

report_step() {
    local step_num="$1"
    local step_name="$2"
    printf "[%s/10] %-30s ... " "$step_num" "$step_name"
}

report_step_ok() {
    echo "OK"
}

# ==============================================================================
# Step 1: Check dependencies
# ==============================================================================
report_step "1" "Check dependencies"

if ! command -v docker >/dev/null 2>&1; then
    report_failure "1" "Check dependencies" "docker not found in PATH" "Docker engine is required" "docs/04-environment-setup.md §1"
fi

if ! $PYTHON_BIN --version >/dev/null 2>&1; then
    report_failure "1" "Check dependencies" "python interpreter not found" "Python 3.11+ is required" "docs/04-environment-setup.md §1"
fi

if ! command -v node >/dev/null 2>&1; then
    report_failure "1" "Check dependencies" "node not found in PATH" "Node.js 20 LTS is required" "docs/04-environment-setup.md §1"
fi

if ! command -v sumo >/dev/null 2>&1; then
    report_failure "1" "Check dependencies" "sumo binary not found" "Eclipse SUMO 1.19+ required at /usr/bin/sumo" "docs/04-environment-setup.md §1"
fi

if ! $PYTHON_BIN -c "import traci" >/dev/null 2>&1; then
    report_failure "1" "Check dependencies" "traci import failed" "$($PYTHON_BIN -c "import sys; print(sys.executable)") cannot import traci" "docs/04-environment-setup.md §2 (SN-013)"
fi

if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
    else
        report_failure "1" "Check dependencies" ".env file missing" "No .env or .env.example in repository root" "docs/04-environment-setup.md §1"
    fi
fi
report_step_ok

# ==============================================================================
# Step 2: Start infrastructure
# ==============================================================================
report_step "2" "Start infrastructure"

OUTPUT=$(docker compose -f "$COMPOSE_FILE" up -d timescaledb redis mosquitto prometheus grafana 2>&1) || {
    report_failure "2" "Start infrastructure" "docker compose up failed" "$OUTPUT" "docs/04-environment-setup.md §7"
}
report_step_ok

# ==============================================================================
# Step 3: Wait for health
# ==============================================================================
report_step "3" "Wait for health"

CONTAINERS=("surakshanet-timescaledb" "surakshanet-redis" "surakshanet-mosquitto")
for c in "${CONTAINERS[@]}"; do
    elapsed=0
    until [[ "$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null)" == "healthy" ]]; do
        if [[ $elapsed -ge ${STEP_TIMEOUT:-60} ]]; then
            report_failure "3" "Wait for health" "container $c timed out waiting for healthy state" "inspect logs with: docker logs $c" "docs/04-environment-setup.md §7"
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
done
report_step_ok

# ==============================================================================
# Step 4: Start backend
# ==============================================================================
report_step "4" "Start backend"

# Up backend container with volume mounts
docker compose -f "$COMPOSE_FILE" up -d backend >/dev/null 2>&1 || {
    report_failure "4" "Start backend" "failed to start backend container" "check docker compose logs backend" "docs/04-environment-setup.md §7"
}

# Run database migrations
docker exec surakshanet-backend alembic upgrade head >/dev/null 2>&1 || {
    report_failure "4" "Start backend" "alembic upgrade head exited with non-zero status" "database migration failed" "docs/04-environment-setup.md §7"
}

# Wait for /health
elapsed=0
until curl -s -f http://127.0.0.1:8000/health >/dev/null 2>&1; do
    if [[ $elapsed -ge ${STEP_TIMEOUT:-60} ]]; then
        report_failure "4" "Start backend" "backend /health endpoint unreachable after 60s" "connection refused or 5xx from http://127.0.0.1:8000/health" "docs/04-environment-setup.md §7"
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done
report_step_ok

# ==============================================================================
# Step 5: Start SUMO bridge
# ==============================================================================
report_step "5" "Start SUMO bridge"

# Stop existing bridge if running
if [[ -f "logs/sumo_bridge.pid" ]]; then
    kill -TERM "$(cat logs/sumo_bridge.pid)" 2>/dev/null || true
    rm -f logs/sumo_bridge.pid
fi

# The bridge runs as a bare host process (not inside the docker-compose
# network), but simulation/sumo_live_bridge.py::_build_db_dsn() defaults to
# POSTGRES_HOST=postgres/PORT=5432 — the in-Docker service hostname/port,
# which never resolves from the host. .env carries that same in-Docker
# value and is never sourced into this script's environment, so the bridge
# always fell through to the unreachable default. Confirmed live
# (2026-09-12): a real corridor activation completed correctly per the
# bridge's own log ("all junctions restored and verified", a real recovery
# figure measured) while its emergency_events row stayed ACTIVE forever —
# every UPDATE the bridge issued was silently failing to connect. Export
# the real host-mapped values (this demo profile's timescaledb container
# publishes 127.0.0.1:5433) so the bridge's direct DB writes (captured
# programs, restore verification, recovery_s) actually reach Postgres.
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5433
export POSTGRES_USER=surakshanet
export POSTGRES_PASSWORD=surakshanet_dev
export POSTGRES_DB=surakshanet

nohup $PYTHON_BIN simulation/sumo_live_bridge.py --seed "$DEMO_SEED" --no-gui >> logs/sumo_bridge.log 2>&1 &
echo $! > logs/sumo_bridge.pid
disown $! 2>/dev/null || true
sleep 2

if ! kill -0 "$(cat logs/sumo_bridge.pid)" 2>/dev/null; then
    report_failure "5" "Start SUMO bridge" "sumo_live_bridge exited immediately" "inspect logs/sumo_bridge.log" "docs/04-environment-setup.md §2"
fi
report_step_ok

# ==============================================================================
# Step 6: Start control service
# ==============================================================================
report_step "6" "Start control service"

# Stop existing control service if running
if [[ -f "logs/control_service.pid" ]]; then
    kill -TERM "$(cat logs/control_service.pid)" 2>/dev/null || true
    rm -f logs/control_service.pid
fi

nohup $PYTHON_BIN services/control_service/main.py >> logs/control_service.log 2>&1 &
echo $! > logs/control_service.pid
disown $! 2>/dev/null || true
sleep 2

if ! kill -0 "$(cat logs/control_service.pid)" 2>/dev/null; then
    report_failure "6" "Start control service" "control_service exited immediately" "inspect logs/control_service.log" "docs/04-environment-setup.md §2"
fi
report_step_ok

# ==============================================================================
# Step 7: Start frontend
# ==============================================================================
report_step "7" "Start frontend"

if [[ "$NO_FRONTEND" == "true" ]]; then
    echo "SKIPPED (--no-frontend)"
else
    if curl -s http://127.0.0.1:5173 >/dev/null 2>&1; then
        echo "ALREADY RUNNING"
    else
        # Stop existing frontend if tracked
        if [[ -f "logs/frontend.pid" ]]; then
            kill -TERM "$(cat logs/frontend.pid)" 2>/dev/null || true
            rm -f logs/frontend.pid
        fi
        (cd frontend/dashboard && nohup npm run dev -- --host 0.0.0.0 --port 5173 >> "$SCRIPT_DIR/logs/frontend.log" 2>&1 & echo $! > "$SCRIPT_DIR/logs/frontend.pid" && disown $! 2>/dev/null || true)

        elapsed=0
        until curl -s http://127.0.0.1:5173 >/dev/null 2>&1; do
            if [[ $elapsed -ge ${STEP_TIMEOUT:-30} ]]; then
                report_failure "7" "Start frontend" "vite dev server timed out" "check logs/frontend.log" "docs/04-environment-setup.md §5"
            fi
            sleep 1
            elapsed=$((elapsed + 1))
        done
        report_step_ok
    fi
fi

# ==============================================================================
# Step 8: Verify all services
# ==============================================================================
report_step "8" "Verify all services"

DEEP_HEALTH_FILE="$(mktemp)"
all_ok=false
HEALTH_ERR=""

for i in $(seq 1 ${STEP_TIMEOUT:-15}); do
    curl -s http://127.0.0.1:8000/health/deep > "$DEEP_HEALTH_FILE" 2>/dev/null || echo '{"status":"error"}' > "$DEEP_HEALTH_FILE"
    if [[ -s "$DEEP_HEALTH_FILE" ]] && ! grep -q '{"status":"error"}' "$DEEP_HEALTH_FILE"; then
        HEALTH_ERR=$($PYTHON_BIN -c "
import sys, json
try:
    with open('$DEEP_HEALTH_FILE') as f:
        data = json.load(f)
    deps = data.get('dependencies', {})
    required = ['postgres', 'redis', 'mqtt', 'sumo', 'traci', 'control_service', 'marl_weights', 'forecast_weights']
    for req in required:
        info = deps.get(req, {})
        status = info.get('status')
        if status != 'ok':
            reason = info.get('reason') or info.get('error') or f'status is {status}'
            print(f'dependency {req} is not ok: {reason}')
            sys.exit(1)
except Exception as e:
    print(f'Failed to parse /health/deep response: {e}')
    sys.exit(1)
" 2>&1)
        if [[ $? -eq 0 ]]; then
            all_ok=true
            break
        fi
    fi
    sleep 1
done

if [[ "$all_ok" != "true" ]]; then
    rm -f "$DEEP_HEALTH_FILE"
    report_failure "8" "Verify all services" "one or more services unhealthy in /health/deep" "$HEALTH_ERR" "docs/04-environment-setup.md §6"
fi
rm -f "$DEEP_HEALTH_FILE"
report_step_ok

# ==============================================================================
# Step 9: Print URLs
# ==============================================================================
echo ""
echo "SurakshaNet is up."
echo "  Operator dashboard  http://localhost:5173/app"
echo "  Citizen view        http://localhost:5173/public"
echo "  API docs            http://localhost:8000/docs"
echo "  Grafana             http://localhost:3001"
echo "  Seed                $DEMO_SEED  (deterministic)"
echo ""

# ==============================================================================
# Step 10: Exit or keep running
# ==============================================================================
if [[ "$FOREGROUND" == "true" ]]; then
    echo "SurakshaNet running in foreground mode. Monitoring services..."
    trap './stop.sh; exit 0' SIGINT SIGTERM
    while true; do
        sleep 5
    done
fi

exit 0
