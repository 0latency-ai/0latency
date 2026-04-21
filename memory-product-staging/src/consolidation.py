"""
Memory Consolidation — Detect and merge duplicate/similar memories.

Keeps the memory graph clean by:
1. Computing pairwise cosine similarity using stored embeddings
2. Flagging pairs above a threshold as potential duplicates
3. Merging duplicates with full version history preservation
4. Redirecting graph edges from old memories to merged memory

Feature gating:
- Free: No access (403)
- Pro: View duplicates + manual merge/dismiss
- Scale: View + auto-consolidation via API
- Enterprise: Full auto-consolidation + custom thresholds
"""

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from storage_multitenant import _db_execute_rows, _embed_text
from versioning import snapshot_version

logger = logging.getLogger("zerolatency.consolidation")


# ─── Feature Gating ─────────────────────────────────────────────────────────

CONSOLIDATION_ACCESS = {
    "free": set(),
    "pro": {"list_duplicates", "merge", "dismiss"},
    "scale": {"list_duplicates", "merge", "dismiss", "auto_consolidate"},
    "enterprise": {"list_duplicates", "merge", "dismiss", "auto_consolidate", "custom_threshold"},
}


def check_consolidation_access(tenant: dict, action: str) -> bool:
    """Check if tenant's plan allows a consolidation action."""
    plan = tenant.get("plan", "free")
    allowed = CONSOLIDATION_ACCESS.get(plan, set())
    return action in allowed


# ─── Similarity Math ────────────────────────────────────────────────────────

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ─── Duplicate Detection ────────────────────────────────────────────────────

def detect_duplicates(
    agent_id: str,
    tenant_id: str,
    similarity_threshold: float = 0.85,
    limit: int = 500,
) -> list[dict]:
    """
    Detect duplicate memories for an agent using pgvector cosine distance.
    
    Uses the database's vector operations for efficiency — avoids pulling
    all embeddings into Python for pairwise comparison.
    
    Returns list of {memory_id_1, memory_id_2, similarity_score, headline_1, headline_2}.
    """
    # Use pgvector's <=> (cosine distance) operator for efficient similarity search.
    # cosine_distance = 1 - cosine_similarity, so we want distance < (1 - threshold).
    max_distance = 1.0 - similarity_threshold
    
    rows = _db_execute_rows("""
        SELECT 
            m1.id AS id_1, m2.id AS id_2,
            1 - (m1.embedding <=> m2.embedding) AS similarity,
            m1.headline AS headline_1, m2.headline AS headline_2
        FROM memory_service.memories m1
        JOIN memory_service.memories m2 
            ON m1.agent_id = m2.agent_id 
            AND m1.tenant_id = m2.tenant_id
            AND m1.id < m2.id
            AND m1.embedding <=> m2.embedding < %s
        WHERE m1.agent_id = %s
            AND m1.tenant_id = %s::UUID
            AND m1.superseded_at IS NULL
            AND m2.superseded_at IS NULL
            AND m1.embedding IS NOT NULL
            AND m2.embedding IS NOT NULL
        ORDER BY m1.embedding <=> m2.embedding ASC
        LIMIT %s
    """, (max_distance, agent_id, tenant_id, limit), tenant_id=tenant_id)
    
    duplicates = []
    for row in (rows or []):
        duplicates.append({
            "memory_id_1": str(row[0]),
            "memory_id_2": str(row[1]),
            "similarity_score": round(float(row[2]), 4),
            "headline_1": str(row[3]),
            "headline_2": str(row[4]),
        })
    
    return duplicates


