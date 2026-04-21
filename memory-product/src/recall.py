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
from storage_multitenant import _db_execute, _embed_text, _embed_text_local, set_tenant_context, _get_connection_pool

import psycopg2

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


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
        rows = _db_execute(f"""
            SELECT id, headline, context, full_content, memory_type,
                   importance, access_count, reinforcement_count,
                   created_at, superseded_at,
                   ts_rank(search_text, websearch_to_tsquery('english', %s)) as bm25_score
            FROM memory_service.memories
            WHERE agent_id = %s 
              AND tenant_id = %s::UUID
              AND superseded_at IS NULL
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
                parts = row.split("|||")
                if len(parts) >= 11:
                    mem_id = parts[0]
                    bm25_score = float(parts[10]) if parts[10] else 0
                    parsed = _parse_candidate_row(parts)
                    parsed['bm25_score'] = bm25_score
                    candidates[mem_id] = parsed
                    logger.debug(f"  • BM25 match: {parts[1][:40]}... score={bm25_score:.3f}")
        
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
                    line = f"- {mem.get('content', mem.get('text', str(mem)))}\n"
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
        rows = _db_execute("""
            SELECT context_budget, recency_weight, semantic_weight, 
                   importance_weight, access_weight, recency_half_life_days,
                   identity::text, user_profile::text
            FROM memory_service.agent_config
            WHERE agent_id = %s
        """, (agent_id,), tenant_id=_tid)
        
        if rows:
            parts = rows[0].split("|||")
            return {
                "context_budget": int(parts[0]) if parts[0] else 4000,
                "recency_weight": float(parts[1]) if parts[1] else 0.35,
                "semantic_weight": float(parts[2]) if parts[2] else 0.4,
                "importance_weight": float(parts[3]) if parts[3] else 0.15,
                "access_weight": float(parts[4]) if parts[4] else 0.1,
                "recency_half_life_days": int(parts[5]) if parts[5] else 3,
                "identity": json.loads(parts[6]) if parts[6] and parts[6] != '{}' else {},
                "user_profile": json.loads(parts[7]) if parts[7] and parts[7] != '{}' else {},
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


def _build_always_include(agent_id: str, tenant_id: str = None, config: dict = None) -> tuple[str, int]:
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
        rows = _db_execute("""
            SELECT summary FROM memory_service.session_handoffs
            WHERE agent_id = %s AND tenant_id = %s::UUID
            ORDER BY created_at DESC LIMIT 1
        """, (agent_id, _tid), tenant_id=_tid)
        if rows:
            blocks.append(f"### Last Session Summary\n{rows[0]}")
    except Exception:
        pass
    
    try:
        rows = _db_execute("""
            SELECT headline, context FROM memory_service.memories
            WHERE agent_id = %s AND tenant_id = %s::UUID
              AND memory_type = 'correction'
              AND superseded_at IS NULL
            ORDER BY created_at DESC LIMIT 5
        """, (agent_id, _tid), tenant_id=_tid)
        if rows:
            corrections = []
            for row in rows:
                parts = row.split("|||")
                corrections.append(f"- ⚠️ {parts[0]}: {parts[1] if len(parts) > 1 else ''}")
            blocks.append(f"### Active Corrections\n" + "\n".join(corrections))
    except Exception:
        pass
    
    always_block = "\n\n".join(blocks) if blocks else ""
    return always_block, _estimate_tokens(always_block)


def _retrieve_candidates(agent_id: str, query_embedding: list[float], context_text: str, tenant_id: str = None, project_id: str = None):
    """Retrieve candidate memories using multiple strategies — fully parameterized."""
    # SECURITY: Use provided tenant_id for all queries
    _tid = tenant_id or "00000000-0000-0000-0000-000000000000"
    
    logger.info(f"🔍 _retrieve_candidates called for agent={agent_id}, tenant={_tid}")
    logger.debug(f"📊 Embedding vector (first 5): {query_embedding[:5]}")
    logger.debug(f"📝 Context text: {context_text[:200]}...")
    
    candidates = {}
    
    # CP6 INSTRUMENTATION: Import timing module
    import time as _time_cp6
    
    # ====================================================================
    # STRATEGY 1: VECTOR SEARCH (7-PHASE INSTRUMENTATION)
    # ====================================================================
    _t_s1_start = _time_cp6.perf_counter()
    
    # S1 Phase 1-2: Extract & Sanitize (N/A for vector search — embedding already provided)
    _t_s1_extract_ms = 0
    _t_s1_sanitize_ms = 0
    
    # S1 Phase 3: Build — embedding string and params
    _t_s1_build_start = _time_cp6.perf_counter()
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    _project_filter = "AND project_id = %s" if project_id else ""
    _s1_params = (embedding_str, agent_id, _tid) + ((project_id,) if project_id else ()) + (embedding_str,)
    _t_s1_build_ms = int((_time_cp6.perf_counter() - _t_s1_build_start) * 1000)
    
    # S1 Phase 4-5: Conn & Exec (handled by _db_execute wrapper)
    # NOTE: _db_execute abstracts connection pooling, so we measure total exec time
    _t_s1_conn_ms = 0  # N/A — _db_execute handles connection
    _t_s1_exec_start = _time_cp6.perf_counter()
    _s1_rows_count = 0
    
    try:
        rows = _db_execute(f"""
            SELECT id, headline, context, full_content, memory_type,
                   importance, access_count, reinforcement_count,
                   created_at, superseded_at,
                   1 - (local_embedding <=> %s::extensions.vector) as similarity
            FROM memory_service.memories
            WHERE agent_id = %s AND tenant_id = %s::UUID
              AND superseded_at IS NULL
              AND local_embedding IS NOT NULL
              {_project_filter}
            ORDER BY local_embedding <=> %s::extensions.vector
            LIMIT 200
        """, _s1_params,
            tenant_id=_tid)
        _t_s1_exec_ms = int((_time_cp6.perf_counter() - _t_s1_exec_start) * 1000)
        
        # S1 Phase 6: Fetch — parse rows returned by _db_execute
        _t_s1_fetch_start = _time_cp6.perf_counter()
        logger.info(f"✅ Semantic search returned {len(rows) if rows else 0} rows")
        for row in rows:
            parts = row.split("|||")
            if len(parts) >= 11:
                mem_id = parts[0]
                candidates[mem_id] = _parse_candidate_row(parts)
                _s1_rows_count += 1
                similarity = float(parts[10]) if parts[10] else 0
                logger.debug(f"  • Memory {parts[1][:50]}... similarity={similarity:.3f}")
        _t_s1_fetch_ms = int((_time_cp6.perf_counter() - _t_s1_fetch_start) * 1000)
    except Exception as e:
        logger.error(f"❌ Semantic search failed: {e}")
        print(f"Warning: Semantic search failed: {e}")
        _t_s1_exec_ms = int((_time_cp6.perf_counter() - _t_s1_exec_start) * 1000)
        _t_s1_fetch_ms = 0
    
    # S1 Phase 7: Commit (N/A — _db_execute handles commit)
    _t_s1_commit_ms = 0
    
    _t_s1_end = _time_cp6.perf_counter()
    _t_s1_ms = int((_t_s1_end - _t_s1_start) * 1000)
    
    # S1 SUBPHASE LOG
    logger.info(
        f"[S1 SUBPHASES] extract={_t_s1_extract_ms}ms sanitize={_t_s1_sanitize_ms}ms "
        f"build={_t_s1_build_ms}ms conn={_t_s1_conn_ms}ms exec={_t_s1_exec_ms}ms "
        f"fetch={_t_s1_fetch_ms}ms commit={_t_s1_commit_ms}ms total={_t_s1_ms}ms"
    )
    
    # ====================================================================
    # STRATEGY 2: HIGH IMPORTANCE (7-PHASE INSTRUMENTATION)
    # ====================================================================
    _t_s2_start = _time_cp6.perf_counter()
    
    # S2 Phase 1-2: Extract & Sanitize (N/A for high-importance query)
    _t_s2_extract_ms = 0
    _t_s2_sanitize_ms = 0
    
    # S2 Phase 3: Build — params for high-importance query
    _t_s2_build_start = _time_cp6.perf_counter()
    existing_ids = list(candidates.keys()) if candidates else ["00000000-0000-0000-0000-000000000000"]
    _s2_params = (agent_id, _tid) + ((project_id,) if project_id else ()) + (existing_ids,)
    _t_s2_build_ms = int((_time_cp6.perf_counter() - _t_s2_build_start) * 1000)
    
    # S2 Phase 4-5: Conn & Exec (handled by _db_execute wrapper)
    _t_s2_conn_ms = 0  # N/A — _db_execute handles connection
    _t_s2_exec_start = _time_cp6.perf_counter()
    _s2_rows_count = 0
    
    try:
        rows2 = _db_execute(f"""
            SELECT id, headline, context, full_content, memory_type,
                   importance, access_count, reinforcement_count,
                   created_at, superseded_at, 0.5 as similarity
            FROM memory_service.memories
            WHERE agent_id = %s AND tenant_id = %s::UUID
              AND superseded_at IS NULL
              AND importance > 0.8
              {_project_filter}
              AND id NOT IN (SELECT unnest(%s::uuid[]))
            ORDER BY importance DESC
            LIMIT 50
        """, _s2_params,
            tenant_id=_tid)
        _t_s2_exec_ms = int((_time_cp6.perf_counter() - _t_s2_exec_start) * 1000)
        
        # S2 Phase 6: Fetch — parse rows
        _t_s2_fetch_start = _time_cp6.perf_counter()
        for row in rows2:
            parts = row.split("|||")
            if len(parts) >= 11:
                mem_id = parts[0]
                if mem_id not in candidates:
                    candidates[mem_id] = _parse_candidate_row(parts)
                    _s2_rows_count += 1
        _t_s2_fetch_ms = int((_time_cp6.perf_counter() - _t_s2_fetch_start) * 1000)
    except Exception as e:
        print(f"Warning: High-importance search failed: {e}")
        _t_s2_exec_ms = int((_time_cp6.perf_counter() - _t_s2_exec_start) * 1000)
        _t_s2_fetch_ms = 0
    
    # S2 Phase 7: Commit (N/A — _db_execute handles commit)
    _t_s2_commit_ms = 0
    
    _t_s2_end = _time_cp6.perf_counter()
    _t_s2_ms = int((_t_s2_end - _t_s2_start) * 1000)
    
    # S2 SUBPHASE LOG
    logger.info(
        f"[S2 SUBPHASES] extract={_t_s2_extract_ms}ms sanitize={_t_s2_sanitize_ms}ms "
        f"build={_t_s2_build_ms}ms conn={_t_s2_conn_ms}ms exec={_t_s2_exec_ms}ms "
        f"fetch={_t_s2_fetch_ms}ms commit={_t_s2_commit_ms}ms total={_t_s2_ms}ms"
    )
    
    # ====================================================================
    # STRATEGY 3: KEYWORD SEARCH (EXISTING 7-PHASE INSTRUMENTATION)
    # ====================================================================
    _t_s3_start = _time_cp6.perf_counter()
    _s3_count = 0
    _s3_skipped = True  # Will be set to False if keyword search runs
    
    # Strategy 3: Keyword search — full-text search with GIN index
    try:
        # Phase 1: Keyword extraction
        _t_s3_extract_start = _time_cp6.perf_counter()
        import re as re_inner
        words = re_inner.findall(r'\b[a-zA-Z]{3,}\b', context_text.lower())
        stop_words = {'this', 'that', 'with', 'from', 'what', 'when', 'where', 'which', 'about',
                      'have', 'been', 'will', 'would', 'could', 'should', 'their', 'there',
                      'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her',
                      'was', 'one', 'our', 'out'}
        keywords = [w for w in words if w not in stop_words][:5]
        _t_s3_extract_ms = int((_time_cp6.perf_counter() - _t_s3_extract_start) * 1000)
        
        if keywords:
            _s3_skipped = False  # Keywords found, search will run
            existing_ids = list(candidates.keys()) if candidates else ["00000000-0000-0000-0000-000000000000"]
            
            # Phase 2: Keyword sanitization
            _t_s3_sanitize_start = _time_cp6.perf_counter()
            sanitized_keywords = []
            for kw in keywords:
                clean_kw = re_inner.sub(r'[^a-zA-Z0-9\s]', '', kw).strip()
                if clean_kw:
                    sanitized_keywords.append(clean_kw)
            _t_s3_sanitize_ms = int((_time_cp6.perf_counter() - _t_s3_sanitize_start) * 1000)
            
            if sanitized_keywords:
                # Phase 3: Query build
                _t_s3_build_start = _time_cp6.perf_counter()
                # Build tsquery: keyword1 OR keyword2 OR keyword3 ...
                tsquery_str = ' OR '.join(sanitized_keywords)
                
                # Use direct psycopg2 query with full-text search
                # Build SQL query string
                query = f"""
                    SELECT id, headline, context, full_content, memory_type,
                           importance, access_count, reinforcement_count,
                           created_at, superseded_at, 0.35 as similarity
                    FROM memory_service.memories
                    WHERE agent_id = %s AND tenant_id = %s::UUID
                      AND superseded_at IS NULL
                      AND search_text @@ websearch_to_tsquery('english', %s)
                      {_project_filter}
                      AND id NOT IN (SELECT unnest(%s::uuid[]))
                    ORDER BY importance DESC
                    LIMIT 100
                """  # nosec B608 — all values parameterized via %s
                params = [agent_id, _tid, tsquery_str] + ([project_id] if project_id else []) + [existing_ids]
                _t_s3_build_ms = int((_time_cp6.perf_counter() - _t_s3_build_start) * 1000)
                
                # Phase 4: DB connection setup
                _t_s3_conn_start = _time_cp6.perf_counter()
                pool = _get_connection_pool()
                conn = pool.getconn()
                cur = conn.cursor()
                cur.execute("BEGIN")
                cur.execute("SELECT memory_service.set_tenant_context(%s)", (_tid,))
                _t_s3_conn_ms = int((_time_cp6.perf_counter() - _t_s3_conn_start) * 1000)
                
                try:
                    # Phase 5: DB execute
                    _t_s3_exec_start = _time_cp6.perf_counter()
                    cur.execute(query, params)
                    _t_s3_exec_ms = int((_time_cp6.perf_counter() - _t_s3_exec_start) * 1000)
                    
                    # Phase 6: Row fetch + materialize
                    _t_s3_fetch_start = _time_cp6.perf_counter()
                    _s3_rows_fetched = 0
                    if cur.description:
                        for row_tuple in cur.fetchall():
                            _s3_rows_fetched += 1
                            row_str = "|||".join(str(val) if val is not None else "" for val in row_tuple)
                            parts = row_str.split("|||")
                            if len(parts) >= 11:
                                mem_id = parts[0]
                                if mem_id not in candidates:
                                    candidates[mem_id] = _parse_candidate_row(parts)
                                    _s3_count += 1
                    _t_s3_fetch_ms = int((_time_cp6.perf_counter() - _t_s3_fetch_start) * 1000)
                    
                    # Phase 7: Commit
                    _t_s3_commit_start = _time_cp6.perf_counter()
                    cur.execute("COMMIT")
                    _t_s3_commit_ms = int((_time_cp6.perf_counter() - _t_s3_commit_start) * 1000)
                except Exception as e:
                    cur.execute("ROLLBACK")
                    print(f"Warning: Keyword search query failed: {e}")
                    _t_s3_sanitize_ms = _t_s3_build_ms = _t_s3_conn_ms = _t_s3_exec_ms = _t_s3_fetch_ms = _t_s3_commit_ms = 0
                    _s3_rows_fetched = 0
                finally:
                    cur.close()
                    pool.putconn(conn)
            else:
                # No valid keywords after sanitization
                _s3_skipped = True
                _t_s3_sanitize_ms = _t_s3_build_ms = _t_s3_conn_ms = _t_s3_exec_ms = _t_s3_fetch_ms = _t_s3_commit_ms = 0
                _s3_rows_fetched = 0
        else:
            # No keywords found
            _t_s3_extract_ms = _t_s3_sanitize_ms = _t_s3_build_ms = _t_s3_conn_ms = _t_s3_exec_ms = _t_s3_fetch_ms = _t_s3_commit_ms = 0
            _s3_rows_fetched = 0
    except Exception as e:
        print(f"Warning: Keyword search failed: {e}")
        _t_s3_extract_ms = _t_s3_sanitize_ms = _t_s3_build_ms = _t_s3_conn_ms = _t_s3_exec_ms = _t_s3_fetch_ms = _t_s3_commit_ms = 0
        _s3_rows_fetched = 0
    
    _t_s3_end = _time_cp6.perf_counter()
    _t_s3_ms = int((_t_s3_end - _t_s3_start) * 1000)
    
    # S3 SUBPHASE LOG (EXISTING)
    logger.info(
        f"[S3 SUBPHASES] extract={_t_s3_extract_ms}ms sanitize={_t_s3_sanitize_ms}ms "
        f"build={_t_s3_build_ms}ms conn={_t_s3_conn_ms}ms exec={_t_s3_exec_ms}ms "
        f"fetch={_t_s3_fetch_ms}ms commit={_t_s3_commit_ms}ms total={_t_s3_ms}ms"
    )

    return list(candidates.values()), {
        "s1_ms": _t_s1_ms,
        "s2_ms": _t_s2_ms,
        "s3_ms": _t_s3_ms,
        "s1_rows": _s1_rows_count,
        "s2_rows": _s2_rows_count,
        "s3_rows": _s3_count,
    }


def _parse_candidate_row(parts: list[str]) -> dict:
    """Parse a raw DB row into a candidate dict."""
    return {
        "id": parts[0],
        "headline": parts[1],
        "context": parts[2],
        "full_content": parts[3],
        "memory_type": parts[4],
        "importance": float(parts[5]) if parts[5] else 0.5,
        "access_count": int(parts[6]) if parts[6] else 0,
        "reinforcement_count": int(parts[7]) if parts[7] else 1,
        "created_at": _parse_timestamp(parts[8]),
        "superseded_at": parts[9] if parts[9] else None,
        "similarity": float(parts[10]) if parts[10] else 0,
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
    project_id: str = None,
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
    cache_key = _hashlib.md5(f"{_tid}:{agent_id}:{conversation_context}:{budget_tokens}".encode(), usedforsecurity=False).hexdigest()
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
    
    semantic_weight = config.get("semantic_weight", 0.4)
    recency_weight = config.get("recency_weight", 0.35)
    importance_weight = config.get("importance_weight", 0.15)
    access_weight = config.get("access_weight", 0.1)
    half_life_days = config.get("recency_half_life_days", 3)
    
    # Step 2: Always-include block
    _always_t0 = _time.time()
    always_block, always_tokens = _build_always_include(agent_id, tenant_id=_tid, config=config)
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
    try:
        _embed_t0 = _time.time()
        query_embedding = _embed_text_local(conversation_context[:2000])
        _embed_t1 = _time.time()
        _embed_ms = (_embed_t1 - _embed_t0) * 1000
    except Exception as e:
        print(f"Embedding failed: {e}")
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }
    
    # Step 4: Retrieve candidates (tenant-scoped)
    _search_t0 = _time.time()
    candidates, _vector_timing = _retrieve_candidates(agent_id, query_embedding, conversation_context, tenant_id=_tid, project_id=project_id)
    _search_t1 = _time.time()
    _search_ms = (_search_t1 - _search_t0) * 1000
    logger.info(f"[VECTOR SUBPHASES] embed={_embed_ms:.0f}ms s1={_vector_timing["s1_ms"]}ms s2={_vector_timing["s2_ms"]}ms s3={_vector_timing["s3_ms"]}ms")
    logger.info(f"📦 Retrieved {len(candidates)} candidates")
    
    if not candidates:
        logger.warning("⚠️ No candidates found - returning empty result")
        return {
            "context_block": always_block,
            "memories_used": 0,
            "tokens_used": always_tokens,
            "budget_remaining": remaining_budget,
            "recall_details": [],
        }
    
    # Step 5: Score each candidate
    now = datetime.now(timezone.utc)
    scored = []
    
    for c in candidates:
        try:
            semantic_sim = c["similarity"]
            
            days_since = (now - c["created_at"]).total_seconds() / 86400
            recency = math.exp(-0.693 * days_since / max(half_life_days, 0.01))
            
            # Boost for very recent memories (< 24 hours) — makes new memories dominate
            if days_since < 1:
                recency *= 2.5  # Strongly favor last 24 hours
            
            importance = c["importance"] * (1 + 0.1 * min(c["reinforcement_count"], 5))
            importance = min(importance, 1.0)
            
            access_freq = min(c["access_count"] / 10, 1.0)
            
            composite = (
                semantic_weight * semantic_sim +
                recency_weight * recency +
                importance_weight * importance +
                access_weight * access_freq
            )
            
            # Type bonuses (tuned: identity was drowning out topically relevant results)
            if c["memory_type"] == "identity":
                composite *= 1.15  # Was 1.5 — too aggressive, caused identity to always win
            elif c["memory_type"] == "correction":
                composite *= 1.25  # Corrections are important — recent overrides matter
            elif c["memory_type"] == "preference":
                composite *= 1.15  # Preferences matter but shouldn't dominate
            elif c["memory_type"] == "decision" and days_since < 7:
                composite *= 1.2   # Recent decisions are highly relevant
            
            if c.get("superseded_at"):
                continue
            
            scored.append({
                **c,
                "composite": composite,
            })
        except Exception:
            continue
    
    # Step 6: Rank by composite score
    scored.sort(key=lambda x: x["composite"], reverse=True)
    logger.info(f"📊 Scored {len(scored)} memories")
    for i, s in enumerate(scored[:5]):
        logger.debug(f"  {i+1}. {s['headline'][:50]}... score={s['composite']:.3f}")
    
    # Step 7: Fill budget using tiered loading
    selected = []
    tokens_used = 0
    
    for candidate in scored:
        if remaining_budget - tokens_used <= 0:
            break
        
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
                "type": s["type"],
                "tier": s["tier"],
                "composite": s["composite"],
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
    tenant_id: str = None
) -> list[dict]:
    """Retrieve candidates from MULTIPLE agent namespaces.
    
    Returns candidates with source_agent field for attribution.
    Used when primary agent search has low confidence.
    """
    _tid = tenant_id or "00000000-0000-0000-0000-000000000000"
    all_candidates = {}
    
    logger.info(f"🔍 Cross-agent search across {len(agent_ids)} agents: {agent_ids}")
    
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    
    # Query each agent's namespace
    for agent_id in agent_ids:
        try:
            # Semantic search across this agent's namespace
            rows = _db_execute("""
                SELECT id, headline, context, full_content, memory_type,
                       importance, access_count, reinforcement_count,
                       created_at, superseded_at,
                       1 - (local_embedding <=> %s::extensions.vector) as similarity
                FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s::UUID
                  AND superseded_at IS NULL
                  AND local_embedding IS NOT NULL
                ORDER BY local_embedding <=> %s::extensions.vector
                LIMIT 10
            """, (embedding_str, agent_id, _tid, embedding_str),
                tenant_id=_tid)
            
            if rows:
                for row in rows:
                    parts = row.split("|||")
                    if len(parts) >= 11:
                        mem_id = parts[0]
                        candidate = _parse_candidate_row(parts)
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
    
    # Default to all known agents if not specified
    if not agent_ids:
        agent_ids = ["thomas", "wall-e", "steve", "scout", "reed", "atlas", "sheila", "lance", "justin", "loop", "echo"]
    
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
    
    semantic_weight = config.get("semantic_weight", 0.4)
    recency_weight = config.get("recency_weight", 0.35)
    importance_weight = config.get("importance_weight", 0.15)
    access_weight = config.get("access_weight", 0.1)
    half_life_days = config.get("recency_half_life_days", 3)
    
    # Step 2: Always-include block (primary agent's identity/profile)
    always_block, always_tokens = _build_always_include(primary_agent_id, tenant_id=_tid, config=config)
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
    try:
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
    candidates = _retrieve_candidates_cross_agent(agent_ids, query_embedding, conversation_context, tenant_id=_tid)
    
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
            recency = math.exp(-0.693 * days_since / max(half_life_days, 0.01))
            
            if days_since < 1:
                recency *= 2.5
            
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
    
    # Step 6: Rank by composite score
    scored.sort(key=lambda x: x["composite"], reverse=True)
    
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
                "type": candidate["memory_type"],
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
                "type": s["type"],
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
) -> dict:
    """Recall with automatic cross-agent fallback.
    
    1. Try primary agent namespace first
    2. Check top result confidence
    3. If max confidence < threshold, fall back to cross-agent search
    
    This is the RECOMMENDED recall method for multi-agent orchestration.
    """
    logger.info(f"🎯 Recall with fallback: agent={agent_id}, threshold={confidence_threshold}")
    
    # Step 1: Try primary agent first
    primary_result = recall_fixed(agent_id, conversation_context, budget_tokens, tenant_id, project_id=project_id)
    
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

