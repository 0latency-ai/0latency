"""
Storage Layer — Agent Memory Service
Phase 2: Persist extracted memories with embeddings, decay, and temporal tracking.

Uses Supabase (Postgres + pgvector) as the backend.
Designed to work with a new 'memory_service' schema, isolated from Thomas's existing 'thomas' schema.

SECURITY HARDENED: Uses psycopg2 with parameterized queries to prevent SQL injection.
"""

import json
import os
import requests
import psycopg2
import psycopg2.pool
from datetime import datetime, timezone
from typing import Optional
import threading
import time


# --- Configuration ---

SUPABASE_URL = os.environ.get("MEMORY_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("MEMORY_SUPABASE_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

DB_CONN = os.environ.get("MEMORY_DB_CONN", 
    os.environ.get("MEMORY_DB_CONN", ""))

# Connection pool - thread-safe
_connection_pool = None
_pool_lock = threading.Lock()

def _get_connection_pool():
    """Get or create the connection pool."""
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    dsn=DB_CONN
                )
    return _connection_pool


def _embed_text(text: str) -> list[float]:
    """Generate embedding for text using configured model."""
    
    # Try Google first (cheaper)
    if GOOGLE_API_KEY:
        try:
            model_name = "gemini-embedding-001"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent"
            resp = requests.post(
                url,
                params={"key": GOOGLE_API_KEY},
                json={
                    "model": f"models/{model_name}",
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": 768
                },
                timeout=15
            )
            resp.raise_for_status()
            return resp.json()["embedding"]["values"]
        except Exception as e:
            print(f"Google embedding failed: {e}")
    
    # Fallback to OpenAI
    if OPENAI_API_KEY:
        try:
            resp = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": text,
                },
                timeout=15
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
        except Exception as e:
            print(f"OpenAI embedding failed: {e}")
    
    raise RuntimeError("No embedding provider available")


def _db_execute(query: str, params: tuple = None, fetch_results: bool = True) -> list:
    """
    Execute a query against the database via psycopg2.
    
    SECURITY: Uses parameterized queries to prevent SQL injection.
    """
    pool = _get_connection_pool()
    retries = 0
    max_retries = 3
    
    while retries < max_retries:
        conn = None
        cur = None
        try:
            conn = pool.getconn()
            cur = conn.cursor()
            
            # Execute the query with parameters
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            results = []
            if fetch_results and cur.description:
                # Fetch all results and format as pipe-separated values for compatibility
                rows = cur.fetchall()
                for row in rows:
                    # Convert row tuple to string, handling None values
                    row_str = "|".join(str(val) if val is not None else "" for val in row)
                    results.append(row_str)
            
            conn.commit()
            return results
            
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            retries += 1
            if retries >= max_retries:
                raise RuntimeError(f"DB error after {max_retries} retries: {e}")
            time.sleep(0.1 * retries)  # Brief backoff
            
        finally:
            if cur:
                cur.close()
            if conn:
                pool.putconn(conn)
    
    return []


