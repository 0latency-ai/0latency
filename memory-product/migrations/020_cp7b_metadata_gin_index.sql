-- Migration 020: CP7b metadata GIN index
-- Closes the operational gap from CP7b Phase 1.
-- The handoff doc claims this index shipped; prod inspection on 2026-04-28 showed it absent.
-- 103 session_checkpoint rows already exist in prod; this index makes their metadata queryable at speed.
-- CONCURRENTLY: no table lock during build. Cannot run inside a transaction.
-- IF NOT EXISTS: idempotent.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_memories_metadata_gin
  ON memory_service.memories USING gin (metadata);
