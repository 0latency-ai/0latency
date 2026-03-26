-- Migration: Audit Logging System
-- Created: 2026-03-25
-- Purpose: Enterprise audit trail for SOC 2 Type I compliance

-- ═══════════════════════════════════════════════════════════════════════════
-- Audit Logs Table
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS memory_service.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Identity
    tenant_id UUID REFERENCES memory_service.tenants(id) ON DELETE SET NULL,
    user_id UUID,  -- No FK (may reference users table in future)
    
    -- Request Context
    endpoint TEXT,
    ip_address VARCHAR(45),  -- IPv6 max length
    user_agent TEXT,
    status_code INTEGER,
    request_id VARCHAR(64),
    
    -- Event Details
    success BOOLEAN NOT NULL DEFAULT true,
    message TEXT,
    metadata JSONB,
    
    -- Indexing
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ═══════════════════════════════════════════════════════════════════════════
-- Indexes for Query Performance
-- ═══════════════════════════════════════════════════════════════════════════

-- Primary query patterns
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_timestamp 
    ON memory_service.audit_logs(tenant_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type_timestamp 
    ON memory_service.audit_logs(event_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_timestamp 
    ON memory_service.audit_logs(user_id, timestamp DESC);

-- Security investigations
CREATE INDEX IF NOT EXISTS idx_audit_logs_ip_timestamp 
    ON memory_service.audit_logs(ip_address, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp 
    ON memory_service.audit_logs(timestamp DESC);

-- Partial indexes for critical events (faster queries, smaller size)
CREATE INDEX IF NOT EXISTS idx_audit_logs_auth_events 
    ON memory_service.audit_logs(event_type, timestamp DESC) 
    WHERE event_type LIKE 'auth_%' OR event_type LIKE 'key_%';

CREATE INDEX IF NOT EXISTS idx_audit_logs_failed_events 
    ON memory_service.audit_logs(timestamp DESC) 
    WHERE success = false;

-- GIN index for metadata search
CREATE INDEX IF NOT EXISTS idx_audit_logs_metadata 
    ON memory_service.audit_logs USING GIN (metadata);

-- ═══════════════════════════════════════════════════════════════════════════
-- Retention Policy Function
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION memory_service.cleanup_audit_logs(
    general_retention_days INTEGER DEFAULT 90,
    auth_retention_days INTEGER DEFAULT 365
) RETURNS TABLE (
    deleted_general INTEGER,
    deleted_auth INTEGER
) AS $$
DECLARE
    cutoff_general TIMESTAMPTZ;
    cutoff_auth TIMESTAMPTZ;
    count_general INTEGER;
    count_auth INTEGER;
BEGIN
    cutoff_general := now() - (general_retention_days || ' days')::INTERVAL;
    cutoff_auth := now() - (auth_retention_days || ' days')::INTERVAL;
    
    -- Delete general logs older than retention period
    DELETE FROM memory_service.audit_logs
    WHERE timestamp < cutoff_general
      AND event_type NOT LIKE 'auth_%'
      AND event_type NOT LIKE 'key_%'
      AND event_type NOT LIKE 'gdpr_%';
    
    GET DIAGNOSTICS count_general = ROW_COUNT;
    
    -- Delete auth/key logs older than auth retention period
    DELETE FROM memory_service.audit_logs
    WHERE timestamp < cutoff_auth
      AND (event_type LIKE 'auth_%' OR event_type LIKE 'key_%');
    
    GET DIAGNOSTICS count_auth = ROW_COUNT;
    
    deleted_general := count_general;
    deleted_auth := count_auth;
    
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════════════════════════════════════════════
-- Helper Views for Common Queries
-- ═══════════════════════════════════════════════════════════════════════════

-- Recent authentication events
CREATE OR REPLACE VIEW memory_service.recent_auth_events AS
SELECT 
    id,
    event_type,
    timestamp,
    user_id,
    ip_address,
    success,
    message,
    metadata->>'email' AS email,
    metadata->>'method' AS auth_method
FROM memory_service.audit_logs
WHERE event_type LIKE 'auth_%'
  AND timestamp > now() - INTERVAL '7 days'
ORDER BY timestamp DESC;

-- Failed login attempts (for security monitoring)
CREATE OR REPLACE VIEW memory_service.failed_logins AS
SELECT 
    id,
    timestamp,
    ip_address,
    user_agent,
    metadata->>'email' AS email,
    metadata->>'method' AS auth_method,
    metadata->>'failure_reason' AS reason
FROM memory_service.audit_logs
WHERE event_type = 'auth_login_failed'
  AND timestamp > now() - INTERVAL '24 hours'
ORDER BY timestamp DESC;

-- API usage summary (per tenant, last 24h)
CREATE OR REPLACE VIEW memory_service.api_usage_24h AS
SELECT 
    tenant_id,
    COUNT(*) AS total_calls,
    COUNT(*) FILTER (WHERE success = true) AS successful_calls,
    COUNT(*) FILTER (WHERE success = false) AS failed_calls,
    COUNT(DISTINCT ip_address) AS unique_ips,
    MAX(timestamp) AS last_call
FROM memory_service.audit_logs
WHERE event_type = 'api_call'
  AND timestamp > now() - INTERVAL '24 hours'
GROUP BY tenant_id
ORDER BY total_calls DESC;

-- ═══════════════════════════════════════════════════════════════════════════
-- Grant Permissions
-- ═══════════════════════════════════════════════════════════════════════════

-- Assuming a role 'memory_service_api' exists (or using public for dev)
-- GRANT SELECT, INSERT ON memory_service.audit_logs TO memory_service_api;
-- GRANT SELECT ON memory_service.recent_auth_events TO memory_service_api;
-- GRANT SELECT ON memory_service.failed_logins TO memory_service_api;
-- GRANT SELECT ON memory_service.api_usage_24h TO memory_service_api;

-- ═══════════════════════════════════════════════════════════════════════════
-- Verification
-- ═══════════════════════════════════════════════════════════════════════════

SELECT 
    'audit_logs table' AS component,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'memory_service' 
          AND table_name = 'audit_logs'
    ) THEN '✓ Created' ELSE '✗ Missing' END AS status
UNION ALL
SELECT 
    'indexes' AS component,
    COUNT(*)::TEXT || ' indexes created' AS status
FROM pg_indexes
WHERE schemaname = 'memory_service' 
  AND tablename = 'audit_logs'
UNION ALL
SELECT 
    'cleanup function' AS component,
    CASE WHEN EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'memory_service'
          AND p.proname = 'cleanup_audit_logs'
    ) THEN '✓ Created' ELSE '✗ Missing' END AS status;