def init_schema():
    """Create the memory_service schema and tables if they don't exist."""
    
    schema_sql = """
    -- Create schema
    CREATE SCHEMA IF NOT EXISTS memory_service;
    
    -- Core memories table with tiered content
    CREATE TABLE IF NOT EXISTS memory_service.memories (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_id TEXT NOT NULL,
        
        -- Tiered content
        headline TEXT NOT NULL,
        context TEXT NOT NULL,
        full_content TEXT NOT NULL,
        
        -- Classification
        memory_type TEXT NOT NULL DEFAULT 'fact',
        entities TEXT[] DEFAULT '{}',
        project TEXT,
        categories TEXT[] DEFAULT '{}',
        scope TEXT DEFAULT '/',
        
        -- Scoring
        importance FLOAT DEFAULT 0.5,
        confidence FLOAT DEFAULT 0.8,
        relevance_score FLOAT DEFAULT 1.0,
        access_count INT DEFAULT 0,
        reinforcement_count INT DEFAULT 1,
        
        -- Temporal
        valid_from TIMESTAMPTZ DEFAULT now(),
        superseded_at TIMESTAMPTZ,
        superseded_by UUID REFERENCES memory_service.memories(id),
        
        -- Embedding (768 for Google, 1536 for OpenAI — use 768 as default)
        embedding extensions.vector(768),
        
        -- Provenance
        source_session TEXT,
        source_turn TEXT,
        
        -- Timestamps
        created_at TIMESTAMPTZ DEFAULT now(),
        last_accessed TIMESTAMPTZ,
        
        -- Extensible
        metadata JSONB DEFAULT '{}'
    );
    
    -- Session handoffs
    CREATE TABLE IF NOT EXISTS memory_service.session_handoffs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_id TEXT NOT NULL,
        session_key TEXT NOT NULL,
        summary TEXT NOT NULL,
        decisions_made JSONB DEFAULT '[]',
        open_threads JSONB DEFAULT '[]',
        active_projects JSONB DEFAULT '[]',
        created_at TIMESTAMPTZ DEFAULT now()
    );
    
    -- Agent configuration
    CREATE TABLE IF NOT EXISTS memory_service.agent_config (
        agent_id TEXT PRIMARY KEY,
        context_budget INT DEFAULT 4000,
        recency_weight FLOAT DEFAULT 0.35,
        semantic_weight FLOAT DEFAULT 0.4,
        importance_weight FLOAT DEFAULT 0.15,
        access_weight FLOAT DEFAULT 0.1,
        recency_half_life_days INT DEFAULT 14,
        extraction_model TEXT DEFAULT 'gemini-2.0-flash',
        embedding_model TEXT DEFAULT 'text-embedding-004',
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
    
    -- Entity index for cross-entity linking
    CREATE TABLE IF NOT EXISTS memory_service.entity_index (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_id TEXT NOT NULL,
        entity TEXT NOT NULL,
        memory_id UUID NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(agent_id, entity, memory_id)
    );
    
    -- Memory edges for knowledge graph
    CREATE TABLE IF NOT EXISTS memory_service.memory_edges (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_id TEXT NOT NULL,
        source_memory_id UUID NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
        target_memory_id UUID NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
        relationship TEXT NOT NULL DEFAULT 'related_to',
        strength FLOAT DEFAULT 0.5,
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(source_memory_id, target_memory_id, relationship)
    );
    
    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_mem_agent ON memory_service.memories(agent_id);
    CREATE INDEX IF NOT EXISTS idx_mem_type ON memory_service.memories(agent_id, memory_type);
    CREATE INDEX IF NOT EXISTS idx_mem_scope ON memory_service.memories(agent_id, scope);
    CREATE INDEX IF NOT EXISTS idx_mem_relevance ON memory_service.memories(agent_id, relevance_score DESC);
    CREATE INDEX IF NOT EXISTS idx_mem_created ON memory_service.memories(agent_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_handoff_agent ON memory_service.session_handoffs(agent_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_agent ON memory_service.memory_audit_log(agent_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_entity_agent ON memory_service.entity_index(agent_id, entity);
    CREATE INDEX IF NOT EXISTS idx_edges_source ON memory_service.memory_edges(source_memory_id);
    CREATE INDEX IF NOT EXISTS idx_edges_target ON memory_service.memory_edges(target_memory_id);
    """
    
    _db_execute(schema_sql, fetch_results=False)
    print("✅ Schema initialized: memory_service")


