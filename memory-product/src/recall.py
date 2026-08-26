"""
Recall layer — retrieves and ranks memories for agent context injection.

SECURITY HARDENED: Uses psycopg2 with parameterized queries via shared storage layer.
"""

import os
import json
import math
import re
from datetime import datetime, timezone
from typing import Optional

# Use the hardened storage layer's DB and embedding infrastructure
from storage_multitenant import _db_execute, _db_execute_rows, _embed_text, _embed_text_local, set_tenant_context, _get_connection_pool

import psycopg2

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# F2: Keyword-match factor in composite ranking (flag-gated)
RECALL_KEYWORD_MATCH_ENABLED = os.getenv("RECALL_KEYWORD_MATCH_ENABLED", "false").lower() in ("true", "1", "yes")

# F1: Voyage voyage-3-large embedding (flag-gated)
RECALL_USE_VOYAGE = os.getenv("RECALL_USE_VOYAGE", "false").lower() in ("true", "1", "yes")

# F3b: Entity-aware recall strategy (flag-gated)
RECALL_ENTITY_STRATEGY_ENABLED = os.getenv("RECALL_ENTITY_STRATEGY_ENABLED", "false").lower() in ("true", "1", "yes")

# F4: Entity-aware type bonus tuning (flag-gated)
RECALL_TYPE_BONUS_ENTITY_AWARE = os.getenv("RECALL_TYPE_BONUS_ENTITY_AWARE", "false").lower() in ("true", "1", "yes")

# Recency clamp: bound days_since >= 0, IQR adaptive spread [q22-recency-clamp]
RECENCY_CLAMP_ENABLED = os.getenv("RECENCY_CLAMP_ENABLED", "true").lower() in ("true", "1", "yes")
# Peak of the tapered sub-day boost in the cross-agent scorer. 1.0 disables the
# boost entirely and leaves plain exponential decay; the result is capped at 1.0
# regardless, so this widens the fresh-window plateau rather than raising the ceiling.
CROSS_AGENT_SUBDAY_BOOST_MAX = float(os.getenv("CROSS_AGENT_SUBDAY_BOOST_MAX", "2.5"))

# F5: Provenance-aware down-weight. Assistant-stated content is lower-trust than
# user-stated facts; when the assistant pass floods a namespace with topic-adjacent
# memories, they out-rank the user's actual answer facts. This gently demotes
# assistant-sourced memories so user facts rank above them. Gentle + reversible:
# on-topic assistant answers can still recover via the preference/topic boosts that
# run AFTER this in the scoring loop. Default OFF to keep isolation tests clean.
RECALL_ASSISTANT_DOWNWEIGHT_ENABLED = os.getenv("RECALL_ASSISTANT_DOWNWEIGHT_ENABLED", "false").lower() in ("true", "1", "yes")
RECALL_ASSISTANT_DOWNWEIGHT = float(os.getenv("RECALL_ASSISTANT_DOWNWEIGHT", "0.75"))

# P3-B2 FIX A: Vector semantic floor. Drop any candidate whose raw cosine
# similarity is below this floor BEFORE the blended/composite score is computed,
# so recency can no longer float a non-matching candidate past the L0 gate.
# Chosen empirically (measure-first, P3-B2): on the agent_id='user-justin' store,
# genuine on-topic matches band at >=0.53 (Project Explore >=0.59; genuine
# Waterbar/calendar 0.53-0.83) while cross-topic leak (Snowflake/Luke under a
# calendar query) bands at <=0.36. 0.50 sits cleanly in the gap (0.44, 0.53].
RECALL_SEMANTIC_FLOOR = float(os.getenv("RECALL_SEMANTIC_FLOOR", "0.50"))

# Supersession recall filter. A superseded memory is stale by definition: it was
# explicitly replaced by a newer memory via _supersede_memory(). Returning it from
# default recall puts the stale fact back in front of the model next to the fact
# that replaced it, which is the whole failure supersession exists to prevent.
#
# Configurable, default EXCLUDE. Turning it off is an inspection tool (see the
# pre-supersession state without a code change), not a supported serving mode.
#
# This flag governs RECALL ONLY. Superseded rows are never deleted and stay fully
# retrievable by explicit lineage query — GET /memories/{id}?include_superseded=true
# — regardless of this setting. That is the audit trail; it does not run through
# here.
RECALL_EXCLUDE_SUPERSEDED = os.getenv("RECALL_EXCLUDE_SUPERSEDED", "true").lower() in ("true", "1", "yes")
_SUPERSEDED_FILTER = "AND superseded_at IS NULL" if RECALL_EXCLUDE_SUPERSEDED else ""




# --- Adaptive Composite Scoring (recall hardening) ---

def _compute_signal_spread(scores: list) -> float:
    """Compute standard deviation of scores to detect signal degeneration."""
    if len(scores) < 2:
        return 0.0
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    return math.sqrt(variance)


def _compute_signal_spread_iqr(scores: list) -> float:
    """Compute IQR of scores — robust spread metric immune to outliers. [q22-recency-clamp]"""
    if len(scores) < 2:
        return 0.0
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    q1 = sorted_scores[n // 4]
    q3 = sorted_scores[(3 * n) // 4]
    return q3 - q1


def _cross_agent_recency(days_since: float, half_life_days: float) -> float:
    """Recency score for the cross-agent scorer. Bounded to [0, 1].

    The sub-day boost used to be a flat `recency *= 2.5` applied to every
    candidate under one day old. That was uncapped while similarity, importance
    and access are all normalised to [0, 1], so a row minutes old scored 0.875 on
    recency alone against a 0.4 selection gate -- recency could clear the gate by
    itself, before relevance was considered. It was also discontinuous: at
    exactly one day the score fell by 1.5 * exp(-0.693/H) in one instant, 0.4169
    of composite at H=3, which is larger than the gate. Two memories written
    minutes apart either side of that mark were ranked as different classes of
    object.

    The boost is retained but tapered linearly to 1.0 as days_since approaches
    the one-day mark, which removes the step, and the result is capped at 1.0,
    which puts recency back on the same scale as every other signal. The cap is
    the load-bearing half: with recency in [0, 1] and a weight of 0.35, recency
    can no longer clear the 0.4 gate on its own at any age.

    Monotone non-increasing in days_since, and continuous everywhere including
    at the boundary, where both sides evaluate to exp(-0.693 / H).

    days_since is floored at zero for the same reason recall_fixed floors it
    (8d8785c, [q22-recency-clamp]): nothing is more recent than now. A negative
    age inverts the exponent, and past roughly -3000 days exp() raises
    OverflowError, which the caller swallows per-candidate and turns into a
    silently dropped memory rather than an error.
    """
    if RECENCY_CLAMP_ENABLED:
        days_since = max(0.0, days_since)  # [q22-recency-clamp] cross-agent parity
    recency = math.exp(-0.693 * days_since / max(half_life_days, 0.01))

    if days_since < 1.0:
        # taper to exactly 1.0 at days_since == 1 so the two branches meet
        boost = 1.0 + (CROSS_AGENT_SUBDAY_BOOST_MAX - 1.0) * (1.0 - days_since)
        recency *= boost

    return min(recency, 1.0)


def _compute_adaptive_weights(
    recency_scores: list,
    semantic_scores: list,
    base_semantic: float,
    base_recency: float,
    base_importance: float,
    base_access: float,
) -> tuple:
    """Adaptively rebalance scoring weights based on signal quality.

    When non-semantic signals carry no query-discriminative information,
    their weight is redistributed to semantic similarity (the only
    query-dependent signal).

    Detects two degeneration modes:
    1. Recency degeneration: all memories share near-identical timestamps
       (batch ingestion).
    2. Semantic degeneration: vector search returned mostly fixed-similarity
       candidates from importance/keyword strategies (sparse embedding column).

    When both are degenerate, importance and access weights are also
    redistributed to semantic since they produce a static global ranking.

    Returns: (semantic_w, recency_w, importance_w, access_w,
              type_bonus_dampening, recency_spread, semantic_spread,
              recency_informative, semantic_informative)
    """
    recency_spread = _compute_signal_spread_iqr(recency_scores) if RECENCY_CLAMP_ENABLED else _compute_signal_spread(recency_scores)  # [q22-recency-clamp]
    semantic_spread = _compute_signal_spread(semantic_scores) if semantic_scores else 0.0

    # Recency informativeness (sigmoid)
    rec_midpoint = 0.15
    rec_steepness = 25.0
    recency_informative = 1.0 / (1.0 + math.exp(-rec_steepness * (recency_spread - rec_midpoint)))

    # Semantic informativeness: when semantic spread is high, vector search
    # is providing real discrimination. When low (< 0.05), most candidates
    # came from importance/keyword strategies with fixed scores.
    sem_midpoint = 0.05
    sem_steepness = 40.0
    semantic_informative = 1.0 / (1.0 + math.exp(-sem_steepness * (semantic_spread - sem_midpoint)))

    # Start with base weights
    recency_w = base_recency
    importance_w = base_importance
    access_w = base_access
    semantic_w = base_semantic
    redistributed = 0.0

    # Phase 1: Redistribute recency when degenerate
    rec_reduction = base_recency * (1.0 - recency_informative)
    recency_w -= rec_reduction
    redistributed += rec_reduction

    # Phase 2: When recency is degenerate AND semantic spread is low,
    # importance and access are also query-independent. Redistribute
    # a portion toward semantic.
    if recency_informative < 0.5:
        query_invariant_factor = (1.0 - recency_informative) * (1.0 - semantic_informative)
        imp_reduction = base_importance * 0.6 * query_invariant_factor
        acc_reduction = base_access * 0.8 * query_invariant_factor
        importance_w -= imp_reduction
        access_w -= acc_reduction
        redistributed += imp_reduction + acc_reduction

    semantic_w += redistributed

    # Type bonus dampening: proportional to how query-dependent the overall
    # scoring is. When signals degenerate, type bonuses must not dominate.
    combined_informative = min(1.0, recency_informative + semantic_informative * 0.5)
    type_bonus_dampening = 0.2 + 0.8 * combined_informative

    return (semantic_w, recency_w, importance_w, access_w,
            type_bonus_dampening, recency_spread, semantic_spread,
            recency_informative, semantic_informative)


# --- Sprint 5: Query Classification & BM25 Fast-Path ---

def classify_query(query: str) -> dict:
    """
    Classify query as keyword-dominant or semantic.
    
    Returns: {
        'is_keyword_dominant': bool,
        'keywords': list[str],
        'has_proper_nouns': bool,
        'has_dates': bool,
        'has_exact_terms': bool,
        'confidence': float (0-1)
    }
    """
    # Normalize
    normalized = query.lower().strip()
    
    # Check for proper nouns (capitalized words at start or after punctuation)
    proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
    has_proper_nouns = len(proper_nouns) > 0
    
    # Check for dates (YYYY-MM-DD, MM/DD/YYYY, "April 2026", etc)
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{1,2}/\d{1,2}/\d{2,4}',  # MM/DD/YYYY
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}',  # Month YYYY
        r'\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)',  # DD Month
    ]
    has_dates = any(re.search(pattern, normalized) for pattern in date_patterns)
    
    # Check for exact terms (quoted or short, specific terms)
    # Short queries with unique terms (agent names, IDs, specific concepts)
    words = normalized.split()
    is_short = len(words) <= 5
    has_exact_terms = is_short or '"' in normalized
    
    # Extract keywords (words that are not stop words)
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'}
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Determine if keyword-dominant
    keyword_signals = sum([has_proper_nouns, has_dates, has_exact_terms, len(keywords) > 0])
    is_keyword_dominant = keyword_signals >= 2 or has_proper_nouns or has_dates
    
    # Confidence: how confident we are that BM25 will work well
    confidence = 0.0
    if has_proper_nouns:
        confidence += 0.4
    if has_dates:
        confidence += 0.3
    if has_exact_terms:
        confidence += 0.2
    if len(keywords) >= 2:
        confidence += 0.1
    confidence = min(1.0, confidence)
    
    return {
        'is_keyword_dominant': is_keyword_dominant,
        'keywords': keywords,
        'has_proper_nouns': has_proper_nouns,
        'has_dates': has_dates,
        'has_exact_terms': has_exact_terms,
        'confidence': confidence,
    }



