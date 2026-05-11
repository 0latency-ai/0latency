#!/bin/bash
# Verification query script for CP9 P2 T1: Time-to-First-Memory instrumentation
# Shows per-path distribution and elapsed_seconds histogram for data analysis

set -euo pipefail
set -a && source .env && set +a

echo "========================================"
echo "CP9 P2 T1: Onboarding Events Analysis"
echo "========================================"
echo ""

echo "=== Total Onboarding Events ==="
psql "$DATABASE_URL" -c "
SELECT COUNT(*) as total_events
FROM memory_service.onboarding_events
WHERE event_type = 'first_memory_add';
"

echo ""
echo "=== Events Per Install Path ==="
psql "$DATABASE_URL" -c "
SELECT 
    install_path,
    COUNT(*) as events,
    ROUND(AVG(elapsed_seconds), 2) as avg_seconds,
    ROUND(MIN(elapsed_seconds), 2) as min_seconds,
    ROUND(MAX(elapsed_seconds), 2) as max_seconds
FROM memory_service.onboarding_events
WHERE event_type = 'first_memory_add'
GROUP BY install_path
ORDER BY events DESC;
"

echo ""
echo "=== Elapsed Seconds Histogram ==="
psql "$DATABASE_URL" -c "
SELECT 
    CASE 
        WHEN elapsed_seconds < 10 THEN '<10s'
        WHEN elapsed_seconds < 30 THEN '10-30s'
        WHEN elapsed_seconds < 60 THEN '30-60s'
        WHEN elapsed_seconds < 120 THEN '1-2min'
        WHEN elapsed_seconds < 300 THEN '2-5min'
        WHEN elapsed_seconds < 900 THEN '5-15min'
        WHEN elapsed_seconds < 3600 THEN '15-60min'
        ELSE '>1hr'
    END as time_bucket,
    COUNT(*) as events,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM memory_service.onboarding_events
WHERE event_type = 'first_memory_add'
GROUP BY time_bucket
ORDER BY MIN(elapsed_seconds);
"

echo ""
echo "=== Recent Onboarding Events (Last 20) ==="
psql "$DATABASE_URL" -c "
SELECT 
    LEFT(tenant_id::text, 8) || '...' as tenant,
    install_path,
    ROUND(elapsed_seconds, 2) as seconds,
    metadata->>'endpoint' as endpoint,
    created_at
FROM memory_service.onboarding_events
WHERE event_type = 'first_memory_add'
ORDER BY created_at DESC
LIMIT 20;
"

echo ""
echo "=== Success Rate: Tenants with First Memory ==="
psql "$DATABASE_URL" -c "
WITH tenant_stats AS (
    SELECT 
        COUNT(DISTINCT t.id) as total_tenants,
        COUNT(DISTINCT oe.tenant_id) as tenants_with_first_memory
    FROM memory_service.tenants t
    LEFT JOIN memory_service.onboarding_events oe 
        ON t.id = oe.tenant_id AND oe.event_type = 'first_memory_add'
    WHERE t.created_at > NOW() - INTERVAL '30 days'  -- Last 30 days only
)
SELECT 
    total_tenants,
    tenants_with_first_memory,
    ROUND(100.0 * tenants_with_first_memory / NULLIF(total_tenants, 0), 1) as conversion_rate_percent
FROM tenant_stats;
"

echo ""
echo "=== Path Distribution Over Time (Last 7 Days) ==="
psql "$DATABASE_URL" -c "
SELECT 
    DATE(created_at) as date,
    install_path,
    COUNT(*) as events
FROM memory_service.onboarding_events
WHERE event_type = 'first_memory_add'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at), install_path
ORDER BY date DESC, events DESC;
"

echo ""
echo "========================================"
echo "Analysis complete"
echo "========================================"