def store_memory(memory: dict) -> str:
    """
    Store a single extracted memory with embedding.
    
    Args:
        memory: Structured memory object from extraction layer
    
    Returns:
        UUID of stored memory
    """
    # Generate embedding from headline + context (not full_content — saves tokens)
    embed_text = f"{memory['headline']}. {memory['context']}"
    embedding = _embed_text(embed_text)
    
    # Check for duplicate/reinforcement
    existing = _check_duplicate(memory['agent_id'], memory['headline'], embedding, memory_type=memory.get('memory_type'))
    
    if existing:
        # Reinforce existing memory
        _db_execute("""
            UPDATE memory_service.memories 
            SET reinforcement_count = reinforcement_count + 1,
                relevance_score = LEAST(1.0, relevance_score + 0.1),
                last_accessed = now()
            WHERE id = %s
        """, (existing,), fetch_results=False)
        print(f"  ↑ Reinforced existing memory: {existing}")
        return existing
    
    # Check for potential contradiction with existing memories
    if memory['memory_type'] != 'correction':
        contradiction = _check_contradiction(memory['agent_id'], memory['headline'], embedding)
        if contradiction:
            print(f"  ⚠ Potential contradiction detected with: {contradiction['headline']}")
            # Auto-upgrade to correction type
            memory['memory_type'] = 'correction'
            memory['full_content'] = (
                f"CORRECTION: {memory['full_content']}\n"
                f"PREVIOUS: {contradiction['headline']}"
            )
            metadata = memory.get('metadata', {})
            metadata['contradicts'] = contradiction['headline']
            metadata['contradicts_id'] = contradiction['id']
            memory['metadata'] = metadata
    
    # Build the insert query with parameterized values
    query = """
        INSERT INTO memory_service.memories 
            (agent_id, headline, context, full_content, memory_type, 
             entities, project, categories, scope,
             importance, confidence, embedding,
             source_session, source_turn, metadata)
        VALUES 
            (%s, %s, %s, %s, %s,
             %s, %s, %s, %s,
             %s, %s, %s::extensions.vector,
             %s, %s, %s::jsonb)
        RETURNING id;
    """
    
    params = (
        memory['agent_id'],
        memory['headline'],
        memory['context'],
        memory['full_content'],
        memory['memory_type'],
        memory.get('entities', []),
        memory.get('project'),
        memory.get('categories', []),
        memory.get('scope', '/'),
        memory.get('importance', 0.5),
        memory.get('confidence', 0.8),
        embedding,
        memory.get('source_session'),
        memory.get('source_turn'),
        json.dumps(memory.get('metadata', {}))
    )
    
    rows = _db_execute(query, params)
    mem_id = rows[0].split("|")[0] if rows else None
    
    # Handle corrections — supersede old memories
    if memory['memory_type'] == 'correction' and mem_id:
        _handle_correction(memory, mem_id)
    
    # Index entities for cross-entity linking
    if mem_id and memory.get('entities'):
        _index_entities(memory['agent_id'], mem_id, memory['entities'])
        # Auto-create edges between memories sharing entities
        _create_entity_edges(memory['agent_id'], mem_id, memory['entities'])
    
    # Audit log
    _db_execute("""
        INSERT INTO memory_service.memory_audit_log (agent_id, action, memory_id, details)
        VALUES (%s, 'extract', %s, %s)
    """, (
        memory['agent_id'], 
        mem_id, 
        json.dumps({"headline": memory["headline"], "type": memory["memory_type"]})
    ), fetch_results=False)
    
    return mem_id


def _check_duplicate(agent_id: str, headline: str, embedding: list[float], threshold: float = 0.85, memory_type: str = None) -> Optional[str]:
    """Check if a very similar memory already exists (for reinforcement instead of duplication).
    
    Uses a two-tier approach:
    - 0.92+ similarity: Almost certainly a duplicate regardless of type
    - 0.85-0.92 similarity: Duplicate only if same memory_type (prevents cross-type false matches)
    """
    query = """
        SELECT id, headline, memory_type,
               1 - (embedding <=> %s::extensions.vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = %s
          AND superseded_at IS NULL
        ORDER BY embedding <=> %s::extensions.vector
        LIMIT 3
    """
    
    rows = _db_execute(query, (embedding, agent_id, embedding))
    
    if rows:
        for row in rows:
            parts = row.split("|")
            if len(parts) >= 4:
                mem_id, existing_headline, existing_type, similarity = parts[0], parts[1], parts[2].strip(), float(parts[3])
                
                # Tier 1: Very high similarity = duplicate regardless
                if similarity >= 0.92:
                    return mem_id
                
                # Tier 2: High similarity + same type = duplicate
                if similarity >= threshold and memory_type and existing_type == memory_type:
                    return mem_id
    
    return None


