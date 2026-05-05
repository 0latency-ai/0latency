"""
Multi-Tenant Storage Layer — Agent Memory Service
Phase B: Enhanced with tenant isolation and Row Level Security (RLS).

SECURITY HARDENED: Uses psycopg2 with parameterized queries to prevent SQL injection.
"""

import json
import os
import numpy as np
import requests
import psycopg2
import psycopg2.pool
from datetime import datetime, timezone
from typing import Optional
import threading
import sys
import os

# Import similarity scanner for Phase 1
try:
    from similarity_scanner import trigger_similarity_scan
except ImportError:
    # Fallback if not in same directory
    sys.path.insert(0, os.path.dirname(__file__))
    from similarity_scanner import trigger_similarity_scan

import time

# Local embedding model for fast CPU inference
_local_embedding_model = None
_local_model_lock = threading.Lock()

def _get_local_model():
    """Lazy-load local embedding model (all-MiniLM-L6-v2, 384 dims, ~10-20ms CPU inference)."""
    global _local_embedding_model
    if _local_embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _local_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        # Warmup inference to avoid deferred init cost on first real call
        _local_embedding_model.encode(["warmup"], show_progress_bar=False)
    return _local_embedding_model


# --- Configuration ---

SUPABASE_URL = os.environ.get("MEMORY_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("MEMORY_SUPABASE_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

def _get_db_conn():
    """Get DB connection string from env. Never hardcoded."""
    conn = os.environ.get("MEMORY_DB_CONN", "")
    if not conn:
        raise RuntimeError("MEMORY_DB_CONN environment variable must be set")
    return conn

# Global tenant context
_current_tenant_id = None

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
                    minconn=1,
                    maxconn=5,
                    dsn=_get_db_conn()
                )
    return _connection_pool


def set_tenant_context(tenant_id: str):
    """Set the current tenant context for this session."""
    global _current_tenant_id
    _current_tenant_id = tenant_id


# Embedding cache — avoids re-embedding identical text
_embed_cache: dict[str, tuple[list[float], float]] = {}
_EMBED_CACHE_MAX = 2000
_EMBED_CACHE_TTL = 3600  # 1 hour

def _embed_text(text: str) -> list[float]:
    """Generate embedding with LRU cache. Avoids re-embedding identical queries."""
    import time as _time
    
    cache_key = text[:2000]  # Cap key length
    now = _time.time()
    
    if cache_key in _embed_cache:
        cached_vec, cached_at = _embed_cache[cache_key]
        if now - cached_at < _EMBED_CACHE_TTL:
            return cached_vec
        else:
            del _embed_cache[cache_key]
    
    vec = _embed_text_uncached(text)
    
    # Evict oldest if at capacity
    if len(_embed_cache) >= _EMBED_CACHE_MAX:
        oldest_key = min(_embed_cache, key=lambda k: _embed_cache[k][1])
        del _embed_cache[oldest_key]
    
    _embed_cache[cache_key] = (vec, now)
    return vec


def _embed_text_local(text: str) -> list[float]:
    """Generate embedding using local model (all-MiniLM-L6-v2).
    
    Fast CPU inference (~10-20ms), no external API dependency.
    Returns 384-dimensional vector (vs 768 for OpenAI).
    Accepts ~5-8% accuracy reduction for 100x speed improvement.
    """
    with _local_model_lock:
        model = _get_local_model()
        # encode() returns numpy array, convert to list
        embedding = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        # Normalize for cosine similarity (pgvector expects normalized vectors)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()


def _embed_text_uncached(text: str) -> list[float]:
    """Generate embedding using local model (all-MiniLM-L6-v2, 384d).
    OpenAI write-path removed 2026-04-25 — local embeddings used for both
    read and write paths to eliminate API cost. Schema migrated to vector(384).
    """
    return _embed_text_local(text)


