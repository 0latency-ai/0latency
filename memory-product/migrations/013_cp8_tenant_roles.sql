-- Migration 013: CP8 Phase 1 Task 3 — Tenant Roles Registry
-- Creates memory_service.tenant_roles table for role-scoped synthesis.
-- Pre-populates every tenant with default roles: public, engineering, product, revenue, legal.
-- Per CHECKPOINT-8-SCOPE-v3.md Phase 1 Task 3 and Decision 2.
-- Idempotent — safe to run multiple times.

BEGIN;

-- ============================================================
-- 1. Create tenant_roles table
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_service.tenant_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    role_name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, role_name)
);

-- ============================================================
-- 2. Create index on tenant_id
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_tenant_roles_tenant_id
ON memory_service.tenant_roles(tenant_id);

-- ============================================================
-- 3. Pre-populate default roles for all existing tenants
-- ============================================================

INSERT INTO memory_service.tenant_roles (tenant_id, role_name, description)
SELECT
    t.id,
    role.name,
    role.description
FROM memory_service.tenants t
CROSS JOIN (
    VALUES
        ('public', 'Public role - visible to all consumers within this tenant'),
        ('engineering', 'Engineering team role - technical context and implementation details'),
        ('product', 'Product team role - feature context and user-facing decisions'),
        ('revenue', 'Revenue team role - sales, pricing, and business metrics'),
        ('legal', 'Legal team role - compliance, contracts, and risk management')
) AS role(name, description)
ON CONFLICT (tenant_id, role_name) DO NOTHING;

-- ============================================================
-- Done. Tenant roles registry is ready.
-- ============================================================

COMMIT;

-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
BEGIN;

-- ============================================================
-- 1. Drop index
-- ============================================================

DROP INDEX IF EXISTS memory_service.idx_tenant_roles_tenant_id;

-- ============================================================
-- 2. Drop table (CASCADE will handle FK references if any exist)
-- ============================================================

DROP TABLE IF EXISTS memory_service.tenant_roles CASCADE;

-- ============================================================
-- Done. Tenant roles registry has been removed.
-- ============================================================

COMMIT;
*/
