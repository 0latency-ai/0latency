"""
CP8 P5.5 — Pattern Memory Extraction Worker

Analyzes recall_feedback events to identify behavioral patterns and creates
pattern memory entries. Runs as a periodic cron job (daily at 04:00) or via
manual trigger (POST /patterns/run).

Pattern types:
- correction: User corrects same topic repeatedly
- preference_confirmation: User confirms same preference multiple times  
- usage_frequency: User queries same topic frequently
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import psycopg2
from anthropic import Anthropic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger("zerolatency.pattern_worker")

# Configuration
LOOKBACK_DAYS = 30  # Analyze feedback from last N days
MIN_OBSERVATIONS = 3  # Minimum feedback events to constitute a pattern
BATCH_SIZE = 50  # Process N agents at a time


def get_model_for_tier(tier: str) -> str:
    """Return the appropriate model based on tier."""
    if tier == "enterprise":
        return "claude-sonnet-4-20250514"
    else:  # scale
        return "claude-3-5-haiku-20241022"


def extract_patterns_for_agent(
    conn,
    tenant_id: str,
    agent_id: str,
    tier: str,
    anthropic_client: Anthropic
) -> List[Dict[str, Any]]:
    """
    Extract patterns from feedback events for a single agent.
    
    Returns:
        List of pattern dicts with keys: pattern_type, headline, context,
        observation_count, last_observation_at, triggering_event_ids
    """
    cur = conn.cursor()
    
    # Fetch recent feedback events for this agent
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    cur.execute(
        """
        SELECT rf.id, rf.feedback_type, rf.context, rf.created_at,
               m.headline, m.context as memory_context, m.full_content
        FROM memory_service.recall_feedback rf
        JOIN memory_service.memories m ON rf.memory_id = m.id
        WHERE rf.tenant_id = %s::uuid
          AND rf.agent_id = %s
          AND rf.created_at >= %s
          AND rf.feedback_type IN ('used', 'ignored', 'contradicted', 'miss')
        ORDER BY rf.created_at DESC
        LIMIT 200
        """,
        (tenant_id, agent_id, cutoff)
    )
    
    feedback_events = cur.fetchall()
    
    if len(feedback_events) < MIN_OBSERVATIONS:
        logger.debug(f"Agent {agent_id}: insufficient feedback ({len(feedback_events)} events)")
        return []
    
    # Format feedback for LLM analysis
    feedback_summary = []
    for event_id, fb_type, context, created_at, headline, mem_context, full_content in feedback_events:
        feedback_summary.append({
            "event_id": str(event_id),
            "type": fb_type,
            "context": context or "",
            "timestamp": created_at.isoformat(),
            "memory_headline": headline,
            "memory_context": mem_context
        })
    
    # Call LLM to identify patterns
    model = get_model_for_tier(tier)
    
    prompt = f"""Analyze the following memory feedback events for agent "{agent_id}" to identify behavioral patterns.

A pattern is a recurring behavior where the user repeatedly:
- Corrects the same type of information (correction pattern)
- Confirms the same preference multiple times (preference_confirmation pattern)
- Queries the same topic frequently (usage_frequency pattern)

Return ONLY valid JSON (no markdown, no code fences) in this exact format:
{{
  "patterns": [
    {{
      "pattern_type": "correction" | "preference_confirmation" | "usage_frequency",
      "headline": "Brief description (max 100 chars)",
      "context": "Detailed explanation with evidence",
      "observation_count": <number>,
      "confidence": <0.0-1.0>,
      "triggering_event_ids": ["uuid1", "uuid2", ...]
    }}
  ]
}}

If no clear patterns exist (fewer than 3 related events), return {{"patterns": []}}.

