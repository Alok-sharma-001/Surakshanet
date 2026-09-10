#!/usr/bin/env bash
# ==============================================================================
# SurakshaNet Graceful Stop Script (SN-021)
# Shuts down processes and containers in reverse dependency order.
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping SurakshaNet services..."

# 1. Stop Frontend
if [[ -f "logs/frontend.pid" ]]; then
    PID="$(cat logs/frontend.pid 2>/dev/null || true)"
    if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
        echo "Stopping frontend (PID: $PID)..."
        kill -TERM "$PID" 2>/dev/null || true
    fi
    rm -f logs/frontend.pid
fi
pkill -f "vite.*5173" 2>/dev/null || true

# 2. Stop Control Service
if [[ -f "logs/control_service.pid" ]]; then
    PID="$(cat logs/control_service.pid 2>/dev/null || true)"
    if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
        echo "Stopping control service (PID: $PID)..."
        kill -TERM "$PID" 2>/dev/null || true
    fi
    rm -f logs/control_service.pid
fi
pkill -f "services/control_service/main.py" 2>/dev/null || true

# 3. Stop SUMO Live Bridge (graceful release of junctions)
if [[ -f "logs/sumo_bridge.pid" ]]; then
    PID="$(cat logs/sumo_bridge.pid 2>/dev/null || true)"
    if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
        echo "Stopping SUMO live bridge (PID: $PID)..."
        kill -TERM "$PID" 2>/dev/null || true
    fi
    rm -f logs/sumo_bridge.pid
fi
pkill -f "simulation/sumo_live_bridge.py" 2>/dev/null || true
pkill -f "sumo" 2>/dev/null || true

# 4. Stop Backend & Infrastructure Containers
if command -v docker >/dev/null 2>&1; then
    echo "Stopping infrastructure containers..."
    docker compose -f infra/docker-compose.demo.yml stop >/dev/null 2>&1 || true
fi

echo "SurakshaNet stopped successfully."
