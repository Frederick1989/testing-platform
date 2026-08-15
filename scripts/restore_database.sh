#!/usr/bin/env bash
# Restore a UAT platform database from a pg_dump -Fc backup.
# Usage: scripts/restore_database.sh backups/<file>.dump
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="${1:-}"
if [[ -z "$FILE" ]]; then
  echo "usage: $0 <dumpfile.dump>" >&2
  exit 1
fi
if [[ ! -f "$FILE" ]]; then
  echo "dump file not found: $FILE" >&2
  exit 1
fi

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-uat}"
DB_NAME="${DB_NAME:-uat_test_intelligence}"
export PGPASSWORD="${PGPASSWORD:-uat}"

echo "This will DROP and recreate database '$DB_NAME'. Type the database name to confirm:"
read -r CONFIRM
if [[ "$CONFIRM" != "$DB_NAME" ]]; then
  echo "aborted" >&2
  exit 1
fi

echo "[restore] dropping existing connections"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();"

echo "[restore] recreating database"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS $DB_NAME;" \
  -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

echo "[restore] restoring from $FILE"
pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --no-owner "$FILE"

echo "[restore] done"
