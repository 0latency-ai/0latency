"""
Multi-Tenant Storage Layer — Agent Memory Service
Phase B: Enhanced with tenant isolation and Row Level Security (RLS).
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

# Global tenant context
_current_tenant_id = None

def set_tenant_context(tenant_id: str):
    """Set the current tenant context for this session."""
    global _current_tenant_id
    _current_tenant_id = tenant_id


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


def _db_execute(query: str, params: dict = None, tenant_id: str = None) -> list:
    """Execute a query against the database with tenant isolation."""
    import subprocess
    
    # Use tenant_id parameter or global context
    current_tenant = tenant_id or _current_tenant_id
    if not current_tenant:
        raise ValueError("No tenant context set. Call set_tenant_context() first.")
    
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
    
    # Prepend tenant context setting to the query
    full_query = f"""
        SELECT memory_service.set_tenant_context('{current_tenant}'::UUID);
        {query}
    """
    
    result = subprocess.run(
        ["psql", DB_CONN, "-t", "-A", "-F", "|||", "-c", full_query],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "PGPASSWORD": "jcYlwEhuHN9VcOuj"}
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"DB error: {result.stderr}")
    
    # Skip the first line (set_tenant_context result) and process actual query results
    lines = result.stdout.strip().split("\n")
    # Filter out: empty lines, set_tenant_context output, INSERT/UPDATE status lines
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip tenant context function return value (UUID of the tenant)
        if line == current_tenant:
            continue
        # Skip SQL status messages
        if line.startswith("INSERT ") or line.startswith("UPDATE ") or line.startswith("DELETE "):
            continue
        if line.startswith("SET") or line == "":
            continue
        rows.append(line)
    return rows


def store_memory(memory: dict, tenant_id: str = None) -> str:
    """
    Store a single extracted memory with embedding and tenant isolation.
    
    Args:
        memory: Structured memory object from extraction layer
        tenant_id: UUID of the tenant (uses global context if not provided)
    
    Returns:
        UUID of stored memory
    """
    current_tenant = tenant_id or _current_tenant_id
    if not current_tenant:
        raise ValueError("No tenant context set")
    
    # Generate embedding from headline + context (not full_content — saves tokens)
    embed_text = f"{memory['headline']}. {memory['context']}"
    embedding = _embed_text(embed_text)
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    
    # Check for duplicate/reinforcement within this tenant
    existing = _check_duplicate(memory['agent_id'], memory['headline'], embedding, 
                               memory_type=memory.get('memory_type'), tenant_id=current_tenant)
    
    if existing:
        # Reinforce existing memory
        _db_execute(f"""
            UPDATE memory_service.memories 
            SET reinforcement_count = reinforcement_count + 1,
                relevance_score = LEAST(1.0, relevance_score + 0.1),
                last_accessed = now()
            WHERE id = '{existing}'
        """, tenant_id=current_tenant)
        print(f"  ↑ Reinforced existing memory: {existing}")
        return existing
    
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
    
    query = f"""
        INSERT INTO memory_service.memories 
            (tenant_id, agent_id, headline, context, full_content, memory_type, 
             entities, project, categories, scope,
             importance, confidence, embedding,
             source_session, source_turn, metadata)
        VALUES 
            ('{current_tenant}'::UUID, '{memory['agent_id']}', '{headline}', '{context}', '{full_content}', '{memory['memory_type']}',
             '{entities_str}', {project_sql}, '{categories_str}', '{scope}',
             {memory.get('importance', 0.5)}, {memory.get('confidence', 0.8)}, '{embedding_str}'::extensions.vector,
             {source_session_sql}, {source_turn_sql}, '{metadata_sql}'::jsonb)
        RETURNING id;
    """
    
    rows = _db_execute(query, tenant_id=current_tenant)
    mem_id = rows[0].split("|||")[0] if rows else None
    
    # Handle corrections — supersede old memories within tenant
    if memory['memory_type'] == 'correction' and mem_id:
        _handle_correction(memory, mem_id, current_tenant)
    
    # Index entities for cross-entity linking within tenant
    if mem_id and memory.get('entities'):
        _index_entities(memory['agent_id'], mem_id, memory['entities'], current_tenant)
        # Auto-create edges between memories sharing entities
        _create_entity_edges(memory['agent_id'], mem_id, memory['entities'], current_tenant)
    
    # Audit log
    _db_execute(f"""
        INSERT INTO memory_service.memory_audit_log (tenant_id, agent_id, action, memory_id, details)
        VALUES ('{current_tenant}'::UUID, '{memory['agent_id']}', 'extract', '{mem_id}', 
                '{json.dumps({"headline": memory["headline"], "type": memory["memory_type"]}).replace("'", "''")}')
    """, tenant_id=current_tenant)
    
    return mem_id


def _check_duplicate(agent_id: str, headline: str, embedding: list[float], 
                    threshold: float = 0.85, memory_type: str = None, tenant_id: str = None) -> Optional[str]:
    """Check if a very similar memory already exists within the tenant."""
    current_tenant = tenant_id or _current_tenant_id
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    
    rows = _db_execute(f"""
        SELECT id, headline, memory_type,
               1 - (embedding <=> '{embedding_str}'::extensions.vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
          AND superseded_at IS NULL
        ORDER BY embedding <=> '{embedding_str}'::extensions.vector
        LIMIT 3
    """, tenant_id=current_tenant)
    
    if rows:
        for row in rows:
            parts = row.split("|||")
            if len(parts) >= 4:
                mem_id, existing_headline, existing_type, similarity = parts[0], parts[1], parts[2].strip(), float(parts[3])
                
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
    """, tenant_id=current_tenant)
    
    if not rows:
        return None
    
    for row in rows:
        parts = row.split("|||")
        if len(parts) >= 5:
            similarity = float(parts[4])
            existing_headline = parts[1]
            
            # Check for contradictions in similar range
            if 0.78 < similarity < 0.88:
                existing_entities = parts[3].strip("{}").split(",") if parts[3] and parts[3] != "{}" else []
                existing_entities = [e.strip().strip('"') for e in existing_entities if e.strip().strip('"')]
                
                new_headline_lower = headline.lower()
                
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


def _handle_correction(memory: dict, correction_id: str, tenant_id: str):
    """Handle correction by superseding old facts within the tenant."""
    # Search for related memories that this corrects (within tenant only)
    embed_text = f"{memory['headline']}. {memory['context']}"
    embedding = _embed_text(embed_text)
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    
    rows = _db_execute(f"""
        SELECT id, headline, agent_id
        FROM memory_service.memories
        WHERE memory_type != 'correction'
          AND superseded_at IS NULL
          AND id != '{correction_id}'
        ORDER BY embedding <=> '{embedding_str}'::extensions.vector
        LIMIT 5
    """, tenant_id=tenant_id)
    
    if rows:
        for row in rows:
            parts = row.split("|||")
            old_id = parts[0].strip()
            old_headline = parts[1].strip() if len(parts) > 1 else ""
            
            # Supersede the top match within this tenant
            _db_execute(f"""
                UPDATE memory_service.memories
                SET superseded_at = now(), superseded_by = '{correction_id}'
                WHERE id = '{old_id}'
            """, tenant_id=tenant_id)
            print(f"  ✂ Superseded memory: {old_id} ({old_headline})")
            break  # Only supersede top match


def store_memories(memories: list[dict], tenant_id: str = None) -> list[str]:
    """Store multiple memories with tenant isolation. Returns list of UUIDs."""
    ids = []
    for mem in memories:
        try:
            mem_id = store_memory(mem, tenant_id)
            ids.append(mem_id)
            print(f"  💾 Stored [{mem['memory_type']}]: {mem['headline']}")
        except Exception as e:
            print(f"  ❌ Failed to store: {mem['headline']} — {e}")
    return ids


def store_handoff(handoff: dict, tenant_id: str = None) -> str:
    """Store a session handoff record with tenant isolation."""
    current_tenant = tenant_id or _current_tenant_id
    if not current_tenant:
        raise ValueError("No tenant context set")
    
    summary = handoff.get('summary', '').replace("'", "''")
    decisions = json.dumps(handoff.get('decisions_made', [])).replace("'", "''")
    threads = json.dumps(handoff.get('open_threads', [])).replace("'", "''")
    projects = json.dumps(handoff.get('active_projects', [])).replace("'", "''")
    
    rows = _db_execute(f"""
        INSERT INTO memory_service.session_handoffs
            (tenant_id, agent_id, session_key, summary, decisions_made, open_threads, active_projects)
        VALUES 
            ('{current_tenant}'::UUID, '{handoff['agent_id']}', '{handoff.get('session_key', 'unknown')}', 
             '{summary}', '{decisions}'::jsonb, '{threads}'::jsonb, '{projects}'::jsonb)
        RETURNING id;
    """, tenant_id=current_tenant)
    
    return rows[0].split("|||")[0] if rows else None


def get_memory_stats(agent_id: str, tenant_id: str = None) -> dict:
    """Get memory statistics for an agent within a tenant."""
    current_tenant = tenant_id or _current_tenant_id
    if not current_tenant:
        raise ValueError("No tenant context set")
    
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
    """, tenant_id=current_tenant)
    
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
        entity_clean = entity.strip().replace("'", "''")
        if not entity_clean:
            continue
        try:
            _db_execute(f"""
                INSERT INTO memory_service.entity_index (tenant_id, agent_id, entity, memory_id)
                VALUES ('{tenant_id}'::UUID, '{agent_id}', '{entity_clean}', '{memory_id}')
                ON CONFLICT (tenant_id, agent_id, entity, memory_id) DO NOTHING
            """, tenant_id=tenant_id)
        except Exception:
            pass  # Skip duplicates silently


def _create_entity_edges(agent_id: str, new_memory_id: str, entities: list[str], tenant_id: str):
    """Auto-create edges between memories sharing entities within a tenant."""
    for entity in entities:
        entity_clean = entity.strip().replace("'", "''")
        if not entity_clean:
            continue
        
        # Find other memories with the same entity within this tenant
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
            """, tenant_id=tenant_id)
        except Exception:
            continue
        
        for row in rows:
            target_id = row.strip().split("|||")[0]
            if not target_id:
                continue
            try:
                _db_execute(f"""
                    INSERT INTO memory_service.memory_edges 
                        (tenant_id, agent_id, source_memory_id, target_memory_id, relationship, strength)
                    VALUES 
                        ('{tenant_id}'::UUID, '{agent_id}', '{new_memory_id}', '{target_id}', 'related_to', 0.5)
                    ON CONFLICT (source_memory_id, target_memory_id, relationship) DO UPDATE
                    SET strength = memory_service.memory_edges.strength + 0.1
                """, tenant_id=tenant_id)
            except Exception:
                pass  # Skip edge creation failures


