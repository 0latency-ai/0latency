"""
Fixed version of the recall function with robust SQL query construction.
"""

import os
import subprocess
import requests
import json
import math
from datetime import datetime, timezone
from typing import Optional


# --- Configuration ---

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
DB_CONN = os.environ.get("MEMORY_DB_CONN",
    "postgresql://postgres.fuojxlabvhtmysbsixdn:jcYlwEhuHN9VcOuj@aws-1-us-east-1.pooler.supabase.com:5432/postgres")


def _db_execute(query: str) -> list:
    """Execute a query against the database."""
    result = subprocess.run(
        ["psql", DB_CONN, "-t", "-A", "-F", "|||", "-c", query],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "PGPASSWORD": "jcYlwEhuHN9VcOuj"}
    )
    if result.returncode != 0:
        raise RuntimeError(f"DB error: {result.stderr}")
    rows = [line for line in result.stdout.strip().split("\n") if line]
    return rows


def _embed_text(text: str) -> list[float]:
    """Generate embedding for recall query."""
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


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars ≈ 1 token)."""
    return max(1, len(text) // 4)


def _load_agent_config(agent_id: str) -> dict:
    """Load agent configuration from DB."""
    try:
        rows = _db_execute(f"""
            SELECT context_budget, recency_weight, semantic_weight, 
                   importance_weight, access_weight, recency_half_life_days,
                   identity::text, user_profile::text
            FROM memory_service.agent_config
            WHERE agent_id = '{agent_id}'
        """)
        
        if rows:
            parts = rows[0].split("|||")
            return {
                "context_budget": int(parts[0]) if parts[0] else 4000,
                "recency_weight": float(parts[1]) if parts[1] else 0.35,
                "semantic_weight": float(parts[2]) if parts[2] else 0.4,
                "importance_weight": float(parts[3]) if parts[3] else 0.15,
                "access_weight": float(parts[4]) if parts[4] else 0.1,
                "recency_half_life_days": int(parts[5]) if parts[5] else 14,
                "identity": json.loads(parts[6]) if parts[6] and parts[6] != '{}' else {},
                "user_profile": json.loads(parts[7]) if parts[7] and parts[7] != '{}' else {},
            }
    except Exception as e:
        print(f"Warning: Could not load agent config: {e}")
    
    # Return defaults if config loading fails
    return {
        "context_budget": 4000,
        "recency_weight": 0.35,
        "semantic_weight": 0.4,
        "importance_weight": 0.15,
        "access_weight": 0.1,
        "recency_half_life_days": 14,
        "identity": {},
        "user_profile": {},
    }


def _build_always_include(agent_id: str) -> tuple[str, int]:
    """Build the always-included context block (identity, profile, last handoff, active corrections)."""
    blocks = []
    
    # Agent identity and user profile from config
    config = _load_agent_config(agent_id)
    
    if config.get("identity"):
        blocks.append(f"### Agent Identity\n{json.dumps(config['identity'], indent=2)}")
    
    if config.get("user_profile"):
        blocks.append(f"### User Profile\n{json.dumps(config['user_profile'], indent=2)}")
    
    try:
        # Latest session handoff
        rows = _db_execute(f"""
            SELECT summary FROM memory_service.session_handoffs
            WHERE agent_id = '{agent_id}'
            ORDER BY created_at DESC LIMIT 1
        """)
        if rows:
            blocks.append(f"### Last Session Summary\n{rows[0]}")
    except Exception:
        pass  # Don't let handoff failures block recall
    
    try:
        # Active corrections (always surface to prevent errors)
        rows = _db_execute(f"""
            SELECT headline, context FROM memory_service.memories
            WHERE agent_id = '{agent_id}'
              AND memory_type = 'correction'
              AND superseded_at IS NULL
            ORDER BY created_at DESC LIMIT 5
        """)
        if rows:
            corrections = []
            for row in rows:
                parts = row.split("|||")
                corrections.append(f"- ⚠️ {parts[0]}: {parts[1] if len(parts) > 1 else ''}")
            blocks.append(f"### Active Corrections\n" + "\n".join(corrections))
    except Exception:
        pass  # Don't let correction failures block recall
    
    always_block = "\n\n".join(blocks) if blocks else ""
    return always_block, _estimate_tokens(always_block)


def _retrieve_candidates(agent_id: str, embedding_str: str, context_text: str) -> list[dict]:
    """Retrieve candidate memories using multiple strategies - FIXED VERSION."""
    
    candidates = {}
    
    # Strategy 1: Semantic similarity search (top 30)
    try:
        rows = _db_execute(f"""
            SELECT id, headline, context, full_content, memory_type,
                   importance, access_count, reinforcement_count,
                   created_at, superseded_at,
                   1 - (embedding <=> '{embedding_str}'::extensions.vector) as similarity
            FROM memory_service.memories
            WHERE agent_id = '{agent_id}'
              AND superseded_at IS NULL
              AND embedding IS NOT NULL
            ORDER BY embedding <=> '{embedding_str}'::extensions.vector
            LIMIT 30
        """)
        
        for row in rows:
            parts = row.split("|||")
            if len(parts) >= 11:
                mem_id = parts[0]
                candidates[mem_id] = {
                    "id": mem_id,
                    "headline": parts[1],
                    "context": parts[2],
                    "full_content": parts[3],
                    "memory_type": parts[4],
                    "importance": float(parts[5]) if parts[5] else 0.5,
                    "access_count": int(parts[6]) if parts[6] else 0,
                    "reinforcement_count": int(parts[7]) if parts[7] else 1,
                    "created_at": datetime.fromisoformat(parts[8].replace("+00", "+00:00")) if parts[8] else datetime.now(timezone.utc),
                    "superseded_at": parts[9] if parts[9] else None,
                    "similarity": float(parts[10]) if parts[10] else 0,
                }
    except Exception as e:
        print(f"Warning: Semantic search failed: {e}")
    
    # Strategy 2: High-importance memories (always consider)
    try:
        # Create safe exclusion list
        exclusion_list = "'" + "','".join(candidates.keys()) + "'" if candidates else "'00000000-0000-0000-0000-000000000000'"
        
        rows2 = _db_execute(f"""
            SELECT id, headline, context, full_content, memory_type,
                   importance, access_count, reinforcement_count,
                   created_at, superseded_at, 0.5 as similarity
            FROM memory_service.memories
            WHERE agent_id = '{agent_id}'
              AND superseded_at IS NULL
              AND importance > 0.8
              AND id NOT IN ({exclusion_list})
            ORDER BY importance DESC
            LIMIT 10
        """)
        
        for row in rows2:
            parts = row.split("|||")
            if len(parts) >= 11:
                mem_id = parts[0]
                if mem_id not in candidates:
                    candidates[mem_id] = {
                        "id": mem_id,
                        "headline": parts[1],
                        "context": parts[2],
                        "full_content": parts[3],
                        "memory_type": parts[4],
                        "importance": float(parts[5]) if parts[5] else 0.5,
                        "access_count": int(parts[6]) if parts[6] else 0,
                        "reinforcement_count": int(parts[7]) if parts[7] else 1,
                        "created_at": datetime.fromisoformat(parts[8].replace("+00", "+00:00")) if parts[8] else datetime.now(timezone.utc),
                        "superseded_at": parts[9] if parts[9] else None,
                        "similarity": float(parts[10]) if parts[10] else 0,
                    }
    except Exception as e:
        print(f"Warning: High-importance search failed: {e}")
    
    # Strategy 3: Keyword/text search (simplified and safer)
    try:
        import re
        words = re.findall(r'\b[a-zA-Z]{3,}\b', context_text.lower())
        stop_words = {'this', 'that', 'with', 'from', 'what', 'when', 'where', 'which', 'about',
                      'have', 'been', 'will', 'would', 'could', 'should', 'their', 'there'}
        keywords = [w for w in words if w not in stop_words][:5]  # Limit to top 5 keywords

        if keywords:
            # Create safe keyword conditions
            keyword_conditions = []
            for kw in keywords:
                # Escape single quotes in keywords
                safe_kw = kw.replace("'", "''")
                keyword_conditions.append(f"(headline ILIKE '%{safe_kw}%' OR context ILIKE '%{safe_kw}%')")
            
            if keyword_conditions:
                exclusion_list = "'" + "','".join(candidates.keys()) + "'" if candidates else "'00000000-0000-0000-0000-000000000000'"
                
                rows_kw = _db_execute(f"""
                    SELECT id, headline, context, full_content, memory_type,
                           importance, access_count, reinforcement_count,
                           created_at, superseded_at, 0.35 as similarity
                    FROM memory_service.memories
                    WHERE agent_id = '{agent_id}'
                      AND superseded_at IS NULL
                      AND ({' OR '.join(keyword_conditions)})
                      AND id NOT IN ({exclusion_list})
                    ORDER BY importance DESC
                    LIMIT 15
                """)

                for row in rows_kw:
                    parts = row.split("|||")
                    if len(parts) >= 11:
                        mem_id = parts[0]
                        if mem_id not in candidates:
                            candidates[mem_id] = {
                                "id": mem_id,
                                "headline": parts[1],
                                "context": parts[2],
                                "full_content": parts[3],
                                "memory_type": parts[4],
                                "importance": float(parts[5]) if parts[5] else 0.5,
                                "access_count": int(parts[6]) if parts[6] else 0,
                                "reinforcement_count": int(parts[7]) if parts[7] else 1,
                                "created_at": datetime.fromisoformat(parts[8].replace("+00", "+00:00")) if parts[8] else datetime.now(timezone.utc),
                                "superseded_at": parts[9] if parts[9] else None,
                                "similarity": float(parts[10]) if parts[10] else 0,
                            }
    except Exception as e:
        print(f"Warning: Keyword search failed: {e}")

    return list(candidates.values())


def recall_fixed(
    agent_id: str,
    conversation_context: str,
    budget_tokens: int = 4000,
) -> dict:
    """
    FIXED VERSION of recall function with better error handling.
    """
    
    print(f"Starting recall for agent '{agent_id}' with query: '{conversation_context[:100]}...'")
    
    # Step 1: Load agent config (with defaults)
    config = _load_agent_config(agent_id)
    print(f"Loaded config: {config}")
    
    semantic_weight = config.get("semantic_weight", 0.4)
    recency_weight = config.get("recency_weight", 0.35)
    importance_weight = config.get("importance_weight", 0.15)
    access_weight = config.get("access_weight", 0.1)
    half_life_days = config.get("recency_half_life_days", 14)
    
    # Step 2: Always-include block
    always_block, always_tokens = _build_always_include(agent_id)
    remaining_budget = budget_tokens - always_tokens
    print(f"Always-include: {always_tokens} tokens, remaining budget: {remaining_budget}")
    
    if remaining_budget <= 0:
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": 0,
            "recall_details": [],
        }
    
    # Step 3: Generate query embedding
    print("Generating embedding...")
    try:
        query_embedding = _embed_text(conversation_context[:2000])
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
        print(f"✅ Generated embedding with {len(query_embedding)} dimensions")
    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }
    
    # Step 4: Retrieve candidates
    print("Retrieving candidates...")
    candidates = _retrieve_candidates(agent_id, embedding_str, conversation_context)
    print(f"Retrieved {len(candidates)} candidates")
    
    if not candidates:
        print("❌ No candidates found")
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }
    
    # Step 5: Score each candidate
    print("Scoring candidates...")
    now = datetime.now(timezone.utc)
    scored = []
    
    for c in candidates:
        try:
            # Semantic similarity (already from DB, 0-1)
            semantic_sim = c["similarity"]
            
            # Recency score (exponential decay)
            days_since = (now - c["created_at"]).total_seconds() / 86400
            recency = math.exp(-0.693 * days_since / half_life_days)
            
            # Importance (boosted by reinforcement)
            importance = c["importance"] * (1 + 0.1 * min(c["reinforcement_count"], 5))
            importance = min(importance, 1.0)
            
            # Access frequency (capped at 1.0)
            access_freq = min(c["access_count"] / 10, 1.0)
            
            # Composite score
            composite = (
                semantic_weight * semantic_sim +
                recency_weight * recency +
                importance_weight * importance +
                access_weight * access_freq
            )
            
            # Type bonuses
            if c["memory_type"] == "identity":
                composite *= 1.5
            elif c["memory_type"] in ("correction", "preference"):
                composite *= 1.3
            elif c["memory_type"] == "decision" and days_since < 7:
                composite *= 1.2
            
            # Skip superseded facts
            if c.get("superseded_at"):
                continue
            
            scored.append({
                **c,
                "composite": composite,
                "semantic_sim": semantic_sim,
                "recency_score": recency,
                "importance_boosted": importance,
                "access_score": access_freq,
            })
        except Exception as e:
            print(f"Warning: Failed to score candidate {c.get('id', 'unknown')}: {e}")
            continue
    
    # Step 6: Rank by composite score
    scored.sort(key=lambda x: x["composite"], reverse=True)
    print(f"Scored {len(scored)} candidates, top score: {scored[0]['composite']:.3f}" if scored else "No candidates scored")
    
    # Step 7: Fill budget using tiered loading
    selected = []
    tokens_used = 0
    
    for candidate in scored:
        if remaining_budget - tokens_used <= 0:
            break
        
        # Choose tier based on composite score
        if candidate["composite"] > 0.7:
            text = candidate["context"]
            tier = "L1"
        elif candidate["composite"] > 0.4:
            text = candidate["headline"]
            tier = "L0"
        else:
            continue
        
        tokens = _estimate_tokens(text)
        
        if tokens <= (remaining_budget - tokens_used):
            selected.append({
                "text": text,
                "tier": tier,
                "type": candidate["memory_type"],
                "composite": round(candidate["composite"], 3),
                "headline": candidate["headline"],
                "id": candidate["id"],
            })
            tokens_used += tokens
    
    print(f"Selected {len(selected)} memories using {tokens_used} tokens")
    
    # Step 8: Format context block
    context_block = always_block
    if selected:
        context_block += "\n\n### Relevant Context\n"
        for mem in selected:
            tier_marker = "•" if mem["tier"] == "L0" else "→"
            context_block += f"  {tier_marker} {mem['text']}\n"
    
    total_tokens = always_tokens + tokens_used
    
    return {
        "context_block": context_block,
        "memories_used": len(selected),
        "tokens_used": total_tokens,
        "budget_remaining": budget_tokens - total_tokens,
        "recall_details": [
            {
                "id": s["id"],
                "headline": s["headline"],
                "type": s["type"],
                "tier": s["tier"],
                "composite": s["composite"],
            }
            for s in selected
        ],
    }


# Test function
if __name__ == "__main__":
    os.environ["GOOGLE_API_KEY"] = "AIzaSyAvFCk21Sz4G3AbKm9USob55DqJnpJBVmI"
    
    test_queries = [
        "memory product decisions",
        "pricing", 
        "pre-launch checklist",
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Testing: '{query}'")
        print('='*60)
        
        try:
            result = recall_fixed("thomas", query, budget_tokens=2000)
            print(f"✅ Result: {result['memories_used']} memories, {result['tokens_used']} tokens")
            
            if result['recall_details']:
                print("Top results:")
                for detail in result['recall_details'][:3]:
                    print(f"  - [{detail['type']}] {detail['headline']} (score: {detail['composite']})")
            else:
                print("No recall details")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()