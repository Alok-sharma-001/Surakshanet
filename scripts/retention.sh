#!/usr/bin/env bash
# ==============================================================================
# SurakshaNet Data Retention & Automated Purge Utility (SN-108)
# ==============================================================================
# Applies data retention schedules per docs/17-security-privacy.md §4:
# 1. Raw / blurred video frames: 72 hours (operational need only)
# 2. cv_detections: 72 hours (operational need only)
# 3. control_decisions: 90 days (model behaviour audit)
# 4. behavior_flags (DISMISSED): 90 days (do not retain disproven suspicion)
# 5. traffic_readings: 365 days (trend analysis, no personal data)
# 6. audit_logs: 365 days (governance & compliance)
#
# Usage:
#   ./scripts/retention.sh [--dry-run]
# ==============================================================================

set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
    if [[ "$arg" == "--dry-run" || "$arg" == "-n" ]]; then
        DRY_RUN=true
    fi
done

echo "=================================================================="
echo "SurakshaNet Automated Data Retention Policy Enforcer (SN-108)"
echo "Mode: $(if [ "$DRY_RUN" = true ]; then echo 'DRY-RUN (Simulated)'; else echo 'ACTIVE PURGE'; fi)"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "=================================================================="

# 1. Purge disk-cached video frames & snapshots older than 72 hours (3 days)
FRAME_DIRS=("frames/blurred" "frames/raw" "frames" "/tmp/surakshanet/frames")
echo ""
echo "[1/2] Checking cached video frames older than 72 hours..."

for dir in "${FRAME_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        if [ "$DRY_RUN" = true ]; then
            OLD_COUNT=$(find "$dir" -type f -mtime +3 2>/dev/null | wc -l || echo 0)
            echo "  - [DRY-RUN] Found ${OLD_COUNT} files in ${dir} older than 72h"
        else
            DELETED=$(find "$dir" -type f -mtime +3 -delete -print 2>/dev/null | wc -l || echo 0)
            echo "  - Purged ${DELETED} stale frame(s) from ${dir}"
        fi
    fi
done

# 2. Database retention enforcement
echo ""
echo "[2/2] Enforcing database retention policies..."

POSTGRES_USER="${POSTGRES_USER:-surakshanet}"
POSTGRES_DB="${POSTGRES_DB:-surakshanet}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

EXEC_SQL() {
    local sql="$1"
    if command -v psql >/dev/null 2>&1 && [ -n "${DATABASE_URL:-}" ]; then
        psql "${DATABASE_URL}" -c "${sql}"
    elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q "surakshanet-timescaledb"; then
        docker exec -i surakshanet-timescaledb psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "${sql}"
    elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q "surakshanet-postgres"; then
        docker exec -i surakshanet-postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "${sql}"
    elif command -v psql >/dev/null 2>&1; then
        PGPASSWORD="${POSTGRES_PASSWORD:-surakshanet_dev}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "${sql}"
    else
        echo "  [WARN] Neither psql nor running surakshanet-timescaledb container found. Skipping direct SQL execution."
    fi
}

if [ "$DRY_RUN" = true ]; then
    echo "  - [DRY-RUN] Would purge cv_detections older than 72h"
    echo "  - [DRY-RUN] Would purge control_decisions older than 90 days"
    echo "  - [DRY-RUN] Would purge DISMISSED behavior_flags older than 90 days"
    echo "  - [DRY-RUN] Would purge traffic_readings older than 365 days"
    echo "  - [DRY-RUN] Would purge audit_logs older than 365 days"
else
    echo "  - Purging DISMISSED suspicion flags older than 90 days..."
    EXEC_SQL "DELETE FROM behavior_flags WHERE status = 'DISMISSED' AND detected_at < NOW() - INTERVAL '90 days';" || true

    echo "  - Executing TimescaleDB chunk drop for cv_detections older than 3 days..."
    EXEC_SQL "DELETE FROM cv_detections WHERE timestamp < NOW() - INTERVAL '3 days';" || true

    echo "  - Executing TimescaleDB chunk drop for control_decisions older than 90 days..."
    EXEC_SQL "DELETE FROM control_decisions WHERE timestamp < NOW() - INTERVAL '90 days';" || true

    echo "  - Executing retention cleanup for audit_logs older than 365 days..."
    EXEC_SQL "DELETE FROM audit_logs WHERE timestamp < NOW() - INTERVAL '365 days';" || true

    echo "  - Executing retention cleanup for traffic_readings older than 365 days..."
    EXEC_SQL "DELETE FROM traffic_readings WHERE timestamp < NOW() - INTERVAL '365 days';" || true
fi

echo ""
echo "=================================================================="
echo "Data retention enforcement run completed successfully."
echo "=================================================================="
