-- Migration 018: CP8 Phase 1 Task 8 — Add updated_at to memories
-- src/synthesis/redaction.py expects this column for state-machine writes.
-- Idempotent — safe to run multiple times.

-- ============================================================
-- 1. Add updated_at column
-- ============================================================
ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- ============================================================
-- 2. Backfill existing rows from created_at
-- ============================================================
UPDATE memory_service.memories
SET updated_at = created_at
WHERE updated_at IS NULL;

-- ============================================================
-- 3. Set default for future inserts
-- ============================================================
ALTER TABLE memory_service.memories
ALTER COLUMN updated_at SET DEFAULT NOW();

-- ============================================================
-- 4. Index for sync/change-tracking queries
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_memories_updated_at
ON memory_service.memories(updated_at);

-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
DROP INDEX IF EXISTS memory_service.idx_memories_updated_at;
ALTER TABLE memory_service.memories DROP COLUMN IF EXISTS updated_at;
*/
