#!/bin/bash
# Zero Latency Memory — Backup Script
BACKUP_DIR="/root/backups/memory-api/$(date +%Y-%m-%d_%H%M)"
DB_CONN="postgresql://postgres.fuojxlabvhtmysbsixdn:jcYlwEhuHN9VcOuj@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

mkdir -p "$BACKUP_DIR"

TABLES="memories tenants api_usage memory_audit_log agent_config session_handoffs entity_index memory_edges"

for table in $TABLES; do
    echo "Backing up memory_service.$table..."
    psql "$DB_CONN" -c "\COPY memory_service.$table TO '$BACKUP_DIR/${table}.csv' WITH CSV HEADER" 2>&1
done

psql "$DB_CONN" -t -c "
SELECT 'memories', COUNT(*) FROM memory_service.memories
UNION ALL SELECT 'tenants', COUNT(*) FROM memory_service.tenants
UNION ALL SELECT 'audit_log', COUNT(*) FROM memory_service.memory_audit_log
" > "$BACKUP_DIR/counts.txt" 2>&1

echo "Backup complete: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"
