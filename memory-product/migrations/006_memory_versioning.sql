-- Migration 006: Memory Versioning enhancements
-- Ensures memory_versions table exists with all needed columns
-- and adds foreign key from memories to track version lineage.
-- Idempotent — safe to run multiple times.

-- ============================================================
-- 1. Create memory_versions table (if not exists)
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_service.memory_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    memory_id UUID NOT NULL,
    version_number INT NOT NULL DEFAULT 1,
    headline TEXT NOT NULL,
    context TEXT,
    full_content TEXT,
    memory_type TEXT,
    importance FLOAT,
    confidence FLOAT,
    changed_by TEXT DEFAULT 'system',
    change_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    diff_summary TEXT
);

-- ============================================================
-- 2. Indexes for memory_versions
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_memory_versions_memory 
ON memory_service.memory_versions(memory_id, version_number);

CREATE INDEX IF NOT EXISTS idx_memory_versions_tenant 
ON memory_service.memory_versions(tenant_id);

-- ============================================================
-- 3. Ensure version column on memories table
-- ============================================================

ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS version INT DEFAULT 1;

-- ============================================================
-- 4. RLS policy for tenant isolation
-- ============================================================

DO $$ BEGIN
    CREATE POLICY tenant_isolation_memory_versions ON memory_service.memory_versions
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE memory_service.memory_versions ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Done. Memory versioning schema is ready.
-- ============================================================