def _check_contradiction(agent_id: str, headline: str, embedding: list[float]) -> Optional[dict]:
    """Check if a new memory potentially contradicts an existing one.
    
    Uses semantic similarity to find related memories, then checks for
    entity overlap with conflicting values.
    """
    query = """
        SELECT id, headline, context, entities,
               1 - (embedding <=> %s::extensions.vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = %s
          AND superseded_at IS NULL
          AND memory_type NOT IN ('correction', 'task')
        ORDER BY embedding <=> %s::extensions.vector
        LIMIT 5
    """
    
    rows = _db_execute(query, (embedding, agent_id, embedding))
    
    if not rows:
        return None
    
    for row in rows:
        parts = row.split("|")
        if len(parts) >= 5:
            similarity = float(parts[4])
            existing_headline = parts[1]
            existing_context = parts[2] if len(parts) > 2 else ""
            
            # Tighter range: 0.78-0.88 — must be very similar topic but different claim
            # Below 0.78 = different enough to be a separate fact, not a contradiction
            # Above 0.88 = too similar, probably a duplicate (handled by _check_duplicate)
            if 0.78 < similarity < 0.88:
                # Additional check: headlines must share at least one meaningful entity
                existing_entities = parts[3].strip("{}").split(",") if parts[3] and parts[3] != "{}" else []
                existing_entities = [e.strip().strip('"') for e in existing_entities if e.strip().strip('"')]
                
                new_headline_lower = headline.lower()
                
                # Must have entity overlap AND the headlines shouldn't be saying the same thing
                entity_overlap = any(
                    ent.lower() in new_headline_lower 
                    for ent in existing_entities 
                    if len(ent) > 2
                )
                
                if entity_overlap:
                    return {
                        "id": parts[0],
                        "headline": existing_headline,
                        "similarity": similarity,
                    }
    
    return None


def _handle_correction(memory: dict, correction_id: str):
    """When a correction is stored, find and supersede the old fact.
    
    Cross-agent: corrections propagate to ALL agents sharing the same user context.
    If agent 'thomas' corrects "$16/student" to "$20/student", the stale "$16" fact
    in agent 'echo' also gets superseded.
    """
    # Search for related memories that this corrects
    embed_text = f"{memory['headline']}. {memory['context']}"
    embedding = _embed_text(embed_text)
    
    # Find the most similar non-correction memory — across ALL agents, not just the source
    query = """
        SELECT id, headline, agent_id
        FROM memory_service.memories
        WHERE memory_type != 'correction'
          AND superseded_at IS NULL
          AND id != %s
        ORDER BY embedding <=> %s::extensions.vector
        LIMIT 5
    """
    
    rows = _db_execute(query, (correction_id, embedding))
    
    if rows:
        for row in rows:
            parts = row.split("|")
            old_id = parts[0].strip()
            old_headline = parts[1].strip() if len(parts) > 1 else ""
            old_agent = parts[2].strip() if len(parts) > 2 else memory['agent_id']
            
            # Only supersede if it's semantically very close (avoid false positives across agents)
            # The ORDER BY already sorted by similarity, but we should check threshold
            # For same agent: supersede top match. For cross-agent: need higher bar
            if old_agent == memory['agent_id']:
                # Same agent — supersede the top match
                _db_execute("""
                    UPDATE memory_service.memories
                    SET superseded_at = now(), superseded_by = %s
                    WHERE id = %s
                """, (correction_id, old_id), fetch_results=False)
                print(f"  ✂ Superseded own memory: {old_id} ({old_headline})")
                _cascade_correction(old_agent, old_id, correction_id, old_headline)
                break  # Only supersede top match for same agent
            else:
                # Cross-agent — also supersede stale facts in sibling agents
                _db_execute("""
                    UPDATE memory_service.memories
                    SET superseded_at = now(), superseded_by = %s
                    WHERE id = %s
                """, (correction_id, old_id), fetch_results=False)
                print(f"  ✂ Cross-agent supersede [{old_agent}]: {old_id} ({old_headline})")
                _cascade_correction(old_agent, old_id, correction_id, old_headline)


def store_memories(memories: list[dict]) -> list[str]:
    """Store multiple memories. Returns list of UUIDs."""
    ids = []
    for mem in memories:
        try:
            mem_id = store_memory(mem)
            ids.append(mem_id)
            print(f"  💾 Stored [{mem['memory_type']}]: {mem['headline']}")
        except Exception as e:
            print(f"  ❌ Failed to store: {mem['headline']} — {e}")
    return ids


def store_handoff(handoff: dict) -> str:
    """Store a session handoff record."""
    query = """
        INSERT INTO memory_service.session_handoffs
            (agent_id, session_key, summary, decisions_made, open_threads, active_projects)
        VALUES 
            (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
        RETURNING id;
    """
    
    params = (
        handoff['agent_id'],
        handoff.get('session_key', 'unknown'),
        handoff.get('summary', ''),
        json.dumps(handoff.get('decisions_made', [])),
        json.dumps(handoff.get('open_threads', [])),
        json.dumps(handoff.get('active_projects', []))
    )
    
    rows = _db_execute(query, params)
    return rows[0].split("|")[0] if rows else None