def store_duplicate_pairs(
    pairs: list[dict],
    agent_id: str,
    tenant_id: str,
) -> int:
    """
    Store detected duplicate pairs in memory_duplicates table.
    Skips pairs that already exist (ON CONFLICT DO NOTHING).
    Returns count of newly inserted pairs.
    """
    inserted = 0
    for pair in pairs:
        id1, id2 = pair["memory_id_1"], pair["memory_id_2"]
        # Ensure canonical ordering (id1 < id2)
        if id1 > id2:
            id1, id2 = id2, id1
        
        try:
            rows = _db_execute_rows("""
                INSERT INTO memory_service.memory_duplicates
                    (tenant_id, agent_id, memory_id_1, memory_id_2, similarity_score)
                VALUES (%s::UUID, %s, %s::UUID, %s::UUID, %s)
                ON CONFLICT (tenant_id, agent_id, memory_id_1, memory_id_2) DO NOTHING
                RETURNING id
            """, (tenant_id, agent_id, id1, id2, pair["similarity_score"]),
                tenant_id=tenant_id)
            if rows:
                inserted += 1
        except Exception as e:
            logger.warning(f"Failed to store duplicate pair ({id1}, {id2}): {e}")
    
    return inserted


# ─── List Duplicates ─────────────────────────────────────────────────────────

def list_duplicates(
    agent_id: str,
    tenant_id: str,
    status: str = "pending",
    min_similarity: float = 0.85,
    limit: int = 50,
) -> list[dict]:
    """List duplicate pairs with memory details."""
    rows = _db_execute_rows("""
        SELECT 
            d.id, d.memory_id_1, d.memory_id_2, d.similarity_score,
            d.status, d.merged_into, d.created_at, d.reviewed_at,
            m1.headline AS headline_1, m1.importance AS importance_1,
            m1.confidence AS confidence_1, m1.memory_type AS type_1,
            m2.headline AS headline_2, m2.importance AS importance_2,
            m2.confidence AS confidence_2, m2.memory_type AS type_2
        FROM memory_service.memory_duplicates d
        JOIN memory_service.memories m1 ON d.memory_id_1 = m1.id
        JOIN memory_service.memories m2 ON d.memory_id_2 = m2.id
        WHERE d.agent_id = %s
            AND d.tenant_id = %s::UUID
            AND d.status = %s
            AND d.similarity_score >= %s
        ORDER BY d.similarity_score DESC
        LIMIT %s
    """, (agent_id, tenant_id, status, min_similarity, limit), tenant_id=tenant_id)
    
    results = []
    for r in (rows or []):
        results.append({
            "id": str(r[0]),
            "memory_id_1": str(r[1]),
            "memory_id_2": str(r[2]),
            "similarity_score": round(float(r[3]), 4),
            "status": str(r[4]),
            "merged_into": str(r[5]) if r[5] else None,
            "created_at": str(r[6]),
            "reviewed_at": str(r[7]) if r[7] else None,
            "memory_1": {
                "headline": str(r[8]),
                "importance": float(r[9]) if r[9] is not None else 0.5,
                "confidence": float(r[10]) if r[10] is not None else 0.8,
                "memory_type": str(r[11]) if r[11] else "fact",
            },
            "memory_2": {
                "headline": str(r[12]),
                "importance": float(r[13]) if r[13] is not None else 0.5,
                "confidence": float(r[14]) if r[14] is not None else 0.8,
                "memory_type": str(r[15]) if r[15] else "fact",
            },
        })
    
    return results


# ─── Merge Logic ─────────────────────────────────────────────────────────────

