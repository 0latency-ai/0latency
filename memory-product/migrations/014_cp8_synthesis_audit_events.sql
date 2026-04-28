-- Migration 014: CP8 Phase 1 Task 4 — Synthesis Audit Events
-- Creates memory_service.synthesis_audit_events table for immutable audit log.
-- Every synthesis write, redaction, consensus run, webhook fire, prompt change is logged here.
-- Append-only enforcement via trigger — no UPDATE or DELETE allowed.
-- Per CHECKPOINT-8-SCOPE-v3.md Phase 1 Task 4.
-- Idempotent — safe to run multiple times.

-- ============================================================
-- 1. Create synthesis_audit_events table
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_service.synthesis_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    target_memory_id UUID,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_payload JSONB DEFAULT '{}'::jsonb,
    CHECK (event_type IN (
        'synthesis_written',
        'redacted',
        'resynthesized',
        'consensus_run',
        'webhook_fired',
        'prompt_version_changed',
        'policy_changed',
        'rate_limit_blocked'
    ))
);

-- ============================================================
-- 2. Create indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_synthesis_audit_events_tenant_id
ON memory_service.synthesis_audit_events(tenant_id);

CREATE INDEX IF NOT EXISTS idx_synthesis_audit_events_target_memory_id
ON memory_service.synthesis_audit_events(target_memory_id)
WHERE target_memory_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_synthesis_audit_events_event_type
ON memory_service.synthesis_audit_events(event_type);

CREATE INDEX IF NOT EXISTS idx_synthesis_audit_events_occurred_at
ON memory_service.synthesis_audit_events(occurred_at DESC);

-- ============================================================
-- 3. Create append-only enforcement trigger function
-- ============================================================

CREATE OR REPLACE FUNCTION memory_service.prevent_audit_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'synthesis_audit_events is append-only; UPDATE/DELETE operations are prohibited';
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 4. Create trigger to prevent mutations
-- ============================================================

DROP TRIGGER IF EXISTS enforce_append_only ON memory_service.synthesis_audit_events;

CREATE TRIGGER enforce_append_only
    BEFORE UPDATE OR DELETE ON memory_service.synthesis_audit_events
    FOR EACH ROW
    EXECUTE FUNCTION memory_service.prevent_audit_mutation();

-- ============================================================
-- Done. Synthesis audit events table is ready.
-- ============================================================

-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
-- ============================================================
-- 1. Drop trigger
-- ============================================================

DROP TRIGGER IF EXISTS enforce_append_only ON memory_service.synthesis_audit_events;

-- ============================================================
-- 2. Drop trigger function
-- ============================================================

DROP FUNCTION IF EXISTS memory_service.prevent_audit_mutation();

-- ============================================================
-- 3. Drop indexes
-- ============================================================

DROP INDEX IF EXISTS memory_service.idx_synthesis_audit_events_occurred_at;
DROP INDEX IF EXISTS memory_service.idx_synthesis_audit_events_event_type;
DROP INDEX IF EXISTS memory_service.idx_synthesis_audit_events_target_memory_id;
DROP INDEX IF EXISTS memory_service.idx_synthesis_audit_events_tenant_id;

-- ============================================================
-- 4. Drop table
-- ============================================================

DROP TABLE IF EXISTS memory_service.synthesis_audit_events CASCADE;

-- ============================================================
-- Done. Synthesis audit events table has been removed.
-- ============================================================
*/
