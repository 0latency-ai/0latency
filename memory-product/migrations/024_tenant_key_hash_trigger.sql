-- DO NOT APPLY UNTIL CP-DB-SANDBOX TASK 4 (Alembic) IS COMPLETE
-- Apply via Alembic, not psql
--
-- Migration: Auto-recompute api_key_hash on api_key_live writes
-- Purpose: Prevent hash drift by maintaining api_key_hash = sha256(api_key_live) invariant
-- Context: Hash drift affected 27/110 tenants (24.5%) due to incomplete UPDATE statements
-- Issue: https://github.com/0latency-ai/0latency/issues/TBD
-- Date: 2026-05-04
-- Tier: 1 (additive, reversible)

-- Enable pgcrypto for digest() function
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Function to auto-compute hash when api_key_live changes
CREATE OR REPLACE FUNCTION memory_service.sync_api_key_hash()
RETURNS TRIGGER AS $$
BEGIN
    -- If api_key_live is being inserted or updated, recompute hash
    IF NEW.api_key_live IS NOT NULL THEN
        NEW.api_key_hash := encode(digest(NEW.api_key_live, 'sha256'), 'hex');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on INSERT and UPDATE
CREATE TRIGGER tenant_api_key_hash_sync
    BEFORE INSERT OR UPDATE OF api_key_live
    ON memory_service.tenants
    FOR EACH ROW
    WHEN (NEW.api_key_live IS NOT NULL)
    EXECUTE FUNCTION memory_service.sync_api_key_hash();

-- Verification query (run after applying migration):
-- SELECT id, name, 
--        api_key_live IS NOT NULL as has_live_key,
--        api_key_hash = encode(digest(api_key_live, 'sha256'), 'hex') as hash_matches
-- FROM memory_service.tenants 
-- WHERE api_key_live IS NOT NULL;

COMMENT ON FUNCTION memory_service.sync_api_key_hash IS 
    'Auto-recompute api_key_hash when api_key_live is written. Prevents hash drift.';

COMMENT ON TRIGGER tenant_api_key_hash_sync ON memory_service.tenants IS
    'Maintains invariant: api_key_hash = sha256(api_key_live). Prevents manual UPDATE bugs.';

-- Rollback (if needed):
-- DROP TRIGGER IF EXISTS tenant_api_key_hash_sync ON memory_service.tenants;
-- DROP FUNCTION IF EXISTS memory_service.sync_api_key_hash();
-- DROP EXTENSION IF EXISTS pgcrypto; -- Only if safe; other tables may use it
