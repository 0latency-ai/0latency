"""
Extraction Layer — Agent Memory Service
Phase 1: Automatically extract structured memories from conversation turns.

This module processes raw conversation exchanges and outputs typed, tiered memory objects.
Uses GPT-4o-mini by default (fast, cheap, sufficient for structured extraction).
"""

import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional
import requests


# --- Configuration ---

EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Extraction prompt — the core of Phase 1
EXTRACTION_PROMPT = """You are a memory extraction system. Your job is to analyze a conversation exchange between a human and an AI agent, and extract structured memories worth preserving.

Extract ONLY information that would be useful in future conversations. Skip:
- Routine pleasantries and filler
- Information that's only relevant to the immediate exchange
- Duplicates of things already in the existing memory context (provided below)
- Hypothetical statements ("what if...", "imagine if...", "could we...") — unless the user explicitly decides to pursue them
- Sarcastic or joking statements — do NOT store jokes as facts
- Speculative future plans that haven't been committed to

For each extracted memory, provide:
1. **headline**: One-line summary (10-20 tokens). Must be self-contained and meaningful.
2. **context**: The fact with enough context to be useful (50-100 tokens). Include WHY it matters.
3. **full_content**: Complete memory with all nuance, caveats, source info (200-500 tokens).
4. **memory_type**: MUST be one of these exact values. Choose carefully:
   - "preference": How the user wants things done. Communication style, behavior rules, tool usage norms, likes/dislikes. If the user says "don't do X" or "always do Y" or "I prefer Z" — this is a preference.
   - "decision": A choice that was made. ONLY use when someone explicitly chose A over B, approved a plan, committed to a direction, or gave a definitive answer. For decisions, you MUST capture in full_content: (a) what was decided, (b) why/rationale, (c) who made it, (d) what alternatives were rejected or what it supersedes. "Agreed" or "yes" in response to a proposal = decision. Vague discussion ≠ decision.
   - "fact": Objective information. Dates, numbers, states of affairs, technical details, business facts. THIS IS THE DEFAULT — if something doesn't clearly fit another type, it's a fact.
   - "task": Something that needs to be done. Action items, todos, follow-ups, deadlines.
   - "correction": ONLY when a previously held belief/fact is EXPLICITLY stated to be wrong and replaced with a new fact. Both the old and new fact must be clearly present in the conversation. Someone adding new information is NOT a correction — it's a fact. An agent status update is NOT a correction. Only use correction when the conversation explicitly says "X was wrong, it's actually Y" or "not X, it's Y."
   - "relationship": A connection between people, organizations, or concepts.
   - "identity": Core identity information — names (people, pets, places), roles, permanent attributes. These NEVER decay.
5. **importance**: 0.0-1.0. How important is this for future interactions?
   - 0.9-1.0: Critical (identity facts like names/roles, non-negotiable rules, key business decisions, user preferences about agent behavior)
   - 0.7-0.8: Important (business decisions, project milestones, key contacts)
   - 0.4-0.6: Moderate (contextual facts, minor details)
   - 0.1-0.3: Low (passing mentions, temporary context)
6. **confidence**: 0.0-1.0. How confident are you this is a real fact vs hypothetical/joke/uncertain?
   - 0.9-1.0: Stated directly and clearly as fact
   - 0.6-0.8: Likely true but inferred or implied
   - 0.3-0.5: Uncertain — might be hypothetical, sarcastic, or conditional
   - 0.0-0.2: Probably not a real fact — clearly hypothetical or joking
7. **entities**: List of people, projects, organizations, or concepts mentioned
8. **project**: Which project/area this relates to (if any)
9. **categories**: 1-3 auto-inferred tags
10. **scope**: Hierarchical path like /project/subarea (e.g., /pfl-academy/oklahoma, /personal/preferences)
11. **temporal_type**: How does this fact relate to time?
    - "permanent": Always true (names, identities, preferences) — should never decay
    - "current": True now but could change (current projects, current status)
    - "event": Something that happened at a specific time (dinner tonight, meeting yesterday)
    - "ephemeral": Only relevant for a few hours (current location, what they're doing right now). Set ttl_hours.
    - "goal": A future aspiration or target ($1M ARR goal)
12. **ttl_hours**: (optional, only for ephemeral) Number of hours this memory stays relevant. Default 12.

STRUCTURED LIST PRESERVATION: When the conversation contains a numbered list, checklist, ordered plan, or set of items that form a coherent group, extract them as ONE memory with the full list preserved. Do NOT shatter a 9-item checklist into 9 separate memories. The headline should reference the list ("9-item pre-launch checklist" or "Phase A→B→C cost comparison"), and full_content should contain all items with their ordering and any dependencies. Individual items from the list should ONLY get their own separate memory if they contain significant standalone information beyond their role in the list.

DECISION SPECIFICITY: When the human responds to a list of items (e.g., "3: Agreed. 4: Yes, let's do that. 5: Sounds good"), extract ONE decision memory that captures ALL their responses together, not individual memories per item. The headline should be "Responses to [list name]" and full_content should map each item to the human's specific response and rationale.

MULTI-TURN INFERENCE: You are given the CURRENT exchange plus RECENT CONTEXT (previous turns). Use the recent context to:
- Catch information IMPLIED across messages but never stated explicitly in one turn
- Understand evolving discussions (e.g., frustration building over multiple messages, decisions being refined)
- Connect references ("that thing we discussed" → match to specific prior turn)
- Extract memories that only become clear when multiple turns are considered together
Do NOT re-extract memories from the recent context turns — only extract NEW memories from the current exchange, informed by the context.

CONTRADICTION CHECK: Before extracting, compare against the existing memory context below. If a new statement CONTRADICTS an existing memory:
- Mark the new memory as type "correction"
- Include BOTH the old fact and new fact in full_content
- Set the field "contradicts" to the headline of the contradicted memory

If nothing worth extracting, return an empty array [].

Respond with a JSON array of memory objects.

EXISTING MEMORY CONTEXT (to avoid duplicates):
{existing_context}

RECENT CONVERSATION CONTEXT (previous turns for multi-turn inference):
{recent_context}

CURRENT EXCHANGE (extract memories from THIS):
Human: {human_message}
Agent: {agent_message}

Extract memories as JSON array:"""