def merge_memories(
    duplicate_id: str,
    tenant_id: str,
) -> dict:
    """
    Merge two duplicate memories into one.
    
    Strategy:
    1. Snapshot both memories (version history preserved)
    2. Create merged memory:
       - Headline: higher confidence one (or combine if both important)
       - Context: concatenate both contexts
       - Importance: max of the two
       - Confidence: average + 0.1 corroboration bonus (capped at 0.99)
       - Sentiment: average if similar, flag conflict if contradictory
    3. Update merged_into pointer in duplicates table
    4. Mark loser memory as superseded
    5. Redirect graph edges from loser to winner
    
    Returns the merged memory details.
    """
    # 1. Get the duplicate record
    dup_rows = _db_execute_rows("""
        SELECT memory_id_1, memory_id_2, similarity_score, agent_id
        FROM memory_service.memory_duplicates
        WHERE id = %s::UUID AND tenant_id = %s::UUID AND status = 'pending'
    """, (duplicate_id, tenant_id), tenant_id=tenant_id)
    
    if not dup_rows:
        raise ValueError("Duplicate record not found or already processed")
    
    mem_id_1, mem_id_2, sim_score, agent_id = dup_rows[0]
    mem_id_1, mem_id_2 = str(mem_id_1), str(mem_id_2)
    
    # 2. Fetch both memories
    mem1 = _get_full_memory(mem_id_1, tenant_id)
    mem2 = _get_full_memory(mem_id_2, tenant_id)
    
    if not mem1 or not mem2:
        raise ValueError("One or both memories no longer exist")
    
    # 3. Snapshot both before merging
    snapshot_version(mem_id_1, tenant_id, changed_by="consolidation", change_reason="pre-merge snapshot")
    snapshot_version(mem_id_2, tenant_id, changed_by="consolidation", change_reason="pre-merge snapshot")
    
    # 4. Determine winner (higher confidence, then higher importance)
    if (mem1["confidence"] or 0.5) >= (mem2["confidence"] or 0.5):
        winner, loser = mem1, mem2
        winner_id, loser_id = mem_id_1, mem_id_2
    else:
        winner, loser = mem2, mem1
        winner_id, loser_id = mem_id_2, mem_id_1
    
    # 5. Compute merged fields
    merged_headline = winner["headline"]
    # If headlines are meaningfully different and both important, combine
    if winner["headline"] != loser["headline"] and (loser["importance"] or 0) >= 0.6:
        merged_headline = f"{winner['headline']} (also: {loser['headline']})"
    
    # Context: concatenate, dedup
    contexts = []
    if winner.get("context"):
        contexts.append(winner["context"])
    if loser.get("context") and loser["context"] != winner.get("context"):
        contexts.append(loser["context"])
    merged_context = "\n---\n".join(contexts) if contexts else None
    
    # Full content: concatenate
    contents = []
    if winner.get("full_content"):
        contents.append(winner["full_content"])
    if loser.get("full_content") and loser["full_content"] != winner.get("full_content"):
        contents.append(loser["full_content"])
    merged_full_content = "\n---\n".join(contents) if contents else None
    
    # Importance: max
    merged_importance = max(winner.get("importance") or 0.5, loser.get("importance") or 0.5)
    
    # Confidence: average + corroboration bonus, capped at 0.99
    avg_conf = ((winner.get("confidence") or 0.5) + (loser.get("confidence") or 0.5)) / 2
    merged_confidence = min(0.99, avg_conf + 0.1)
    
    # Sentiment: average if similar, keep winner's if contradictory
    merged_sentiment = winner.get("sentiment")
    merged_sentiment_score = winner.get("sentiment_score")
    if winner.get("sentiment_score") is not None and loser.get("sentiment_score") is not None:
        w_score = winner["sentiment_score"]
        l_score = loser["sentiment_score"]
        # If same sign (both positive or both negative), average
        if (w_score >= 0 and l_score >= 0) or (w_score < 0 and l_score < 0):
            merged_sentiment_score = (w_score + l_score) / 2
        # Otherwise keep winner's (conflict)
    
    # 6. Update winner memory with merged content
    _db_execute_rows("""
        UPDATE memory_service.memories
        SET headline = %s, context = %s, full_content = %s,
            importance = %s, confidence = %s,
            sentiment_score = %s,
            merged_from = array_append(COALESCE(merged_from, '{}'), %s::UUID),
            version = COALESCE(version, 1) + 1
        WHERE id = %s::UUID AND tenant_id = %s::UUID
    """, (
        merged_headline, merged_context, merged_full_content,
        merged_importance, merged_confidence,
        merged_sentiment_score,
        loser_id, winner_id, tenant_id,
    ), tenant_id=tenant_id, fetch_results=False)
    
    # 7. Re-embed the merged headline+context for updated vector
    try:
        merged_text = f"{merged_headline}. {merged_context or ''}"[:2000]
        new_embedding = _embed_text(merged_text)
        _db_execute_rows("""
            UPDATE memory_service.memories
            SET embedding = %s::vector
            WHERE id = %s::UUID AND tenant_id = %s::UUID
        """, (str(new_embedding), winner_id, tenant_id), tenant_id=tenant_id, fetch_results=False)
    except Exception as e:
        logger.warning(f"Failed to re-embed merged memory {winner_id}: {e}")
    
    # 8. Supersede the loser memory
    _db_execute_rows("""
        UPDATE memory_service.memories
        SET superseded_at = NOW()
        WHERE id = %s::UUID AND tenant_id = %s::UUID
    """, (loser_id, tenant_id), tenant_id=tenant_id, fetch_results=False)
    
    # 9. Redirect graph edges from loser to winner
    _redirect_edges(loser_id, winner_id, tenant_id)
    
    # 10. Update entity index — point loser's entities to winner
    _db_execute_rows("""
        UPDATE memory_service.entity_index
        SET memory_id = %s::UUID
        WHERE memory_id = %s::UUID
    """, (winner_id, loser_id), tenant_id=tenant_id, fetch_results=False)
    
    # 11. Update duplicate record
    _db_execute_rows("""
        UPDATE memory_service.memory_duplicates
        SET status = 'merged', merged_into = %s::UUID, reviewed_at = NOW()
        WHERE id = %s::UUID AND tenant_id = %s::UUID
    """, (winner_id, duplicate_id, tenant_id), tenant_id=tenant_id, fetch_results=False)
    
    # 12. Also mark any other pending duplicates involving the loser as dismissed
    _db_execute_rows("""
        UPDATE memory_service.memory_duplicates
        SET status = 'dismissed', reviewed_at = NOW()
        WHERE tenant_id = %s::UUID
            AND status = 'pending'
            AND (memory_id_1 = %s::UUID OR memory_id_2 = %s::UUID)
            AND id != %s::UUID
    """, (tenant_id, loser_id, loser_id, duplicate_id), tenant_id=tenant_id, fetch_results=False)
    
    logger.info(f"Merged memory {loser_id} into {winner_id} (similarity={sim_score:.3f}) agent={agent_id}")
    
    return {
        "merged_memory_id": winner_id,
        "superseded_memory_id": loser_id,
        "similarity_score": float(sim_score),
        "merged_headline": merged_headline,
        "merged_importance": merged_importance,
        "merged_confidence": round(merged_confidence, 3),
    }