def _sanitize_bm25_query(query: str) -> str:
    """Sanitize query for BM25/tsvector search.
    
    Handles special characters that cause websearch_to_tsquery to fail:
    - Hyphens in dates (2026-03-15 -> 2026 03 15)
    - Multiple spaces in proper nouns
    - Leading/trailing spaces
    """
    # Strip whitespace
    query = query.strip()
    
    # Replace hyphens with spaces (for dates like 2026-03-15)
    query = query.replace('-', ' ')
    
    # Replace multiple spaces with single space
    query = re.sub(r'\s+', ' ', query)
    
    return query


def _bm25_search(agent_id: str, query: str, tenant_id: str = None, limit: int = 50, project_id: str = None) -> list[dict]:
    """
    BM25 full-text search using PostgreSQL tsvector/tsquery.
    Returns results in <100ms for keyword-dominant queries.
    
    Args:
        agent_id: Agent ID to scope search
        query: Query text (should be keyword-dominant)
        tenant_id: Tenant ID for isolation
        limit: Max results to return
    
    Returns: List of candidate memories {id, headline, context, ...}
    """
    import time as _time
    _start = _time.time()
    
    _tid = tenant_id or "00000000-0000-0000-0000-000000000000"
    
    try:
        # Sanitize query to handle special characters
        clean_query = _sanitize_bm25_query(query)
        
        # Use websearch_to_tsquery for better tolerance to spaces/special chars
        # This handles "April 2026", "Sequoia Capital", etc. better than plainto_tsquery
        _bm25_project_filter = "AND project_id = %s" if project_id else ""
        _bm25_params = (clean_query, agent_id, _tid) + ((project_id,) if project_id else ()) + (clean_query, limit)
        rows = _db_execute_rows(f"""
            SELECT id, headline, context, full_content, memory_type,
                   importance, access_count, reinforcement_count,
                   created_at, superseded_at,
                   ts_rank(search_text, websearch_to_tsquery('english', %s)) as bm25_score
            FROM memory_service.memories
            WHERE agent_id = %s 
              AND tenant_id = %s::UUID
              {_SUPERSEDED_FILTER}
              AND memory_type != 'raw_turn'
              {_bm25_project_filter}
              AND search_text @@ websearch_to_tsquery('english', %s)
            ORDER BY bm25_score DESC, importance DESC
            LIMIT %s
        """, _bm25_params,
            tenant_id=_tid)
        
        elapsed_ms = (_time.time() - _start) * 1000
        logger.info(f"⚡ BM25 search (sanitized: '{clean_query}') returned {len(rows) if rows else 0} results in {elapsed_ms:.1f}ms")
        
        candidates = {}
        if rows:
            for row in rows:
                if len(row) >= 11:
                    mem_id = str(row[0])
                    bm25_score = float(row[10]) if row[10] else 0
                    parsed = _parse_candidate_row(row)
                    parsed['bm25_score'] = bm25_score
                    candidates[mem_id] = parsed
                    logger.debug(f"  • BM25 match: {row[1][:40]}... score={bm25_score:.3f}")
        
        return list(candidates.values())
    
    except Exception as e:
        elapsed_ms = (_time.time() - _start) * 1000
        logger.error(f"❌ BM25 search failed after {elapsed_ms:.1f}ms: {e}")
        return []


