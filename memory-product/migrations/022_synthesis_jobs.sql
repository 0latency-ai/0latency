-- Migration 022: synthesis_jobs table for persistent async job state
-- Replaces in-memory dict; survives memory-api restarts.

CREATE TABLE memory_service.synthesis_jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
  agent_id        text NOT NULL,
  job_type        text NOT NULL,  -- 'synthesis_run', 'cluster_then_synthesize', 'manual_trigger'
  status          text NOT NULL DEFAULT 'queued',
                                  -- 'queued', 'running', 'succeeded', 'failed', 'cancelled'
  payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
                                  -- request params, e.g. {role_scope, recency_window, force}
  result          jsonb,          -- final output: cluster_count, synthesis_ids[], tokens_used
  error           text,           -- truncated error message on failure
  created_at      timestamptz NOT NULL DEFAULT now(),
  started_at      timestamptz,
  completed_at    timestamptz,

  CONSTRAINT synthesis_jobs_status_check CHECK (
    status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
  ),
  CONSTRAINT synthesis_jobs_job_type_check CHECK (
    job_type IN ('synthesis_run', 'cluster_then_synthesize', 'manual_trigger')
  )
);

CREATE INDEX idx_synthesis_jobs_tenant_id ON memory_service.synthesis_jobs(tenant_id);
CREATE INDEX idx_synthesis_jobs_status ON memory_service.synthesis_jobs(status)
  WHERE status IN ('queued', 'running');
CREATE INDEX idx_synthesis_jobs_created_at ON memory_service.synthesis_jobs(created_at DESC);
CREATE INDEX idx_synthesis_jobs_tenant_agent ON memory_service.synthesis_jobs(tenant_id, agent_id);

-- DOWN (manual rollback):
-- DROP INDEX IF EXISTS memory_service.idx_synthesis_jobs_tenant_agent;
-- DROP INDEX IF EXISTS memory_service.idx_synthesis_jobs_created_at;
-- DROP INDEX IF EXISTS memory_service.idx_synthesis_jobs_status;
-- DROP INDEX IF EXISTS memory_service.idx_synthesis_jobs_tenant_id;
-- DROP TABLE IF EXISTS memory_service.synthesis_jobs;
