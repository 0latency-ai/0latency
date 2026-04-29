"""
Consolidation Classifier - Phase 2 of Self-Improving Memory
Processes pending pairs in consolidation_queue.
Classifies each pair using an LLM call.
Updates the queue with classification results.
Does NOT modify any memories.

Run manually: cd /root/.openclaw/workspace/memory-product && python3 -m src.consolidation.classifier
Run via cron: */30 * * * * cd /root/.openclaw/workspace/memory-product && python3 -m src.consolidation.classifier >> /root/logs/classifier-cron.log 2>&1
"""

import os
import json
import datetime
import logging
import requests
import psycopg2
import psycopg2.pool
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("classifier")

# Database connection
def _get_db_conn_str():
    return os.environ["MEMORY_DB_CONN"]

# LLM API keys
def _google_key():
    return os.environ.get("GOOGLE_API_KEY", "")

def _openrouter_key():
    return os.environ.get("OPENROUTER_API_KEY", "")

# Use the CHEAPEST model available for classification
CLASSIFICATION_MODEL = "gemini-2.0-flash"

CLASSIFICATION_PROMPT = """You are a memory deduplication classifier for an AI agent memory system.

Given two memories belonging to the same agent, classify their relationship as exactly one of:

DUPLICATE — Same core information stated differently. Safe to merge.
UPDATE — Memory B contains newer information that supersedes Memory A. A is outdated.
CONTRADICTION — The memories make conflicting factual claims. Requires human review.
DISTINCT — Different topics or meaningfully different information. Keep both.

Memory A (stored: {date_a}):
  Headline: {headline_a}
  Content: {content_a}
  Type: {type_a}
  Importance: {importance_a}

Memory B (stored: {date_b}):
  Headline: {headline_b}
  Content: {content_b}
  Type: {type_b}
  Importance: {importance_b}

Classification rules:
- If memory types differ (e.g., 'fact' vs 'task'), classify as DISTINCT
- If both describe the same entity but with different attribute values, classify as UPDATE (keep the newer one) unless the older one is less than 24 hours old, then CONTRADICTION
- If importance scores differ by more than 0.3 AND content overlaps significantly, classify as UPDATE not DUPLICATE
- When uncertain, always default to DISTINCT — false merges are worse than missed merges
- NEVER classify identity memories (memory_type='identity') as DUPLICATE

Respond with ONLY this JSON, no other text:
{{
  "classification": "DUPLICATE|UPDATE|CONTRADICTION|DISTINCT",
  "confidence": 0.0-1.0,
  "reasoning": "one sentence explaining your classification"
}}"""


def _call_gemini(prompt: str, model: str = "gemini-2.0-flash", max_tokens: int = 1024) -> str:
    """Call Gemini API with JSON output."""
    raise NotImplementedError("Gemini removed 2026-04-21; reintegrate with Anthropic/OpenAI when needed")


