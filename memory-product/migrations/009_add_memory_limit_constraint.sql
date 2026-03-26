-- Migration: Add memory limit enforcement trigger
-- Created: 2026-03-25
-- Purpose: Prevent race conditions in concurrent bulk imports

-- Create function to check tenant memory count
CREATE OR REPLACE FUNCTION memory_service.check_memory_limit()
RETURNS TRIGGER AS $$
DECLARE
    current_count INTEGER;
    max_limit INTEGER;
BEGIN
    -- Count non-superseded memories for this tenant
    SELECT COUNT(*) INTO current_count
    FROM memory_service.memories
    WHERE tenant_id = NEW.tenant_id 
      AND superseded_at IS NULL;
    
    -- Get limit for tenant
    SELECT memory_limit INTO max_limit
    FROM memory_service.tenants
    WHERE id = NEW.tenant_id;
    
    -- Check if limit would be exceeded
    IF current_count >= max_limit THEN
        RAISE EXCEPTION 'Memory limit exceeded for tenant % (limit: %, current: %)', 
            NEW.tenant_id, max_limit, current_count
        USING ERRCODE = '23514';  -- check_violation
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on INSERT
DROP TRIGGER IF EXISTS enforce_memory_limit ON memory_service.memories;

CREATE TRIGGER enforce_memory_limit
    BEFORE INSERT ON memory_service.memories
    FOR EACH ROW
    EXECUTE FUNCTION memory_service.check_memory_limit();

-- Verify trigger is active
SELECT 
    trigger_name, 
    event_manipulation, 
    event_object_table, 
    action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'memory_service'
  AND trigger_name = 'enforce_memory_limit';
