-- Migration 016: CP8 Phase 1 Task 7 — Synthesis Policy DSL
-- Adds synthesis_policy JSONB column to tenants table for policy-based synthesis control.
-- Backfills all existing tenants with tier-appropriate default policies.
-- Per CP8 Phase 1 Task 7.
-- Idempotent — safe to run multiple times.

-- ============================================================
-- 1. Add synthesis_policy column with default policy
-- ============================================================

DO $$ 
BEGIN
    -- Add column only if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'memory_service' 
        AND table_name = 'tenants' 
        AND column_name = 'synthesis_policy'
    ) THEN
        ALTER TABLE memory_service.tenants 
        ADD COLUMN synthesis_policy JSONB NOT NULL DEFAULT '{
            "redaction_rules": {
                "on_source_redacted": "resynthesize_without",
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
    END IF;
END $$;

-- ============================================================
-- 2. Update enterprise tenants with enterprise-specific policy
-- ============================================================

UPDATE memory_service.tenants
SET synthesis_policy = '{
    "redaction_rules": {
        "on_source_redacted": "resynthesize_without",
        "on_source_modified": "mark_pending_review",
        "cascade_depth": "evidence_chain_only"
    },
    "role_visibility": {
        "default_role": "public",
        "produce_for_roles": ["public", "engineering", "product", "revenue", "legal"],
        "cross_role_read": false
    },
    "retention": {
        "max_age_days": null,
        "auto_archive": false
    },
    "consensus_requirements": {
        "method": "majority_vote",
        "min_agents": 3,
        "tie_breaker": "highest_confidence"
    }
}'::jsonb
WHERE plan = 'enterprise';

-- ============================================================
-- Done. Synthesis policy column is ready with tier-appropriate defaults.
-- ============================================================

-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
-- ============================================================
-- 1. Remove synthesis_policy column
-- ============================================================

ALTER TABLE memory_service.tenants DROP COLUMN IF EXISTS synthesis_policy CASCADE;

-- ============================================================
-- Done. Synthesis policy column has been removed.
-- ============================================================
*/
