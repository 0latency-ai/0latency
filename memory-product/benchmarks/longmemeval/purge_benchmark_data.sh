#!/bin/bash
# Purge benchmark tenant data for clean run

set -a
source ../../.env
set +a

TENANT_ID="382faaf1-5cbf-49a1-b689-5ffef8918d10"

echo "Purging benchmark tenant data..."

psql "$DATABASE_URL" << EOSQL
DELETE FROM memory_service.memories 
WHERE tenant_id = '$TENANT_ID';

DELETE FROM memory_service.graph_entities 
WHERE tenant_id = '$TENANT_ID';

DELETE FROM memory_service.graph_relationships 
WHERE tenant_id = '$TENANT_ID';
EOSQL

echo "✓ Purge complete"
