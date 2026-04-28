-- Migration 017: CP8 Phase 1 Task 8 — Redaction State Machine
-- Adds synthesis_state column and updates redaction_state CHECK constraint.
-- Implements two state machines: source state (all memories) and synthesis state (synthesis rows only).
-- Per Task 8 architectural requirements.
-- Idempotent — safe to run multiple times.

-- ============================================================
-- 1. Drop and recreate redaction_state CHECK constraint
-- ============================================================

-- Drop existing constraint
ALTER TABLE memory_service.memories
DROP CONSTRAINT IF EXISTS check_redaction_state;

-- Add updated constraint with all four states
ALTER TABLE memory_service.memories
ADD CONSTRAINT check_redaction_state
CHECK (redaction_state IN ('active', 'redacted', 'modified', 'pending_resynthesis'));

-- ============================================================
-- 2. Add synthesis_state column
-- ============================================================

ALTER TABLE memory_service.memories
ADD COLUMN IF NOT EXISTS synthesis_state TEXT DEFAULT NULL;

-- ============================================================
-- 3. Add CHECK constraint for synthesis_state
-- ============================================================

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'check_synthesis_state'
        AND conrelid = 'memory_service.memories'::regclass
    ) THEN
        ALTER TABLE memory_service.memories
        ADD CONSTRAINT check_synthesis_state
        CHECK (synthesis_state IS NULL OR synthesis_state IN ('valid', 'pending_review', 'invalidated', 'resynthesized'));
    END IF;
END $$;

-- ============================================================
-- 4. Create partial index on synthesis_state
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_memories_synthesis_state
ON memory_service.memories(synthesis_state)
WHERE memory_type = 'synthesis';

-- ============================================================
-- 5. Update synthesis_audit_events to allow state_transition event type
-- ============================================================

-- Drop existing CHECK constraint on event_type
ALTER TABLE memory_service.synthesis_audit_events
DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check;

-- Add updated constraint with state_transition
ALTER TABLE memory_service.synthesis_audit_events
ADD CONSTRAINT synthesis_audit_events_event_type_check
CHECK (event_type IN (
    'synthesis_written',
    'redacted',
    'resynthesized',
    'consensus_run',
    'webhook_fired',
    'prompt_version_changed',
    'policy_changed',
    'rate_limit_blocked',
    'state_transition'
));

-- ============================================================
-- Done. Redaction state machine schema is ready.
-- ============================================================

-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
-- ============================================================
-- 1. Drop partial index
-- ============================================================

DROP INDEX IF EXISTS memory_service.idx_memories_synthesis_state;

-- ============================================================
-- 2. Drop synthesis_state CHECK constraint
-- ============================================================

ALTER TABLE memory_service.memories
DROP CONSTRAINT IF EXISTS check_synthesis_state;

-- ============================================================
-- 3. Drop synthesis_state column
-- ============================================================

ALTER TABLE memory_service.memories
DROP COLUMN IF EXISTS synthesis_state;

-- ============================================================
-- 4. Restore original redaction_state CHECK constraint
-- ============================================================

ALTER TABLE memory_service.memories
DROP CONSTRAINT IF EXISTS check_redaction_state;

ALTER TABLE memory_service.memories
ADD CONSTRAINT check_redaction_state
CHECK (redaction_state IN ('active', 'redacted', 'pending_resynthesis'));

-- ============================================================
-- 5. Restore original synthesis_audit_events event_type CHECK
-- ============================================================

ALTER TABLE memory_service.synthesis_audit_events
DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check;

ALTER TABLE memory_service.synthesis_audit_events
ADD CONSTRAINT synthesis_audit_events_event_type_check
CHECK (event_type IN (
    'synthesis_written',
    'redacted',
    'resynthesized',
    'consensus_run',
    'webhook_fired',
    'prompt_version_changed',
    'policy_changed',
    'rate_limit_blocked'
));

-- ============================================================
-- Done. Redaction state machine schema has been removed.
-- ============================================================
*/
