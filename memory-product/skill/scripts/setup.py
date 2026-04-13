#!/usr/bin/env python3
"""
Memory Engine — Database Setup
Creates the memory_service schema and all required tables in Postgres.
"""

import os
import sys
import subprocess


DB_CONN = os.environ.get("MEMORY_DB_CONN", "")

if not DB_CONN:
    print("❌ MEMORY_DB_CONN not set. Please set your Postgres connection string:")
    print('   export MEMORY_DB_CONN="postgresql://postgres.[ref]:[password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres"')
    sys.exit(1)


SCHEMA_SQL = """
-- Enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector SCHEMA extensions;

-- Create schema
CREATE SCHEMA IF NOT EXISTS memory_service;

-- Memories table
CREATE TABLE IF NOT EXISTS memory_service.memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL DEFAULT 'default',
    headline TEXT NOT NULL,
    context TEXT,
    full_content TEXT,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('fact', 'preference', 'decision', 'task', 'correction', 'relationship', 'identity')),
    entities TEXT[] DEFAULT '{}',
    project TEXT,
    categories TEXT[] DEFAULT '{}',
    scope TEXT DEFAULT '/',
    importance FLOAT DEFAULT 0.5,
    confidence FLOAT DEFAULT 0.8,
    relevance_score FLOAT DEFAULT 1.0,
    access_count INT DEFAULT 0,
    reinforcement_count INT DEFAULT 1,
    valid_from TIMESTAMPTZ DEFAULT now(),
    superseded_at TIMESTAMPTZ,
    superseded_by UUID,
    embedding extensions.vector(768),
    source_session TEXT,
    source_turn TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_accessed TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}',
    recall_count INT DEFAULT 0,
    recall_used_count INT DEFAULT 0,
    recall_ignored_count INT DEFAULT 0,
    expires_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_memories_agent ON memory_service.memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memory_service.memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memory_service.memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memory_service.memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memory_service.memories USING ivfflat (embedding extensions.vector_cosine_ops) WITH (lists = 100);

-- Session handoffs
CREATE TABLE IF NOT EXISTS memory_service.session_handoffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    session_key TEXT,
    summary TEXT,
    decisions_made JSONB DEFAULT '[]',
    open_threads JSONB DEFAULT '[]',
    active_projects JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_handoffs_agent ON memory_service.session_handoffs(agent_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_created ON memory_service.session_handoffs(created_at DESC);

-- Entity index (for cross-entity linking)
CREATE TABLE IF NOT EXISTS memory_service.entity_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    entity TEXT NOT NULL,
    memory_id UUID REFERENCES memory_service.memories(id),
    entity_type TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entity_agent ON memory_service.entity_index(agent_id);
CREATE INDEX IF NOT EXISTS idx_entity_name ON memory_service.entity_index(entity);

-- Memory edges (relationships between memories)
CREATE TABLE IF NOT EXISTS memory_service.memory_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    source_memory_id UUID REFERENCES memory_service.memories(id),
    target_memory_id UUID REFERENCES memory_service.memories(id),
    relationship TEXT,
    strength FLOAT DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

-- Topic coverage (negative recall)
CREATE TABLE IF NOT EXISTS memory_service.topic_coverage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    scope TEXT DEFAULT '/',
    first_discussed TIMESTAMPTZ DEFAULT now(),
    last_discussed TIMESTAMPTZ DEFAULT now(),
    discussion_count INT DEFAULT 1,
    depth TEXT DEFAULT 'shallow',
    known_gaps TEXT[],
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_topics_agent ON memory_service.topic_coverage(agent_id);

-- Memory clusters (compaction)
CREATE TABLE IF NOT EXISTS memory_service.memory_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    cluster_name TEXT,
    summary TEXT,
    member_memory_ids UUID[],
    member_count INT DEFAULT 0,
    centroid_embedding extensions.vector(768),
    importance_avg FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

-- Agent config
CREATE TABLE IF NOT EXISTS memory_service.agent_config (
    agent_id TEXT PRIMARY KEY,
    context_budget INT DEFAULT 4000,
    recency_weight FLOAT DEFAULT 0.35,
    semantic_weight FLOAT DEFAULT 0.4,
    importance_weight FLOAT DEFAULT 0.15,
    access_weight FLOAT DEFAULT 0.1,
    recency_half_life_days INT DEFAULT 14,
    extraction_model TEXT DEFAULT 'gemini-2.0-flash',
    embedding_model TEXT DEFAULT 'gemini-embedding-001',
    identity JSONB DEFAULT '{}',
    user_profile JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

-- Audit log
CREATE TABLE IF NOT EXISTS memory_service.memory_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    action TEXT NOT NULL,
    memory_id UUID,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_agent ON memory_service.memory_audit_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON memory_service.memory_audit_log(created_at DESC);

SELECT 'Memory Engine schema created successfully!' AS status;
"""


def main():
    print("🧠 Memory Engine — Database Setup")
    print(f"   Connecting to: {DB_CONN[:50]}...")
    
    # Extract password for PGPASSWORD
    # Format: postgresql://user:password@host:port/db
    password = ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(DB_CONN)
        password = parsed.password or ""
    except:
        pass
    
    env = {**os.environ}
    if password:
        env["PGPASSWORD"] = password
    
    result = subprocess.run(
        ["psql", DB_CONN, "-c", SCHEMA_SQL],
        capture_output=True, text=True, timeout=30,
        env=env
    )
    
    if result.returncode != 0:
        print(f"❌ Setup failed: {result.stderr}")
        
        if "pgvector" in result.stderr.lower() or "vector" in result.stderr.lower():
            print("\n💡 The pgvector extension isn't available.")
            print("   If using Supabase: Go to Database → Extensions → Enable 'vector'")
            print("   If self-hosted: Install pgvector (https://github.com/pgvector/pgvector)")
        
        sys.exit(1)
    
    print("✅ Schema created successfully!")
    print("\nNext steps:")
    print("1. Set OPENAI_API_KEY for extraction (GPT-4o-mini)")
    print("2. Start the daemon: python3 scripts/session_processor.py daemon")
    print("3. Verify: python3 scripts/health.py")


if __name__ == "__main__":
    main()
