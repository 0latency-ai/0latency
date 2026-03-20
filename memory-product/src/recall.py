"""
Recall Layer — Agent Memory Service
Phase 3: Proactive, budget-aware, temporally-weighted context injection.

This is the core differentiator. Nobody does proactive + budget-aware + temporal recall well.
"""

import json
import math
import os
import subprocess
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
    import requests
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


def estimate_dynamic_budget(conversation_context: str, base_budget: int = 3000) -> int:
    """
    Dynamically scale the recall budget based on conversation complexity.
    
    Heuristics:
    - More unique topics/entities → higher budget (need more context)
    - Longer conversation context → more complex discussion → higher budget
    - Short casual exchange → lower budget (save tokens)
    
    Returns budget between base_budget * 0.5 and base_budget * 2.0
    """
    context_len = len(conversation_context)
    
    # Count unique "topic signals" — rough proxy for complexity
    # Look for entities, project names, numbers, URLs
    import re
    entities = set(re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', conversation_context))
    numbers = set(re.findall(r'\$[\d,]+|\d+%|\d{4}', conversation_context))
    
    topic_count = len(entities) + len(numbers)
    
    # Scale factor: 0.5x to 2.0x
    if context_len < 200 and topic_count < 3:
        # Casual / simple exchange
        scale = 0.6
    elif context_len < 500 and topic_count < 6:
        # Moderate complexity
        scale = 0.8
    elif context_len < 1500 or topic_count < 10:
        # Standard complexity
        scale = 1.0
    elif context_len < 3000 or topic_count < 20:
        # Complex discussion
        scale = 1.4
    else:
        # Very complex / multi-topic
        scale = 1.8
    
    budget = int(base_budget * scale)
    # Clamp to reasonable range
    return max(1500, min(budget, 6000))


def recall(
    agent_id: str,
    conversation_context: str,
    budget_tokens: int = 4000,
    dynamic_budget: bool = False,
    config: Optional[dict] = None,
) -> dict:
    """
    Proactive, budget-aware, temporally-weighted recall.
    
    Args:
        agent_id: Which agent is requesting recall
        conversation_context: Recent conversation (last 2-3 turns)
        budget_tokens: Maximum tokens for memory injection (overridden if dynamic_budget=True)
        dynamic_budget: If True, auto-scale budget based on conversation complexity
        config: Optional override for scoring weights
    
    Returns:
        {
            "context_block": str,       # Formatted text to inject into system prompt
            "memories_used": int,       # How many memories included
            "tokens_used": int,         # Estimated tokens consumed
            "budget_remaining": int,    # Tokens left in budget
            "recall_details": list,     # Debug info about what was recalled and why
        }
    """
    
    # --- Step 0: Dynamic budget scaling ---
    if dynamic_budget:
        base = config.get("context_budget", budget_tokens) if config else budget_tokens
        budget_tokens = estimate_dynamic_budget(conversation_context, base)
    
    # --- Step 1: Load agent config ---
    if not config:
        config = _load_agent_config(agent_id)
    
    semantic_weight = config.get("semantic_weight", 0.4)
    recency_weight = config.get("recency_weight", 0.35)
    importance_weight = config.get("importance_weight", 0.15)
    access_weight = config.get("access_weight", 0.1)
    half_life_days = config.get("recency_half_life_days", 14)
    
    # --- Step 2: Always-include block (identity, user profile, latest handoff) ---
    always_block, always_tokens = _build_always_include(agent_id)
    remaining_budget = budget_tokens - always_tokens
    
    if remaining_budget <= 0:
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": 0,
            "recall_details": [],
        }
    
    # --- Step 2.5: Negative recall — detect gaps ---
    gap_warning = None
    try:
        from negative_recall import detect_gaps
        gap_result = detect_gaps(agent_id, conversation_context[:500])
        gap_warning = gap_result.get("gap_warning")
    except Exception:
        pass  # Don't let negative recall failures block regular recall
    
    # --- Step 3: Generate query embedding from conversation context ---
    query_embedding = _embed_text(conversation_context[:2000])  # Cap to avoid huge embeds
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    
    # --- Step 4: Candidate retrieval (cast a wide net) ---
    candidates = _retrieve_candidates(agent_id, embedding_str, conversation_context)
    
    if not candidates:
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }
    
    # --- Step 4.5: Conversational momentum — pull in entity-linked memories ---
    # For the top semantic matches, find connected memories via the entity graph
    # This preloads related context even before the user explicitly asks about it
    candidate_ids = {c["id"] for c in candidates}
    momentum_candidates = []
    
    top_candidates = sorted(candidates, key=lambda x: x["similarity"], reverse=True)[:5]
    for tc in top_candidates:
        try:
            linked_rows = _db_execute(f"""
                SELECT DISTINCT m.id, m.headline, m.context, m.full_content,
                       m.memory_type, m.importance, m.confidence,
                       m.entities::text, m.categories::text, m.scope,
                       m.created_at, m.access_count, m.reinforcement_count,
                       0.6 as similarity,
                       m.superseded_at
                FROM memory_service.memory_edges me
                JOIN memory_service.memories m ON (
                    CASE WHEN me.source_memory_id = '{tc["id"]}' THEN m.id = me.target_memory_id
                         ELSE m.id = me.source_memory_id END
                )
                WHERE (me.source_memory_id = '{tc["id"]}' OR me.target_memory_id = '{tc["id"]}')
                  AND me.agent_id = '{agent_id}'
                  AND m.superseded_at IS NULL
                  AND me.strength >= 0.4
                LIMIT 3
            """)
            
            for row in linked_rows:
                parts = row.split("|||")
                if len(parts) >= 14:
                    linked_id = parts[0]
                    if linked_id not in candidate_ids:
                        candidate_ids.add(linked_id)
                        momentum_candidates.append({
                            "id": linked_id,
                            "headline": parts[1],
                            "context": parts[2],
                            "full_content": parts[3],
                            "memory_type": parts[4],
                            "importance": float(parts[5] or 0.5),
                            "confidence": float(parts[6] or 0.8),
                            "entities": parts[7],
                            "categories": parts[8],
                            "scope": parts[9],
                            "created_at": datetime.fromisoformat(parts[10].replace('+00', '+00:00')) if parts[10] else now,
                            "access_count": int(parts[11] or 0),
                            "reinforcement_count": int(parts[12] or 0),
                            "similarity": 0.55,  # Momentum bonus — not as strong as direct semantic match
                            "superseded_at": parts[14] if len(parts) > 14 and parts[14] else None,
                            "_momentum": True,  # Flag for debugging
                        })
        except Exception:
            pass  # Don't let momentum failures block recall
    
    candidates.extend(momentum_candidates)
    
    # --- Step 5: Score each candidate ---
    now = datetime.now(timezone.utc)
    scored = []
    
    for c in candidates:
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
            composite *= 1.5  # Identity facts are always critical
        elif c["memory_type"] in ("correction", "preference"):
            composite *= 1.3  # Prevent errors and frustration
        elif c["memory_type"] == "decision" and days_since < 7:
            composite *= 1.2  # Recent decisions are actionable
        
        # Never return superseded facts
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
    
    # --- Step 6: Rank by composite score ---
    scored.sort(key=lambda x: x["composite"], reverse=True)
    
    # --- Step 7: Fill budget using tiered loading ---
    selected = []
    tokens_used = 0
    
    for candidate in scored:
        if remaining_budget - tokens_used <= 0:
            break
        
        # Choose tier based on composite score
        if candidate["composite"] > 0.7:
            # High relevance: use L1 (context level)
            text = candidate["context"]
            tier = "L1"
        elif candidate["composite"] > 0.4:
            # Medium relevance: use L0 (headline only)
            text = candidate["headline"]
            tier = "L0"
        else:
            # Low relevance: skip
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
            
            # Update access stats
            _update_access(candidate["id"])
    
    # --- Step 8: Format as structured context block ---
    context_block = _format_context_block(always_block, selected)
    
    # Append gap warning from negative recall
    if gap_warning:
        context_block += f"\n\n### Knowledge Gaps\n{gap_warning}"
    
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


