-- Migration 002: Feature parity — graph memory, versioning, webhooks, org memory, criteria retrieval
-- Closes 8 gaps vs mem0 competitive analysis

BEGIN;

-- 1. Memory Versions (audit trail / history)
CREATE TABLE IF NOT EXISTS memory_service.memory_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    memory_id UUID NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    headline TEXT NOT NULL,
    context TEXT,
    full_content TEXT,
    memory_type TEXT,
    importance FLOAT,
    confidence FLOAT,
    changed_by TEXT DEFAULT 'system',  -- 'system', 'api', 'extraction'
    change_reason TEXT,                -- 'contradiction', 'reinforcement', 'manual_update'
    created_at TIMESTAMPTZ DEFAULT now(),
    diff_summary TEXT                  -- human-readable "changed importance 0.5→0.8"
);

CREATE INDEX IF NOT EXISTS idx_memory_versions_memory ON memory_service.memory_versions(memory_id, version_number);
CREATE INDEX IF NOT EXISTS idx_memory_versions_tenant ON memory_service.memory_versions(tenant_id);

ALTER TABLE memory_service.memory_versions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_memory_versions ON memory_service.memory_versions;
CREATE POLICY tenant_isolation_memory_versions ON memory_service.memory_versions
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 2. Organization / Team Memory
ALTER TABLE memory_service.tenants 
ADD COLUMN IF NOT EXISTS org_id UUID;

CREATE TABLE IF NOT EXISTS memory_service.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

-- Org-scoped shared memories
CREATE TABLE IF NOT EXISTS memory_service.org_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES memory_service.organizations(id),
    headline TEXT NOT NULL,
    context TEXT,
    full_content TEXT,
    memory_type TEXT DEFAULT 'fact',
    importance FLOAT DEFAULT 0.5,
    entities TEXT[] DEFAULT '{}',
    categories TEXT[] DEFAULT '{}',
    embedding extensions.vector(768),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_by UUID REFERENCES memory_service.tenants(id),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_org_memories_org ON memory_service.org_memories(org_id);
CREATE INDEX IF NOT EXISTS idx_org_memories_embedding ON memory_service.org_memories 
    USING ivfflat (embedding extensions.vector_cosine_ops) WITH (lists = 10);

-- 3. Graph Memory — lightweight using existing tables + new traversal support
-- We already have entity_index and memory_edges. Add richer relationship types.
ALTER TABLE memory_service.memory_edges 
ADD COLUMN IF NOT EXISTS relationship_type TEXT DEFAULT 'related_to',
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

-- Entity nodes table for proper graph structure
CREATE TABLE IF NOT EXISTS memory_service.entity_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    agent_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    entity_type TEXT DEFAULT 'unknown',  -- person, org, project, concept, location
    summary TEXT,                        -- evolving summary of what we know
    first_seen TIMESTAMPTZ DEFAULT now(),
    last_seen TIMESTAMPTZ DEFAULT now(),
    mention_count INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    UNIQUE(tenant_id, agent_id, entity_name)
);

CREATE INDEX IF NOT EXISTS idx_entity_nodes_tenant ON memory_service.entity_nodes(tenant_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_entity_nodes_name ON memory_service.entity_nodes(entity_name);

ALTER TABLE memory_service.entity_nodes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_entity_nodes ON memory_service.entity_nodes;
CREATE POLICY tenant_isolation_entity_nodes ON memory_service.entity_nodes
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Entity-to-entity relationships (the actual graph edges)
CREATE TABLE IF NOT EXISTS memory_service.entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    agent_id TEXT NOT NULL,
    source_entity TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    relationship TEXT NOT NULL,          -- 'works_at', 'reports_to', 'part_of', 'related_to'
    strength FLOAT DEFAULT 0.5,
    evidence_memory_id UUID,             -- which memory established this
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, agent_id, source_entity, target_entity, relationship)
);

CREATE INDEX IF NOT EXISTS idx_entity_rels_tenant ON memory_service.entity_relationships(tenant_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_entity_rels_source ON memory_service.entity_relationships(source_entity);
CREATE INDEX IF NOT EXISTS idx_entity_rels_target ON memory_service.entity_relationships(target_entity);

ALTER TABLE memory_service.entity_relationships ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_entity_rels ON memory_service.entity_relationships;
CREATE POLICY tenant_isolation_entity_rels ON memory_service.entity_relationships
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 4. Webhooks
CREATE TABLE IF NOT EXISTS memory_service.webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    url TEXT NOT NULL,
    events TEXT[] NOT NULL DEFAULT '{}',  -- 'memory.created', 'memory.updated', 'memory.deleted', 'memory.corrected'
    secret TEXT,                          -- HMAC signing secret
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_triggered TIMESTAMPTZ,
    failure_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_webhooks_tenant ON memory_service.webhooks(tenant_id);

-- Webhook delivery log
CREATE TABLE IF NOT EXISTS memory_service.webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES memory_service.webhooks(id),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status_code INTEGER,
    response_body TEXT,
    delivered_at TIMESTAMPTZ DEFAULT now(),
    success BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON memory_service.webhook_deliveries(webhook_id, delivered_at DESC);

-- 5. Criteria Retrieval — custom scoring attributes per tenant
CREATE TABLE IF NOT EXISTS memory_service.recall_criteria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL,              -- 'urgency', 'joy', 'negativity', 'confidence'
    weight FLOAT DEFAULT 0.5,       -- how much this criteria affects scoring
    description TEXT,                -- human-readable description
    scoring_prompt TEXT,             -- LLM prompt fragment for scoring memories on this criteria
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, agent_id, name)
);

CREATE INDEX IF NOT EXISTS idx_recall_criteria_tenant ON memory_service.recall_criteria(tenant_id, agent_id);

-- Memory criteria scores (cached LLM-scored values)
CREATE TABLE IF NOT EXISTS memory_service.memory_criteria_scores (
    memory_id UUID NOT NULL,
    criteria_id UUID NOT NULL REFERENCES memory_service.recall_criteria(id),
    score FLOAT NOT NULL,            -- 0.0-1.0
    scored_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (memory_id, criteria_id)
);

-- 6. Structured JSON Schemas — developer-defined extraction templates
CREATE TABLE IF NOT EXISTS memory_service.extraction_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
    name TEXT NOT NULL,
    schema_definition JSONB NOT NULL,  -- JSON Schema describing custom fields
    extraction_prompt TEXT,            -- custom extraction instructions
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, name)
);

-- Add custom_fields to memories for schema-driven extraction
ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS custom_fields JSONB DEFAULT '{}';

-- 7. Add version tracking column to memories
ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

COMMIT;
