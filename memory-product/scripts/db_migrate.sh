#!/usr/bin/env bash
# Migrate flow: backup prod -> apply to staging -> apply to prod.
# Usage: db_migrate.sh up | down | status
set -euo pipefail

MODE="${1:-status}"

if [[ -z "${DATABASE_URL:-}" ]] || [[ -z "${STAGING_DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL and STAGING_DATABASE_URL must be set"
  exit 1
fi

case "$MODE" in
  status)
    echo "=== Prod ==="
    alembic current
    echo "=== Staging ==="
    alembic -x env=staging current
    echo "=== Pending ==="
    alembic history | head -10
    ;;

  up)
    echo "=== Step 1: backup prod ==="
    BACKUP=$(bash scripts/db_backup.sh | tail -1)
    echo "Backup: $BACKUP"

    echo "=== Step 2: reset staging from prod schema ==="
    bash scripts/staging_reset.sh
    alembic -x env=staging stamp 0001_baseline

    echo "=== Step 3: apply pending migrations to staging ==="
    alembic -x env=staging upgrade head

    echo "=== Step 4: verify staging health ==="
    psql "$STAGING_DATABASE_URL" -c "SELECT version_num FROM memory_service.alembic_version;"

    echo "=== Step 5: apply to prod ==="
    echo "Applying to prod in 5 seconds. Ctrl+C to abort."
    sleep 5
    alembic upgrade head

    echo "=== Step 6: verify prod ==="
    alembic current
    echo "Migration complete. Backup retained at $BACKUP"
    ;;

  down)
    echo "=== Step 1: backup prod ==="
    BACKUP=$(bash scripts/db_backup.sh | tail -1)
    echo "Backup: $BACKUP"

    echo "=== Step 2: downgrade staging by 1 ==="
    alembic -x env=staging downgrade -1

    echo "=== Step 3: verify staging health ==="
    psql "$STAGING_DATABASE_URL" -c "SELECT version_num FROM memory_service.alembic_version;"

    echo "=== Step 4: downgrade prod by 1 ==="
    echo "Downgrading prod in 5 seconds. Ctrl+C to abort."
    sleep 5
    alembic downgrade -1

    echo "=== Step 5: verify prod ==="
    alembic current
    echo "Downgrade complete. Backup at $BACKUP can restore the prior state if needed."
    ;;

  *)
    echo "Usage: $0 up | down | status"
    exit 1
    ;;
esac