Feedback events (most recent first):
{json.dumps(feedback_summary[:50], indent=2)}
"""
    
    try:
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        
        # Parse JSON response
        patterns_data = json.loads(response_text)
        patterns = patterns_data.get("patterns", [])
        
        # Validate and filter patterns
        valid_patterns = []
        for p in patterns:
            if (p.get("observation_count", 0) >= MIN_OBSERVATIONS and
                p.get("pattern_type") in ["correction", "preference_confirmation", "usage_frequency"] and
                len(p.get("triggering_event_ids", [])) >= MIN_OBSERVATIONS):
                
                # Add last_observation_at from most recent triggering event
                triggering_ids_set = set(p["triggering_event_ids"])
                matching_events = [e for e in feedback_events if str(e[0]) in triggering_ids_set]
                if matching_events:
                    p["last_observation_at"] = max(e[3] for e in matching_events)
                    valid_patterns.append(p)
        
        logger.info(f"Agent {agent_id}: extracted {len(valid_patterns)} patterns from {len(feedback_events)} events")
        return valid_patterns
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response for {agent_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Pattern extraction failed for {agent_id}: {e}")
        return []


def write_pattern_memory(
    conn,
    tenant_id: str,
    agent_id: str,
    pattern: Dict[str, Any]
) -> Optional[str]:
    """
    Write a pattern memory to the database.
    
    Returns:
        Memory ID if successful, None otherwise
    """
    cur = conn.cursor()
    
    try:
        # Check if similar pattern already exists (dedupe)
        cur.execute(
            """
            SELECT id FROM memory_service.memories
            WHERE tenant_id = %s::uuid
              AND agent_id = %s
              AND memory_type = 'pattern'
              AND pattern_type = %s
              AND superseded_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (tenant_id, agent_id, pattern["pattern_type"])
        )
        
        existing = cur.fetchone()
        
        if existing:
            # Update existing pattern
            memory_id = existing[0]
            cur.execute(
                """
                UPDATE memory_service.memories
                SET observation_count = %s,
                    last_observation_at = %s,
                    triggering_event_ids = %s,
                    confidence = %s,
                    context = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    pattern["observation_count"],
                    pattern["last_observation_at"],
                    pattern["triggering_event_ids"],
                    pattern.get("confidence", 0.8),
                    pattern["context"],
                    memory_id
                )
            )
            logger.debug(f"Updated existing pattern {memory_id}")
        else:
            # Create new pattern memory
            cur.execute(
                """
                INSERT INTO memory_service.memories
                  (tenant_id, agent_id, memory_type, pattern_type,
                   headline, context, full_content,
                   observation_count, last_observation_at,
                   triggering_event_ids, confidence,
                   importance, created_at)
                VALUES
                  (%s::uuid, %s, 'pattern', %s,
                   %s, %s, %s,
                   %s, %s, %s, %s,
                   0.8, NOW())
                RETURNING id
                """,
                (
                    tenant_id,
                    agent_id,
                    pattern["pattern_type"],
                    pattern["headline"],
                    pattern["context"],
                    json.dumps(pattern),  # full_content contains the raw pattern data
                    pattern["observation_count"],
                    pattern["last_observation_at"],
                    pattern["triggering_event_ids"],
                    pattern.get("confidence", 0.8)
                )
            )
            memory_id = cur.fetchone()[0]
            logger.info(f"Created pattern memory {memory_id} for agent {agent_id}")
        
        # Log audit event
        cur.execute(
            """
            INSERT INTO memory_service.synthesis_audit_events
              (tenant_id, target_memory_id, event_type, actor, occurred_at, event_payload)
            VALUES
              (%s::uuid, %s::uuid, 'pattern_extracted', %s, NOW(), %s::jsonb)
            """,
            (
                tenant_id,
                memory_id,
                f"system:pattern_worker",
                json.dumps({
                    "pattern_type": pattern["pattern_type"],
                    "observation_count": pattern["observation_count"],
                    "confidence": pattern.get("confidence", 0.8)
                })
            )
        )
        
        return str(memory_id)
        
    except Exception as e:
        logger.error(f"Failed to write pattern memory: {e}")
        return None


def run_pattern_extraction(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Run pattern extraction for all eligible agents.
    
    Args:
        tenant_id: If provided, only process this tenant
    
    Returns:
        Statistics dict
    """
    from storage_multitenant import _get_connection_pool
    import tier_gates
    
    stats = {
        "tenants_processed": 0,
        "agents_processed": 0,
        "patterns_created": 0,
        "patterns_updated": 0,
        "errors": 0
    }
    
    pool = _get_connection_pool()
    conn = pool.getconn()
    
    try:
        anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        cur = conn.cursor()
        
        # Get tenants eligible for pattern extraction
        if tenant_id:
            tenant_filter = f"AND id = '{tenant_id}'::uuid"
        else:
            tenant_filter = ""
        
        cur.execute(f"""
            SELECT id, plan
            FROM memory_service.tenants
            WHERE plan IN ('scale', 'enterprise')
              {tenant_filter}
        """)
        
        tenants = cur.fetchall()
        
        for tenant_id_row, tier in tenants:
            tenant_id_str = str(tenant_id_row)
            
            # Check tier gate
            tier_matrix = tier_gates.TIER_MATRIX.get(tier, {})
            if not tier_matrix.get("pattern_extraction_enabled", False):
                logger.debug(f"Tenant {tenant_id_str}: pattern extraction not enabled for tier {tier}")
                continue
            
            # Get agents with sufficient feedback
            cur.execute(
                """
                SELECT DISTINCT agent_id, COUNT(*) as feedback_count
                FROM memory_service.recall_feedback
                WHERE tenant_id = %s::uuid
                  AND created_at >= %s
                GROUP BY agent_id
                HAVING COUNT(*) >= %s
                ORDER BY feedback_count DESC
                LIMIT %s
                """,
                (
                    tenant_id_str,
                    datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS),
                    MIN_OBSERVATIONS,
                    BATCH_SIZE
                )
            )
            
            agents = cur.fetchall()
            
            if not agents:
                logger.debug(f"Tenant {tenant_id_str}: no agents with sufficient feedback")
                continue
            
            stats["tenants_processed"] += 1
            
            for agent_id, feedback_count in agents:
                try:
                    patterns = extract_patterns_for_agent(
                        conn, tenant_id_str, agent_id, tier, anthropic_client
                    )
                    
                    for pattern in patterns:
                        memory_id = write_pattern_memory(conn, tenant_id_str, agent_id, pattern)
                        if memory_id:
                            if "updated" in memory_id.lower():
                                stats["patterns_updated"] += 1
                            else:
                                stats["patterns_created"] += 1
                    
                    stats["agents_processed"] += 1
                    conn.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing agent {agent_id}: {e}")
                    stats["errors"] += 1
                    conn.rollback()
        
        logger.info(f"Pattern extraction complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Pattern extraction failed: {e}")
        raise
    finally:
        pool.putconn(conn)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract pattern memories from feedback events")
    parser.add_argument("--tenant-id", help="Process only this tenant")
    args = parser.parse_args()
    
    result = run_pattern_extraction(tenant_id=args.tenant_id)
    print(json.dumps(result, indent=2))
