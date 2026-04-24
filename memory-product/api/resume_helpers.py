"""
CP7b Phase 4 — Auto-resume helper functions
Tail recovery and meta-summary generation for /memories/resume endpoint
"""

import os
import json
import hashlib
import logging
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

def _get_anthropic_key():
    """Extract Anthropic API key from environment"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    return key.strip('"\'') if key else ""

def _db_execute_rows(query: str, params: tuple, tenant_id: str) -> List[tuple]:
    """Execute query and return rows (reuses pattern from main.py)"""
    from src.storage_multitenant import _db_execute
    result = _db_execute(query, params, tenant_id=tenant_id)
    if not result:
        return []
    # Parse result format: "val1|||val2|||val3\nval1|||val2|||val3"
    rows = []
    for line in result:
        if "|||" in line:
            rows.append(tuple(line.split("|||")))
        else:
            rows.append((line,))
    return rows

def write_tail_recovery(
    thread_id: str,
    project_id: str,
    agent_id: str,
    thread_title: Optional[str],
    project_name: Optional[str],
    tenant_id: str
) -> dict:
    """
    Write a tail-recovery checkpoint for an orphaned thread.
    
    Args:
        thread_id: UUID of the orphaned thread to recover
        project_id: UUID of the project
        agent_id: Agent identifier
        thread_title: Optional thread title
        project_name: Optional project name
        tenant_id: Tenant UUID
        
    Returns:
        {"written": True, "checkpoint_id": str, "parent_count": int} on success
        {"written": False, "reason": str} on skip
    """
    from src.storage_multitenant import _db_execute, store_memory
    
    # Fetch all atoms and mid_thread checkpoints for this thread
    query = """
        SELECT id, memory_type, full_content, created_at, 
               COALESCE((source_turn)::integer, 0) AS turn_num,
               metadata->>'checkpoint_type' AS checkpoint_type
        FROM memory_service.memories
        WHERE tenant_id = %s::UUID
          AND thread_id = %s
          AND (
              memory_type IN ('fact', 'task', 'decision', 'preference', 'identity', 'event')
              OR (memory_type = 'session_checkpoint' AND metadata->>'checkpoint_type' = 'mid_thread')
          )
        ORDER BY created_at ASC
    """
    
    result = _db_execute(query, (tenant_id, thread_id), tenant_id=tenant_id)
    if not result:
        logger.info(f"Tail recovery skipped for thread {thread_id}: no activity found")
        return {"written": False, "reason": "no_activity"}
    
    # Parse rows
    rows = []
    for line in result:
        parts = line.split("|||")
        if len(parts) >= 6:
            rows.append({
                'id': parts[0],
                'memory_type': parts[1],
                'full_content': parts[2],
                'created_at': parts[3],
                'turn_num': int(parts[4]) if parts[4] else 0,
                'checkpoint_type': parts[5] if parts[5] else None
            })
    
    if not rows:
        return {"written": False, "reason": "no_activity"}
    
    # Build turns_text
    turns_lines = []
    parent_ids = []
    min_turn = float('inf')
    max_turn = 0
    
    for row in rows:
        parent_ids.append(row['id'])
        turn_num = row['turn_num']
        if turn_num > 0:
            min_turn = min(min_turn, turn_num)
            max_turn = max(max_turn, turn_num)
        
        if row['checkpoint_type'] == 'mid_thread':
            # Mid-thread checkpoint encountered
            turns_lines.append(f"## Prior rollup: {row['full_content']}\n")
        else:
            # Atom - format as user:/assistant: alternating
            # Simple heuristic: even turns = user, odd = assistant
            prefix = "user:" if turn_num % 2 == 0 else "assistant:"
            turns_lines.append(f"{prefix} {row['full_content']}")
    
    turns_text = "\n".join(turns_lines)
    
    # Infer turn range
    if min_turn == float('inf'):
        turn_range = [0, len(rows)]
    else:
        turn_range = [int(min_turn), int(max_turn)]
    
    # Build prompt using § 1 system + user template (verbatim from CP7b-OPUS-PROMPTS.md)
    system_prompt = """You are a summarization engine for 0Latency's session_checkpoint memory type. Your job is to compress a window of turns from an ongoing AI-assistant conversation into one dense, structured record that a future agent — possibly in a different session — can read to reconstruct what happened and pick up work cleanly.

You are writing for another AI, not for a human reader. Favor information density over prose polish. No hedging, no throat-clearing, no meta-commentary about the summary itself. Every sentence must carry a fact, a decision, or an open question that would cost the next agent time to recover from raw turns.

