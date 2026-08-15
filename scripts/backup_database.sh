#!/usr/bin/env bash
# Backup the UAT platform: PostgreSQL dump + report/artifact archive.
# Usage: scripts/backup_database.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-uat}"
DB_NAME="${DB_NAME:-uat_test_intelligence}"
export PGPASSWORD="${PGPASSWORD:-uat}"

mkdir -p "$BACKUP_DIR"
DUMP_FILE="$BACKUP_DIR/${STAMP}.dump"
ARTIFACTS_FILE="$BACKUP_DIR/${STAMP}-artifacts.tar.gz"

echo "[backup] dumping database -> $DUMP_FILE"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -Fc -d "$DB_NAME" > "$DUMP_FILE"

echo "[backup] archiving reports -> $ARTIFACTS_FILE"
tar -czf "$ARTIFACTS_FILE" \
  --exclude='generated' \
  -C "$ROOT" reports 2>/dev/null || true

echo "[backup] done"
echo "[backup] $(date -u +%FT%TZ) db=$DUMP_FILE artifacts=$ARTIFACTS_FILE" >> "$BACKUP_DIR/backup.log"
