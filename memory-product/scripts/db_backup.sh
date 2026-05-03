#!/usr/bin/env bash
# Backup prod DB to /var/backups/0latency/ with timestamped filename.
# Retains last 10 backups; older ones removed.
set -euo pipefail

BACKUP_DIR="/var/backups/0latency"
RETAIN=10

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

TS=$(date -u +%Y%m%dT%H%M%SZ)
DB_NAME=$(echo "$DATABASE_URL" | sed -E "s|.*/([^?]+).*|\1|")
OUT="$BACKUP_DIR/${DB_NAME}_${TS}.sql.gz"

echo "Backing up $DB_NAME to $OUT..."
pg_dump "$DATABASE_URL" --no-owner --no-privileges | gzip > "$OUT"

# Verify the backup is non-empty and gunzip-able
if ! gunzip -t "$OUT"; then
  echo "ERROR: backup archive is corrupt"
  rm -f "$OUT"
  exit 1
fi

SIZE=$(stat -c %s "$OUT")
if [[ "$SIZE" -lt 1024 ]]; then
  echo "ERROR: backup is suspiciously small ($SIZE bytes)"
  exit 1
fi

# Retention: keep last $RETAIN by mtime
ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +$((RETAIN + 1)) | xargs -r rm -f

echo "Backup OK: $OUT ($SIZE bytes)"
echo "$OUT"   # last line is the path, scriptable