def _load_agent_config(agent_id: str) -> dict:
    """Load agent configuration from DB."""
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
    
    return {}  # Defaults


def _build_always_include(agent_id: str) -> tuple[str, int]:
    """Build the always-included context block (identity, profile, last handoff, active corrections)."""
    blocks = []
    
    # Agent identity and user profile from config
    config = _load_agent_config(agent_id)
    
    if config.get("identity"):
        blocks.append(f"### Agent Identity\n{json.dumps(config['identity'], indent=2)}")
    
    if config.get("user_profile"):
        blocks.append(f"### User Profile\n{json.dumps(config['user_profile'], indent=2)}")
    
    # Latest session handoff
    rows = _db_execute(f"""
        SELECT summary FROM memory_service.session_handoffs
        WHERE agent_id = '{agent_id}'
        ORDER BY created_at DESC LIMIT 1
    """)
    if rows:
        blocks.append(f"### Last Session Summary\n{rows[0]}")
    
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
    
    # Active preferences (always surface to prevent frustration)
    rows = _db_execute(f"""
        SELECT headline FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
          AND memory_type = 'preference'
          AND superseded_at IS NULL
          AND relevance_score > 0.3
        ORDER BY importance DESC LIMIT 10
    """)
    if rows:
        prefs = [f"- {row.split('|||')[0]}" for row in rows]
        blocks.append(f"### User Preferences\n" + "\n".join(prefs))
    
    always_block = "\n\n".join(blocks) if blocks else ""
    return always_block, _estimate_tokens(always_block)


