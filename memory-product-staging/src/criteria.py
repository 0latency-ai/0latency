"""
Criteria Retrieval — Custom scoring attributes for re-ranking recalled memories.
Feature gap #4 vs mem0: Developer-defined criteria like 'urgency', 'joy', 'confidence'
that dynamically influence recall scoring.
"""

import json
from typing import Optional
from storage_multitenant import _db_execute_rows


def create_criteria(tenant_id: str, agent_id: str, name: str, weight: float = 0.5,
                    description: str = None, scoring_prompt: str = None) -> dict:
    """Create a custom recall criteria for an agent."""
    rows = _db_execute_rows("""
        INSERT INTO memory_service.recall_criteria 
            (tenant_id, agent_id, name, weight, description, scoring_prompt)
        VALUES (%s::UUID, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, agent_id, name) DO UPDATE
        SET weight = EXCLUDED.weight,
            description = COALESCE(EXCLUDED.description, memory_service.recall_criteria.description),
            scoring_prompt = COALESCE(EXCLUDED.scoring_prompt, memory_service.recall_criteria.scoring_prompt)
        RETURNING id, created_at
    """, (tenant_id, agent_id, name, weight, description, scoring_prompt), tenant_id=tenant_id)
    
    if rows:
        return {
            "id": str(rows[0][0]),
            "name": name,
            "weight": weight,
            "description": description,
            "created_at": str(rows[0][1]),
        }
    raise RuntimeError("Failed to create criteria")


def list_criteria(tenant_id: str, agent_id: str) -> list[dict]:
    """List all active criteria for an agent."""
    rows = _db_execute_rows("""
        SELECT id, name, weight, description, scoring_prompt, active
        FROM memory_service.recall_criteria
        WHERE tenant_id = %s::UUID AND agent_id = %s AND active = true
        ORDER BY weight DESC
    """, (tenant_id, agent_id), tenant_id=tenant_id)
    
    return [{
        "id": str(r[0]),
        "name": str(r[1]),
        "weight": float(r[2]) if r[2] else 0.5,
        "description": str(r[3]) if r[3] else None,
        "scoring_prompt": str(r[4]) if r[4] else None,
        "active": bool(r[5]),
    } for r in (rows or [])]


def delete_criteria(tenant_id: str, criteria_id: str) -> bool:
    """Soft-delete a criteria."""
    rows = _db_execute_rows("""
        UPDATE memory_service.recall_criteria 
        SET active = false
        WHERE id = %s::UUID AND tenant_id = %s::UUID
        RETURNING id
    """, (criteria_id, tenant_id), tenant_id=tenant_id)
    return bool(rows)


def score_memory_against_criteria(memory: dict, criteria: list[dict]) -> dict:
    """
    Score a memory against custom criteria using heuristics.
    For lightweight scoring without an LLM call.
    Returns {criteria_name: score} dict.
    """
    scores = {}
    text = f"{memory.get('headline', '')} {memory.get('context', '')} {memory.get('full_content', '')}".lower()
    
    for c in criteria:
        name = c["name"].lower()
        score = 0.5  # default neutral
        
        if name == "urgency":
            urgency_words = ["urgent", "asap", "immediately", "critical", "deadline", "overdue", "blocker", "now"]
            hits = sum(1 for w in urgency_words if w in text)
            score = min(1.0, 0.3 + hits * 0.15)
            
        elif name == "joy" or name == "positivity":
            positive_words = ["great", "excellent", "love", "happy", "success", "win", "celebrate", "perfect", "amazing"]
            hits = sum(1 for w in positive_words if w in text)
            score = min(1.0, 0.2 + hits * 0.15)
            
        elif name == "negativity" or name == "risk":
            negative_words = ["fail", "error", "broken", "risk", "problem", "issue", "bug", "concern", "worry", "loss"]
            hits = sum(1 for w in negative_words if w in text)
            score = min(1.0, 0.2 + hits * 0.15)
            
        elif name == "actionability":
            action_words = ["should", "must", "need to", "todo", "action", "next step", "implement", "build", "fix"]
            hits = sum(1 for w in action_words if w in text)
            score = min(1.0, 0.2 + hits * 0.15)
            
        elif name == "confidence":
            score = memory.get("confidence", 0.8)
            
        elif name == "complexity":
            # Longer memories tend to be more complex
            word_count = len(text.split())
            score = min(1.0, word_count / 200)
            
        else:
            # Unknown criteria — use importance as proxy
            score = memory.get("importance", 0.5)
        
        scores[c["name"]] = round(score, 3)
    
    return scores


def apply_criteria_reranking(candidates: list[dict], criteria: list[dict]) -> list[dict]:
    """
    Re-rank recall candidates using custom criteria.
    Each candidate gets a criteria_boost that adjusts its composite score.
    """
    if not criteria:
        return candidates
    
    total_criteria_weight = sum(c.get("weight", 0.5) for c in criteria)
    if total_criteria_weight == 0:
        return candidates
    
    for candidate in candidates:
        criteria_scores = score_memory_against_criteria(candidate, criteria)
        
        # Weighted sum of criteria scores
        criteria_boost = 0
        for c in criteria:
            score = criteria_scores.get(c["name"], 0.5)
            weight = c.get("weight", 0.5) / total_criteria_weight
            criteria_boost += score * weight
        
        # Blend: 70% original composite + 30% criteria
        original = candidate.get("composite", 0.5)
        candidate["composite"] = 0.7 * original + 0.3 * criteria_boost
        candidate["criteria_scores"] = criteria_scores
    
    # Re-sort
    candidates.sort(key=lambda x: x.get("composite", 0), reverse=True)
    return candidates


def cache_criteria_scores(memory_id: str, criteria_scores: dict, tenant_id: str):
    """Cache LLM-scored criteria values for a memory."""
    for criteria_id, score in criteria_scores.items():
        _db_execute_rows("""
            INSERT INTO memory_service.memory_criteria_scores (memory_id, criteria_id, score)
            VALUES (%s::UUID, %s::UUID, %s)
            ON CONFLICT (memory_id, criteria_id) DO UPDATE
            SET score = EXCLUDED.score, scored_at = now()
        """, (memory_id, criteria_id, score), tenant_id=tenant_id, fetch_results=False)
