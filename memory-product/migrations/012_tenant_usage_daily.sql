-- Migration 012: Tenant usage rollup table for admin analytics
-- Created: 2026-04-18
-- Purpose: Daily aggregation of per-tenant usage metrics for admin dashboard

BEGIN;

-- ============================================================
-- 1. Create tenant_usage_daily table
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_service.tenant_usage_daily (
  tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
  day DATE NOT NULL,

  -- Memory counts
  memories_total INT NOT NULL DEFAULT 0,           -- cumulative count as of end-of-day
  memories_added_today INT NOT NULL DEFAULT 0,     -- new memories created this day

  -- API activity
  recalls_today INT NOT NULL DEFAULT 0,            -- recall API calls
  extractions_today INT NOT NULL DEFAULT 0,        -- extraction/store calls (memories created)
  api_calls_today INT NOT NULL DEFAULT 0,          -- total API calls (all endpoints)

  -- Agent/namespace tracking
  agents_active INT NOT NULL DEFAULT 0,            -- distinct agent_ids active this day

  -- Storage (rough estimate)
  storage_bytes BIGINT NOT NULL DEFAULT 0,         -- total storage size estimate

  -- Cost estimate (rough coefficients - see rollup job for formula)
  estimated_cost_usd NUMERIC(10,4) NOT NULL DEFAULT 0,

  -- Activity timestamp
  last_active_at TIMESTAMPTZ,

  PRIMARY KEY (tenant_id, day)
);

-- ============================================================
-- 2. Indexes for admin queries
-- ============================================================

CREATE INDEX idx_tenant_usage_day ON memory_service.tenant_usage_daily(day DESC);
CREATE INDEX idx_tenant_usage_tenant ON memory_service.tenant_usage_daily(tenant_id);
CREATE INDEX idx_tenant_usage_cost ON memory_service.tenant_usage_daily(estimated_cost_usd DESC);

-- ============================================================
-- 3. Add promo_code tracking to tenants table
-- ============================================================

ALTER TABLE memory_service.tenants
ADD COLUMN IF NOT EXISTS promo_code VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_tenants_promo_code ON memory_service.tenants(promo_code);

-- ============================================================
-- 4. Verification
-- ============================================================

SELECT 
    'tenant_usage_daily table' AS component,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'memory_service' 
          AND table_name = 'tenant_usage_daily'
    ) THEN '✓ Created' ELSE '✗ Missing' END AS status
UNION ALL
SELECT 
    'promo_code column' AS component,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'memory_service' 
          AND table_name = 'tenants'
          AND column_name = 'promo_code'
    ) THEN '✓ Added' ELSE '✗ Missing' END AS status
UNION ALL
SELECT 
    'indexes' AS component,
    COUNT(*)::TEXT || ' indexes created on tenant_usage_daily' AS status
FROM pg_indexes
WHERE schemaname = 'memory_service' 
  AND tablename = 'tenant_usage_daily';

COMMIT;