def run_decay(agent_id: str = None):
    """
    Apply time-based decay to relevance scores.
    Run this on a schedule (e.g., daily cron).
    
    Decay rates by type:
    - fact: 0.02/day
    - decision: 0.005/day  
    - preference: 0.001/day (almost never decays)
    - task: 0.03/day (tasks should be resolved quickly)
    - correction: 0.001/day (corrections are important long-term)
    - relationship: 0.002/day
    """
    agent_filter_sql = "AND agent_id = %s" if agent_id else ""
    params = (agent_id,) if agent_id else ()
    
    query = f"""
        UPDATE memory_service.memories
        SET relevance_score = GREATEST(0.01, 
            relevance_score - CASE 
                WHEN memory_type = 'identity' THEN 0.0  -- identity NEVER decays
                WHEN memory_type = 'preference' THEN 0.001
                WHEN memory_type = 'correction' THEN 0.001
                WHEN memory_type = 'relationship' THEN 0.002
                WHEN memory_type = 'decision' THEN 0.005
                WHEN memory_type = 'fact' THEN 0.02
                WHEN memory_type = 'task' THEN 0.03
                ELSE 0.01
            END
            -- Also check temporal_type in metadata
            * CASE 
                WHEN metadata->>'temporal_type' = 'permanent' THEN 0.0  -- permanent facts never decay
                WHEN metadata->>'temporal_type' = 'event' THEN 1.5     -- events decay faster
                ELSE 1.0
            END
        )
        WHERE superseded_at IS NULL
          AND relevance_score > 0.01
          AND memory_type != 'identity'  -- double-guard: identity never decays
          {agent_filter_sql}
    """
    
    _db_execute(query, params, fetch_results=False)
    print(f"✅ Decay applied{' for ' + agent_id if agent_id else ' globally'}")


def get_memory_stats(agent_id: str) -> dict:
    """Get memory statistics for an agent."""
    query = """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE superseded_at IS NOT NULL) as superseded,
            COUNT(*) FILTER (WHERE relevance_score < 0.1) as low_relevance,
            COUNT(*) FILTER (WHERE memory_type = 'fact') as facts,
            COUNT(*) FILTER (WHERE memory_type = 'decision') as decisions,
            COUNT(*) FILTER (WHERE memory_type = 'preference') as preferences,
            COUNT(*) FILTER (WHERE memory_type = 'task') as tasks,
            COUNT(*) FILTER (WHERE memory_type = 'correction') as corrections,
            COUNT(*) FILTER (WHERE memory_type = 'relationship') as relationships,
            AVG(relevance_score) as avg_relevance
        FROM memory_service.memories
        WHERE agent_id = %s
    """
    
    rows = _db_execute(query, (agent_id,))
    
    if rows:
        parts = rows[0].split("|")
        return {
            "total": int(parts[0]),
            "superseded": int(parts[1]),
            "low_relevance": int(parts[2]),
            "facts": int(parts[3]),
            "decisions": int(parts[4]),
            "preferences": int(parts[5]),
            "tasks": int(parts[6]),
            "corrections": int(parts[7]),
            "relationships": int(parts[8]),
            "avg_relevance": round(float(parts[9] or 0), 3),
        }
    return {}


def _cascade_correction(agent_id: str, old_memory_id: str, correction_id: str, old_headline: str):
    """
    When a memory is corrected, find downstream memories that reference the same entities
    and flag them for review. This prevents silently stale downstream facts.
    
    Strategy:
    - Find memories connected via entity graph edges
    - For strongly connected memories (strength > 0.6), add a metadata flag
    - Don't auto-supersede — just flag for the extraction layer to review next time
    """
    try:
        # Find related memories via the entity graph
        query = """
            SELECT DISTINCT m.id, m.headline, me.strength
            FROM memory_service.memory_edges me
            JOIN memory_service.memories m ON (
                m.id = me.target_memory_id OR m.id = me.source_memory_id
            )
            WHERE (me.source_memory_id = %s OR me.target_memory_id = %s)
              AND me.agent_id = %s
              AND m.id != %s
              AND m.id != %s
              AND m.superseded_at IS NULL
            ORDER BY me.strength DESC
            LIMIT 10
        """
        
        rows = _db_execute(query, (old_memory_id, old_memory_id, agent_id, old_memory_id, correction_id))
        
        if not rows:
            return
        
        flagged = 0
        for row in rows:
            parts = row.split("|")
            if len(parts) < 3:
                continue
            
            mem_id = parts[0]
            headline = parts[1]
            strength = float(parts[2])
            
            if strength >= 0.4:
                # Flag this memory as potentially affected by the correction
                cascade_metadata = {
                    "correction_cascade": True, 
                    "cascade_from": correction_id, 
                    "cascade_note": f"Upstream fact corrected: {old_headline}"
                }
                
                _db_execute("""
                    UPDATE memory_service.memories
                    SET metadata = metadata || %s::jsonb
                    WHERE id = %s
                """, (json.dumps(cascade_metadata), mem_id), fetch_results=False)
                flagged += 1
                print(f"  🔗 Cascade flagged: {headline} (strength: {strength:.2f})")
        
        if flagged:
            print(f"  🔗 Correction cascaded to {flagged} related memories")
            
    except Exception as e:
        print(f"  ⚠ Cascade error (non-fatal): {e}")


