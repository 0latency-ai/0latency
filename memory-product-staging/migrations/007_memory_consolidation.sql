-- Migration 007: Memory Consolidation / Duplicate Detection
-- Auto-detect and merge similar/duplicate memories to keep memory graph clean.
-- Idempotent — safe to run multiple times.

-- ============================================================
-- 1. Create memory_duplicates table
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_service.memory_duplicates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    agent_id VARCHAR(128) NOT NULL,
    memory_id_1 UUID NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
    memory_id_2 UUID NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
    similarity_score FLOAT NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1),
    status VARCHAR(32) DEFAULT 'pending',  -- 'pending', 'merged', 'dismissed'
    merged_into UUID REFERENCES memory_service.memories(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    UNIQUE(tenant_id, agent_id, memory_id_1, memory_id_2),
    CHECK (memory_id_1 < memory_id_2)
);

-- ============================================================
-- 2. Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_memory_duplicates_agent
ON memory_service.memory_duplicates(agent_id, tenant_id);

CREATE INDEX IF NOT EXISTS idx_memory_duplicates_status
ON memory_service.memory_duplicates(status);

CREATE INDEX IF NOT EXISTS idx_memory_duplicates_tenant
ON memory_service.memory_duplicates(tenant_id);

-- ============================================================
-- 3. RLS policy for tenant isolation
-- ============================================================

DO $$ BEGIN
    CREATE POLICY tenant_isolation_memory_duplicates ON memory_service.memory_duplicates
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE memory_service.memory_duplicates ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 4. Add superseded_by column to memories for merge tracking
-- ============================================================

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS merged_from UUID[] DEFAULT '{}';

-- ============================================================
-- Done. Memory consolidation schema is ready.
-- ============================================================
