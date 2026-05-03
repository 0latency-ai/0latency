#!/usr/bin/env bash
# Restore prod DB from a named backup. Refuses unless --confirm flag passed.
set -euo pipefail

if [[ "${1:-}" != "--confirm" ]] || [[ -z "${2:-}" ]]; then
  echo "Usage: $0 --confirm /var/backups/0latency/FILENAME.sql.gz"
  echo "Restores prod DB from the named backup. Existing data will be replaced."
  exit 1
fi

BACKUP_FILE="$2"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "ERROR: backup not found: $BACKUP_FILE"
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set"
  exit 1
fi

echo "Restoring $BACKUP_FILE to $DATABASE_URL..."
echo "Press Ctrl+C in the next 5 seconds to abort."
sleep 5

gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"
echo "Restore complete."
