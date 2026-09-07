#!/usr/bin/env bash
# ==============================================================================
# Surakshanet Database Backup & Restore Utility
# Backs up consolidated PostGIS + TimescaleDB instance using pg_dump
# ==============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
CONTAINER_NAME="${DB_CONTAINER:-surakshanet-timescaledb}"
DB_USER="${POSTGRES_USER:-surakshanet}"
DB_NAME="${POSTGRES_DB:-surakshanet}"
RETENTION_DAYS=7

mkdir -p "${BACKUP_DIR}"

usage() {
    echo "Usage: $0 [--backup | --restore <backup_file> | --list]"
    exit 1
}

do_backup() {
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="${BACKUP_DIR}/surakshanet_backup_${TIMESTAMP}.dump"
    
    echo "Starting automated database backup from container '${CONTAINER_NAME}'..."
    docker exec -t "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" -Fc > "${BACKUP_FILE}"
    
    FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "Backup completed successfully: ${BACKUP_FILE} (${FILESIZE})"
    
    echo "Cleaning up backups older than ${RETENTION_DAYS} days..."
    find "${BACKUP_DIR}" -name "surakshanet_backup_*.dump" -mtime +${RETENTION_DAYS} -delete || true
    echo "Retention policy applied."
}

do_restore() {
    RESTORE_FILE="$1"
    if [ ! -f "${RESTORE_FILE}" ]; then
        echo "ERROR: Backup file not found: ${RESTORE_FILE}" >&2
        exit 1
    fi
    
    echo "WARNING: Restoring will overwrite existing tables in '${DB_NAME}'!"
    read -rp "Are you sure you want to proceed? (y/N): " CONFIRM
    if [[ "${CONFIRM}" != "y" && "${CONFIRM}" != "Y" ]]; then
        echo "Restore cancelled."
        exit 0
    fi
    
    echo "Restoring database from ${RESTORE_FILE}..."
    docker exec -i "${CONTAINER_NAME}" pg_restore -U "${DB_USER}" -d "${DB_NAME}" -c < "${RESTORE_FILE}"
    echo "Database restore completed successfully."
}

do_list() {
    echo "Available backups in ${BACKUP_DIR}:"
    ls -lh "${BACKUP_DIR}"/surakshanet_backup_*.dump 2>/dev/null || echo "No backups found."
}

case "${1:---backup}" in
    --backup)
        do_backup
        ;;
    --restore)
        if [ -z "${2:-}" ]; then
            usage
        fi
        do_restore "$2"
        ;;
    --list)
        do_list
        ;;
    *)
        usage
        ;;
esac
