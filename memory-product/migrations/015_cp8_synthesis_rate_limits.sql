-- Migration 015: CP8 Phase 1 Task 5 — Synthesis Rate Limits
-- Creates memory_service.synthesis_rate_limits table for per-tenant cost-ceiling enforcement.
-- Tracks synthesis runs, LLM token usage, and consensus runs per day/month.
-- Per CHECKPOINT-8-SCOPE-v3.md Phase 1 Task 5.
-- Idempotent — safe to run multiple times.

-- ============================================================
-- 1. Create synthesis_rate_limits table
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_service.synthesis_rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    synthesis_runs_today INT NOT NULL DEFAULT 0,
    synthesis_runs_this_month INT NOT NULL DEFAULT 0,
    llm_tokens_today BIGINT NOT NULL DEFAULT 0,
    llm_tokens_this_month BIGINT NOT NULL DEFAULT 0,
    consensus_runs_this_month INT NOT NULL DEFAULT 0,
    daily_reset_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    monthly_reset_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id)
);

-- ============================================================
-- 2. Pre-populate rate limit rows for all existing tenants
-- ============================================================

INSERT INTO memory_service.synthesis_rate_limits (tenant_id)
SELECT id FROM memory_service.tenants
ON CONFLICT (tenant_id) DO NOTHING;

-- ============================================================
-- Done. Synthesis rate limits table is ready.
-- ============================================================

-- ============================================================
-- DOWN MIGRATION (manual rollback)
-- ============================================================
/*
-- ============================================================
-- 1. Drop table
-- ============================================================

DROP TABLE IF EXISTS memory_service.synthesis_rate_limits CASCADE;

-- ============================================================
-- Done. Synthesis rate limits table has been removed.
-- ============================================================
*/