def _call_anthropic(prompt: str) -> str:
    """Call Anthropic (Haiku) as fallback."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "prompt-caching-2024-07-31",
        "content-type": "application/json"
    }
    
    body = {
        "model": "claude-3-5-haiku-latest",
        "max_tokens": 4096,
        "temperature": 0.1,
        "system": [
            {
                "type": "text",
                "text": "You are a memory extraction system. Extract structured memories from conversations. Always respond with valid JSON.",
                "cache_control": {"type": "ephemeral"}
            }
        ],
        "messages": [{"role": "user", "content": prompt}]
    }
    
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    
    result = resp.json()
    return result["content"][0]["text"]


def _call_openai(prompt: str) -> str:
    """Call OpenAI (GPT-4o-mini) as fallback."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You extract structured memories from conversations. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ]
        # Note: OpenAI prompt caching is automatic for prompts >1024 tokens (no explicit flag needed)
    }
    
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    
    result = resp.json()
    return result["choices"][0]["message"]["content"]


def _call_model(prompt: str) -> str:
    """Call the configured extraction model with fallback chain."""
    if OPENAI_API_KEY:
        try:
            return _call_openai(prompt)
        except Exception as e:
            print(f"OpenAI failed ({e}), trying Anthropic fallback...")
    
    if ANTHROPIC_API_KEY:
        try:
            return _call_anthropic(prompt)
        except Exception as e:
            print(f"Anthropic failed ({e})")
    
    raise RuntimeError("No extraction model available. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")


def _generate_id(content: str, timestamp: str) -> str:
    """Generate a deterministic ID for deduplication."""
    return hashlib.sha256(f"{content}:{timestamp}".encode()).hexdigest()[:16]


