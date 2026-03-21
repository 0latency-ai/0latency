-- Migration 003: Audit fixes — RLS WITH CHECK, vector index
-- Fixes C1 from Claude Code audit

BEGIN;

-- C1: Add WITH CHECK to all RLS policies (fixes INSERT/UPDATE bypass)

-- Memories
DROP POLICY IF EXISTS tenant_isolation_memories ON memory_service.memories;
CREATE POLICY tenant_isolation_memories ON memory_service.memories
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Entity Index
DROP POLICY IF EXISTS tenant_isolation_entity_index ON memory_service.entity_index;
CREATE POLICY tenant_isolation_entity_index ON memory_service.entity_index
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Memory Edges
DROP POLICY IF EXISTS tenant_isolation_memory_edges ON memory_service.memory_edges;
CREATE POLICY tenant_isolation_memory_edges ON memory_service.memory_edges
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Memory Clusters
DROP POLICY IF EXISTS tenant_isolation_memory_clusters ON memory_service.memory_clusters;
CREATE POLICY tenant_isolation_memory_clusters ON memory_service.memory_clusters
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Topic Coverage
DROP POLICY IF EXISTS tenant_isolation_topic_coverage ON memory_service.topic_coverage;
CREATE POLICY tenant_isolation_topic_coverage ON memory_service.topic_coverage
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Audit Log
DROP POLICY IF EXISTS tenant_isolation_audit_log ON memory_service.memory_audit_log;
CREATE POLICY tenant_isolation_audit_log ON memory_service.memory_audit_log
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Session Handoffs
DROP POLICY IF EXISTS tenant_isolation_handoffs ON memory_service.session_handoffs;
CREATE POLICY tenant_isolation_handoffs ON memory_service.session_handoffs
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Agent Config
DROP POLICY IF EXISTS tenant_isolation_agent_config ON memory_service.agent_config;
CREATE POLICY tenant_isolation_agent_config ON memory_service.agent_config
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- API Usage
DROP POLICY IF EXISTS tenant_isolation_api_usage ON memory_service.api_usage;
CREATE POLICY tenant_isolation_api_usage ON memory_service.api_usage
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Memory Versions
DROP POLICY IF EXISTS tenant_isolation_memory_versions ON memory_service.memory_versions;
CREATE POLICY tenant_isolation_memory_versions ON memory_service.memory_versions
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Entity Nodes
DROP POLICY IF EXISTS tenant_isolation_entity_nodes ON memory_service.entity_nodes;
CREATE POLICY tenant_isolation_entity_nodes ON memory_service.entity_nodes
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Entity Relationships
DROP POLICY IF EXISTS tenant_isolation_entity_rels ON memory_service.entity_relationships;
CREATE POLICY tenant_isolation_entity_rels ON memory_service.entity_relationships
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Add IVFFLAT index on memories.embedding (fixes M-series performance issue)
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memory_service.memories 
    USING ivfflat (embedding extensions.vector_cosine_ops) WITH (lists = 50);

COMMIT;
