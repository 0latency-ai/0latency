-- Migration 025: CP8 P5.2 audit events query composite index
-- Tier 1: additive, reversible, CONCURRENTLY applied (no table lock)
-- Problem: Audit log queries filter by tenant_id and sort by occurred_at DESC.
--          Existing single-column indexes on each field force a sequential scan or inefficient merge.
-- Solution: Composite index (tenant_id, occurred_at DESC) for direct seek + sorted scan.
-- Reversible: Can drop if query patterns change (unlikely — time-series + tenant filtering is core to audit).

-- Up migration
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_synthesis_audit_events_tenant_time
  ON memory_service.synthesis_audit_events (tenant_id, occurred_at DESC);
