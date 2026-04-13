-- Add local_embedding column for local model (384 dimensions for all-MiniLM-L6-v2)
ALTER TABLE memory_service.memories ADD COLUMN IF NOT EXISTS local_embedding vector(384);

-- Create HNSW index for local embeddings (faster than IVFFlat for reads)
CREATE INDEX IF NOT EXISTS idx_memories_local_embedding_hnsw 
ON memory_service.memories USING hnsw (local_embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

-- Create IVFFlat index as backup (for compatibility)
CREATE INDEX IF NOT EXISTS idx_memories_local_embedding_ivf
ON memory_service.memories USING ivfflat (local_embedding vector_cosine_ops)
WITH (lists = 50);
