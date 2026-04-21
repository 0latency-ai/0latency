-- Migration 013: Analytics events table
-- Tracks user events for dashboard metrics and PostHog integration

BEGIN;

-- Create analytics_events table
CREATE TABLE IF NOT EXISTS memory_service.analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_analytics_events_tenant_id 
    ON memory_service.analytics_events(tenant_id);

CREATE INDEX IF NOT EXISTS idx_analytics_events_event_type 
    ON memory_service.analytics_events(event_type);

CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at 
    ON memory_service.analytics_events(created_at);

-- Composite index for tenant + event_type queries
CREATE INDEX IF NOT EXISTS idx_analytics_events_tenant_event 
    ON memory_service.analytics_events(tenant_id, event_type);

-- Composite index for tenant + created_at (time-range queries)
CREATE INDEX IF NOT EXISTS idx_analytics_events_tenant_created 
    ON memory_service.analytics_events(tenant_id, created_at);

-- Enable Row Level Security
ALTER TABLE memory_service.analytics_events ENABLE ROW LEVEL SECURITY;

-- RLS Policy: tenant isolation
DROP POLICY IF EXISTS tenant_isolation_analytics_events ON memory_service.analytics_events;
CREATE POLICY tenant_isolation_analytics_events ON memory_service.analytics_events
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

COMMIT;
