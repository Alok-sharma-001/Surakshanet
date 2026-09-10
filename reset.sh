#!/usr/bin/env bash
# ==============================================================================
# SurakshaNet Reset Script (SN-021)
# Drops & recreates database, clears Redis state, re-seeds, restores to step 0.
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Resetting SurakshaNet to clean initial demo state..."

# 1. Graceful stop of running services
./stop.sh || true

# 2. Ensure infrastructure containers are running
echo "Starting clean infrastructure containers..."
docker compose -f infra/docker-compose.demo.yml up -d timescaledb redis mosquitto

# 3. Wait for database and redis readiness
echo "Waiting for database readiness..."
elapsed=0
until [[ "$(docker inspect --format '{{.State.Health.Status}}' surakshanet-timescaledb 2>/dev/null)" == "healthy" ]]; do
    if [[ $elapsed -ge 60 ]]; then
        echo "TimescaleDB failed to become ready." >&2
        exit 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done

# 4. Drop and recreate database
echo "Re-creating database surakshanet..."
docker exec -i surakshanet-timescaledb psql -U surakshanet -d postgres -c "DROP DATABASE IF EXISTS surakshanet;" >/dev/null
docker exec -i surakshanet-timescaledb psql -U surakshanet -d postgres -c "CREATE DATABASE surakshanet;" >/dev/null
docker exec -i surakshanet-timescaledb psql -U surakshanet -d surakshanet -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" >/dev/null
docker exec -i surakshanet-timescaledb psql -U surakshanet -d surakshanet -c "CREATE EXTENSION IF NOT EXISTS postgis CASCADE;" >/dev/null

# 5. Flush Redis
echo "Flushing Redis state..."
docker exec -i surakshanet-redis redis-cli FLUSHALL >/dev/null

# 6. Run database migrations via backend
echo "Running Alembic migrations..."
docker compose -f infra/docker-compose.demo.yml up -d backend
docker exec surakshanet-backend alembic upgrade head

# 7. Seed admin and city baseline
echo "Seeding initial admin and city topology..."
docker exec surakshanet-backend python scripts/seed_admin.py || true
docker exec surakshanet-backend python scripts/seed_city.py || true

# 8. Clean up logs and reset state
rm -f logs/*.pid
echo "0" > /tmp/surakshanet_sumo_step 2>/dev/null || true

echo ""
echo "Reset complete. System restored to initial step 0 state."
echo "You can now run ./start.sh"
