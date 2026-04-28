-- Migration 019: CP8 Phase 1 Task 8 fixup — Fix synthesis_policy defaults
-- Migration 016 shipped with on_source_redacted="resynthesize_without" but
-- src/synthesis/redaction.py only implements mark_pending_review in Phase 1.
-- This migration corrects the column default AND backfills existing rows.
-- Idempotent — safe to run multiple times.

-- ============================================================
-- 1. Update column default for new tenants going forward
-- ============================================================
ALTER TABLE memory_service.tenants
ALTER COLUMN synthesis_policy SET DEFAULT '{
    "redaction_rules": {
        "on_source_redacted": "mark_pending_review",
        "on_source_modified": "mark_pending_review",
        "cascade_depth": "evidence_chain_only"
    },
    "role_visibility": {
        "default_role": "public",
        "produce_for_roles": ["public"],
        "cross_role_read": false
    },
    "retention": {
        "max_age_days": null,
        "auto_archive": false
    },
    "consensus_requirements": {
        "method": "majority_vote",
        "min_agents": 1,
        "tie_breaker": "highest_confidence"
    }
}'::jsonb;

-- ============================================================
-- 2. Backfill existing rows where the broken default is still set
-- ============================================================
UPDATE memory_service.tenants
SET synthesis_policy = jsonb_set(
    synthesis_policy,
    '{redaction_rules,on_source_redacted}',
    '"mark_pending_review"'::jsonb
)
WHERE synthesis_policy->'redaction_rules'->>'on_source_redacted' = 'resynthesize_without';

-- ============================================================
-- DOWN MIGRATION (manual rollback — not recommended)
-- ============================================================
/*
ALTER TABLE memory_service.tenants
ALTER COLUMN synthesis_policy SET DEFAULT '{... original broken default ...}'::jsonb;

UPDATE memory_service.tenants
SET synthesis_policy = jsonb_set(
    synthesis_policy,
    '{redaction_rules,on_source_redacted}',
    '"resynthesize_without"'::jsonb
);
*/