def recall_hybrid(
    agent_id: str,
    conversation_context: str,
    budget_tokens: int = 4000,
    tenant_id: str = None,
    bm25_threshold: float = 0.15,  # Min BM25 score to skip vector search
    project_id: str = None,
    include_synthesis: bool = True,
    caller_role: str = "public",
    expand: str = None,
) -> dict:
    """
    Hybrid recall: tries BM25 first, falls back to vector search.
    
    Sprint 5 implementation: fast-path for keyword-dominant queries.
    """
    import time as _time
    _start_total = _time.time()
    
    _tid = tenant_id or "00000000-0000-0000-0000-000000000000"
    
    # Step 1: Classify query
    classification = classify_query(conversation_context)
    logger.info(f"🔍 Query classification: keyword_dominant={classification['is_keyword_dominant']}, "
                f"confidence={classification['confidence']:.2f}")
    
    # Capture upfront decision before running searches
    ran_bm25 = classification['is_keyword_dominant'] and classification['confidence'] > 0.6
    
    # Step 2: Try BM25 for keyword-dominant queries
    bm25_results = []
    bm25_time = 0
    max_bm25_score = 0
    
    # 0.6 chosen empirically — see Checkpoint 5 prep, BM25 was running on weak signals and wasting ~280ms with zero recall contribution.
    if classification['is_keyword_dominant'] and classification['confidence'] > 0.6:
        _bm25_start = _time.time()
        bm25_results = _bm25_search(agent_id, conversation_context, tenant_id=_tid, limit=50, project_id=project_id)
        bm25_time = (_time.time() - _bm25_start) * 1000
        
        if bm25_results:
            max_bm25_score = max(r.get('bm25_score', 0) for r in bm25_results)
            logger.info(f"✨ BM25 returned {len(bm25_results)} results, max_score={max_bm25_score:.3f}")
            
            # High-confidence BM25 results: skip vector search
            if max_bm25_score > bm25_threshold:
                logger.info(f"🚀 BM25-only result (score {max_bm25_score:.3f} > {bm25_threshold})")
                
                # Rank and select from BM25 results
                context_block = ""
                tokens_used = 0
                for mem in bm25_results:
                    line = f"- {mem.get('context', mem.get('headline', ''))}\n"
                    tokens_used += len(line.split())
                    if tokens_used > budget_tokens:
                        break
                    context_block += line
                
                total_time = (_time.time() - _start_total) * 1000
                logger.info(f"📊 Hybrid recall complete (BM25-only): {total_time:.0f}ms [bm25={bm25_time:.0f}ms]")
                
                return {
                    "context_block": context_block,
                    "memories_used": len(bm25_results),
                    "tokens_used": sum(len(m.get('content', m.get('text', ''))) // 4 for m in bm25_results),
                    "recall_details": [{"id": m['id'], "headline": m.get('headline', m.get('content', '')[:50]), "bm25_score": m.get('bm25_score', 0)} for m in bm25_results],
                    "_timing": {"bm25_ms": bm25_time, "total_ms": total_time},
                }
    
    # Step 3: Fall back to vector search
    logger.info(f"📍 Falling back to vector search (BM25 confidence too low)")
    
    _vector_start = _time.time()
    # Use existing recall_fixed function
    vector_result = recall_fixed(
        agent_id=agent_id,
        conversation_context=conversation_context,
        budget_tokens=budget_tokens,
        tenant_id=_tid,
        project_id=project_id,
        include_synthesis=include_synthesis,
        expand=expand,
    )
    vector_time = (_time.time() - _vector_start) * 1000
    
    total_time = (_time.time() - _start_total) * 1000
    logger.info(f"📊 Hybrid recall complete (vector): {total_time:.0f}ms [bm25={bm25_time:.0f}ms, vector={vector_time:.0f}ms]")
    
    # Annotate with timing
    vector_result['_timing'] = {
        'bm25_ms': bm25_time,
        'vector_ms': vector_time,
        'total_ms': total_time,
        'path': 'bm25+vector' if ran_bm25 else 'vector-only',
        'bm25_returned_results': bool(bm25_results) if ran_bm25 else None,
    }
    
    return vector_result


# --- End Sprint 5 ---





def _estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars ≈ 1 token)."""
    return max(1, len(text) // 4)


def _load_agent_config(agent_id: str, tenant_id: str = None) -> dict:
    """Load agent configuration from DB using parameterized queries."""
    # Use provided tenant_id or fall back to global context
    _tid = tenant_id or "00000000-0000-0000-0000-000000000000"
    try:
        rows = _db_execute_rows("""
            SELECT context_budget, recency_weight, semantic_weight,
                   importance_weight, access_weight, recency_half_life_days,
                   identity::text, user_profile::text
            FROM memory_service.agent_config
            WHERE agent_id = %s
        """, (agent_id,), tenant_id=_tid)

        if rows:
            row = rows[0]
            return {
                # `is not None`, not truthiness: a configured 0 is a real value.
                # Under `if row[N]` a deliberate 0.0 weight is falsy and silently
                # becomes the default, so recency could not be disabled through
                # config -- setting recency_weight=0 yielded 0.35.
                "context_budget": int(row[0]) if row[0] is not None else 4000,
                "recency_weight": float(row[1]) if row[1] is not None else 0.35,
                "semantic_weight": float(row[2]) if row[2] is not None else 0.4,
                "importance_weight": float(row[3]) if row[3] is not None else 0.15,
                "access_weight": float(row[4]) if row[4] is not None else 0.1,
                "recency_half_life_days": int(row[5]) if row[5] is not None else 3,
                "identity": json.loads(row[6]) if row[6] and row[6] != '{}' else {},
                "user_profile": json.loads(row[7]) if row[7] and row[7] != '{}' else {},
            }
    except Exception as e:
        print(f"Warning: Could not load agent config: {e}")
    
    return {
        "context_budget": 4000,
        "recency_weight": 0.35,
        "semantic_weight": 0.4,
        "importance_weight": 0.15,
        "access_weight": 0.1,
        "recency_half_life_days": 3,
        "identity": {},
        "user_profile": {},
    }


def _build_always_include(agent_id: str, tenant_id: str = None, config: dict = None, query_context: str = None) -> tuple[str, int]:
    """Build the always-included context block (identity, profile, last handoff, active corrections)."""
    # Use provided tenant_id or fall back to global context
    _tid = tenant_id or "00000000-0000-0000-0000-000000000000"
    blocks = []
    
    if config is None:
        config = _load_agent_config(agent_id, tenant_id=_tid)
    
    if config.get("identity"):
        blocks.append(f"### Agent Identity\n{json.dumps(config['identity'], indent=2)}")
    
    if config.get("user_profile"):
        blocks.append(f"### User Profile\n{json.dumps(config['user_profile'], indent=2)}")
    
    try:
        rows = _db_execute_rows("""
            SELECT summary FROM memory_service.session_handoffs
            WHERE agent_id = %s AND tenant_id = %s::UUID
            ORDER BY created_at DESC LIMIT 1
        """, (agent_id, _tid), tenant_id=_tid)
        if rows:
            blocks.append(f"### Last Session Summary\n{rows[0][0]}")
    except Exception:
        pass
    
    # P3-B3: Query-gate Active Corrections on topical relevance. Each of the up-to-5
    # most-recent corrections is included only if its cosine similarity to the query
    # is >= RECALL_SEMANTIC_FLOOR. A correction with no embedding (or when there is no
    # query to score against) is included unconditionally — fail-safe: never silently
    # drop a rule we cannot score. Uses the LOCAL embedding (matches local_embedding
    # column dimension) so gating is consistent regardless of the retrieval model.
    try:
        _ac_emb_str = None
        if query_context and query_context.strip():
            try:
                _ac_emb = _embed_text_local(query_context[:2000])
                if _ac_emb and len(_ac_emb) == 384:
                    _ac_emb_str = "[" + ",".join(str(v) for v in _ac_emb) + "]"
            except Exception as _e:
                logger.warning("Active Corrections gating embed failed (non-fatal, fail-safe include): %s", _e)
        if _ac_emb_str is not None:
            rows = _db_execute_rows(f"""
                SELECT headline, context,
                       CASE WHEN local_embedding IS NOT NULL
                            THEN 1 - (local_embedding <=> %s::vector)
                            ELSE NULL END AS sim
                FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s::UUID
                  AND memory_type = 'correction'
                  {_SUPERSEDED_FILTER}
                ORDER BY created_at DESC LIMIT 5
            """, (_ac_emb_str, agent_id, _tid), tenant_id=_tid)
        else:
            rows = _db_execute_rows(f"""
                SELECT headline, context, NULL AS sim FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s::UUID
                  AND memory_type = 'correction'
                  {_SUPERSEDED_FILTER}
                ORDER BY created_at DESC LIMIT 5
            """, (agent_id, _tid), tenant_id=_tid)
        if rows:
            corrections = []
            for row in rows:
                _sim = row[2] if len(row) > 2 else None
                if _sim is not None and float(_sim) < RECALL_SEMANTIC_FLOOR:
                    continue  # gated out — not topically relevant to this query
                corrections.append(f"- ⚠️ {row[0]}: {row[1] if len(row) > 1 else ''}")
            if corrections:
                blocks.append(f"### Active Corrections\n" + "\n".join(corrections))
    except Exception:
        pass
    
    always_block = "\n\n".join(blocks) if blocks else ""
    return always_block, _estimate_tokens(always_block)



def _extract_entities(text: str) -> list[str]:
    """Extract proper noun entities from text for entity-aware retrieval (F3b)."""
    words = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
    # Common words that are often capitalized at sentence starts — not entities
    skip = {'The', 'This', 'That', 'What', 'When', 'Where', 'Which', 'How',
            'Are', 'Was', 'Were', 'Has', 'Have', 'Had', 'Will', 'Would',
            'Could', 'Should', 'Can', 'May', 'Did', 'Does', 'But', 'And',
            'For', 'Not', 'All', 'Any', 'Her', 'His', 'Its', 'Our', 'They',
            'Who', 'Why', 'After', 'Before', 'Recent', 'Also', 'Just',
            'About', 'From', 'Into', 'Over', 'Some', 'Than', 'Then',
            'Very', 'More', 'Much', 'Such', 'Each', 'Every', 'Other',
            'Most', 'Same', 'Still', 'Back', 'Here', 'There', 'User',
            'Recently', 'Now', 'Already', 'Never', 'Often', 'Being'}
    entities = [w for w in words if w not in skip]
    seen = set()
    unique = []
    for e in entities:
        if e.lower() not in seen:
            seen.add(e.lower())
            unique.append(e)
    return unique[:5]


def _retrieve_candidates(agent_id: str, query_embedding: list[float], context_text: str, tenant_id: str = None, project_id: str = None, include_raw_turns: bool = False, include_synthesis: bool = True, caller_role: str = "public", use_voyage: bool = False, entities: list[str] = None):
    """Retrieve candidate memories using multiple strategies — consolidated single query."""
    # SECURITY: Use provided tenant_id for all queries
    _tid = tenant_id or "00000000-0000-0000-0000-000000000000"
    # F1: Select embedding column based on flag
    _emb_col = "embedding_voyage" if use_voyage else "local_embedding"
    
    logger.info(f"🔍 _retrieve_candidates called for agent={agent_id}, tenant={_tid}")
    logger.debug(f"📊 Embedding vector (first 5): {query_embedding[:5]}")
    logger.debug(f"📝 Context text: {context_text[:200]}...")
    
    candidates = {}
    
    import time as _time_cp6
    
    # Task 8b: Default filter excludes raw_turn memories
    _raw_turn_filter = "" if include_raw_turns else "AND memory_type != 'raw_turn'"
    _synthesis_filter = "" if include_synthesis else "AND memory_type != 'synthesis'"

    # Redaction enforcement (B-3.5 Stage 03)
    _redaction_filter = "AND COALESCE(redaction_state, 'active') NOT IN ('redacted', 'pending_resynthesis')"
    
    # Role-based access control (B-4 Stage 01)
    if caller_role == "admin":
        _role_filter = ""
    else:
        _safe_role = caller_role.replace("'", "''")  # SQL escape
        _role_filter = f"AND (role_tag IS NULL OR role_tag IN ('{_safe_role}', 'public'))"

    # ====================================================================
    # EMBEDDING PREPARATION
    # ====================================================================
    _t_embed_start = _time_cp6.perf_counter()
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    _t_embed_ms = int((_time_cp6.perf_counter() - _t_embed_start) * 1000)
    
    # ====================================================================
    # KEYWORD EXTRACTION (for S3)
    # ====================================================================
    import re as re_inner
    words = re_inner.findall(r'\b[a-zA-Z]{3,}\b', context_text.lower())
    stop_words = {'this', 'that', 'with', 'from', 'what', 'when', 'where', 'which', 'about',
                  'have', 'been', 'will', 'would', 'could', 'should', 'their', 'there',
                  'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her',
                  'was', 'one', 'our', 'out'}
    keywords = [w for w in words if w not in stop_words][:5]
    
    sanitized_keywords = []
    for kw in keywords:
        clean_kw = re_inner.sub(r'[^a-zA-Z0-9\s]', '', kw).strip()
        if clean_kw:
            sanitized_keywords.append(clean_kw)
    
    tsquery_str = ' OR '.join(sanitized_keywords) if sanitized_keywords else '__no_keywords__'
    
    # ====================================================================
    # ENTITY EXTRACTION (for S4, F3b)
    # ====================================================================
    _entity_regex = None
    if entities:
        escaped = [re.escape(e) for e in entities]
        _entity_regex = r'\m(' + '|'.join(escaped) + r')\M'
        logger.info(f"🏷️ Entity regex for S4: {_entity_regex}")

    # ====================================================================
    # CONSOLIDATED CTE QUERY (S1 + S2 + S3 + optional S4 in one round trip)
    # ====================================================================
    _t_db_start = _time_cp6.perf_counter()

    _project_filter = "AND project_id = %s" if project_id else ""

    # Build S4 entity CTE conditionally (F3b)
    _s4_cte = ""
    _s4_union = ""
    _s4_params = ()
    if _entity_regex:
        _s4_cte = f""",
            entity_results AS (
                SELECT id, headline, context, full_content, memory_type,
                       importance, access_count, reinforcement_count,
                       created_at, event_at, superseded_at, categories,
                       0.4 as similarity,
                       'entity' as strategy,
                       source_type
                FROM memory_service.memories
                WHERE (agent_id = %s OR memory_type = 'synthesis') AND tenant_id = %s::UUID
                  {_SUPERSEDED_FILTER}
                  AND (headline ~* %s OR context ~* %s)
                  {_raw_turn_filter}
                  {_synthesis_filter}
                  {_project_filter}
                  {_redaction_filter}
                  AND id NOT IN (SELECT id FROM vector_results)
                  AND id NOT IN (SELECT id FROM importance_results)
                  AND id NOT IN (SELECT id FROM keyword_results)
                ORDER BY importance DESC
                LIMIT 30
            )"""
        _s4_union = "\n            UNION ALL\n            SELECT * FROM entity_results"
        if project_id:
            _s4_params = (agent_id, _tid, _entity_regex, _entity_regex, project_id)
        else:
            _s4_params = (agent_id, _tid, _entity_regex, _entity_regex)

    # Build params list based on whether project_id is present
    if project_id:
        _params = (
            embedding_str, agent_id, _tid, project_id, embedding_str,  # S1: vector_results
            agent_id, _tid, project_id,  # S2: importance_results
            agent_id, _tid, tsquery_str, project_id  # S3: keyword_results
        ) + _s4_params
    else:
        _params = (
            embedding_str, agent_id, _tid, embedding_str,  # S1: vector_results
            agent_id, _tid,  # S2: importance_results
            agent_id, _tid, tsquery_str  # S3: keyword_results
        ) + _s4_params

    try:
        rows = _db_execute_rows(f"""
            WITH vector_results AS (
                SELECT id, headline, context, full_content, memory_type,
                       importance, access_count, reinforcement_count,
                       created_at, event_at, superseded_at, categories,
                       1 - ({_emb_col} <=> %s::vector) as similarity,
                       'vector' as strategy,
                       source_type
                FROM memory_service.memories
                WHERE (agent_id = %s OR memory_type = 'synthesis') AND tenant_id = %s::UUID
                  {_SUPERSEDED_FILTER}
                  AND {_emb_col} IS NOT NULL
                  {_raw_turn_filter}
                  {_synthesis_filter}
                  {_project_filter}
                  {_redaction_filter}
                ORDER BY {_emb_col} <=> %s::vector
                LIMIT 150
            ),
            importance_results AS (
                SELECT id, headline, context, full_content, memory_type,
                       importance, access_count, reinforcement_count,
                       created_at, event_at, superseded_at, categories,
                       0.5 as similarity,
                       'importance' as strategy,
                       source_type
                FROM memory_service.memories
                WHERE (agent_id = %s OR memory_type = 'synthesis') AND tenant_id = %s::UUID
                  {_SUPERSEDED_FILTER}
                  AND importance > 0.8
                  {_raw_turn_filter}
                  {_synthesis_filter}
                  {_project_filter}
                  {_redaction_filter}
                  AND id NOT IN (SELECT id FROM vector_results)
                ORDER BY importance DESC
                LIMIT 50
            ),
            keyword_results AS (
                SELECT id, headline, context, full_content, memory_type,
                       importance, access_count, reinforcement_count,
                       created_at, event_at, superseded_at, categories,
                       0.35 as similarity,
                       'keyword' as strategy,
                       source_type
                FROM memory_service.memories
                WHERE (agent_id = %s OR memory_type = 'synthesis') AND tenant_id = %s::UUID
                  {_SUPERSEDED_FILTER}
                  AND search_text @@ websearch_to_tsquery('english', %s)
                  {_raw_turn_filter}
                  {_synthesis_filter}
                  {_project_filter}
                  {_redaction_filter}
                  AND id NOT IN (SELECT id FROM vector_results)
                  AND id NOT IN (SELECT id FROM importance_results)
                ORDER BY importance DESC
                LIMIT 50
            ){_s4_cte}
            SELECT * FROM vector_results
            UNION ALL
            SELECT * FROM importance_results
            UNION ALL
            SELECT * FROM keyword_results{_s4_union}
        """, _params, tenant_id=_tid)
        
        _t_db_ms = int((_time_cp6.perf_counter() - _t_db_start) * 1000)
        
        # Parse results and count by strategy
        _s1_rows_count = 0
        _s2_rows_count = 0
        _s3_rows_count = 0
        _s4_rows_count = 0

        logger.info(f"✅ Consolidated query returned {len(rows) if rows else 0} rows")
        for row in rows:
            if len(row) >= 15:  # 15 cols: 0-10 base, 11 categories, 12 similarity, 13 strategy, 14 source_type
                mem_id = str(row[0])
                strategy = row[13]

                if mem_id not in candidates:
                    candidates[mem_id] = _parse_candidate_row(row)

                    if strategy == 'vector':
                        _s1_rows_count += 1
                    elif strategy == 'importance':
                        _s2_rows_count += 1
                    elif strategy == 'keyword':
                        _s3_rows_count += 1
                    elif strategy == 'entity':
                        _s4_rows_count += 1

                    similarity = float(row[12]) if row[12] is not None else 0
                    logger.debug(f"  • [{strategy}] Memory {str(row[1])[:50]}... similarity={similarity:.3f}")

    except Exception as e:
        logger.error(f"_retrieve_candidates failed: {type(e).__name__}: {e}", exc_info=True)
        logger.error(f"❌ Consolidated query failed: {e}")
        print(f"Warning: Consolidated query failed: {e}")
        _t_db_ms = int((_time_cp6.perf_counter() - _t_db_start) * 1000)
        _s1_rows_count = _s2_rows_count = _s3_rows_count = _s4_rows_count = 0
    
    # Simplified logging: just embed + db
    _t_total_ms = _t_embed_ms + _t_db_ms
    logger.info(f"[VECTOR SUBPHASES] embed={_t_embed_ms}ms db={_t_db_ms}ms total={_t_total_ms}ms")
    
    return list(candidates.values()), {
        "s1_ms": _t_db_ms,  # For backward compatibility, report DB time as s1_ms
        "s2_ms": 0,
        "s3_ms": 0,
        "s1_rows": _s1_rows_count,
        "s2_rows": _s2_rows_count,
        "s3_rows": _s3_rows_count,
        "s4_rows": _s4_rows_count,
    }



def _parse_candidate_row(row: tuple) -> dict:
    """Parse a raw DB row tuple into a candidate dict."""
    return {
        "id": str(row[0]),
        "headline": row[1],
        "context": row[2],
        "full_content": row[3],
        "memory_type": row[4],
        "importance": float(row[5]) if row[5] is not None else 0.5,
        "access_count": int(row[6]) if row[6] is not None else 0,
        "reinforcement_count": int(row[7]) if row[7] is not None else 1,
        "created_at": row[8] if row[8] else datetime.now(timezone.utc),
        "event_at": row[9],  # nullable — prefer over created_at for temporal scoring
        "superseded_at": row[10],
        "categories": list(row[11]) if row[11] else [],  # text[] column from memories table
        "similarity": float(row[12]) if row[12] is not None else 0,
        # row[13] = strategy (read at call site, not needed in candidate dict)
        "source_type": row[14] if len(row) > 14 else None,  # 'assistant' | 'conversation' | ...
    }


def _parse_timestamp(ts_str: str) -> datetime:
    """Safely parse a timestamp string."""
    if not ts_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(ts_str.replace("+00", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


# Response cache — short TTL for identical recall queries
import hashlib as _hashlib
import threading as _threading
_recall_cache: dict[str, tuple[dict, float]] = {}
_recall_cache_lock = _threading.RLock()
_RECALL_CACHE_TTL = 60  # 1 minute
_RECALL_CACHE_MAX = 200

def recall_fixed(
    agent_id: str,
    conversation_context: str,
    budget_tokens: int = 4000,
    tenant_id: str = None,
    include_raw_turns: bool = False,
    project_id: str = None,
    include_synthesis: bool = True,
    caller_role: str = "public",
    expand: str = None,
) -> dict:
    """
    Recall relevant memories for agent context injection.
    Fully hardened with parameterized queries. Response-cached.

    SECURITY: tenant_id is used to scope all queries. If not provided,
    falls back to the global tenant context set by set_tenant_context().
    """
    import time as _time
    _start = _time.time()

    # Validate inputs
    if not agent_id or not isinstance(agent_id, str):
        return {"context_block": "", "memories_used": 0, "tokens_used": 1}
    
    if not conversation_context or not conversation_context.strip():
        return {"context_block": "", "memories_used": 0, "tokens_used": 1}
    
    budget_tokens = max(500, min(budget_tokens, 16000))
    
    # SECURITY: Resolve tenant_id from parameter or global context
    from storage_multitenant import _current_tenant_id
    _tid = tenant_id or _current_tenant_id or "00000000-0000-0000-0000-000000000000"
    logger.info(f"🎯 recall_fixed called: agent={agent_id}, tenant={_tid}, budget={budget_tokens}")
    logger.debug(f"📝 Context: {conversation_context[:200]}...")
    
    # Check response cache (thread-safe) — cache key includes tenant_id for isolation
    cache_key = _hashlib.md5(f"{_tid}:{agent_id}:{conversation_context}:{budget_tokens}:{expand}".encode(), usedforsecurity=False).hexdigest()
    now = _time.time()
    with _recall_cache_lock:
        if cache_key in _recall_cache:
            cached_result, cached_at = _recall_cache[cache_key]
            age = now - cached_at
            if age < _RECALL_CACHE_TTL:
                elapsed = (_time.time() - _start) * 1000
                logger.info(f"✅ CACHE HIT: {cache_key[:12]}... age={age:.1f}s, size={len(_recall_cache)}, elapsed={elapsed:.0f}ms")
                return cached_result
            else:
                logger.info(f"⏰ CACHE EXPIRED: {cache_key[:12]}... age={age:.1f}s > TTL={_RECALL_CACHE_TTL}")
                del _recall_cache[cache_key]
        else:
            logger.info(f"❌ CACHE MISS: {cache_key[:12]}... size={len(_recall_cache)}")
    
    # Step 1: Load agent config
    _config_t0 = _time.time()
    config = _load_agent_config(agent_id, tenant_id=_tid)
    _config_t1 = _time.time()
    _config_ms = (_config_t1 - _config_t0) * 1000
    
    semantic_weight = config.get("semantic_weight", 0.55)
    recency_weight = config.get("recency_weight", 0.15)
    importance_weight = config.get("importance_weight", 0.20)
    access_weight = config.get("access_weight", 0.10)
    half_life_days = config.get("recency_half_life_days", 3)
    
    # Step 2: Always-include block
    _always_t0 = _time.time()
    always_block, always_tokens = _build_always_include(agent_id, tenant_id=_tid, config=config, query_context=conversation_context)
    _always_t1 = _time.time()
    _always_ms = (_always_t1 - _always_t0) * 1000
    remaining_budget = budget_tokens - always_tokens
    
    if remaining_budget <= 0:
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": 0,
            "recall_details": [],
        }
    
    # Step 3: Generate query embedding
    _use_voyage = RECALL_USE_VOYAGE
    try:
        _embed_t0 = _time.time()
        if _use_voyage:
            from src.embedder import embed_voyage_single
            query_embedding = embed_voyage_single(conversation_context[:2000], input_type="query")
        else:
            query_embedding = _embed_text_local(conversation_context[:2000])
        _embed_t1 = _time.time()
        _embed_ms = (_embed_t1 - _embed_t0) * 1000
        logger.info(f"🧭 Embedding: {'voyage-3-large' if _use_voyage else 'MiniLM-L6-v2'}, {len(query_embedding)}d, {_embed_ms:.0f}ms")
    except Exception as e:
        print(f"Embedding failed: {e}")
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }
    
    # Step 3a: Check embedding coverage — fall back to local if configured
    # column is sparse (e.g. RECALL_USE_VOYAGE=true but most memories lack
    # embedding_voyage). This is a defensive fallback, not a model switch.
    if _use_voyage:
        try:
            _cov_rows = _db_execute_rows(
                "SELECT COUNT(embedding_voyage), COUNT(*) "
                "FROM memory_service.memories "
                f"WHERE tenant_id = %s::UUID {_SUPERSEDED_FILTER} "
                "AND (agent_id = %s OR memory_type = 'synthesis')",
                (_tid, agent_id), tenant_id=_tid
            )
            if _cov_rows and _cov_rows[0][1] > 0:
                _voyage_count = _cov_rows[0][0] or 0
                _total_count = _cov_rows[0][1]
                _voyage_coverage = _voyage_count / _total_count
                if _voyage_coverage < 0.5:
                    logger.info("[ADAPTIVE] Voyage coverage %.1f%% (%d/%d) — falling back to local_embedding",
                                _voyage_coverage * 100, _voyage_count, _total_count)
                    _use_voyage = False
                    # Re-generate query embedding with local model
                    _embed_t0 = _time.time()
                    query_embedding = _embed_text_local(conversation_context[:2000])
                    _embed_t1 = _time.time()
                    _embed_ms = (_embed_t1 - _embed_t0) * 1000
                    logger.info("Re-embedded with MiniLM-L6-v2, %dd, %.0fms",
                                len(query_embedding), _embed_ms)
        except Exception as e:
            logger.warning("Embedding coverage check failed (non-fatal): %s", e)

    # Step 3b: Entity extraction (F3b — flag-gated)
    _entities = _extract_entities(conversation_context) if RECALL_ENTITY_STRATEGY_ENABLED else []
    if _entities:
        logger.info(f"🏷️ Extracted entities: {_entities}")

    # Step 4: Retrieve candidates (tenant-scoped)
    _search_t0 = _time.time()
    candidates, _vector_timing = _retrieve_candidates(agent_id, query_embedding, conversation_context, tenant_id=_tid, project_id=project_id, include_raw_turns=include_raw_turns, include_synthesis=include_synthesis, caller_role=caller_role, use_voyage=_use_voyage, entities=_entities)
    _search_t1 = _time.time()
    _search_ms = (_search_t1 - _search_t0) * 1000
    # logger.info(f"[VECTOR SUBPHASES] embed={_embed_ms:.0f}ms s1={_vector_timing["s1_ms"]}ms s2={_vector_timing["s2_ms"]}ms s3={_vector_timing["s3_ms"]}ms")  # Old logging - consolidated query now logs internally
    logger.info(f"📦 Retrieved {len(candidates)} candidates")
    
    # Prepare embedding string for SQL similarity computation
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    _emb_col = "embedding_voyage" if _use_voyage else "local_embedding"

    # Recompute real cosine similarity for candidates from non-vector
    # strategies (S2/S3) that have placeholder similarity values.
    # Without this, S2 candidates (similarity=0.5) and S3 candidates
    # (similarity=0.35) have fake semantic scores that pollute the
    # adaptive scoring formula.
    _candidates_to_fix = [c for c in candidates if c["similarity"] in (0.5, 0.35)]
    if _candidates_to_fix and query_embedding:
        try:
            _fix_ids = [c["id"] for c in _candidates_to_fix]
            _fix_rows = _db_execute_rows(
                f"SELECT id::text, 1 - ({_emb_col} <=> %s::vector) as sim "
                f"FROM memory_service.memories "
                f"WHERE id = ANY(%s::uuid[]) AND {_emb_col} IS NOT NULL",
                (embedding_str, _fix_ids), tenant_id=_tid
            )
            if _fix_rows:
                _sim_map = {str(r[0]): float(r[1]) if r[1] is not None else 0.1 for r in _fix_rows}
                _fixed_count = 0
                for c in candidates:
                    if c["id"] in _sim_map:
                        c["similarity"] = _sim_map[c["id"]]
                        _fixed_count += 1
                logger.info("[ADAPTIVE] Recomputed real similarity for %d/%d non-vector candidates",
                            _fixed_count, len(_candidates_to_fix))
        except Exception as e:
            logger.warning("Similarity recomputation failed (non-fatal): %s", e)

    if not candidates:
        logger.warning("⚠️ No candidates found - returning empty result")
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }

    # Step 4b: Keyword match lookup (F2 — flag-gated)
    # When enabled: recency_weight reduced from 0.35→0.20, freed 0.15 goes to keyword_match.
    # When disabled: weights unchanged from pre-F2 values.
    keyword_match_weight = 0.0
    keyword_matches = {}
    if RECALL_KEYWORD_MATCH_ENABLED:
        keyword_match_weight = 0.15
        recency_weight = max(recency_weight - 0.15, 0.05)  # 0.35→0.20 (or floor at 0.05)
        _kw_t0 = _time.time()
        try:
            # Extract keywords from query (same logic as S3 in _retrieve_candidates)
            _kw_words = re.findall(r'\b[a-zA-Z]{3,}\b', conversation_context[:2000].lower())
            _kw_stop = {'this', 'that', 'with', 'from', 'what', 'when', 'where', 'which', 'about',
                        'have', 'been', 'will', 'would', 'could', 'should', 'their', 'there',
                        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her',
                        'was', 'one', 'our', 'out', 'did', 'does', 'how', 'who', 'why',
                        'after', 'before', 'into', 'than', 'then', 'also', 'just', 'very'}
            _kw_filtered = [w for w in _kw_words if w not in _kw_stop][:8]
            _kw_sanitized = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in _kw_filtered]
            _kw_sanitized = [w for w in _kw_sanitized if w]
            _kw_tsquery = ' OR '.join(_kw_sanitized) if _kw_sanitized else '__no_keywords__'

            candidate_ids = [c["id"] for c in candidates]
            import storage_multitenant as _st_mod
            kw_rows = _st_mod._db_execute_rows("""
                SELECT id::text,
                       ts_rank(search_text, websearch_to_tsquery('english', %s))
                FROM memory_service.memories
                WHERE id = ANY(%s::uuid[])
                  AND search_text @@ websearch_to_tsquery('english', %s)
            """, (_kw_tsquery, candidate_ids, _kw_tsquery), tenant_id=_tid)
            _raw_kw_scores = {str(row[0]): float(row[1]) for row in (kw_rows or [])}
            # Normalize to [0, 1] so top keyword match gets full weight
            _kw_max = max(_raw_kw_scores.values()) if _raw_kw_scores else 1.0
            keyword_matches = {k: v / _kw_max if _kw_max > 0 else 0.0 for k, v in _raw_kw_scores.items()}
        except Exception as e:
            logger.warning(f"Keyword match lookup failed (non-fatal): {e}")
        _kw_ms = (_time.time() - _kw_t0) * 1000
        _kw_hits = sum(1 for v in keyword_matches.values() if v > 0.01)
        logger.info(f"🔑 Keyword match: {_kw_hits}/{len(keyword_matches)} hits, tsquery='{_kw_tsquery}', {_kw_ms:.0f}ms (recency_weight={recency_weight:.2f})")

    # Step 5: Score each candidate (adaptive composite scoring)
    now = datetime.now(timezone.utc)
    scored = []

    # Query intent detection — used to apply targeted boosts/penalties below.
    # Preference queries ("recommend X for me") should surface user-specific
    # preference/identity memories. Generic-advice memories ("10 tips for Y")
    # should be penalized when they crowd out specific facts.
    _ctx_lower = conversation_context.lower()
    _is_preference_query = bool(re.search(
        r'\b(recommend|suggest|what should i|what would you|tailor|complement|for me\b|that i .{0,20}(like|prefer|enjoy))',
        _ctx_lower,
    ))
    # Narrow regex: only clearly generic guidance ("N tips/strategies/ways/steps for X").
    # Avoid penalizing legitimate count-based facts like "10 dessert restaurants in Orlando"
    # by requiring a guidance-style noun AND a "for/to" preposition that follows.
    _GENERIC_ADVICE_RE = re.compile(
        r'^\s*\d+[-\s.]*(tips|strategies|ways|steps|techniques|methods|approaches|practices|principles|rules|guidelines|criteria|tactics)\b',
        re.IGNORECASE,
    )

    # Topic-scoped retrieval: extract topic keywords from the query and use them
    # to bias scoring toward memories tagged with matching `categories`. Targets
    # the AI/healthcare / Miami-hotel / Sony-camera class of preference questions
    # where user has multiple topic interests and recall surfaces the wrong one.
    _TOPIC_KEYWORDS = {
        # Tech/AI
        "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
        # Health/medical
        "healthcare", "medical", "health", "medicine", "doctor",
        # Photography
        "photography", "camera", "cameras", "photo", "lens", "sony", "canon", "nikon",
        # Travel/places
        "travel", "trip", "vacation", "hotel", "miami", "orlando", "paris", "bandung",
        # Food
        "restaurant", "food", "cuisine", "dining", "korean", "japanese", "italian",
        # Topics
        "politics", "current events", "news", "finance", "investing", "real-estate",
        "mortgage", "education", "career", "fitness", "running", "marathon", "5k",
        # Hobbies
        "model kits", "modeling", "gaming", "reading", "cooking",
        "camping", "hiking", "outdoor",
        # Entertainment
        "movie", "movies", "marvel", "star wars", "music", "concert", "theater",
    }
    _query_topics = {kw for kw in _TOPIC_KEYWORDS if kw in _ctx_lower}

    # Pre-compute recency for all candidates to detect degeneration
    raw_recencies = []
    for c in candidates:
        temporal_ref = c.get("event_at") or c["created_at"]
        days_since = (now - temporal_ref).total_seconds() / 86400
        if RECENCY_CLAMP_ENABLED:
            days_since = max(0.0, days_since)  # [q22-recency-clamp] Nothing is more recent than now
        raw_recencies.append(math.exp(-0.693 * days_since / max(half_life_days, 0.01)))

    # Adaptive weight rebalancing based on signal quality
    raw_semantics = [c["similarity"] for c in candidates]
    adaptive = _compute_adaptive_weights(
        raw_recencies,
        raw_semantics,
        base_semantic=semantic_weight,
        base_recency=recency_weight,
        base_importance=importance_weight,
        base_access=access_weight,
    )
    a_semantic_w, a_recency_w, a_importance_w, a_access_w, type_bonus_dampening, recency_spread, semantic_spread, recency_informative, semantic_informative = adaptive
    logger.info("[ADAPTIVE] rec_spread=%.4f sem_spread=%.4f rec_info=%.3f sem_info=%.3f "
                "weights: sem=%.3f rec=%.3f imp=%.3f acc=%.3f "
                "type_dampen=%.3f",
                recency_spread, semantic_spread, recency_informative, semantic_informative,
                a_semantic_w, a_recency_w, a_importance_w, a_access_w,
                type_bonus_dampening)

    for idx_c, c in enumerate(candidates):
        try:
            semantic_sim = c["similarity"]
            # P3-B2 FIX A: enforce raw-cosine floor before blending. By this point
            # non-vector (S2/S3) candidates have had real cosine recomputed above,
            # so this gate is a true semantic floor — recency can no longer rescue
            # a sub-floor candidate past the L0 gate.
            if semantic_sim < RECALL_SEMANTIC_FLOOR:
                continue
            recency = raw_recencies[idx_c]
            temporal_ref = c.get("event_at") or c["created_at"]
            days_since = (now - temporal_ref).total_seconds() / 86400

            importance_val = c["importance"] * (1 + 0.1 * min(c["reinforcement_count"], 5))
            importance_val = min(importance_val, 1.0)

            access_freq = min(c["access_count"] / 10, 1.0)

            # F2: keyword match score
            kw_score = keyword_matches.get(c["id"], 0.0)

            composite = (
                a_semantic_w * semantic_sim +
                a_recency_w * recency +
                a_importance_w * importance_val +
                a_access_w * access_freq +
                keyword_match_weight * kw_score
            )

            # Type bonuses -- dampened when recency is degenerate so they
            # re-rank within a semantic tier, never across tiers.
            _has_entity_overlap = False
            if _entities and RECALL_TYPE_BONUS_ENTITY_AWARE:
                _hl_low = (c.get("headline") or "").lower()
                _has_entity_overlap = any(e.lower() in _hl_low for e in _entities)

            # Compute raw type multiplier, then dampen
            type_mult = 1.0
            if c["memory_type"] == "identity":
                if RECALL_TYPE_BONUS_ENTITY_AWARE:
                    type_mult = 1.15 if _has_entity_overlap else 1.05
                else:
                    type_mult = 1.15
            elif c["memory_type"] == "correction":
                type_mult = 1.10
            elif c["memory_type"] == "preference":
                if RECALL_TYPE_BONUS_ENTITY_AWARE:
                    type_mult = 1.15 if _has_entity_overlap else 1.05
                else:
                    type_mult = 1.15
            elif c["memory_type"] == "event":
                type_mult = 1.10
            elif c["memory_type"] == "decision" and days_since < 7:
                type_mult = 1.2
            elif c["memory_type"] == "synthesis":
                type_mult = 1.15
            elif c["memory_type"] == "pattern":
                pattern_boost = 1.2
                obs_count = c.get("observation_count", 0)
                if obs_count >= 5:
                    pattern_boost *= 1.1
                if days_since < 3:
                    pattern_boost *= 1.15
                type_mult = pattern_boost

            # Apply dampened type bonus: lerp between 1.0 (no bonus) and full bonus
            dampened_mult = 1.0 + (type_mult - 1.0) * type_bonus_dampening
            composite *= dampened_mult

            # CP8 P5.5 Task 12: Pin-wins-over-pattern (not dampened -- explicit user intent)
            if c.get("is_pinned"):
                composite *= 2.0

            # F3b: Entity-mention bonus (dampened like other type bonuses)
            if _entities:
                hl_lower = (c.get("headline") or "").lower()
                for ent in _entities:
                    if ent.lower() in hl_lower:
                        entity_mult = 1.0 + (1.05 - 1.0) * type_bonus_dampening
                        composite *= entity_mult
                        break

            # Generic-advice penalty: "10 tips for X" / "Six strategies for Y" headlines
            # are usually assistant-generated guidance, not user-specific facts. They
            # outrank specific factual memories when the question is about a specific fact.
            # Reduce their composite so factual memories surface higher.
            if _GENERIC_ADVICE_RE.match(c.get("headline") or ""):
                composite *= 0.65

            # F5: Provenance down-weight. Assistant-stated content is lower-trust
            # than user-stated facts. When the assistant pass floods a namespace
            # with topic-adjacent memories, they out-rank the user's actual answer
            # facts (pushing real answers to rank 39-114, outside the reasoner slice).
            # Applied AFTER the generic-advice penalty but BEFORE the preference/topic
            # boosts below, so a genuinely on-topic assistant answer (e.g. a detail
            # only the assistant stated) can still recover via those boosts.
            _assistant_downweighted = False
            if RECALL_ASSISTANT_DOWNWEIGHT_ENABLED and c.get("source_type") == "assistant":
                composite *= RECALL_ASSISTANT_DOWNWEIGHT
                _assistant_downweighted = True

            # Preference-query boost: when the user explicitly asks "recommend X
            # for me" / "suggest X" / "what should I", strongly favor user-specific
            # preference and identity memories over high-importance generic facts.
            # Not dampened — explicit query intent overrides recency-spread degeneration.
            if _is_preference_query and c["memory_type"] in ("preference", "identity"):
                composite *= 1.5

            # Topic-scoped scoring: boost candidates whose categories intersect
            # the query's detected topics; penalize off-topic preference/identity
            # candidates when the query has clear topic signals.
            # Targets AI/healthcare-vs-politics, Miami-hotel-vs-Seattle, Sony-camera
            # classes where user has multiple preferences and we want the right topic.
            if _query_topics:
                cand_categories = {str(cat).lower() for cat in (c.get("categories") or [])}
                if cand_categories:
                    if cand_categories & _query_topics:
                        composite *= 1.3
                    elif c["memory_type"] in ("preference", "identity"):
                        composite *= 0.8

            if c.get("superseded_at"):
                continue

            scored.append({
                **c,
                "composite": composite,
                "_score_components": {
                    "semantic": round(a_semantic_w * semantic_sim, 4),
                    "recency": round(a_recency_w * recency, 4),
                    "importance": round(a_importance_w * importance_val, 4),
                    "access": round(a_access_w * access_freq, 4),
                    "keyword": round(keyword_match_weight * kw_score, 4),
                    "type_multiplier": round(dampened_mult, 4),
                    "assistant_downweight": RECALL_ASSISTANT_DOWNWEIGHT if _assistant_downweighted else 1.0,
                    "raw_semantic": round(semantic_sim, 4),
                    "raw_recency": round(recency, 4),
                    "recency_spread": round(recency_spread, 4),
                    "semantic_spread": round(semantic_spread, 4),
                    "recency_informative": round(recency_informative, 3),
                    "semantic_informative": round(semantic_informative, 3),
                },
            })
        except Exception:
            continue

    # Step 6: Rank by composite score (stable: secondary key = id ASC for deterministic ties)
    scored.sort(key=lambda x: (-x["composite"], x.get("id", "")))
    logger.info(f"📊 Scored {len(scored)} memories")
    for i, s in enumerate(scored[:5]):
        logger.debug(f"  {i+1}. {s['headline'][:50]}... score={s['composite']:.3f}")
    
    # Step 7: Fill budget using tiered loading
    selected = []
    tokens_used = 0
    
    for candidate in scored:
        if remaining_budget - tokens_used <= 0:
            break
        
        if candidate["composite"] > 0.45:
            text = candidate["context"]
            tier = "L1"
        elif candidate["composite"] > 0.25:
            text = candidate["headline"]
            tier = "L0"
        else:
            continue
        
        tokens = _estimate_tokens(text)
        
        if tokens <= (remaining_budget - tokens_used):
            selected.append({
                "text": text,
                "tier": tier,
                "memory_type": candidate["memory_type"],
                "composite": round(candidate["composite"], 3),
                "headline": candidate["headline"],
                "context": candidate.get("context", ""),
                "full_content": candidate.get("full_content", ""),
                "id": candidate["id"],
                "event_at": candidate.get("event_at"),
                "created_at": candidate.get("created_at"),
                "_score_components": candidate.get("_score_components"),
                "metadata": candidate.get("metadata", {}),
                "source_type": candidate.get("source_type"),
            })
            tokens_used += tokens

    # Step 8: Format context block
    logger.info(f"✅ Selected {len(selected)} memories, {tokens_used} tokens used")
    context_block = always_block
    if selected:
        context_block += "\n\n### Relevant Context\n"
        for mem in selected:
            tier_marker = "•" if mem["tier"] == "L0" else "→"
            context_block += f"  {tier_marker} {mem['text']}\n"
    
    total_tokens = always_tokens + tokens_used
    
    result = {
        "context_block": context_block,
        "memories_used": len(selected),
        "tokens_used": total_tokens,
        "budget_remaining": budget_tokens - total_tokens,
        "recall_details": [
            {
                "id": s["id"],
                "headline": s["headline"],
                "context": s.get("context", ""),
                "full_content": s.get("full_content", ""),
                "tier": s["tier"],
                "composite": s["composite"],
                "memory_type": s.get("memory_type", "fact"),
                "source_type": s.get("source_type"),
                "event_at": s.get("event_at").isoformat() if s.get("event_at") else None,
                "created_at": s.get("created_at").isoformat() if s.get("created_at") else None,
                "metadata": s.get("metadata", {}),
                "_score_components": s.get("_score_components"),
            }
            for s in selected
        ],
    }
    
    # Log per-phase timing
    _score_ms = (_time.time() - _search_t1) * 1000
    _total_recall_ms = (_time.time() - _start) * 1000
    logger.info(f"[RECALL SPLIT] config={_config_ms:.0f}ms always_include={_always_ms:.0f}ms embed={_embed_ms:.0f}ms search={_search_ms:.0f}ms score={_score_ms:.0f}ms total={_total_recall_ms:.0f}ms")

    # Cache the response (thread-safe)
    with _recall_cache_lock:
        if len(_recall_cache) >= _RECALL_CACHE_MAX:
            oldest = min(_recall_cache, key=lambda k: _recall_cache[k][1])
            del _recall_cache[oldest]
            logger.info(f"🗑️ CACHE EVICT: oldest entry")
        _recall_cache[cache_key] = (result, _time.time())
        elapsed = (_time.time() - _start) * 1000
        logger.info(f"💾 CACHE STORE: {cache_key[:12]}... size={len(_recall_cache)}, elapsed={elapsed:.0f}ms")


    # B-4 Stage 02: Hierarchical expansion
    # Score decomposition: default OFF. Only include _score_components
    # in recall_details when expand=decomposition is requested.
    if "recall_details" in result and result["recall_details"]:
        _expand_opts = set(opt.strip() for opt in (expand or "").split(",")) if expand else set()
        if "decomposition" not in _expand_opts:
            for detail in result["recall_details"]:
                detail.pop("_score_components", None)

    if expand and "recall_details" in result:
        expand_opts = set(opt.strip() for opt in expand.split(","))
        if "evidence" in expand_opts:
            # Collect all synthesis memory IDs that need evidence expansion
            synthesis_ids_to_expand = []
            for detail in result["recall_details"]:
                if detail.get("memory_type") == "synthesis":
                    parent_ids = detail.get("metadata", {}).get("parent_memory_ids", [])
                    if parent_ids:
                        synthesis_ids_to_expand.append({
                            "memory_id": detail["id"],
                            "parent_ids": parent_ids
                        })
            
            # Fetch parent memories in a single batched query
            if synthesis_ids_to_expand:
                all_parent_ids = []
                for item in synthesis_ids_to_expand:
                    all_parent_ids.extend(item["parent_ids"])
                
                if all_parent_ids:
                    import storage_multitenant as _st_evidence
                    placeholders = ",".join(["%s"] * len(all_parent_ids))
                    parent_query = f"""
                        SELECT id, headline, context, full_content, memory_type, importance
                        FROM memory_service.memories
                        WHERE id = ANY(%s::uuid[])
                          AND tenant_id = %s
                          {_SUPERSEDED_FILTER}
                    """
                    parent_rows = _st_evidence._db_execute_rows(parent_query, (all_parent_ids, _tid), tenant_id=_tid)
                    
                    # Build lookup dict
                    parent_lookup = {}
                    for row in parent_rows:
                        parent_lookup[str(row[0])] = {
                            "id": str(row[0]),
                            "headline": row[1],
                            "context": row[2],
                            "full_content": row[3],
                            "memory_type": row[4],
                            "importance": float(row[5]) if row[5] else 0.5
                        }
                    
                    # Attach evidence to synthesis memories
                    for detail in result["recall_details"]:
                        if detail.get("memory_type") == "synthesis":
                            parent_ids = detail.get("metadata", {}).get("parent_memory_ids", [])
                            if parent_ids:
                                detail["evidence"] = [parent_lookup[pid] for pid in parent_ids if pid in parent_lookup]
        
        if "cluster" in expand_opts:
            # Collect all synthesis memory cluster IDs that need cluster expansion
            synthesis_clusters = []
            for detail in result["recall_details"]:
                if detail.get("memory_type") == "synthesis":
                    cluster_id = detail.get("metadata", {}).get("cluster_id")
                    if cluster_id:
                        synthesis_clusters.append({
                            "memory_id": detail["id"],
                            "cluster_id": cluster_id
                        })
            
            # Fetch cluster members in a single batched query
            if synthesis_clusters:
                cluster_ids = list(set(item["cluster_id"] for item in synthesis_clusters))
                
                if cluster_ids:
                    import storage_multitenant as _st_evidence
                    cluster_query = f"""
                        SELECT id, headline, context, full_content, memory_type, importance, metadata->>'cluster_id' as cluster_id
                        FROM memory_service.memories
                        WHERE metadata->>'cluster_id' = ANY(%s::text[])
                          AND tenant_id = %s
                          AND agent_id = %s
                          {_SUPERSEDED_FILTER}
                    """
                    cluster_rows = _db_execute_rows(cluster_query, (cluster_ids, _tid, agent_id), tenant_id=_tid)
                    
                    # Build cluster lookup dict
                    cluster_lookup = {}
                    for row in cluster_rows:
                        cluster_id = row[6]
                        if cluster_id not in cluster_lookup:
                            cluster_lookup[cluster_id] = []
                        cluster_lookup[cluster_id].append({
                            "id": str(row[0]),
                            "headline": row[1],
                            "context": row[2],
                            "full_content": row[3],
                            "memory_type": row[4],
                            "importance": float(row[5]) if row[5] else 0.5
                        })
                    
                    # Attach cluster to synthesis memories
                    for detail in result["recall_details"]:
                        if detail.get("memory_type") == "synthesis":
                            cluster_id = detail.get("metadata", {}).get("cluster_id")
                            if cluster_id and cluster_id in cluster_lookup:
                                detail["cluster"] = cluster_lookup[cluster_id]


    return result


# CLI test
if __name__ == "__main__":
    # GOOGLE_API_KEY must be set in environment
    
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
            print(f"✅ {result['memories_used']} memories, {result['tokens_used']} tokens")
            
            if result['recall_details']:
                for detail in result['recall_details'][:3]:
                    print(f"  - [{detail['type']}] {detail['headline']} (score: {detail['composite']})")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-AGENT RECALL - Multi-Namespace Query Support
# Added: April 1, 2026 for multi-agent orchestration
# ═══════════════════════════════════════════════════════════════════════════

def _retrieve_candidates_cross_agent(
    agent_ids: list[str],
    query_embedding: list[float],
    context_text: str,
    tenant_id: str = None,
    use_voyage: bool = False,
) -> list[dict]:
    """Retrieve candidates from MULTIPLE agent namespaces.

    Returns candidates with source_agent field for attribution.
    Used when primary agent search has low confidence.
    """
    _tid = tenant_id or "00000000-0000-0000-0000-000000000000"
    _emb_col = "embedding_voyage" if use_voyage else "local_embedding"
    all_candidates = {}

    logger.info(f"🔍 Cross-agent search across {len(agent_ids)} agents: {agent_ids}")

    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # Query each agent's namespace
    for agent_id in agent_ids:
        try:
            # Semantic search across this agent's namespace
            rows = _db_execute_rows(f"""
                SELECT id, headline, context, full_content, memory_type,
                       importance, access_count, reinforcement_count,
                       created_at, event_at, superseded_at, categories,
                       1 - ({_emb_col} <=> %s::vector) as similarity
                FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s::UUID
                  {_SUPERSEDED_FILTER}
                  AND {_emb_col} IS NOT NULL
                ORDER BY {_emb_col} <=> %s::vector
                LIMIT 10
            """, (embedding_str, agent_id, _tid, embedding_str),
                tenant_id=_tid)
            
            if rows:
                for row in rows:
                    if len(row) >= 11:
                        mem_id = row[0]
                        candidate = _parse_candidate_row(row)
                        candidate["source_agent"] = agent_id  # Add source attribution
                        all_candidates[mem_id] = candidate
                        
                logger.info(f"  {agent_id}: {len(rows)} candidates")
        except Exception as e:
            logger.warning(f"  {agent_id}: search failed - {e}")
    
    return list(all_candidates.values())


def recall_cross_agent(
    primary_agent_id: str,
    conversation_context: str,
    budget_tokens: int = 4000,
    agent_ids: list[str] = None,
    tenant_id: str = None,
) -> dict:
    """Recall memories from multiple agent namespaces.
    
    Used when primary agent search returns low-confidence results.
    Queries all agent namespaces, merges results, and attributes sources.
    
    Args:
        primary_agent_id: The agent making the query (for config/always-include)
        conversation_context: Query context
        budget_tokens: Token budget
        agent_ids: List of agent namespaces to search (default: all agents)
        tenant_id: Tenant isolation
    
    Returns:
        Same structure as recall_fixed, with source attribution in headlines
    """
    import time as _time
    
    # Default to all known agents if not specified.
    # 'user-justin' was missing: it is tenant thomas's default_agent_id and holds
    # ~17k of its ~24.8k rows, so cross-agent recall reached 2,395 rows and could
    # not see the primary store at all. 'justin' (9 rows, April-2026 migration
    # residue) was in the list and looks like it but is not it.
    # Deliberately NOT derived from a "select distinct agent_id" over the tenant:
    # that would pull in the 4,690 LongMemEval fixture rows under 'default' and
    # the lme-*/test-* namespaces. See docs/NAMESPACE-UNIFICATION-SCOPE.md.
    if not agent_ids:
        agent_ids = ["user-justin", "thomas", "wall-e", "steve", "scout", "reed", "atlas", "sheila", "lance", "justin", "loop", "echo"]

    # The caller's own namespace must always be searched. recall_with_fallback()
    # RETURNS this function's result in place of the primary result, so any
    # primary_agent_id absent from the list was silently dropped from its own
    # fallback. Keeps the fix from rotting the next time a namespace is added.
    if primary_agent_id and primary_agent_id not in agent_ids:
        agent_ids = [primary_agent_id] + agent_ids
    
    # Validate inputs
    if not primary_agent_id or not isinstance(primary_agent_id, str):
        return {"context_block": "", "memories_used": 0, "tokens_used": 1}
    
    if not conversation_context or not conversation_context.strip():
        return {"context_block": "", "memories_used": 0, "tokens_used": 1}
    
    budget_tokens = max(500, min(budget_tokens, 16000))
    
    from storage_multitenant import _current_tenant_id
    _tid = tenant_id or _current_tenant_id or "00000000-0000-0000-0000-000000000000"
    
    logger.info(f"🌐 Cross-agent recall: primary={primary_agent_id}, agents={len(agent_ids)}, budget={budget_tokens}")
    
    # Step 1: Load primary agent config (use their scoring weights)
    config = _load_agent_config(primary_agent_id, tenant_id=_tid)
    
    semantic_weight = config.get("semantic_weight", 0.55)
    recency_weight = config.get("recency_weight", 0.15)
    importance_weight = config.get("importance_weight", 0.20)
    access_weight = config.get("access_weight", 0.10)
    half_life_days = config.get("recency_half_life_days", 3)
    
    # Step 2: Always-include block (primary agent's identity/profile)
    always_block, always_tokens = _build_always_include(primary_agent_id, tenant_id=_tid, config=config, query_context=conversation_context)
    remaining_budget = budget_tokens - always_tokens
    
    if remaining_budget <= 0:
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": 0,
            "recall_details": [],
        }
    
    # Step 3: Generate query embedding
    _use_voyage = RECALL_USE_VOYAGE
    try:
        if _use_voyage:
            from src.embedder import embed_voyage_single
            query_embedding = embed_voyage_single(conversation_context[:2000], input_type="query")
        else:
            query_embedding = _embed_text_local(conversation_context[:2000])
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }

    # Step 4: Retrieve candidates from ALL agent namespaces
    candidates = _retrieve_candidates_cross_agent(agent_ids, query_embedding, conversation_context, tenant_id=_tid, use_voyage=_use_voyage)
    
    logger.info(f"📦 Retrieved {len(candidates)} candidates from {len(agent_ids)} agents")
    
    if not candidates:
        logger.warning("⚠️ No cross-agent candidates found")
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }
    
    # Step 5: Score each candidate (same logic as recall_fixed)
    now = datetime.now(timezone.utc)
    scored = []
    
    for c in candidates:
        try:
            semantic_sim = c["similarity"]
            
            days_since = (now - c["created_at"]).total_seconds() / 86400
            recency = _cross_agent_recency(days_since, half_life_days)
            
            importance = c["importance"] * (1 + 0.1 * min(c["reinforcement_count"], 5))
            importance = min(importance, 1.0)
            
            access_freq = min(c["access_count"] / 10, 1.0)
            
            composite = (
                semantic_weight * semantic_sim +
                recency_weight * recency +
                importance_weight * importance +
                access_weight * access_freq
            )
            
            scored.append({
                "id": c["id"],
                "headline": c["headline"],
                "context": c["context"],
                "memory_type": c["memory_type"],
                "source_agent": c["source_agent"],  # Attribution
                "composite": composite,
                "similarity": semantic_sim,
                "recency": recency,
            })
        except Exception as e:
            logger.warning(f"Scoring failed for {c.get('id', 'unknown')}: {e}")
    
    # Step 6: Rank by composite score (stable: secondary key = id ASC for deterministic ties)
    scored.sort(key=lambda x: (-x["composite"], x.get("id", "")))
    
    logger.info(f"📊 Scored {len(scored)} cross-agent memories")
    for i, s in enumerate(scored[:5]):
        logger.debug(f"  {i+1}. [{s['source_agent']}] {s['headline'][:40]}... score={s['composite']:.3f}")
    
    # Step 7: Fill budget with source attribution
    selected = []
    tokens_used = 0
    
    for candidate in scored:
        if remaining_budget - tokens_used <= 0:
            break
        
        # Add source prefix to headline for attribution
        source_prefix = f"[From {candidate['source_agent']}] "
        
        if candidate["composite"] > 0.7:
            text = source_prefix + candidate["context"]
            tier = "L1"
        elif candidate["composite"] > 0.4:
            text = source_prefix + candidate["headline"]
            tier = "L0"
        else:
            continue
        
        tokens = _estimate_tokens(text)
        
        if tokens <= (remaining_budget - tokens_used):
            selected.append({
                "text": text,
                "tier": tier,
                "memory_type": candidate["memory_type"],
                "composite": round(candidate["composite"], 3),
                "headline": candidate["headline"],
                "source_agent": candidate["source_agent"],
                "id": candidate["id"],
            })
            tokens_used += tokens
    
    # Step 8: Format context block with cross-agent section
    logger.info(f"✅ Selected {len(selected)} cross-agent memories, {tokens_used} tokens")
    
    context_block = always_block
    if selected:
        context_block += "\n\n### Relevant Context (Cross-Agent)\n"
        for mem in selected:
            tier_marker = "•" if mem["tier"] == "L0" else "→"
            context_block += f"  {tier_marker} {mem['text']}\n"
    
    total_tokens = always_tokens + tokens_used
    
    return {
        "context_block": context_block,
        "memories_used": len(selected),
        "tokens_used": total_tokens,
        "budget_remaining": budget_tokens - total_tokens,
        "cross_agent": True,
        "agents_queried": agent_ids,
        "recall_details": [
            {
                "id": s["id"],
                "headline": s["headline"],
                "source_agent": s["source_agent"],
                "tier": s["tier"],
                "composite": s["composite"],
            }
            for s in selected
        ],
    }


def recall_with_fallback(
    agent_id: str,
    conversation_context: str,
    budget_tokens: int = 4000,
    confidence_threshold: float = 0.6,
    tenant_id: str = None,
    project_id: str = None,
    caller_role: str = "public",
    expand: str = None,
    include_synthesis: bool = True,
) -> dict:
    """Recall with automatic cross-agent fallback.
    
    1. Try primary agent namespace first
    2. Check top result confidence
    3. If max confidence < threshold, fall back to cross-agent search
    
    This is the RECOMMENDED recall method for multi-agent orchestration.
    """
    logger.info(f"🎯 Recall with fallback: agent={agent_id}, threshold={confidence_threshold}")
    
    # Step 1: Try primary agent first
    primary_result = recall_fixed(agent_id, conversation_context, budget_tokens, tenant_id, project_id=project_id, caller_role=caller_role, expand=expand, include_synthesis=include_synthesis)
    
    # Step 2: Check confidence
    if primary_result["recall_details"]:
        max_confidence = max(d["composite"] for d in primary_result["recall_details"])
        logger.info(f"📊 Primary search max confidence: {max_confidence:.3f}")
        
        if max_confidence >= confidence_threshold:
            logger.info(f"✅ Primary search sufficient (confidence {max_confidence:.3f} >= {confidence_threshold})")
            return primary_result
    
    # Step 3: Fall back to cross-agent search
    logger.info(f"⚠️ Primary search low confidence - falling back to cross-agent")
    cross_result = recall_cross_agent(agent_id, conversation_context, budget_tokens, tenant_id=tenant_id)
    
    return cross_result


# Alias for backwards compatibility
recall = recall_fixed