def warm_embedding_cache():
    """Pre-warm the embedding cache with common query patterns."""
    import threading
    
    def _warm_cache():
        """Background thread to warm the cache."""
        common_queries = [
            "what do I know about",
            "recent decisions",
            "active tasks", 
            "people and contacts",
            "Palmer",
            "ZeroClick",
            "PFL Academy",
            "pricing",
            "launch",
            "memory",
            "goals",
            "roadmap",
            "partners",
            "customers",
            "technical details",
            "integration",
            "API",
            "authentication",
            "deployment",
            "strategy",
        ]
        
        print("Warming embedding cache...")
        for query in common_queries:
            try:
                _embed_text(query)
            except Exception as e:
                print(f"Cache warming failed for '{query}': {e}")
        
        # Also warm cache with recent memory contents
        try:
            pool = _get_connection_pool()
            conn = pool.getconn()
            cur = conn.cursor()
            
            # Get 10 most recent memory headlines
            cur.execute("""
                SELECT DISTINCT headline, created_at 
                FROM memory_service.memories 
                WHERE superseded_at IS NULL 
                  AND headline IS NOT NULL
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            
            for row in cur.fetchall():
                try:
                    _embed_text(row[0])
                except Exception:
                    pass
            
            cur.close()
            pool.putconn(conn)
            
            print(f"✅ Embedding cache warmed: {len(_embed_cache)} entries")
        except Exception as e:
            print(f"Failed to warm cache with recent memories: {e}")
    
    # Run in background thread to not block startup
    thread = threading.Thread(target=_warm_cache, daemon=True)
    thread.start()



def _db_execute(query: str, params: tuple = None, tenant_id: str = None, fetch_results: bool = True) -> list:
    """
    Execute a query against the database with tenant isolation.
    
    SECURITY: Uses parameterized queries to prevent SQL injection.
    Returns list of pipe-separated strings for backward compat.
    Use _db_execute_rows() for proper tuple results.
    """
    rows = _db_execute_rows(query, params, tenant_id, fetch_results)
    # Convert tuples to pipe-separated strings for backward compat
    results = []
    for row in rows:
        row_str = "|||".join(str(val) if val is not None else "" for val in row)
        results.append(row_str)
    return results


def _db_execute_rows(query: str, params: tuple = None, tenant_id: str = None, fetch_results: bool = True) -> list[tuple]:
    """
    Execute a query against the database with tenant isolation.
    Returns raw tuples — no string conversion, no delimiter issues.
    
    SECURITY: Uses parameterized queries to prevent SQL injection.
    """
    pool = _get_connection_pool()
    current_tenant = tenant_id or _current_tenant_id
    
    if not current_tenant:
        raise ValueError("No tenant context set. Call set_tenant_context() first.")
    
    retries = 0
    max_retries = 3
    
    while retries < max_retries:
        conn = None
        cur = None
        try:
            conn = pool.getconn()
            conn.autocommit = True  # CP6: Enable autocommit to eliminate BEGIN/COMMIT round trips
            cur = conn.cursor()
            
            # Set tenant context (round trip 1 of 2)
            cur.execute("SELECT memory_service.set_tenant_context(%s)", (current_tenant,))
            
            # Execute the actual query with parameters (round trip 2 of 2)
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            results = []
            if fetch_results and cur.description:
                results = cur.fetchall()
            
            return results
            
        except psycopg2.Error as e:
            # CP6: No ROLLBACK needed in autocommit mode - connection is in clean state
            retries += 1
            if retries >= max_retries:
                import logging
                logging.getLogger("zerolatency").error(f"DB error after {max_retries} retries: {e}")
                raise RuntimeError("Database operation failed. Please try again.")
            time.sleep(0.1 * retries)
            
        finally:
            if cur:
                cur.close()
            if conn:
                pool.putconn(conn)
    
    return []


def store_memory(memory: dict, tenant_id: str = None) -> dict:
    """
    Store a single extracted memory with embedding and tenant isolation.
    
    Args:
    
    Returns:
        dict with keys: 'id' (UUID of stored/existing memory) and 'deduplicated' (bool)
        UUID of stored memory
    """
    current_tenant = tenant_id or _current_tenant_id
    if not current_tenant:
        raise ValueError("No tenant context set")
    
    # Extract scope fields from top-level or metadata (dual-source for compatibility)
    meta_dict = memory.get('metadata', {})
    thread_id_val = memory.get('thread_id') or meta_dict.get('thread_id')
    project_id_val = memory.get('project_id') or meta_dict.get('project_id')
    thread_title_val = memory.get('thread_title') or meta_dict.get('thread_title')
    project_name_val = memory.get('project_name') or meta_dict.get('project_name')
    
    # Generate embedding from headline + context (not full_content — saves tokens)
    embed_text = f"{memory['headline']}. {memory['context']}"
    embedding = _embed_text(embed_text)
    local_embedding = _embed_text_local(embed_text)  # Local model (384d) for fast reads
    
    # Check for duplicate/reinforcement within this tenant
    existing = _check_duplicate(memory['agent_id'], memory['headline'], embedding, 
                               memory_type=memory.get('memory_type'), tenant_id=current_tenant)
    
    if existing:
        # Snapshot version before reinforcement
        try:
            from versioning import snapshot_version
            snapshot_version(existing, current_tenant, changed_by="extraction", change_reason="reinforcement")
        except Exception:
            pass  # Don't break store on versioning failure
        
        # Reinforce existing memory
        _db_execute("""
            UPDATE memory_service.memories 
            SET reinforcement_count = reinforcement_count + 1,
                relevance_score = LEAST(1.0, relevance_score + 0.1),
                last_accessed = now()
            WHERE id = %s
        """, (existing,), tenant_id=current_tenant, fetch_results=False)
        
        # Fire webhook
        try:
            from webhooks import trigger_event
            trigger_event(current_tenant, "memory.reinforced", {
                "memory_id": existing,
                "headline": memory.get("headline", ""),
            })
        except Exception:
            pass
        
        print(f"  ↑ Reinforced existing memory (deduplicated): {existing}")
        return {"id": existing, "deduplicated": True}
    
    # Check for potential contradiction with existing memories in this tenant
    if memory['memory_type'] != 'correction':
        contradiction = _check_contradiction(memory['agent_id'], memory['headline'], 
                                           embedding, tenant_id=current_tenant)
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
    
    # Insert new memory using parameterized query
    query = """
        INSERT INTO memory_service.memories 
            (tenant_id, agent_id, headline, context, full_content, memory_type, 
             entities, project, categories, scope,
             importance, confidence, embedding, local_embedding,
             source_session, source_turn, metadata,
             thread_id, project_id, thread_title, project_name)
        VALUES 
            (%s::UUID, %s, %s, %s, %s, %s,
             %s, %s, %s, %s,
             %s, %s, %s::vector, %s::vector,
             %s, %s, %s::jsonb,
             %s, %s, %s, %s)
        RETURNING id;
    """
    
    params = (
        current_tenant,
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
        local_embedding,
        memory.get('source_session'),
        memory.get('source_turn'),
        json.dumps(memory.get('metadata', {})),
        thread_id_val, project_id_val, thread_title_val, project_name_val
    )
    
    rows = _db_execute_rows(query, params, tenant_id=current_tenant)
    mem_id = rows[0][0] if rows else None
    
    # Handle corrections — supersede old memories within tenant
    if memory['memory_type'] == 'correction' and mem_id:
        _handle_correction(memory, mem_id, current_tenant)
    
    # Index entities for cross-entity linking within tenant
    if mem_id and memory.get('entities'):
        _index_entities(memory['agent_id'], mem_id, memory['entities'], current_tenant)
        # Auto-create edges between memories sharing entities
        _create_entity_edges(memory['agent_id'], mem_id, memory['entities'], current_tenant)
    
    # Auto-extract entity relationships for graph memory
    if mem_id:
        try:
            from graph import extract_relationships_from_memory
            memory["id"] = mem_id  # Overwrite temp dedup hash with real DB UUID
            extract_relationships_from_memory(memory, memory['agent_id'], tenant_id=current_tenant)
        except Exception as e:
            print(f"  ⚠ Graph extraction failed (non-fatal): {e}")
    
    # Fire webhook for new memory
    event_type = "memory.corrected" if memory['memory_type'] == 'correction' else "memory.created"
    try:
        from webhooks import trigger_event
        trigger_event(current_tenant, event_type, {
            "memory_id": mem_id,
            "headline": memory.get("headline", ""),
            "memory_type": memory.get("memory_type", "fact"),
            "importance": memory.get("importance", 0.5),
        })
    except Exception:
        pass
    
    # Audit log
    _db_execute("""
        INSERT INTO memory_service.memory_audit_log (tenant_id, agent_id, action, memory_id, details)
        VALUES (%s::UUID, %s, 'extract', %s, %s)
    """, (
        current_tenant, 
        memory['agent_id'], 
        mem_id, 
        json.dumps({"headline": memory["headline"], "type": memory["memory_type"]})
    ), tenant_id=current_tenant, fetch_results=False)
    
    # Phase 1: Trigger similarity scanner (non-blocking)
    try:
        trigger_similarity_scan(mem_id, current_tenant, memory['agent_id'], embedding)
    except Exception:
        pass  # Fire-and-forget, don't break on scanner failure
    
    return {"id": mem_id, "deduplicated": False}


def _check_duplicate(agent_id: str, headline: str, embedding: list[float], 
                    threshold: float = 0.85, memory_type: str = None, tenant_id: str = None) -> Optional[str]:
    """Check if a very similar memory already exists within the tenant."""
    current_tenant = tenant_id or _current_tenant_id
    
    query = """
        SELECT id, headline, memory_type,
               1 - (embedding <=> %s::vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = %s AND tenant_id = %s
          AND superseded_at IS NULL
        ORDER BY embedding <=> %s::vector
        LIMIT 3
    """
    
    rows = _db_execute_rows(query, (embedding, agent_id, current_tenant, embedding), tenant_id=current_tenant)
    
    if rows:
        for row in rows:
            mem_id, existing_headline, existing_type, similarity = row[0], row[1], row[2].strip(), float(row[3])
            
            # Tier 1: Very high similarity = duplicate regardless
            if similarity >= 0.92:
                return mem_id
            
            # Tier 2: High similarity + same type = duplicate
            if similarity >= threshold and memory_type and existing_type == memory_type:
                return mem_id
    
    return None


def _check_contradiction(agent_id: str, headline: str, embedding: list[float], tenant_id: str = None) -> Optional[dict]:
    """Check if a new memory potentially contradicts an existing one within the tenant."""
    current_tenant = tenant_id or _current_tenant_id
    
    # Find semantically similar memories (high similarity = same topic)
    query = """
        SELECT id, headline, context, entities,
               1 - (embedding <=> %s::vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = %s
          AND superseded_at IS NULL
          AND memory_type NOT IN ('correction', 'task')
        ORDER BY embedding <=> %s::vector
        LIMIT 5
    """
    
    rows = _db_execute_rows(query, (embedding, agent_id, embedding), tenant_id=current_tenant)
    
    if not rows:
        return None
    
    for row in rows:
        similarity = float(row[4])
        existing_headline = row[1]
        
        # Check for contradictions in similar range
        if 0.78 < similarity < 0.88:
            existing_entities = row[3].strip("{}").split(",") if row[3] and row[3] != "{}" else []
            existing_entities = [e.strip().strip('"') for e in existing_entities if e.strip().strip('"')]
            
            new_headline_lower = headline.lower()
            
            entity_overlap = any(
                ent.lower() in new_headline_lower 
                for ent in existing_entities 
                if len(ent) > 2
            )
            
            if entity_overlap:
                return {
                    "id": row[0],
                    "headline": existing_headline,
                    "similarity": similarity,
                }
    
    return None


def _handle_correction(memory: dict, correction_id: str, tenant_id: str):
    """Handle correction by superseding old facts within the tenant.
    Snapshots the old memory's state to memory_versions before superseding.
    """
    # Search for related memories that this corrects (within tenant only)
    embed_text = f"{memory['headline']}. {memory['context']}"
    embedding = _embed_text(embed_text)
    
    query = """
        SELECT id, headline, agent_id
        FROM memory_service.memories
        WHERE memory_type != 'correction'
          AND superseded_at IS NULL
          AND id != %s
        ORDER BY embedding <=> %s::vector
        LIMIT 5
    """
    
    rows = _db_execute(query, (correction_id, embedding), tenant_id=tenant_id)
    
    if rows:
        for row in rows:
            parts = row.split("|||")
            old_id = parts[0].strip()
            old_headline = parts[1].strip() if len(parts) > 1 else ""
            
            # Snapshot version before superseding
            try:
                from versioning import snapshot_version
                snapshot_version(old_id, tenant_id, changed_by="extraction",
                                change_reason=f"superseded by correction: {memory['headline'][:120]}")
            except Exception as e:
                print(f"  ⚠ Version snapshot failed (non-fatal): {e}")
            
            # Supersede the top match within this tenant
            _db_execute("""
                UPDATE memory_service.memories
                SET superseded_at = now(), superseded_by = %s
                WHERE id = %s
            """, (correction_id, old_id), tenant_id=tenant_id, fetch_results=False)
            print(f"  ✂ Superseded memory: {old_id} ({old_headline})")
            break  # Only supersede top match


def store_memories(memories: list[dict], tenant_id: str = None) -> dict:
    """Store multiple memories with tenant isolation. Returns dict with ids, deduplicated_ids, and new_ids."""
    ids = []
    deduplicated_ids = []
    new_ids = []
    
    for mem in memories:
        try:
            result = store_memory(mem, tenant_id)
            ids.append(result["id"])
            
            if result["deduplicated"]:
                deduplicated_ids.append(result["id"])
                print(f"  🔄 Deduplicated [{mem['memory_type']}]: {mem['headline']}")
            else:
                new_ids.append(result["id"])
                print(f"  💾 Stored [{mem['memory_type']}]: {mem['headline']}")
        except Exception as e:
            print(f"  ❌ Failed to store: {mem['headline']} — {e}")
    
    return {
        "ids": ids,
        "deduplicated_ids": deduplicated_ids,
        "new_ids": new_ids
    }

def store_handoff(handoff: dict, tenant_id: str = None) -> str:
    """Store a session handoff record with tenant isolation."""
    current_tenant = tenant_id or _current_tenant_id
    if not current_tenant:
        raise ValueError("No tenant context set")
    
    query = """
        INSERT INTO memory_service.session_handoffs
            (tenant_id, agent_id, session_key, summary, decisions_made, open_threads, active_projects)
        VALUES 
            (%s::UUID, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
        RETURNING id;
    """
    
    params = (
        current_tenant,
        handoff['agent_id'],
        handoff.get('session_key', 'unknown'),
        handoff.get('summary', ''),
        json.dumps(handoff.get('decisions_made', [])),
        json.dumps(handoff.get('open_threads', [])),
        json.dumps(handoff.get('active_projects', []))
    )
    
    rows = _db_execute(query, params, tenant_id=current_tenant)
    return rows[0].split("|||")[0] if rows else None


def get_memory_stats(agent_id: str, tenant_id: str = None) -> dict:
    """Get memory statistics for an agent within a tenant."""
    current_tenant = tenant_id or _current_tenant_id
    if not current_tenant:
        raise ValueError("No tenant context set")
    
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
    
    rows = _db_execute(query, (agent_id,), tenant_id=current_tenant)
    
    if rows:
        parts = rows[0].split("|||")
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


def _index_entities(agent_id: str, memory_id: str, entities: list[str], tenant_id: str):
    """Index entities for a memory within a tenant."""
    for entity in entities:
        entity_clean = entity.strip()
        if not entity_clean:
            continue
        try:
            _db_execute("""
                INSERT INTO memory_service.entity_index (tenant_id, agent_id, entity, memory_id)
                VALUES (%s::UUID, %s, %s, %s)
                ON CONFLICT (agent_id, entity, memory_id) DO NOTHING
            """, (tenant_id, agent_id, entity_clean, memory_id), tenant_id=tenant_id, fetch_results=False)
        except Exception:
            pass  # Skip duplicates silently


def _create_entity_edges(agent_id: str, new_memory_id: str, entities: list[str], tenant_id: str):
    """Auto-create edges between memories sharing entities within a tenant."""
    for entity in entities:
        entity_clean = entity.strip()
        if not entity_clean:
            continue
        
        # Find other memories with the same entity within this tenant
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
            rows = _db_execute(query, (agent_id, entity_clean, new_memory_id), tenant_id=tenant_id)
        except Exception:
            continue
        
        for row in rows:
            target_id = row.strip().split("|||")[0]
            if not target_id:
                continue
            try:
                _db_execute("""
                    INSERT INTO memory_service.memory_edges 
                        (tenant_id, agent_id, source_memory_id, target_memory_id, relationship, strength)
                    VALUES 
                        (%s::UUID, %s, %s, %s, 'related_to', 0.5)
                    ON CONFLICT (source_memory_id, target_memory_id, relationship) DO UPDATE
                    SET strength = memory_service.memory_edges.strength + 0.1
                """, (tenant_id, agent_id, new_memory_id, target_id), tenant_id=tenant_id, fetch_results=False)
            except Exception:
                pass  # Skip edge creation failures


def get_tenant_by_api_key(api_key_hash: str) -> Optional[dict]:
    """Look up tenant by API key hash via memory_service.api_keys.

    Status branching:
    - 'active' -> return tenant
    - 'rotating' AND revoke_at IS NULL OR revoke_at > now() -> return tenant + warn
    - 'rotating' AND revoke_at <= now() -> treat as revoked
    - 'revoked' -> None (caller raises 401)

    Falls back to tenants.api_key_hash for any rows not yet backfilled
    (defense-in-depth; backfill_api_keys.py should make this path unused).
    """
    query = """
        SELECT
            t.id, t.name, t.plan, t.memory_limit, t.rate_limit_rpm, t.active, t.api_calls_count,
            ak.status,
            (ak.status = 'rotating' AND ak.revoke_at IS NOT NULL AND ak.revoke_at <= now()) AS rotation_expired,
            COALESCE(ak.metadata->>'role', 'public') AS caller_role
        FROM memory_service.api_keys ak
        JOIN memory_service.tenants t ON t.id = ak.tenant_id
        WHERE ak.key_hash = %s
          AND t.active = true
        LIMIT 1
    """
    rows = _db_execute_rows(query, (api_key_hash,), tenant_id="00000000-0000-0000-0000-000000000000")

    if rows:
        r = rows[0]
        status = r[7]
        rotation_expired = r[8]
        if status == 'revoked' or rotation_expired:
            return None
        # Update last_used_at fire-and-forget (doesn't block the response)
        try:
            _db_execute_rows(
                "UPDATE memory_service.api_keys SET last_used_at = now() WHERE key_hash = %s",
                (api_key_hash,),
                tenant_id="00000000-0000-0000-0000-000000000000",
            )
        except Exception:
            pass  # last_used_at is observability, not correctness
        return {
            "id": r[0],
            "name": r[1],
            "plan": r[2],
            "memory_limit": int(r[3]) if r[3] is not None else 0,
            "rate_limit_rpm": int(r[4]) if r[4] is not None else 60,
            "active": bool(r[5]),
            "api_calls_count": int(r[6] or 0),
            "_key_status": status,  # surfaced for auth-time logging
        }

    # Fallback: legacy lookup against tenants.api_key_hash for any pre-backfill rows
    fallback_query = """
        SELECT id, name, plan, memory_limit, rate_limit_rpm, active, api_calls_count
        FROM memory_service.tenants
        WHERE api_key_hash = %s AND active = true
        LIMIT 1
    """
    rows = _db_execute_rows(fallback_query, (api_key_hash,), tenant_id="00000000-0000-0000-0000-000000000000")
    if rows:
        r = rows[0]
        return {
            "id": r[0],
            "name": r[1],
            "plan": r[2],
            "memory_limit": int(r[3]) if r[3] is not None else 0,
            "rate_limit_rpm": int(r[4]) if r[4] is not None else 60,
            "active": bool(r[5]),
            "api_calls_count": int(r[6] or 0),
            "_key_status": "legacy_tenant_row",
        }
    return None


def create_tenant(name: str, plan: str = 'free') -> dict:
    """Create a new tenant and return tenant info with API key."""
    import hashlib
    import secrets
    
    # Generate API key
    api_key = f"zl_live_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Default limits by plan
    limits = {
        'free': {'memory_limit': 10000, 'rate_limit_rpm': 20},
        'pro': {'memory_limit': 50000, 'rate_limit_rpm': 100},
        'enterprise': {'memory_limit': 500000, 'rate_limit_rpm': 500}
    }
    
    plan_limits = limits.get(plan, limits['free'])
    
    # Insert tenant (bypassing RLS for admin operation)
    query = """
        INSERT INTO memory_service.tenants (name, api_key_hash, api_key_live, plan, memory_limit, rate_limit_rpm)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, created_at;
    """
    
    params = (
        name,
        api_key_hash,
        api_key,  # Store plaintext key for dashboard display
        plan,
        plan_limits['memory_limit'],
        plan_limits['rate_limit_rpm']
    )
    
    rows = _db_execute(query, params, tenant_id="00000000-0000-0000-0000-000000000000")
    
    if rows:
        parts = rows[0].split("|||")
        return {
            "tenant_id": parts[0],
            "name": name,
            "api_key": api_key,
            "plan": plan,
            "created_at": parts[1],
            "memory_limit": plan_limits['memory_limit'],
            "rate_limit_rpm": plan_limits['rate_limit_rpm']
        }
    
    raise RuntimeError("Failed to create tenant")


def track_api_usage(tenant_id: str, endpoint: str, tokens_used: int = 0, 
                   response_time_ms: int = 0, status_code: int = 200):
    """Track API usage for a tenant."""
    try:
        # Use a transaction for both operations
        pool = _get_connection_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        
        try:
            cur.execute("BEGIN")
            cur.execute("SELECT memory_service.set_tenant_context(%s)", (tenant_id,))
            
            cur.execute("""
                INSERT INTO memory_service.api_usage 
                    (tenant_id, endpoint, tokens_used, response_time_ms, status_code)
                VALUES (%s::UUID, %s, %s, %s, %s)
            """, (tenant_id, endpoint, tokens_used, response_time_ms, status_code))
            
            cur.execute("""
                UPDATE memory_service.tenants 
                SET api_calls_count = api_calls_count + 1, last_api_call = now()
                WHERE id = %s::UUID
            """, (tenant_id,))
            
            cur.execute("COMMIT")
            
        except Exception as e:
            cur.execute("ROLLBACK")
            raise e
        finally:
            cur.close()
            pool.putconn(conn)
            
    except Exception as e:
        print(f"Failed to track usage: {e}")


# --- CLI ---
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create-tenant":
        name = sys.argv[2] if len(sys.argv) > 2 else "Test Tenant"
        plan = sys.argv[3] if len(sys.argv) > 3 else "free"
        tenant = create_tenant(name, plan)
        print(json.dumps(tenant, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        tenant_id = sys.argv[2] if len(sys.argv) > 2 else "00000000-0000-0000-0000-000000000000"
        agent = sys.argv[3] if len(sys.argv) > 3 else "thomas"
        set_tenant_context(tenant_id)
        stats = get_memory_stats(agent)
        print(json.dumps(stats, indent=2))
    else:
        print("Usage:")
        print("  python storage_multitenant_secure.py create-tenant <name> [plan]")
        print("  python storage_multitenant_secure.py stats <tenant_id> [agent]")