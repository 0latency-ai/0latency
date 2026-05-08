-- Migration 026: Add decision journal structured columns
-- Tier 2: Additive schema change (5 nullable columns + partial index + partial CHECK)
-- Prerequisites: memory_type='decision' already in CHECK constraint (verified)

ALTER TABLE memory_service.memories
  ADD COLUMN IF NOT EXISTS decision_text text,
  ADD COLUMN IF NOT EXISTS alternatives_considered text[],
  ADD COLUMN IF NOT EXISTS rationale text,
  ADD COLUMN IF NOT EXISTS predicted_outcome text,
  ADD COLUMN IF NOT EXISTS actual_outcome text;

-- Index on decision rows for retrieval-by-type queries
CREATE INDEX IF NOT EXISTS idx_memories_decision_tenant_agent
  ON memory_service.memories (tenant_id, agent_id, created_at DESC)
  WHERE memory_type = 'decision';

-- Validation: decision rows MUST have decision_text + rationale populated.
-- Enforced via partial CHECK so non-decision rows are unaffected.
ALTER TABLE memory_service.memories
  ADD CONSTRAINT check_decision_required_fields
  CHECK (
    memory_type != 'decision'
    OR (decision_text IS NOT NULL AND rationale IS NOT NULL)
  );