def unmerge_memory(
    duplicate_id: str,
    tenant_id: str,
) -> dict:
    """
    Reverse a merge by restoring the superseded memory from version history.
    
    Returns details about the un-merged memories.
    """
    # Get the duplicate record
    dup_rows = _db_execute_rows("""
        SELECT memory_id_1, memory_id_2, merged_into, agent_id
        FROM memory_service.memory_duplicates
        WHERE id = %s::UUID AND tenant_id = %s::UUID AND status = 'merged'
    """, (duplicate_id, tenant_id), tenant_id=tenant_id)
    
    if not dup_rows:
        raise ValueError("Merged duplicate record not found")
    
    mem_id_1, mem_id_2, merged_into, agent_id = dup_rows[0]
    merged_into = str(merged_into) if merged_into else None
    
    if not merged_into:
        raise ValueError("No merge target recorded — cannot unmerge")
    
    # Determine which was the loser (the one that got superseded)
    loser_id = str(mem_id_1) if str(mem_id_1) != merged_into else str(mem_id_2)
    winner_id = merged_into
    
    # Restore the loser from the last version snapshot
    versions = _db_execute_rows("""
        SELECT headline, context, full_content, memory_type, importance, confidence
        FROM memory_service.memory_versions
        WHERE memory_id = %s::UUID AND tenant_id = %s::UUID
        ORDER BY version_number DESC LIMIT 1
    """, (loser_id, tenant_id), tenant_id=tenant_id)
    
    if versions:
        v = versions[0]
        _db_execute_rows("""
            UPDATE memory_service.memories
            SET headline = %s, context = %s, full_content = %s,
                memory_type = %s, importance = %s, confidence = %s,
                superseded_at = NULL,
                version = COALESCE(version, 1) + 1
            WHERE id = %s::UUID AND tenant_id = %s::UUID
        """, (v[0], v[1], v[2], v[3], v[4], v[5], loser_id, tenant_id),
            tenant_id=tenant_id, fetch_results=False)
    else:
        # No version history — just un-supersede
        _db_execute_rows("""
            UPDATE memory_service.memories
            SET superseded_at = NULL
            WHERE id = %s::UUID AND tenant_id = %s::UUID
        """, (loser_id, tenant_id), tenant_id=tenant_id, fetch_results=False)
    
    # Restore winner from its pre-merge version
    winner_versions = _db_execute_rows("""
        SELECT headline, context, full_content, memory_type, importance, confidence
        FROM memory_service.memory_versions
        WHERE memory_id = %s::UUID AND tenant_id = %s::UUID
            AND change_reason = 'pre-merge snapshot'
        ORDER BY version_number DESC LIMIT 1
    """, (winner_id, tenant_id), tenant_id=tenant_id)
    
    if winner_versions:
        v = winner_versions[0]
        _db_execute_rows("""
            UPDATE memory_service.memories
            SET headline = %s, context = %s, full_content = %s,
                memory_type = %s, importance = %s, confidence = %s,
                merged_from = array_remove(COALESCE(merged_from, '{}'), %s::UUID),
                version = COALESCE(version, 1) + 1
            WHERE id = %s::UUID AND tenant_id = %s::UUID
        """, (v[0], v[1], v[2], v[3], v[4], v[5], loser_id, winner_id, tenant_id),
            tenant_id=tenant_id, fetch_results=False)
    
    # Reset duplicate record
    _db_execute_rows("""
        UPDATE memory_service.memory_duplicates
        SET status = 'pending', merged_into = NULL, reviewed_at = NOW()
        WHERE id = %s::UUID AND tenant_id = %s::UUID
    """, (duplicate_id, tenant_id), tenant_id=tenant_id, fetch_results=False)
    
    logger.info(f"Unmerged: restored {loser_id} from {winner_id} agent={agent_id}")
    
    return {
        "restored_memory_id": loser_id,
        "winner_memory_id": winner_id,
        "status": "unmerged",
    }


