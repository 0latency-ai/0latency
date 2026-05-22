#!/bin/bash
# Purge benchmark tenant data for a clean LongMemEval run.
#
# Usage: bash purge_benchmark_data.sh
#
# Override the target tenant via environment variable:
#   TENANT_ID=<uuid> bash purge_benchmark_data.sh

set -euo pipefail

# Load DB connection from the project .env (one level up from benchmarks/)
set -a
source ../../.env
set +a

# Default to the dedicated benchmark tenant created on 2026-05-10
TENANT_ID="${TENANT_ID:-382faaf1-5cbf-49a1-b689-5ffef8918d10}"

# Prefer MEMORY_DB_CONN (current convention), fall back to DATABASE_URL
DB_URL="${MEMORY_DB_CONN:-${DATABASE_URL:-}}"

if [ -z "$DB_URL" ]; then
    echo "ERROR: MEMORY_DB_CONN (or DATABASE_URL) must be set in ../../.env" >&2
    exit 1
fi

echo "Purging memories for tenant $TENANT_ID..."

psql "$DB_URL" -c "DELETE FROM memory_service.memories WHERE tenant_id = '$TENANT_ID';"

echo "✓ Purge complete"
