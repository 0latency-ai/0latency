-- Migration 011: Error Logs and Observability Tables
-- Adds comprehensive error tracking, performance metrics, and alerting tables

-- Error logs table - stores individual error occurrences
CREATE TABLE IF NOT EXISTS error_logs (
    id SERIAL PRIMARY KEY,
    error_hash VARCHAR(16) NOT NULL,  -- Hash for grouping similar errors
    error_type VARCHAR(255) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    level VARCHAR(20) NOT NULL,  -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    -- Context
    tenant_id VARCHAR(50),
    request_id VARCHAR(100),
    user_agent TEXT,
    ip_address VARCHAR(45),
    endpoint VARCHAR(500),
    context JSONB,  -- Additional context as JSON
    
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for error_logs
CREATE INDEX IF NOT EXISTS idx_error_logs_hash ON error_logs(error_hash);
CREATE INDEX IF NOT EXISTS idx_error_logs_tenant ON error_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_error_logs_occurred ON error_logs(occurred_at);
CREATE INDEX IF NOT EXISTS idx_error_logs_level ON error_logs(level);
CREATE INDEX IF NOT EXISTS idx_error_logs_endpoint ON error_logs(endpoint);

-- Error groups table - aggregates similar errors
CREATE TABLE IF NOT EXISTS error_groups (
    error_hash VARCHAR(16) PRIMARY KEY,
    error_type VARCHAR(255) NOT NULL,
    sample_message TEXT NOT NULL,
    sample_stack_trace TEXT,
    
    -- Aggregation stats
    first_seen TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL,
    occurrence_count INTEGER DEFAULT 1,
    affected_tenants TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    level VARCHAR(20) NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(100)
);

-- Indexes for error_groups
CREATE INDEX IF NOT EXISTS idx_error_groups_last_seen ON error_groups(last_seen);
CREATE INDEX IF NOT EXISTS idx_error_groups_occurrence ON error_groups(occurrence_count);
CREATE INDEX IF NOT EXISTS idx_error_groups_resolved ON error_groups(resolved);

-- Performance metrics table - stores periodic snapshots
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Endpoint performance (stored as TEXT for flexibility)
    endpoint_stats TEXT,
    
    -- Database performance
    database_stats TEXT,
    
    -- External API performance (OpenAI, etc.)
    embedding_stats TEXT,
    
    -- System resources
    system_stats TEXT
);

-- Index for performance_metrics
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp);

-- Alerts table - tracks all alerts sent
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(100) NOT NULL,  -- high_error_rate, database_failure, etc.
    level VARCHAR(20) NOT NULL,  -- INFO, WARNING, ERROR, CRITICAL
    message TEXT NOT NULL,
    context TEXT,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for alerts
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts(sent_at);

-- Add comments for documentation
COMMENT ON TABLE error_logs IS 'Individual error occurrences with full context';
COMMENT ON TABLE error_groups IS 'Aggregated error groups for deduplication and analysis';
COMMENT ON TABLE performance_metrics IS 'Periodic snapshots of API and system performance';
COMMENT ON TABLE alerts IS 'History of all alerts sent to monitoring channels';

-- Create view for recent errors (last 24 hours)
CREATE OR REPLACE VIEW recent_errors AS
SELECT 
    eg.error_hash,
    eg.error_type,
    eg.sample_message,
    eg.occurrence_count,
    eg.affected_tenants,
    array_length(eg.affected_tenants, 1) as affected_tenant_count,
    eg.first_seen,
    eg.last_seen,
    eg.level,
    COUNT(el.id) as last_24h_count
FROM error_groups eg
LEFT JOIN error_logs el ON eg.error_hash = el.error_hash 
    AND el.occurred_at > NOW() - INTERVAL '24 hours'
WHERE eg.last_seen > NOW() - INTERVAL '7 days'
GROUP BY eg.error_hash, eg.error_type, eg.sample_message, eg.occurrence_count,
         eg.affected_tenants, eg.first_seen, eg.last_seen, eg.level
ORDER BY eg.last_seen DESC;

COMMENT ON VIEW recent_errors IS 'Recent error groups with 24-hour occurrence counts';

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT ON error_logs, error_groups, performance_metrics, alerts TO readonly_user;
-- GRANT ALL ON error_logs, error_groups, performance_metrics, alerts TO app_user;
