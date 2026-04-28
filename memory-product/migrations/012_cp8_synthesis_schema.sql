-- Migration 012: CP8 Phase 1 Task 1 — Synthesis Layer Schema
-- Adds 10 columns to memory_service.memories to support synthesis layer
-- with provenance, versioning, role-scoping, redaction, and confidence scoring.
-- Per CHECKPOINT-8-SCOPE-v3.md Architecture map and Phase 1 Task 1.
-- Idempotent — safe to run multiple times.

BEGIN;

-- ============================================================
-- 1. Add synthesis layer columns to memories table
-- ============================================================

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS synthesis_version INT DEFAULT 1;

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS source_memory_ids UUID[] DEFAULT NULL;

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS role_tag TEXT DEFAULT NULL;

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS redaction_state TEXT DEFAULT 'active';

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT NULL;

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS contributing_agents TEXT[] DEFAULT '{}';

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS consensus_method TEXT DEFAULT 'single_agent';

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS synthesis_prompt_version TEXT DEFAULT NULL;

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS superseded_by UUID DEFAULT NULL;

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT false;

-- ============================================================
-- 2. Add CHECK constraint for redaction_state enum
-- ============================================================

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'check_redaction_state'
        AND conrelid = 'memory_service.memories'::regclass
    ) THEN
        ALTER TABLE memory_service.memories
        ADD CONSTRAINT check_redaction_state
        CHECK (redaction_state IN ('active', 'redacted', 'pending_resynthesis'));
    END IF;
END $$;

-- ============================================================
-- 3. Create indexes for synthesis queries
-- ============================================================

-- GIN index on source_memory_ids for redaction cascade queries (partial: only indexed when populated)
CREATE INDEX IF NOT EXISTS idx_memories_source_memory_ids
ON memory_service.memories USING gin(source_memory_ids)
WHERE source_memory_ids IS NOT NULL;

-- btree index on role_tag for recall filtering
CREATE INDEX IF NOT EXISTS idx_memories_role_tag
ON memory_service.memories(role_tag);

-- btree index on superseded_by for version chain walks (partial: only indexed when populated)
CREATE INDEX IF NOT EXISTS idx_memories_superseded_by
ON memory_service.memories(superseded_by)
WHERE superseded_by IS NOT NULL;

-- btree index on redaction_state for filtering redacted/pending rows
CREATE INDEX IF NOT EXISTS idx_memories_redaction_state
ON memory_service.memories(redaction_state);

-- ============================================================
-- Done. Synthesis layer schema columns are ready.
-- ============================================================

COMMIT;

-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
BEGIN;

-- ============================================================
-- 1. Drop indexes
-- ============================================================

DROP INDEX IF EXISTS memory_service.idx_memories_redaction_state;
DROP INDEX IF EXISTS memory_service.idx_memories_superseded_by;
DROP INDEX IF EXISTS memory_service.idx_memories_role_tag;
DROP INDEX IF EXISTS memory_service.idx_memories_source_memory_ids;

-- ============================================================
-- 2. Drop CHECK constraint
-- ============================================================

ALTER TABLE memory_service.memories
DROP CONSTRAINT IF EXISTS check_redaction_state;

-- ============================================================
-- 3. Drop columns (in reverse order)
-- ============================================================

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS is_pinned;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS superseded_by;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS synthesis_prompt_version;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS consensus_method;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS contributing_agents;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS confidence_score;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS redaction_state;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS role_tag;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS source_memory_ids;

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS synthesis_version;

-- ============================================================
-- Done. Synthesis layer schema has been removed.
-- ============================================================

COMMIT;
*/
