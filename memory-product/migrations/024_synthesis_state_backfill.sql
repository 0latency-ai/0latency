-- Migration 024: synthesis_state backfill and redaction cascade support
-- Tier: 1 (additive, reversible)
-- Reason: P5.1 Stage 2 - Enable redaction cascade end-to-end
--   1. Extend synthesis_state CHECK constraint to include 'pending_resynthesis' state
--   2. Extend synthesis_audit_events event_type CHECK to include cascade event types
--   3. Backfill synthesis_state NULL -> 'valid' for pre-existing synthesis rows
-- Forensic reconstruction: introspected from production schema 2026-05-06
--   Applied via Alembic revision 7fc534bdbff2 on 2026-05-05

-- NO inner BEGIN/COMMIT — wrapper handles transaction.

-- ============================================================
-- Step 1: Extend synthesis_audit_events event_type constraint
-- ============================================================

ALTER TABLE memory_service.synthesis_audit_events
DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check;

ALTER TABLE memory_service.synthesis_audit_events
ADD CONSTRAINT synthesis_audit_events_event_type_check
CHECK (event_type = ANY (ARRAY[
    'synthesis_written'::text,
    'redacted'::text,
    'resynthesized'::text,
    'consensus_run'::text,
    'consensus_disagreement_logged'::text,
    'synthesis_candidate_prepared'::text,
    'webhook_fired'::text,
    'prompt_version_changed'::text,
    'policy_changed'::text,
    'rate_limit_blocked'::text,
    'state_transition'::text,
    'consensus_run_started'::text,
    'consensus_skipped_insufficient_agents'::text,
    'consensus_failed_insufficient_candidates'::text,
    'consensus_merge_failed'::text,
    'consensus_disagreement_write_failed'::text,
    'read'::text,
    'redaction_cascade_initiated'::text,      -- NEW: cascade initiated event
    'redaction_cascade_overflow'::text        -- NEW: cascade overflow event
]));

-- ============================================================
-- Step 2: Extend memories synthesis_state constraint
-- ============================================================

ALTER TABLE memory_service.memories
DROP CONSTRAINT IF EXISTS check_synthesis_state;

ALTER TABLE memory_service.memories
ADD CONSTRAINT check_synthesis_state
CHECK ((synthesis_state IS NULL) OR (synthesis_state = ANY (ARRAY[
    'valid'::text,
    'pending_review'::text,
    'invalidated'::text,
    'resynthesized'::text,
    'pending_resynthesis'::text               -- NEW: enables cascade workflow
])));

-- ============================================================
-- Step 3: Backfill synthesis_state for existing synthesis rows
-- ============================================================

UPDATE memory_service.memories
SET synthesis_state = 'valid'
WHERE memory_type = 'synthesis'
  AND synthesis_state IS NULL;

-- ============================================================
-- Done. Redaction cascade infrastructure is ready.
-- ============================================================

-- Reversal note (for ops, not executed):
-- Revert constraints to previous values and set synthesis_state back to NULL
-- for rows where it was backfilled. In practice, backfill is the correct end
-- state and should not be reversed.