# ─── Full Consolidation Pass ────────────────────────────────────────────────

def run_consolidation(
    agent_id: str,
    tenant_id: str,
    similarity_threshold: float = 0.85,
    auto_merge: bool = False,
    auto_merge_threshold: float = 0.95,
) -> dict:
    """
    Run a full consolidation pass for an agent.
    
    1. Detect duplicates above similarity_threshold
    2. Store them in memory_duplicates
    3. If auto_merge=True, auto-merge pairs above auto_merge_threshold
    
    Returns summary of actions taken.
    """
    # Step 1: Detect
    duplicates = detect_duplicates(agent_id, tenant_id, similarity_threshold)
    
    if not duplicates:
        return {
            "duplicates_found": 0,
            "pairs_stored": 0,
            "auto_merged": 0,
            "agent_id": agent_id,
        }
    
    # Step 2: Store
    stored = store_duplicate_pairs(duplicates, agent_id, tenant_id)
    
    # Step 3: Auto-merge high-confidence duplicates if requested
    auto_merged = 0
    if auto_merge:
        # Fetch the stored pairs that are above auto_merge_threshold
        high_conf = _db_execute_rows("""
            SELECT id FROM memory_service.memory_duplicates
            WHERE agent_id = %s AND tenant_id = %s::UUID
                AND status = 'pending'
                AND similarity_score >= %s
            ORDER BY similarity_score DESC
            LIMIT 100
        """, (agent_id, tenant_id, auto_merge_threshold), tenant_id=tenant_id)
        
        for row in (high_conf or []):
            try:
                merge_memories(str(row[0]), tenant_id)
                auto_merged += 1
            except Exception as e:
                logger.warning(f"Auto-merge failed for duplicate {row[0]}: {e}")
    
    logger.info(
        f"Consolidation complete: agent={agent_id} found={len(duplicates)} "
        f"stored={stored} auto_merged={auto_merged}"
    )
    
    return {
        "duplicates_found": len(duplicates),
        "pairs_stored": stored,
        "auto_merged": auto_merged,
        "agent_id": agent_id,
    }


