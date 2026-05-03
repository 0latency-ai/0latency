-- Migration 023: Add 'synthesis' to memory_type CHECK constraint
-- Required for CP8 Phase 2 Task 2 (Writer)
-- Idempotent — safe to run multiple times.

BEGIN;

-- ============================================================
-- 1. Drop existing memory_type CHECK constraint
-- ============================================================

ALTER TABLE memory_service.memories
DROP CONSTRAINT IF EXISTS check_memory_type;

-- ============================================================
-- 2. Recreate with 'synthesis' added
-- ============================================================

ALTER TABLE memory_service.memories
ADD CONSTRAINT check_memory_type
CHECK (memory_type IN (
    'fact',
    'decision',
    'preference',
    'task',
    'correction',
    'relationship',
    'identity',
    'session_checkpoint',
    'pattern',
    'raw_turn',
    'synthesis'  -- NEW: enables synthesis layer writes
));

-- ============================================================
-- Done. Synthesis memory_type is now allowed.
-- ============================================================

COMMIT;

-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
BEGIN;

ALTER TABLE memory_service.memories
DROP CONSTRAINT IF EXISTS check_memory_type;

ALTER TABLE memory_service.memories
ADD CONSTRAINT check_memory_type
CHECK (memory_type IN (
    'fact',
    'decision',
    'preference',
    'task',
    'correction',
    'relationship',
    'identity',
    'session_checkpoint',
    'pattern',
    'raw_turn'
));

COMMIT;
*/
