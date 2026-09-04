#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET_ENV="${ROOT_DIR}/.env.production"

echo "=== Generating Production Environment Secrets in ${TARGET_ENV} ==="

JWT_SECRET=$(openssl rand -hex 32)
POSTGRES_PWD=$(openssl rand -hex 16)
TIMESCALEDB_PWD=$(openssl rand -hex 16)

cat <<EOF > "${TARGET_ENV}"
# =================================================================
# Surakshanet Intelligent Transportation System - Production Environment
# Generated automatically: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# =================================================================

# Security & Authentication
ENVIRONMENT=production
DEBUG=false
JWT_SECRET_KEY=${JWT_SECRET}
ACCESS_TOKEN_EXPIRE_MINUTES=480

# PostgreSQL / PostGIS
POSTGRES_USER=surakshanet
POSTGRES_PASSWORD=${POSTGRES_PWD}
POSTGRES_DB=surakshanet
DATABASE_URL=postgresql+asyncpg://surakshanet:${POSTGRES_PWD}@postgres:5432/surakshanet

# TimescaleDB (Time-series Traffic Telemetry)
TIMESCALE_USER=surakshanet
TIMESCALE_PASSWORD=${TIMESCALEDB_PWD}
TIMESCALE_DB=surakshanet
TIMESCALE_URL=postgresql+asyncpg://surakshanet:${TIMESCALEDB_PWD}@timescaledb:5432/surakshanet

# Redis Pub/Sub & Caching
REDIS_URL=redis://redis:6379/0

# MQTT Broker (IoT Sensors & Edge Signal Cabinets)
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883

# Web Server Configuration
HOST=0.0.0.0
PORT=8000
WORKERS=2
EOF

chmod 600 "${TARGET_ENV}"
echo "✅ Production environment secrets generated: ${TARGET_ENV}"
