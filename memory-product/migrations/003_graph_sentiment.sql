-- Migration 005: Graph + Sentiment + Confidence enhancements
-- Adds sentiment analysis, recall tracking, and improves graph capabilities
-- All changes are backward-compatible (additive only)

-- ============================================================
-- 1. Add sentiment columns to memories table
-- ============================================================

ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS sentiment VARCHAR(16);  -- 'positive', 'negative', 'neutral'

ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS sentiment_score FLOAT;

ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS sentiment_intensity FLOAT;

-- Add CHECK constraints (safe for existing NULL rows)
DO $$ BEGIN
    ALTER TABLE memory_service.memories 
    ADD CONSTRAINT chk_sentiment_score CHECK (sentiment_score >= -1 AND sentiment_score <= 1);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE memory_service.memories 
    ADD CONSTRAINT chk_sentiment_intensity CHECK (sentiment_intensity >= 0 AND sentiment_intensity <= 1);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- 2. Add recall tracking columns to memories table
-- ============================================================

ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS recall_count INT DEFAULT 0;

ALTER TABLE memory_service.memories 
ADD COLUMN IF NOT EXISTS last_recalled_at TIMESTAMPTZ;

-- ============================================================
-- 3. Add confidence constraint (column already exists, add CHECK)
-- ============================================================

DO $$ BEGIN
    ALTER TABLE memory_service.memories 
    ADD CONSTRAINT chk_confidence CHECK (confidence >= 0 AND confidence <= 1);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- 4. Create indexes for new columns
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_memories_sentiment 
ON memory_service.memories(sentiment) 
WHERE sentiment IS NOT NULL AND superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_memories_sentiment_score 
ON memory_service.memories(sentiment_score) 
WHERE sentiment_score IS NOT NULL AND superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_memories_recall_count 
ON memory_service.memories(recall_count DESC) 
WHERE superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_memories_confidence 
ON memory_service.memories(confidence) 
WHERE superseded_at IS NULL;

-- ============================================================
-- 5. Add relationship_type column to entity_relationships if missing
-- ============================================================

-- The existing entity_relationships table has 'relationship' VARCHAR(128).
-- The spec wants specific types. We'll add a check constraint for known types
-- but allow custom types too.

-- Add strength index for graph traversal filtering
CREATE INDEX IF NOT EXISTS idx_entity_rels_strength 
ON memory_service.entity_relationships(strength DESC) 
WHERE strength > 0.3;

-- ============================================================
-- 6. Add entity_type index for faster type-based queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_entity_nodes_type 
ON memory_service.entity_nodes(entity_type) 
WHERE entity_type IS NOT NULL;

-- ============================================================
-- 7. Composite index for common query patterns
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_memories_agent_sentiment 
ON memory_service.memories(agent_id, tenant_id, sentiment) 
WHERE superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_entity_index_agent_entity 
ON memory_service.entity_index(agent_id, entity);

-- ============================================================
-- Done. All changes are additive and backward-compatible.
-- Existing data is unaffected (new columns default to NULL/0).
-- ============================================================