# ─── Dismiss ─────────────────────────────────────────────────────────────────

def dismiss_duplicate(duplicate_id: str, tenant_id: str) -> bool:
    """Mark a duplicate pair as dismissed so it won't be suggested again."""
    rows = _db_execute_rows("""
        UPDATE memory_service.memory_duplicates
        SET status = 'dismissed', reviewed_at = NOW()
        WHERE id = %s::UUID AND tenant_id = %s::UUID AND status = 'pending'
        RETURNING id
    """, (duplicate_id, tenant_id), tenant_id=tenant_id)
    return bool(rows)


# ─── Helper Functions ────────────────────────────────────────────────────────

def _get_full_memory(memory_id: str, tenant_id: str) -> Optional[dict]:
    """Fetch complete memory record."""
    rows = _db_execute_rows("""
        SELECT id, headline, context, full_content, memory_type,
               importance, confidence, sentiment, sentiment_score,
               agent_id, embedding
        FROM memory_service.memories
        WHERE id = %s::UUID AND tenant_id = %s::UUID AND superseded_at IS NULL
    """, (memory_id, tenant_id), tenant_id=tenant_id)
    
    if not rows:
        return None
    
    r = rows[0]
    return {
        "id": str(r[0]),
        "headline": str(r[1]),
        "context": str(r[2]) if r[2] else None,
        "full_content": str(r[3]) if r[3] else None,
        "memory_type": str(r[4]) if r[4] else "fact",
        "importance": float(r[5]) if r[5] is not None else 0.5,
        "confidence": float(r[6]) if r[6] is not None else 0.8,
        "sentiment": str(r[7]) if r[7] else None,
        "sentiment_score": float(r[8]) if r[8] is not None else None,
        "agent_id": str(r[9]),
    }


def _redirect_edges(old_id: str, new_id: str, tenant_id: str):
    """Redirect graph edges from old memory to new memory."""
    try:
        # Update source edges
        _db_execute_rows("""
            UPDATE memory_service.memory_edges
            SET source_memory_id = %s::UUID
            WHERE source_memory_id = %s::UUID AND tenant_id = %s::UUID
        """, (new_id, old_id, tenant_id), tenant_id=tenant_id, fetch_results=False)
        
        # Update target edges
        _db_execute_rows("""
            UPDATE memory_service.memory_edges
            SET target_memory_id = %s::UUID
            WHERE target_memory_id = %s::UUID AND tenant_id = %s::UUID
        """, (new_id, old_id, tenant_id), tenant_id=tenant_id, fetch_results=False)
        
        # Remove any self-loops that may have been created
        _db_execute_rows("""
            DELETE FROM memory_service.memory_edges
            WHERE source_memory_id = target_memory_id AND tenant_id = %s::UUID
        """, (tenant_id,), tenant_id=tenant_id, fetch_results=False)
    except Exception as e:
        logger.warning(f"Edge redirect failed for {old_id} -> {new_id}: {e}")
