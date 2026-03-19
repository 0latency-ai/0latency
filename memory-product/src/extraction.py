"""
Extraction Layer — Agent Memory Service
Phase 1: Automatically extract structured memories from conversation turns.

This module processes raw conversation exchanges and outputs typed, tiered memory objects.
Uses Gemini Flash 2.0 by default (10x cheaper than Haiku, sufficient for structured extraction).
"""

import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional
import requests


# --- Configuration ---

EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "gemini-2.0-flash")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Extraction prompt — the core of Phase 1
EXTRACTION_PROMPT = """You are a memory extraction system. Your job is to analyze a conversation exchange between a human and an AI agent, and extract structured memories worth preserving.

Extract ONLY information that would be useful in future conversations. Skip:
- Routine pleasantries and filler
- Information that's only relevant to the immediate exchange
- Duplicates of things already in the existing memory context (provided below)

For each extracted memory, provide:
1. **headline**: One-line summary (10-20 tokens). Must be self-contained and meaningful.
2. **context**: The fact with enough context to be useful (50-100 tokens). Include WHY it matters.
3. **full_content**: Complete memory with all nuance, caveats, source info (200-500 tokens).
4. **memory_type**: MUST be one of these exact values. Choose carefully:
   - "preference": How the user wants things done. Communication style, behavior rules, tool usage norms, likes/dislikes. If the user says "don't do X" or "always do Y" or "I prefer Z" — this is a preference.
   - "decision": A choice that was made. If someone chose option A over option B, selected a vendor, approved a plan, picked a direction — this is a decision.
   - "fact": Objective information. Dates, numbers, states of affairs, technical details, business facts.
   - "task": Something that needs to be done. Action items, todos, follow-ups, deadlines.
   - "correction": A previously held belief/fact was wrong and is now updated. The old fact and new fact must both be stated.
   - "relationship": A connection between people, organizations, or concepts.
5. **importance**: 0.0-1.0. How important is this for future interactions?
   - 0.9-1.0: Critical (identity, non-negotiable rules, key business decisions, user preferences about agent behavior)
   - 0.7-0.8: Important (business decisions, project milestones, key contacts)
   - 0.4-0.6: Moderate (contextual facts, minor details)
   - 0.1-0.3: Low (passing mentions, temporary context)
6. **entities**: List of people, projects, organizations, or concepts mentioned
7. **project**: Which project/area this relates to (if any)
8. **categories**: 1-3 auto-inferred tags
9. **scope**: Hierarchical path like /project/subarea (e.g., /pfl-academy/oklahoma, /personal/preferences)

If a new fact CONTRADICTS or UPDATES a previously known fact, mark it as type "correction" and include both the old fact and the new fact in the full_content.

Respond with a JSON array of memory objects. If there's nothing worth extracting, return an empty array [].

EXISTING MEMORY CONTEXT (to avoid duplicates):
{existing_context}

CONVERSATION EXCHANGE:
Human: {human_message}
Agent: {agent_message}

Extract memories as JSON array:"""


def _call_gemini(prompt: str) -> str:
    """Call Gemini Flash 2.0 API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EXTRACTION_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": GOOGLE_API_KEY}
    
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,  # Low temp for structured extraction
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json"
        }
    }
    
    resp = requests.post(url, headers=headers, params=params, json=body, timeout=30)
    resp.raise_for_status()
    
    result = resp.json()
    text = result["candidates"][0]["content"]["parts"][0]["text"]
    return text


def _call_anthropic(prompt: str) -> str:
    """Call Anthropic (Haiku) as fallback."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    body = {
        "model": "claude-3-5-haiku-latest",
        "max_tokens": 4096,
        "temperature": 0.1,
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
    }
    
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    
    result = resp.json()
    return result["choices"][0]["message"]["content"]


def _call_model(prompt: str) -> str:
    """Call the configured extraction model with fallback chain."""
    model = EXTRACTION_MODEL.lower()
    
    if "gemini" in model and GOOGLE_API_KEY:
        try:
            return _call_gemini(prompt)
        except Exception as e:
            print(f"Gemini failed ({e}), trying fallback...")
    
    if ANTHROPIC_API_KEY:
        try:
            return _call_anthropic(prompt)
        except Exception as e:
            print(f"Anthropic failed ({e}), trying fallback...")
    
    if OPENAI_API_KEY:
        try:
            return _call_openai(prompt)
        except Exception as e:
            print(f"OpenAI failed ({e})")
    
    raise RuntimeError("No extraction model available. Set GOOGLE_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.")


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
) -> list[dict]:
    """
    Extract structured memories from a single conversation exchange.
    
    Args:
        human_message: The human's message
        agent_message: The agent's response
        agent_id: Which agent this is for
        session_key: Current session identifier
        turn_id: Specific turn/message ID
        existing_context: Recent memories to avoid duplicates (L0 headlines)
    
    Returns:
        List of structured memory objects ready for storage
    """
    # Skip extraction for very short exchanges (greetings, acks)
    if len(human_message) < 20 and len(agent_message) < 50:
        return []
    
    # Build the prompt
    prompt = EXTRACTION_PROMPT.format(
        existing_context=existing_context or "(no existing context)",
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
        valid_types = {"fact", "decision", "preference", "task", "correction", "relationship"}
        if memory_type not in valid_types:
            memory_type = "fact"
        
        # Build the structured memory object
        memory_obj = {
            "id": _generate_id(headline, now),
            "agent_id": agent_id,
            "headline": headline,
            "context": context,
            "full_content": full_content,
            "memory_type": memory_type,
            "importance": max(0.0, min(1.0, float(mem.get("importance", 0.5)))),
            "confidence": max(0.0, min(1.0, float(mem.get("confidence", 0.8)))),
            "entities": mem.get("entities", []),
            "project": mem.get("project"),
            "categories": mem.get("categories", []),
            "scope": mem.get("scope", "/"),
            "source_session": session_key,
            "source_turn": turn_id,
            "extracted_at": now,
            "valid_from": now,
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