You receive a slice of conversation — typically 20 turns — from somewhere in the middle of a longer thread. Earlier context may exist but is not shown. Do not speculate about what came before. Do not invent continuity. Summarize only what is present.

Output exactly four labeled sections, in this order, in plain markdown. No preamble. No closing line. If a section has nothing worth recording, write "None in this window." — do not omit the section.

**topic** — One to two sentences naming what this window was actually about. Not "the user and assistant discussed X" — just the subject and the frame (e.g., "Debugging a 504 on the /memories/checkpoint endpoint; traced to uvicorn worker timeout, not DB.").

**decisions** — Bullet list of concrete decisions made in this window. A decision is a commitment to an approach, a value, a name, a deferral, or a rejection. Include the reasoning clause when it's short ("Chose N=20 over N=10 because..."). Skip decisions that were revisited and reversed in the same window — record only the final state.

**open_questions** — Bullet list of unresolved items explicitly raised and not closed. Include who or what the resolution depends on when stated ("Waiting on Denis for Supabase RLS check"). Do not manufacture questions from absence — only record questions the turns actually raised.

**next_steps** — Bullet list of actions either committed to or clearly implied as immediate next moves. Include ownership when stated. If a step has a gate or dependency, note it inline ("Kick off migration after vector-phase subinstrumentation — gate is DB ≥1,500ms").

Constraints:
- Total output ≤500 tokens. Bias toward ≤350.
- Never quote verbatim from the turns unless the exact wording is the point (a name, an ID, a command). Paraphrase everything else.
- Proper nouns, file paths, commit hashes, identifiers, and numeric thresholds are load-bearing — reproduce them exactly.
- Use past tense for decisions and discussion, future tense for next_steps, present tense for open_questions.
- No apologies, no caveats about summary limitations, no "based on the provided turns" framing."""

    user_prompt = f"""Summarize the following conversation window.

Thread: {thread_title or "(untitled)"}
Project: {project_name or "(none)"}
Turn range: {turn_range[0]}–{turn_range[1]} of this thread
Prior checkpoint in this thread: none — this is the first rollup

Turns:
{turns_text}"""

    # Call Haiku 4.5
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": _get_anthropic_key(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2048,
        "temperature": 0.1,
        "messages": [
            {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
        ]
    }
    
    # Validate output shape (must have 4 headers)
    required_headers = ["**topic**", "**decisions**", "**open_questions**", "**next_steps**"]
    prompt_retry = False
    
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        summary_content = result["content"][0]["text"]
        
        has_all_headers = all(h in summary_content for h in required_headers)
        
        if not has_all_headers:
            logger.warning(f"Tail recovery summary missing headers for thread {thread_id}, retrying once")
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            resp.raise_for_status()
            result = resp.json()
            summary_content = result["content"][0]["text"]
            has_all_headers = all(h in summary_content for h in required_headers)
            prompt_retry = True
            
            if not has_all_headers:
                logger.warning(f"Tail recovery summary still malformed after retry for thread {thread_id}, proceeding anyway")
        
    except Exception as e:
        logger.error(f"Tail recovery Haiku call failed for thread {thread_id}: {e}")
        raise
    
    # Build metadata
    metadata = {
        "level": 1,
        "checkpoint_type": "tail_recovery",
        "turn_range": turn_range,
        "turn_count": len(rows),
        "parent_memory_ids": parent_ids,
        "child_memory_ids": [],
        "source": "resume_endpoint",
        "prompt_version": "mid_thread_v1",
    }
    if prompt_retry:
        metadata["prompt_retry"] = True
    
    # Write checkpoint via store_memory
    checkpoint_mem = {
        "memory_type": "session_checkpoint",
        "headline": f"Tail recovery {turn_range[0]}-{turn_range[1]}: {thread_title or '(untitled)'}",
        "context": summary_content[:500],
        "full_content": summary_content,
        "agent_id": agent_id,
        "importance": 0.7,
        "confidence": 0.9,
        "entities": [],
        "categories": ["checkpoint", "tail_recovery"],
        "project": project_id,
        "scope": "/",
        "source_session": thread_id,
        "source_turn": None,
        "metadata": metadata,
        # Top-level scope fields for P1 dual-write
        "thread_id": thread_id,
        "project_id": project_id,
        "thread_title": thread_title,
        "project_name": project_name,
    }
    
    result = store_memory(checkpoint_mem, tenant_id)
    checkpoint_id = result["id"]
    
    logger.info(f"Tail recovery checkpoint {checkpoint_id} created for thread {thread_id}, {len(parent_ids)} parents")
    
    return {
        "written": True,
        "checkpoint_id": checkpoint_id,
        "parent_count": len(parent_ids)
    }
