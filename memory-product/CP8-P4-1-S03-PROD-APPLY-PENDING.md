# Stage 03 — Cluster ID backfill: STAGING SHIPPED, PROD APPLY PENDING

Script authored, validated on staging.
Operator must run on prod manually:

    cd /root/.openclaw/workspace/memory-product
    set -a && source .env && set +a
    python3 scripts/backfill_cluster_id.py

Staging receipt:
```
$ DATABASE_URL="$STAGING_DATABASE_URL" python3 scripts/backfill_cluster_id.py
Backfilled cluster_id on 0 synthesis rows (skipped 0 rows without parents)

$ psql "$STAGING_DATABASE_URL" -c "SELECT COUNT(*) FILTER (WHERE metadata->>'cluster_id' IS NOT NULL) as with_cid, COUNT(*) FILTER (WHERE metadata->>'cluster_id' IS NULL) as without_cid FROM memory_service.memories WHERE memory_type='synthesis';"
 with_cid | without_cid 
----------+-------------
        0 |           0
```

Staging has zero synthesis memories, so zero rows updated (expected).

This is a halt-at-boundary, not a chain bail. Stages 04+ continue.