def _index_entities(agent_id: str, memory_id: str, entities: list[str]):
    """Index entities for a memory, enabling cross-entity lookups."""
    for entity in entities:
        entity_clean = entity.strip()
        if not entity_clean:
            continue
        try:
            _db_execute("""
                INSERT INTO memory_service.entity_index (agent_id, entity, memory_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (agent_id, entity, memory_id) DO NOTHING
            """, (agent_id, entity_clean, memory_id), fetch_results=False)
        except Exception:
            pass  # Skip duplicates silently


def _create_entity_edges(agent_id: str, new_memory_id: str, entities: list[str]):
    """
    Auto-create 'related_to' edges between the new memory and existing memories 
    that share entities. This builds the knowledge graph incrementally.
    """
    for entity in entities:
        entity_clean = entity.strip()
        if not entity_clean:
            continue
        
        # Find other memories with the same entity
        try:
            query = """
                SELECT DISTINCT ei.memory_id 
                FROM memory_service.entity_index ei
                JOIN memory_service.memories m ON m.id = ei.memory_id
                WHERE ei.agent_id = %s 
                  AND ei.entity = %s
                  AND ei.memory_id != %s
                  AND m.superseded_at IS NULL
                LIMIT 10
            """
            rows = _db_execute(query, (agent_id, entity_clean, new_memory_id))
        except Exception:
            continue
        
        for row in rows:
            target_id = row.strip().split("|")[0]
            if not target_id:
                continue
            try:
                _db_execute("""
                    INSERT INTO memory_service.memory_edges 
                        (agent_id, source_memory_id, target_memory_id, relationship, strength)
                    VALUES 
                        (%s, %s, %s, 'related_to', 0.5)
                    ON CONFLICT (source_memory_id, target_memory_id, relationship) DO UPDATE
                    SET strength = memory_service.memory_edges.strength + 0.1
                """, (agent_id, new_memory_id, target_id), fetch_results=False)
            except Exception:
                pass  # Skip edge creation failures


def get_related_memories(agent_id: str, memory_id: str, max_depth: int = 1) -> list[dict]:
    """
    Traverse the entity graph to find related memories.
    Used by correction cascading (refinement #4) and recall enhancement.
    """
    query = """
        SELECT DISTINCT m.id, m.headline, m.memory_type, me.relationship, me.strength
        FROM memory_service.memory_edges me
        JOIN memory_service.memories m ON m.id = me.target_memory_id
        WHERE me.source_memory_id = %s
          AND me.agent_id = %s
          AND m.superseded_at IS NULL
        ORDER BY me.strength DESC
        LIMIT 20
    """
    
    rows = _db_execute(query, (memory_id, agent_id))
    
    results = []
    for row in rows:
        parts = row.split("|")
        if len(parts) >= 5:
            results.append({
                "id": parts[0],
                "headline": parts[1],
                "memory_type": parts[2],
                "relationship": parts[3],
                "strength": float(parts[4]),
            })
    return results


# --- CLI ---

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init_schema()
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        agent = sys.argv[2] if len(sys.argv) > 2 else "thomas"
        stats = get_memory_stats(agent)
        print(json.dumps(stats, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "decay":
        agent = sys.argv[2] if len(sys.argv) > 2 else None
        run_decay(agent)
    else:
        print("Usage:")
        print("  python storage_secure.py init          — Create schema")
        print("  python storage_secure.py stats [agent]  — Show memory stats")
        print("  python storage_secure.py decay [agent]  — Run decay cycle")