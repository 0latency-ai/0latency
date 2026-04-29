-- Migration 021: CP8 Phase 2 v3 Task 8b — Raw Turn Memory Type
-- Adds partial index for fast parent_memory_ids traversal on raw_turn memories.
-- Per CP8 Phase 2 v3 Task 8b decision: raw_turns are sub-atomic evidence rows.
-- Idempotent — safe to run multiple times.
--
-- SCOPE REVISION (2026-04-29): Original plan included a CHECK constraint on memory_type
-- to enforce valid types. Dropped from this migration after discovering 31 distinct
-- memory_type values in production (session_checkpoint, pattern, fix, system, event, etc.).
-- Schema hygiene and type consolidation deferred to separate cleanup task.
-- This migration ONLY adds the raw_turn partial index needed for Task 8b functionality.

-- ============================================================
-- UP MIGRATION
-- ============================================================

-- Add partial index on id for raw_turn parent traversal
-- This speeds up queries like: WHERE metadata->'parent_memory_ids' @> '["uuid"]'::jsonb
-- when clients need to find atoms that reference a raw_turn
CREATE INDEX IF NOT EXISTS idx_memories_raw_turn_parents
ON memory_service.memories(id)
WHERE memory_type = 'raw_turn';

-- ============================================================
-- Done. Raw turn partial index is ready.
-- ============================================================


-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
-- Drop partial index
DROP INDEX IF EXISTS memory_service.idx_memories_raw_turn_parents;

-- ============================================================
-- Done. Raw turn partial index has been removed.
-- ============================================================
*/