def _retrieve_candidates(agent_id: str, embedding_str: str, context_text: str) -> list[dict]:
    """Retrieve candidate memories using multiple strategies."""
    
    # Strategy 1: Semantic similarity search (top 30)
    rows = _db_execute(f"""
        SELECT id, headline, context, full_content, memory_type,
               importance, access_count, reinforcement_count,
               created_at, superseded_at,
               1 - (embedding <=> '{embedding_str}'::extensions.vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
          AND superseded_at IS NULL
        ORDER BY embedding <=> '{embedding_str}'::extensions.vector
        LIMIT 30
    """)
    
    candidates = {}
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
    
    # Strategy 2: High-importance memories (always consider)
    rows2 = _db_execute(f"""
        SELECT id, headline, context, full_content, memory_type,
               importance, access_count, reinforcement_count,
               created_at, superseded_at, 0.5 as similarity
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
          AND superseded_at IS NULL
          AND importance > 0.8
          AND id NOT IN ({','.join(f"'{k}'" for k in candidates.keys()) if candidates else "'00000000-0000-0000-0000-000000000000'"})
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
    
    # Strategy 3: Recently accessed memories (last 48h)
    rows3 = _db_execute(f"""
        SELECT id, headline, context, full_content, memory_type,
               importance, access_count, reinforcement_count,
               created_at, superseded_at, 0.4 as similarity
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
          AND superseded_at IS NULL
          AND last_accessed > now() - interval '48 hours'
          AND id NOT IN ({','.join(f"'{k}'" for k in candidates.keys()) if candidates else "'00000000-0000-0000-0000-000000000000'"})
        ORDER BY last_accessed DESC
        LIMIT 10
    """)
    
    for row in rows3:
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
    
    # Strategy 4: Keyword/text search (catches what semantic search misses)
    import re
    words = re.findall(r'\b[a-zA-Z]{4,}\b', context_text.lower())
    stop_words = {'this', 'that', 'with', 'from', 'what', 'when', 'where', 'which', 'about',
                  'have', 'been', 'will', 'would', 'could', 'should', 'their', 'there', 'these',
                  'those', 'your', 'they', 'into', 'some', 'more', 'also', 'just', 'very',
                  'here', 'then', 'than', 'like', 'well', 'back', 'make', 'made', 'need',
                  'want', 'know', 'think', 'thing', 'things', 'going', 'does', 'doing'}
    keywords = list(set(w for w in words if w not in stop_words))[:8]

    if keywords:
        keyword_conditions = " OR ".join(
            f"(headline ILIKE '%{kw}%' OR context ILIKE '%{kw}%')" for kw in keywords
        )
        exclude_ids = ','.join(f"'{k}'" for k in candidates.keys()) if candidates else "'00000000-0000-0000-0000-000000000000'"

        rows_kw = _db_execute(f"""
            SELECT id, headline, context, full_content, memory_type,
                   importance, access_count, reinforcement_count,
                   created_at, superseded_at, 0.35 as similarity
            FROM memory_service.memories
            WHERE agent_id = '{agent_id}'
              AND superseded_at IS NULL
              AND ({keyword_conditions})
              AND id NOT IN ({exclude_ids})
            ORDER BY importance DESC
            LIMIT 10
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

    return list(candidates.values())


def _update_access(memory_id: str):
    """Update access stats for a recalled memory."""
    _db_execute(f"""
        UPDATE memory_service.memories
        SET last_accessed = now(), access_count = access_count + 1
        WHERE id = '{memory_id}'
    """)


def _format_context_block(always_block: str, selected: list) -> str:
    """Format the final context block for system prompt injection."""
    sections = ["## Agent Memory Context"]
    
    if always_block:
        sections.append(always_block)
    
    if selected:
        # Group by type
        by_type = {}
        for s in selected:
            t = s["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(s)
        
        # Order: preferences first, then corrections, decisions, facts, tasks, relationships
        type_order = ["preference", "correction", "decision", "fact", "task", "relationship"]
        type_labels = {
            "preference": "User Preferences",
            "correction": "Corrections",
            "decision": "Recent Decisions",
            "fact": "Relevant Facts",
            "task": "Active Tasks",
            "relationship": "Relationships",
        }
        
        relevant_section = []
        for t in type_order:
            if t in by_type and t not in ("preference", "correction"):  # Already in always-include
                relevant_section.append(f"\n**{type_labels.get(t, t)}:**")
                for mem in by_type[t]:
                    tier_marker = "•" if mem["tier"] == "L0" else "→"
                    relevant_section.append(f"  {tier_marker} {mem['text']}")
        
        if relevant_section:
            sections.append("### Relevant Context" + "\n".join(relevant_section))
    
    return "\n\n".join(sections)


# --- CLI ---

if __name__ == "__main__":
    import sys
    
    os.environ["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "AIzaSyAvFCk21Sz4G3AbKm9USob55DqJnpJBVmI")
    
    agent = sys.argv[1] if len(sys.argv) > 1 else "test-agent"
    context = sys.argv[2] if len(sys.argv) > 2 else "Tell me about NemoClaw and the memory product"
    
    print(f"Recalling for agent '{agent}'...")
    print(f"Context: {context[:100]}...")
    print()
    
    result = recall(agent, context, budget_tokens=4000)
    
    print(f"Memories used: {result['memories_used']}")
    print(f"Tokens used: {result['tokens_used']}")
    print(f"Budget remaining: {result['budget_remaining']}")
    print()
    
    print("=== CONTEXT BLOCK ===")
    print(result["context_block"])
    print()
    
    print("=== RECALL DETAILS ===")
    for d in result["recall_details"]:
        print(f"  [{d['type'].upper()}] {d['tier']} (score={d['composite']}) {d['headline']}")