def extract_memories(
    human_message: str,
    agent_message: str,
    agent_id: str = "default",
    session_key: Optional[str] = None,
    turn_id: Optional[str] = None,
    existing_context: str = "",
    recent_turns: Optional[list[tuple[str, str]]] = None,
) -> list[dict]:
    """
    Extract structured memories from a single conversation exchange,
    with multi-turn context for inference across messages.
    
    Args:
        human_message: The human's message
        agent_message: The agent's response
        agent_id: Which agent this is for
        session_key: Current session identifier
        turn_id: Specific turn/message ID
        existing_context: Recent memories to avoid duplicates (L0 headlines)
        recent_turns: List of (human_msg, agent_msg) tuples for the previous 3-4 turns
    
    Returns:
        List of structured memory objects ready for storage
    """
    # Skip extraction for very short exchanges (greetings, acks)
    if len(human_message) < 20 and len(agent_message) < 50:
        return []
    
    # Build recent context string from sliding window
    recent_context = "(no prior turns)"
    if recent_turns:
        parts = []
        for i, (h, a) in enumerate(recent_turns[-4:]):  # Max 4 prior turns
            parts.append(f"[Turn -{len(recent_turns)-i}]\nHuman: {h[:500]}\nAgent: {a[:500]}")
        recent_context = "\n\n".join(parts)
    
    # Build the prompt
    prompt = EXTRACTION_PROMPT.format(
        existing_context=existing_context or "(no existing context)",
        recent_context=recent_context,
        human_message=human_message,
        agent_message=agent_message,
    )
    
    # Call the model
    raw_response = _call_model(prompt)
    
    # Parse response
    try:
        # Handle potential markdown code blocks
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        
        memories = json.loads(cleaned)
        
        # Handle case where model wraps array in an object
        if isinstance(memories, dict):
            if "memories" in memories:
                memories = memories["memories"]
            elif "extracted_memories" in memories:
                memories = memories["extracted_memories"]
            else:
                memories = [memories]
        
        if not isinstance(memories, list):
            memories = [memories]
            
    except json.JSONDecodeError as e:
        print(f"Failed to parse extraction response: {e}")
        print(f"Raw response: {raw_response[:500]}")
        return []
    
    # Validate and enrich each memory
    now = datetime.now(timezone.utc).isoformat()
    validated = []
    
    for mem in memories:
        if not isinstance(mem, dict):
            continue
        
        # Required fields
        headline = mem.get("headline", "").strip()
        if not headline:
            continue
        
        context = mem.get("context", headline).strip()
        full_content = mem.get("full_content", context).strip()
        memory_type = mem.get("memory_type", "fact")
        
        # Validate memory_type
        valid_types = {"fact", "decision", "preference", "task", "correction", "relationship", "identity"}
        if memory_type not in valid_types:
            memory_type = "fact"
        
        # Get confidence — skip low-confidence extractions (hypotheticals, jokes)
        confidence = max(0.0, min(1.0, float(mem.get("confidence", 0.8))))
        if confidence < 0.3:
            continue  # Don't store things we're not sure about
        
        # Get temporal type
        temporal_type = mem.get("temporal_type", "current")
        if temporal_type not in {"permanent", "current", "event", "goal", "ephemeral"}:
            temporal_type = "current"
        
        # Auto-upgrade to identity type for permanent personal facts
        if temporal_type == "permanent" and memory_type == "fact":
            memory_type = "identity"
        
        # Calculate TTL for ephemeral memories
        ttl_hours = None
        if temporal_type == "ephemeral":
            ttl_hours = int(mem.get("ttl_hours", 12))
        
        # Build metadata with new fields
        metadata = {
            "temporal_type": temporal_type,
            "contradicts": mem.get("contradicts"),
        }
        
        # Build the structured memory object
        memory_obj = {
            "id": _generate_id(headline, now),
            "agent_id": agent_id,
            "headline": headline,
            "context": context,
            "full_content": full_content,
            "memory_type": memory_type,
            "importance": max(0.0, min(1.0, float(mem.get("importance", 0.5)))),
            "confidence": confidence,
            "entities": mem.get("entities", []),
            "project": mem.get("project"),
            "categories": mem.get("categories", []),
            "scope": mem.get("scope", "/"),
            "source_session": session_key,
            "source_turn": turn_id,
            "extracted_at": now,
            "valid_from": now,
            "metadata": metadata,
            "ttl_hours": ttl_hours,
        }
        
        validated.append(memory_obj)
    
    return validated


def extract_session_handoff(
    session_summary: str,
    agent_id: str = "default",
    session_key: Optional[str] = None,
) -> dict:
    """
    Extract a session handoff record at session end or compaction.
    
    Args:
        session_summary: Summary of what happened this session
        agent_id: Which agent
        session_key: Session identifier
    
    Returns:
        Structured handoff record
    """
    prompt = f"""Analyze this session summary and extract a structured handoff record for the next session.

SESSION SUMMARY:
{session_summary}

Return a JSON object with:
- "summary": 2-3 sentence summary of what happened
- "decisions_made": array of decisions that were made (each with "what" and "context")
- "open_threads": array of things that were in progress or need follow-up
- "active_projects": array of projects that were discussed (each with "name" and "status")

JSON:"""

    raw = _call_model(prompt)
    
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        
        handoff = json.loads(cleaned)
    except json.JSONDecodeError:
        handoff = {
            "summary": session_summary[:500],
            "decisions_made": [],
            "open_threads": [],
            "active_projects": [],
        }
    
    handoff["agent_id"] = agent_id
    handoff["session_key"] = session_key
    handoff["created_at"] = datetime.now(timezone.utc).isoformat()
    
    return handoff


# --- Testing ---

def test_extraction():
    """Test extraction with a sample conversation turn."""
    human = """I need you to explore what Nvidia just launched with NemoClaw to tell me how it's different 
    than what we have here and how / if they've addressed the memory issue."""
    
    agent = """NemoClaw is not a replacement for OpenClaw. It's an enterprise wrapper Nvidia announced at GTC. 
    It addresses security and sandboxing via OpenShell and Nemotron models. On the memory issue — they haven't 
    solved it. Zero mention of memory persistence, context window limits, or long-term continuity anywhere in 
    their coverage. The memory problem remains unsolved at the platform level."""
    
    print("Testing extraction...")
    print(f"Human message: {human[:100]}...")
    print(f"Agent message: {agent[:100]}...")
    print()
    
    memories = extract_memories(
        human_message=human,
        agent_message=agent,
        agent_id="thomas",
        session_key="test-session",
        turn_id="test-turn-001",
    )
    
    print(f"Extracted {len(memories)} memories:\n")
    for mem in memories:
        print(f"  [{mem['memory_type'].upper()}] (importance: {mem['importance']})")
        print(f"  L0: {mem['headline']}")
        print(f"  L1: {mem['context']}")
        print(f"  Entities: {mem['entities']}")
        print(f"  Scope: {mem['scope']}")
        print()
    
    return memories


if __name__ == "__main__":
    test_extraction()