def get_tenant_by_api_key(api_key_hash: str) -> Optional[dict]:
    """Look up tenant by API key hash."""
    import subprocess
    
    # Direct query without RLS bypass - tenants table doesn't have RLS enabled yet
    # We'll disable RLS on tenants table since it's needed for auth lookup
    DB_CONN = "postgresql://postgres.fuojxlabvhtmysbsixdn:jcYlwEhuHN9VcOuj@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
    
    query = f"""
        SELECT id, name, plan, memory_limit, rate_limit_rpm, active, api_calls_count
        FROM memory_service.tenants 
        WHERE api_key_hash = '{api_key_hash}' AND active = true;
    """
    
    result = subprocess.run(
        ["psql", DB_CONN, "-t", "-A", "-F", "|||", "-c", query],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "PGPASSWORD": "jcYlwEhuHN9VcOuj"}
    )
    
    if result.returncode != 0:
        print(f"DB error in get_tenant_by_api_key: {result.stderr}")
        return None
    
    rows = [line for line in result.stdout.strip().split("\n") if line]
    if rows:
        parts = rows[0].split("|||")
        if len(parts) >= 7:
            return {
                "id": parts[0],
                "name": parts[1],
                "plan": parts[2],
                "memory_limit": int(parts[3]),
                "rate_limit_rpm": int(parts[4]),
                "active": parts[5] == 't',
                "api_calls_count": int(parts[6] or 0),
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
        'free': {'memory_limit': 1000, 'rate_limit_rpm': 20},
        'pro': {'memory_limit': 50000, 'rate_limit_rpm': 100},
        'enterprise': {'memory_limit': 500000, 'rate_limit_rpm': 500}
    }
    
    plan_limits = limits.get(plan, limits['free'])
    
    # Insert tenant (bypassing RLS for admin operation)
    rows = _db_execute(f"""
        SET session_authorization postgres;
        INSERT INTO memory_service.tenants (name, api_key_hash, plan, memory_limit, rate_limit_rpm)
        VALUES ('{name.replace("'", "''")}', '{api_key_hash}', '{plan}', 
                {plan_limits['memory_limit']}, {plan_limits['rate_limit_rpm']})
        RETURNING id, created_at;
        RESET session_authorization;
    """, tenant_id="00000000-0000-0000-0000-000000000000")
    
    if rows and len(rows) > 1:
        parts = rows[1].split("|||")
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
        _db_execute(f"""
            INSERT INTO memory_service.api_usage 
                (tenant_id, endpoint, tokens_used, response_time_ms, status_code)
            VALUES ('{tenant_id}'::UUID, '{endpoint}', {tokens_used}, {response_time_ms}, {status_code});
            
            UPDATE memory_service.tenants 
            SET api_calls_count = api_calls_count + 1, last_api_call = now()
            WHERE id = '{tenant_id}'::UUID;
        """, tenant_id=tenant_id)
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
        print("  python storage_multitenant.py create-tenant <name> [plan]")
        print("  python storage_multitenant.py stats <tenant_id> [agent]")