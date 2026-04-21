-- Migration 001: Add multi-tenant support with Row Level Security
-- Phase B production infrastructure

BEGIN;

-- 1. Create tenants table first (needed for foreign keys)
CREATE TABLE IF NOT EXISTS memory_service.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    api_key_hash TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    memory_limit INTEGER DEFAULT 10000,  -- max memories per tenant
    rate_limit_rpm INTEGER DEFAULT 60,   -- requests per minute
    active BOOLEAN DEFAULT true,
    api_calls_count BIGINT DEFAULT 0,
    last_api_call TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- 2. Add tenant_id columns to all existing tables
ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES memory_service.tenants(id);

ALTER TABLE memory_service.entity_index 
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES memory_service.tenants(id);

ALTER TABLE memory_service.memory_edges 
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES memory_service.tenants(id);

ALTER TABLE memory_service.memory_clusters 
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES memory_service.tenants(id);

ALTER TABLE memory_service.topic_coverage 
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES memory_service.tenants(id);

ALTER TABLE memory_service.memory_audit_log 
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES memory_service.tenants(id);

ALTER TABLE memory_service.session_handoffs 
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES memory_service.tenants(id);

ALTER TABLE memory_service.agent_config 
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES memory_service.tenants(id);

-- 3. Create default tenant for existing data (using placeholder hash)
INSERT INTO memory_service.tenants (id, name, api_key_hash, plan, memory_limit, rate_limit_rpm)
VALUES (
    '00000000-0000-0000-0000-000000000000'::UUID,
    'Default Tenant', 
    'placeholder_hash_for_migration',
    'pro',
    100000,
    300
) ON CONFLICT (api_key_hash) DO NOTHING;

-- 4. Backfill existing data with default tenant_id
UPDATE memory_service.memories 
SET tenant_id = '00000000-0000-0000-0000-000000000000'::UUID 
WHERE tenant_id IS NULL;

UPDATE memory_service.entity_index 
SET tenant_id = '00000000-0000-0000-0000-000000000000'::UUID 
WHERE tenant_id IS NULL;

UPDATE memory_service.memory_edges 
SET tenant_id = '00000000-0000-0000-0000-000000000000'::UUID 
WHERE tenant_id IS NULL;

UPDATE memory_service.memory_clusters 
SET tenant_id = '00000000-0000-0000-0000-000000000000'::UUID 
WHERE tenant_id IS NULL;

UPDATE memory_service.topic_coverage 
SET tenant_id = '00000000-0000-0000-0000-000000000000'::UUID 
WHERE tenant_id IS NULL;

UPDATE memory_service.memory_audit_log 
SET tenant_id = '00000000-0000-0000-0000-000000000000'::UUID 
WHERE tenant_id IS NULL;

UPDATE memory_service.session_handoffs 
SET tenant_id = '00000000-0000-0000-0000-000000000000'::UUID 
WHERE tenant_id IS NULL;

UPDATE memory_service.agent_config 
SET tenant_id = '00000000-0000-0000-0000-000000000000'::UUID 
WHERE tenant_id IS NULL;

-- 5. Make tenant_id NOT NULL after backfill
ALTER TABLE memory_service.memories ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE memory_service.entity_index ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE memory_service.memory_edges ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE memory_service.memory_clusters ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE memory_service.topic_coverage ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE memory_service.memory_audit_log ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE memory_service.session_handoffs ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE memory_service.agent_config ALTER COLUMN tenant_id SET NOT NULL;

-- 6. Create usage tracking table
CREATE TABLE IF NOT EXISTS memory_service.api_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    endpoint TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT now(),
    tokens_used INTEGER DEFAULT 0,
    response_time_ms INTEGER DEFAULT 0,
    status_code INTEGER DEFAULT 200,
    metadata JSONB DEFAULT '{}'
);

-- 7. Enable Row Level Security on all tables
ALTER TABLE memory_service.memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_service.entity_index ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_service.memory_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_service.memory_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_service.topic_coverage ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_service.memory_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_service.session_handoffs ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_service.agent_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_service.api_usage ENABLE ROW LEVEL SECURITY;

-- 8. Create RLS policies (tenant isolation)
-- Each tenant can only see their own data

-- Memories
DROP POLICY IF EXISTS tenant_isolation_memories ON memory_service.memories;
CREATE POLICY tenant_isolation_memories ON memory_service.memories
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Entity Index
DROP POLICY IF EXISTS tenant_isolation_entity_index ON memory_service.entity_index;
CREATE POLICY tenant_isolation_entity_index ON memory_service.entity_index
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Memory Edges
DROP POLICY IF EXISTS tenant_isolation_memory_edges ON memory_service.memory_edges;
CREATE POLICY tenant_isolation_memory_edges ON memory_service.memory_edges
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Memory Clusters
DROP POLICY IF EXISTS tenant_isolation_memory_clusters ON memory_service.memory_clusters;
CREATE POLICY tenant_isolation_memory_clusters ON memory_service.memory_clusters
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Topic Coverage
DROP POLICY IF EXISTS tenant_isolation_topic_coverage ON memory_service.topic_coverage;
CREATE POLICY tenant_isolation_topic_coverage ON memory_service.topic_coverage
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Audit Log
DROP POLICY IF EXISTS tenant_isolation_audit_log ON memory_service.memory_audit_log;
CREATE POLICY tenant_isolation_audit_log ON memory_service.memory_audit_log
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Session Handoffs
DROP POLICY IF EXISTS tenant_isolation_handoffs ON memory_service.session_handoffs;
CREATE POLICY tenant_isolation_handoffs ON memory_service.session_handoffs
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Agent Config
DROP POLICY IF EXISTS tenant_isolation_agent_config ON memory_service.agent_config;
CREATE POLICY tenant_isolation_agent_config ON memory_service.agent_config
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- API Usage
DROP POLICY IF EXISTS tenant_isolation_api_usage ON memory_service.api_usage;
CREATE POLICY tenant_isolation_api_usage ON memory_service.api_usage
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 9. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_memories_tenant ON memory_service.memories(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entity_index_tenant ON memory_service.entity_index(tenant_id);
CREATE INDEX IF NOT EXISTS idx_memory_edges_tenant ON memory_service.memory_edges(tenant_id);
CREATE INDEX IF NOT EXISTS idx_memory_clusters_tenant ON memory_service.memory_clusters(tenant_id);
CREATE INDEX IF NOT EXISTS idx_topic_coverage_tenant ON memory_service.topic_coverage(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON memory_service.memory_audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_session_handoffs_tenant ON memory_service.session_handoffs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_config_tenant ON memory_service.agent_config(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_tenant ON memory_service.api_usage(tenant_id, timestamp);

-- 10. Create composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_memories_tenant_agent ON memory_service.memories(tenant_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_tenant_endpoint_time ON memory_service.api_usage(tenant_id, endpoint, timestamp);

-- 11. Create helper function for setting tenant context
CREATE OR REPLACE FUNCTION memory_service.set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::text, true);
END;
$$ LANGUAGE plpgsql;

COMMIT;