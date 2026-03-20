"""
Storage Layer — Agent Memory Service
Phase 2: Persist extracted memories with embeddings, decay, and temporal tracking.

Uses Supabase (Postgres + pgvector) as the backend.
Designed to work with a new 'memory_service' schema, isolated from Thomas's existing 'thomas' schema.
"""

import json
import os
import requests
from datetime import datetime, timezone
from typing import Optional


# --- Configuration ---

SUPABASE_URL = os.environ.get("MEMORY_SUPABASE_URL", "https://fuojxlabvhtmysbsixdn.supabase.co")
SUPABASE_KEY = os.environ.get("MEMORY_SUPABASE_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

DB_CONN = os.environ.get("MEMORY_DB_CONN", 
    "postgresql://postgres.fuojxlabvhtmysbsixdn:jcYlwEhuHN9VcOuj@aws-1-us-east-1.pooler.supabase.com:5432/postgres")


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


def _db_execute(query: str, params: dict = None) -> list:
    """Execute a query against the database via psql."""
    import subprocess
    
    # Substitute params into query (basic, for prototyping)
    if params:
        for key, val in params.items():
            if isinstance(val, str):
                val = val.replace("'", "''")
                query = query.replace(f":{key}", f"'{val}'")
            elif isinstance(val, (list, dict)):
                val_str = json.dumps(val).replace("'", "''")
                query = query.replace(f":{key}", f"'{val_str}'")
            elif val is None:
                query = query.replace(f":{key}", "NULL")
            else:
                query = query.replace(f":{key}", str(val))
    
    result = subprocess.run(
        ["psql", DB_CONN, "-t", "-A", "-F", "|", "-c", query],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "PGPASSWORD": "jcYlwEhuHN9VcOuj"}
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"DB error: {result.stderr}")
    
    rows = [line for line in result.stdout.strip().split("\n") if line]
    return rows


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
    
    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_mem_agent ON memory_service.memories(agent_id);
    CREATE INDEX IF NOT EXISTS idx_mem_type ON memory_service.memories(agent_id, memory_type);
    CREATE INDEX IF NOT EXISTS idx_mem_scope ON memory_service.memories(agent_id, scope);
    CREATE INDEX IF NOT EXISTS idx_mem_relevance ON memory_service.memories(agent_id, relevance_score DESC);
    CREATE INDEX IF NOT EXISTS idx_mem_created ON memory_service.memories(agent_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_handoff_agent ON memory_service.session_handoffs(agent_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_agent ON memory_service.memory_audit_log(agent_id, created_at DESC);
    """
    
    _db_execute(schema_sql)
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
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    
    # Check for duplicate/reinforcement
    existing = _check_duplicate(memory['agent_id'], memory['headline'], embedding)
    
    if existing:
        # Reinforce existing memory
        _db_execute(f"""
            UPDATE memory_service.memories 
            SET reinforcement_count = reinforcement_count + 1,
                relevance_score = LEAST(1.0, relevance_score + 0.1),
                last_accessed = now()
            WHERE id = '{existing}'
        """)
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
    
    # Build entities and categories arrays
    entities_str = "{" + ",".join(f'"{e}"' for e in memory.get('entities', [])) + "}"
    categories_str = "{" + ",".join(f'"{c}"' for c in memory.get('categories', [])) + "}"
    
    # Escape strings for SQL
    headline = memory['headline'].replace("'", "''")
    context = memory['context'].replace("'", "''")
    full_content = memory['full_content'].replace("'", "''")
    scope = memory.get('scope', '/').replace("'", "''")
    project = memory.get('project')
    project_sql = f"'{project.replace(chr(39), chr(39)*2)}'" if project else "NULL"
    source_session = memory.get('source_session')
    source_session_sql = f"'{source_session}'" if source_session else "NULL"
    source_turn = memory.get('source_turn')
    source_turn_sql = f"'{source_turn}'" if source_turn else "NULL"
    
    # Build metadata JSON
    metadata = memory.get('metadata', {})
    metadata_sql = json.dumps(metadata).replace("'", "''")
    
    # Handle ephemeral TTL
    ttl_hours = memory.get('ttl_hours')
    expires_clause = f", expires_at = now() + interval '{ttl_hours} hours'" if ttl_hours else ""
    expires_col = ", expires_at" if ttl_hours else ""
    expires_val = f", now() + interval '{ttl_hours} hours'" if ttl_hours else ""
    
    query = f"""
        INSERT INTO memory_service.memories 
            (agent_id, headline, context, full_content, memory_type, 
             entities, project, categories, scope,
             importance, confidence, embedding,
             source_session, source_turn, metadata{expires_col})
        VALUES 
            ('{memory['agent_id']}', '{headline}', '{context}', '{full_content}', '{memory['memory_type']}',
             '{entities_str}', {project_sql}, '{categories_str}', '{scope}',
             {memory.get('importance', 0.5)}, {memory.get('confidence', 0.8)}, '{embedding_str}'::extensions.vector,
             {source_session_sql}, {source_turn_sql}, '{metadata_sql}'::jsonb{expires_val})
        RETURNING id;
    """
    
    rows = _db_execute(query)
    mem_id = rows[0] if rows else None
    
    # Handle corrections — supersede old memories
    if memory['memory_type'] == 'correction' and mem_id:
        _handle_correction(memory, mem_id)
    
    # Index entities for cross-entity linking
    if mem_id and memory.get('entities'):
        _index_entities(memory['agent_id'], mem_id, memory['entities'])
        # Auto-create edges between memories sharing entities
        _create_entity_edges(memory['agent_id'], mem_id, memory['entities'])
    
    # Audit log
    _db_execute(f"""
        INSERT INTO memory_service.memory_audit_log (agent_id, action, memory_id, details)
        VALUES ('{memory['agent_id']}', 'extract', '{mem_id}', 
                '{json.dumps({"headline": memory["headline"], "type": memory["memory_type"]}).replace("'", "''")}')
    """)
    
    return mem_id


def _check_duplicate(agent_id: str, headline: str, embedding: list[float], threshold: float = 0.88) -> Optional[str]:
    """Check if a very similar memory already exists (for reinforcement instead of duplication)."""
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    
    rows = _db_execute(f"""
        SELECT id, headline, 
               1 - (embedding <=> '{embedding_str}'::extensions.vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
          AND superseded_at IS NULL
        ORDER BY embedding <=> '{embedding_str}'::extensions.vector
        LIMIT 1
    """)
    
    if rows:
        parts = rows[0].split("|")
        if len(parts) >= 3:
            mem_id, existing_headline, similarity = parts[0], parts[1], float(parts[2])
            if similarity >= threshold:
                return mem_id
    
    return None


def _check_contradiction(agent_id: str, headline: str, embedding: list[float]) -> Optional[dict]:
    """Check if a new memory potentially contradicts an existing one.
    
    Uses semantic similarity to find related memories, then checks for
    entity overlap with conflicting values.
    """
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    
    # Find semantically similar memories (high similarity = same topic)
    rows = _db_execute(f"""
        SELECT id, headline, context, entities,
               1 - (embedding <=> '{embedding_str}'::extensions.vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
          AND superseded_at IS NULL
          AND memory_type NOT IN ('correction', 'task')
        ORDER BY embedding <=> '{embedding_str}'::extensions.vector
        LIMIT 5
    """)
    
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
    """When a correction is stored, find and supersede the old fact."""
    # Search for related memories that this corrects
    embed_text = f"{memory['headline']}. {memory['context']}"
    embedding = _embed_text(embed_text)
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    
    # Find the most similar non-correction memory
    rows = _db_execute(f"""
        SELECT id, headline
        FROM memory_service.memories
        WHERE agent_id = '{memory['agent_id']}'
          AND memory_type != 'correction'
          AND superseded_at IS NULL
          AND id != '{correction_id}'
        ORDER BY embedding <=> '{embedding_str}'::extensions.vector
        LIMIT 1
    """)
    
    if rows:
        old_id = rows[0].split("|")[0]
        old_headline = rows[0].split("|")[1] if "|" in rows[0] else ""
        _db_execute(f"""
            UPDATE memory_service.memories
            SET superseded_at = now(), superseded_by = '{correction_id}'
            WHERE id = '{old_id}'
        """)
        print(f"  ✂ Superseded old memory: {old_id}")
        
        # Correction cascading: find downstream memories that depend on the corrected fact
        _cascade_correction(memory['agent_id'], old_id, correction_id, old_headline)
        print(f"  ✂ Superseded old memory: {old_id}")


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
    summary = handoff.get('summary', '').replace("'", "''")
    decisions = json.dumps(handoff.get('decisions_made', [])).replace("'", "''")
    threads = json.dumps(handoff.get('open_threads', [])).replace("'", "''")
    projects = json.dumps(handoff.get('active_projects', [])).replace("'", "''")
    
    rows = _db_execute(f"""
        INSERT INTO memory_service.session_handoffs
            (agent_id, session_key, summary, decisions_made, open_threads, active_projects)
        VALUES 
            ('{handoff['agent_id']}', '{handoff.get('session_key', 'unknown')}', 
             '{summary}', '{decisions}'::jsonb, '{threads}'::jsonb, '{projects}'::jsonb)
        RETURNING id;
    """)
    
    return rows[0] if rows else None


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
    agent_filter = f"AND agent_id = '{agent_id}'" if agent_id else ""
    
    _db_execute(f"""
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
          {agent_filter}
    """)
    
    print(f"✅ Decay applied{' for ' + agent_id if agent_id else ' globally'}")


def get_memory_stats(agent_id: str) -> dict:
    """Get memory statistics for an agent."""
    rows = _db_execute(f"""
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
        WHERE agent_id = '{agent_id}'
    """)
    
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
        rows = _db_execute(f"""
            SELECT DISTINCT m.id, m.headline, me.strength
            FROM memory_service.memory_edges me
            JOIN memory_service.memories m ON (
                m.id = me.target_memory_id OR m.id = me.source_memory_id
            )
            WHERE (me.source_memory_id = '{old_memory_id}' OR me.target_memory_id = '{old_memory_id}')
              AND me.agent_id = '{agent_id}'
              AND m.id != '{old_memory_id}'
              AND m.id != '{correction_id}'
              AND m.superseded_at IS NULL
            ORDER BY me.strength DESC
            LIMIT 10
        """)
        
        if not rows:
            return
        
        flagged = 0
        for row in rows:
            parts = row.split("|||")
            if len(parts) < 3:
                continue
            
            mem_id = parts[0]
            headline = parts[1]
            strength = float(parts[2])
            
            if strength >= 0.4:
                # Flag this memory as potentially affected by the correction
                _db_execute(f"""
                    UPDATE memory_service.memories
                    SET metadata = metadata || '{{"correction_cascade": true, "cascade_from": "{correction_id}", "cascade_note": "Upstream fact corrected: {old_headline.replace(chr(39), chr(39)*2)}"}}'::jsonb
                    WHERE id = '{mem_id}'
                """)
                flagged += 1
                print(f"  🔗 Cascade flagged: {headline} (strength: {strength:.2f})")
        
        if flagged:
            print(f"  🔗 Correction cascaded to {flagged} related memories")
            
    except Exception as e:
        print(f"  ⚠ Cascade error (non-fatal): {e}")


def _index_entities(agent_id: str, memory_id: str, entities: list[str]):
    """Index entities for a memory, enabling cross-entity lookups."""
    for entity in entities:
        entity_clean = entity.strip().replace("'", "''")
        if not entity_clean:
            continue
        try:
            _db_execute(f"""
                INSERT INTO memory_service.entity_index (agent_id, entity, memory_id)
                VALUES ('{agent_id}', '{entity_clean}', '{memory_id}')
                ON CONFLICT (agent_id, entity, memory_id) DO NOTHING
            """)
        except Exception:
            pass  # Skip duplicates silently


def _create_entity_edges(agent_id: str, new_memory_id: str, entities: list[str]):
    """
    Auto-create 'related_to' edges between the new memory and existing memories 
    that share entities. This builds the knowledge graph incrementally.
    """
    for entity in entities:
        entity_clean = entity.strip().replace("'", "''")
        if not entity_clean:
            continue
        
        # Find other memories with the same entity
        try:
            rows = _db_execute(f"""
                SELECT DISTINCT ei.memory_id 
                FROM memory_service.entity_index ei
                JOIN memory_service.memories m ON m.id = ei.memory_id
                WHERE ei.agent_id = '{agent_id}' 
                  AND ei.entity = '{entity_clean}'
                  AND ei.memory_id != '{new_memory_id}'
                  AND m.superseded_at IS NULL
                LIMIT 10
            """)
        except Exception:
            continue
        
        for row in rows:
            target_id = row.strip()
            if not target_id:
                continue
            try:
                _db_execute(f"""
                    INSERT INTO memory_service.memory_edges 
                        (agent_id, source_memory_id, target_memory_id, relationship, strength)
                    VALUES 
                        ('{agent_id}', '{new_memory_id}', '{target_id}', 'related_to', 0.5)
                    ON CONFLICT (source_memory_id, target_memory_id, relationship) DO UPDATE
                    SET strength = memory_service.memory_edges.strength + 0.1
                """)
            except Exception:
                pass  # Skip edge creation failures


def get_related_memories(agent_id: str, memory_id: str, max_depth: int = 1) -> list[dict]:
    """
    Traverse the entity graph to find related memories.
    Used by correction cascading (refinement #4) and recall enhancement.
    """
    rows = _db_execute(f"""
        SELECT DISTINCT m.id, m.headline, m.memory_type, me.relationship, me.strength
        FROM memory_service.memory_edges me
        JOIN memory_service.memories m ON m.id = me.target_memory_id
        WHERE me.source_memory_id = '{memory_id}'
          AND me.agent_id = '{agent_id}'
          AND m.superseded_at IS NULL
        ORDER BY me.strength DESC
        LIMIT 20
    """)
    
    results = []
    for row in rows:
        parts = row.split("|||")
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
        print("  python storage.py init          — Create schema")
        print("  python storage.py stats [agent]  — Show memory stats")
        print("  python storage.py decay [agent]  — Run decay cycle")