def _call_openrouter(prompt: str, model: str = "openai/gpt-4o-mini", max_tokens: int = 1024) -> str:
    """Call OpenRouter API as fallback."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {_openrouter_key()}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You analyze memory pairs and return structured JSON classification. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ]
    }
    
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def call_llm(prompt: str) -> str:
    """Call LLM with fallback chain."""
    # Try Gemini first (cheapest)
    if _google_key():
        try:
            return _call_gemini(prompt, model=CLASSIFICATION_MODEL)
        except Exception as e:
            logger.warning(f"Gemini failed: {e}, trying OpenRouter...")
    
    # Fallback to OpenRouter
    if _openrouter_key():
        try:
            return _call_openrouter(prompt, model="openai/gpt-4o-mini")
        except Exception as e:
            logger.error(f"OpenRouter failed: {e}")
            raise
    
    raise RuntimeError("No LLM API keys available")


def classify_pending_pairs(conn, max_pairs=20):
    """Process up to max_pairs pending consolidation queue entries."""
    cur = conn.cursor()
    
    # Fetch pending pairs, ordered by similarity (highest first)
    cur.execute("""
        SELECT cq.id, cq.memory_id_a, cq.memory_id_b, cq.similarity_score, cq.agent_id, cq.tenant_id
        FROM memory_service.consolidation_queue cq
        WHERE cq.status = 'pending'
        ORDER BY cq.similarity_score DESC
        LIMIT %s
    """, (max_pairs,))
    
    pairs = cur.fetchall()
    
    log_path = f"/root/logs/classifier-{datetime.date.today()}.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    classified_count = 0
    
    for pair in pairs:
        pair_id, mem_id_a, mem_id_b, similarity, agent_id, tenant_id = pair
        
        # Fetch both memories
        cur.execute("""
            SELECT id, headline, context, memory_type, importance, created_at 
            FROM memory_service.memories 
            WHERE id = %s
        """, (mem_id_a,))
        mem_a = cur.fetchone()
        
        cur.execute("""
            SELECT id, headline, context, memory_type, importance, created_at 
            FROM memory_service.memories 
            WHERE id = %s
        """, (mem_id_b,))
        mem_b = cur.fetchone()
        
        if not mem_a or not mem_b:
            # One of the memories was deleted since queuing
            cur.execute("""
                UPDATE memory_service.consolidation_queue 
                SET status = 'rejected', 
                    classification_reasoning = 'Memory no longer exists',
                    classified_at = NOW()
                WHERE id = %s
            """, (pair_id,))
            conn.commit()
            logger.info(f"Pair {pair_id}: Rejected - memory deleted")
            continue
        
        # Unpack memory data
        _, headline_a, content_a, type_a, importance_a, created_a = mem_a
        _, headline_b, content_b, type_b, importance_b, created_b = mem_b
        
        # Build prompt
        prompt = CLASSIFICATION_PROMPT.format(
            date_a=created_a.isoformat() if created_a else 'unknown',
            headline_a=headline_a or '',
            content_a=content_a or '',
            type_a=type_a or 'unknown',
            importance_a=importance_a or 0.5,
            date_b=created_b.isoformat() if created_b else 'unknown',
            headline_b=headline_b or '',
            content_b=content_b or '',
            type_b=type_b or 'unknown',
            importance_b=importance_b or 0.5,
        )
        
        # Call LLM for classification
        try:
            result = call_llm(prompt)
            parsed = json.loads(result)
            
            classification = parsed.get('classification', 'DISTINCT')
            confidence = parsed.get('confidence', 0.0)
            reasoning = parsed.get('reasoning', 'No reasoning provided')
            
            # Validate classification type
            valid_types = ['DUPLICATE', 'UPDATE', 'CONTRADICTION', 'DISTINCT']
            if classification not in valid_types:
                logger.warning(f"Invalid classification '{classification}', defaulting to DISTINCT")
                classification = 'DISTINCT'
            
            cur.execute("""
                UPDATE memory_service.consolidation_queue 
                SET status = 'classified',
                    consolidation_type = %s,
                    classification_confidence = %s,
                    classification_reasoning = %s,
                    classified_at = NOW()
                WHERE id = %s
            """, (classification, confidence, reasoning, pair_id))
            conn.commit()
            
            classified_count += 1
            
            with open(log_path, "a") as f:
                f.write(f"{datetime.datetime.now().isoformat()} | "
                       f"pair={pair_id} | type={classification} | "
                       f"conf={confidence:.2f} | sim={similarity:.3f} | "
                       f"reason={reasoning}\n")
            
            logger.info(f"Pair {pair_id}: {classification} (conf={confidence:.2f})")
                        
        except Exception as e:
            with open(log_path, "a") as f:
                f.write(f"{datetime.datetime.now().isoformat()} | "
                       f"pair={pair_id} | ERROR: {str(e)}\n")
            logger.error(f"Pair {pair_id}: Classification failed - {e}")
            continue
    
    cur.close()
    return classified_count


def main():
    """Main entry point for classifier."""
    logger.info("Starting consolidation classifier...")
    
    try:
        conn = psycopg2.connect(_get_db_conn_str())
        
        classified = classify_pending_pairs(conn, max_pairs=20)
        
        logger.info(f"Classification complete: {classified} pairs processed")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Classifier failed: {e}")
        raise


if __name__ == "__main__":
    main()
