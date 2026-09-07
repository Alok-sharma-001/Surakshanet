#!/usr/bin/env bash
# ==============================================================================
# SurakshaNet Production Secret Generator & Mosquitto Auth Provisioner
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET_ENV="${ROOT_DIR}/.env.production"
MOSQUITTO_DIR="${ROOT_DIR}/infra/mosquitto"
PASSWORD_FILE="${MOSQUITTO_DIR}/password_file"

echo "=== Generating Production Environment Secrets ==="

JWT_SECRET=$(openssl rand -hex 32)
POSTGRES_PWD=$(openssl rand -hex 16)
REDIS_PWD=$(openssl rand -hex 16)
MQTT_USER="surakshanet_operator"
MQTT_PWD=$(openssl rand -hex 16)
ADMIN_PWD=$(openssl rand -base64 16 | tr -dc 'A-Za-z0-9!@#%^&*' | head -c 16)

# 1. Generate .env.production
cat <<EOF > "${TARGET_ENV}"
# ==============================================================================
# Surakshanet Intelligent Transportation System - Production Secrets
# Generated automatically: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# ==============================================================================

# Application & Environment
ENVIRONMENT=production
DEBUG=false
APP_NAME=Surakshanet
APP_VERSION=1.0.0
CORS_ORIGINS=https://localhost,https://127.0.0.1

# Security & Authentication
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Initial Production Administrator
ADMIN_EMAIL=admin@surakshanet.local
ADMIN_PASSWORD=${ADMIN_PWD}

# Unified TimescaleDB (PostGIS Topology + Hypertable Telemetry)
POSTGRES_USER=surakshanet
POSTGRES_PASSWORD=${POSTGRES_PWD}
POSTGRES_DB=surakshanet
DATABASE_URL=postgresql+asyncpg://surakshanet:${POSTGRES_PWD}@timescaledb:5432/surakshanet

# Redis Pub/Sub & Token Denylist
REDIS_PASSWORD=${REDIS_PWD}
REDIS_URL=redis://:${REDIS_PWD}@redis:6379/0

# MQTT Broker (Edge Sensors, Cameras & Signal Controllers)
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
MQTT_USERNAME=${MQTT_USER}
MQTT_PASSWORD=${MQTT_PWD}

# Web Server Runtime
HOST=0.0.0.0
PORT=8000
WORKERS=2
EOF

chmod 600 "${TARGET_ENV}"
echo "✅ Production environment secrets written to: ${TARGET_ENV}"

# 2. Generate Mosquitto password_file
echo "=== Provisioning Mosquitto MQTT Password File ==="
mkdir -p "${MOSQUITTO_DIR}"

if command -v mosquitto_passwd >/dev/null 2>&1; then
    mosquitto_passwd -b -c "${PASSWORD_FILE}" "${MQTT_USER}" "${MQTT_PWD}"
    chmod 600 "${PASSWORD_FILE}"
    echo "✅ Mosquitto password_file generated locally: ${PASSWORD_FILE}"
elif command -v docker >/dev/null 2>&1; then
    docker run --rm -v "${MOSQUITTO_DIR}:/mosquitto/config" eclipse-mosquitto:2 \
        mosquitto_passwd -b -c /mosquitto/config/password_file "${MQTT_USER}" "${MQTT_PWD}" >/dev/null 2>&1 || true
    chmod 600 "${PASSWORD_FILE}" 2>/dev/null || true
    echo "✅ Mosquitto password_file generated via container: ${PASSWORD_FILE}"
fi

echo ""
echo "=== Secret Generation Complete ==="
echo "Admin Email:    admin@surakshanet.local"
echo "Admin Password: ${ADMIN_PWD}"
echo "MQTT Username:  ${MQTT_USER}"
echo "MQTT Password:  ${MQTT_PWD}"
echo "Redis Password: ${REDIS_PWD}"
echo "DB Password:    ${POSTGRES_PWD}"
