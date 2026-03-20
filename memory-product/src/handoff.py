"""
Session Handoff — Conversation State Tracker (Layer 2)

Maintains a rolling "state of the conversation" that captures:
- What we're actively discussing right now
- Decisions made this session
- Open threads (unresolved questions, pending actions)
- Active projects being worked on

Updates on CHANGE, not on a timer. After each extraction, evaluates whether
the conversation state has meaningfully shifted. If yes, regenerates the handoff.
If the turn was just acknowledgment/continuation, skips.

This is the Layer 2 that was missing from the original architecture.
Layer 1 (extraction) captures atoms. Layer 2 captures the narrative.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

import requests
from storage import _db_execute, DB_CONN as DB_URL

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyAvFCk21Sz4G3AbKm9USob55DqJnpJBVmI")

# --- Prompts ---

CHANGE_DETECTION_PROMPT = """Analyze this conversation turn and determine if the conversation STATE has meaningfully shifted.

A state shift means one or more of:
- A new topic or thread was introduced
- A decision was made (someone chose A over B, approved something, committed to a direction)
- An action item was created or resolved
- An open question was asked that changes what's being discussed
- A previous thread was closed or revisited
- The conversation pivoted to a different subject

NOT a state shift:
- Simple acknowledgment ("yes", "agreed", "ok", "got it")
- Continuation of the same topic without new information
- Clarifying questions that don't change the thread
- Emotional reactions without substance

Recent conversation context:
{recent_context}

Current turn:
Human: {human_message}
Agent: {agent_message}

Respond with ONLY a JSON object:
{{
  "state_shifted": true/false,
  "reason": "brief explanation of what shifted (or why it didn't)"
}}"""

HANDOFF_PROMPT = """You are generating a conversation state snapshot. This snapshot will be read by a future version of this agent after a context reset, so it needs to orient them INSTANTLY.

Recent conversation (last ~10 turns):
{recent_turns}

Current conversation state (if any):
{current_handoff}

Recent memories extracted this session:
{recent_memories}

Generate a structured conversation state snapshot. Be SPECIFIC and ACTIONABLE — vague summaries are useless.

Respond with ONLY a JSON object:
{{
  "summary": "2-3 sentence summary of what's actively being discussed RIGHT NOW. Not the whole session — just the current thread. Include enough context that a fresh agent can pick up mid-sentence.",
  "decisions_made": [
    {{
      "decision": "What was decided",
      "rationale": "Why (brief)",
      "who": "Who made the decision",
      "timestamp_approx": "When in the conversation (e.g., 'early session', 'just now')"
    }}
  ],
  "open_threads": [
    {{
      "thread": "What's still being discussed or unresolved",
      "context": "Enough context to pick it up",
      "waiting_on": "Who/what is needed to resolve this"
    }}
  ],
  "active_projects": [
    {{
      "project": "Project name",
      "status": "What's happening with it right now",
      "next_action": "What needs to happen next"
    }}
  ],
  "conversation_phase": "What phase is the conversation in? (e.g., 'brainstorming', 'decision-making', 'execution planning', 'debugging', 'reviewing')",
  "key_context": "Any critical context that would be lost without this snapshot (names, numbers, specific items being referenced)"
}}"""


def detect_state_change(human_message: str, agent_message: str, recent_turns: list) -> dict:
    """Determine if this turn represents a meaningful conversation state shift."""
    
    # Build recent context from last few turns
    recent_context = ""
    if recent_turns:
        parts = []
        for h, a in recent_turns[-3:]:
            parts.append(f"Human: {h[:300]}\nAgent: {a[:300]}")
        recent_context = "\n---\n".join(parts)
    
    prompt = CHANGE_DETECTION_PROMPT.format(
        recent_context=recent_context or "(start of conversation)",
        human_message=human_message[:1000],
        agent_message=agent_message[:1000],
    )
    
    try:
        result = _call_gemini(prompt)
        # Parse JSON from response
        data = _extract_json(result)
        return data
    except Exception as e:
        # On error, assume state shifted (better to over-update than under-update)
        return {"state_shifted": True, "reason": f"Error in detection: {e}"}


def generate_handoff(agent_id: str, session_key: str, recent_turns: list, 
                     current_handoff: Optional[dict] = None) -> dict:
    """Generate a new conversation state snapshot."""
    
    # Build recent turns text
    turns_text = ""
    if recent_turns:
        parts = []
        for h, a in recent_turns[-10:]:
            parts.append(f"Human: {h[:500]}\nAgent: {a[:500]}")
        turns_text = "\n---\n".join(parts)
    
    # Get recent memories from this session
    try:
        rows = _db_execute(f"""
            SELECT headline, memory_type, importance 
            FROM memory_service.memories 
            WHERE agent_id = '{agent_id}' 
            AND created_at > NOW() - INTERVAL '2 hours'
            ORDER BY created_at DESC 
            LIMIT 30
        """)
        memories_text = "\n".join(rows) if rows else "(no recent memories)"
    except:
        memories_text = "(unable to fetch)"
    
    current_text = json.dumps(current_handoff, indent=2) if current_handoff else "(no previous state)"
    
    prompt = HANDOFF_PROMPT.format(
        recent_turns=turns_text or "(no turns yet)",
        current_handoff=current_text,
        recent_memories=memories_text,
    )
    
    try:
        result = _call_gemini(prompt)
        data = _extract_json(result)
        return data
    except Exception as e:
        return {
            "summary": f"Error generating handoff: {e}",
            "decisions_made": [],
            "open_threads": [],
            "active_projects": [],
        }


def save_handoff(agent_id: str, session_key: str, handoff: dict):
    """Save/upsert the session handoff to Postgres AND write to filesystem for cold-start discovery."""
    import psycopg2
    
    # Write to filesystem so memory_search can find it on cold start
    _write_handoff_file(agent_id, handoff)
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    try:
        # Check if a handoff exists for this session
        cur.execute(
            "SELECT id FROM memory_service.session_handoffs WHERE agent_id = %s AND session_key = %s",
            (agent_id, session_key)
        )
        existing = cur.fetchone()
        
        summary = handoff.get("summary", "")
        decisions = json.dumps(handoff.get("decisions_made", []))
        open_threads = json.dumps(handoff.get("open_threads", []))
        active_projects = json.dumps(handoff.get("active_projects", []))
        
        if existing:
            # Update existing handoff
            cur.execute("""
                UPDATE memory_service.session_handoffs 
                SET summary = %s, decisions_made = %s, open_threads = %s, 
                    active_projects = %s, created_at = NOW()
                WHERE id = %s
            """, (summary, decisions, open_threads, active_projects, existing[0]))
        else:
            # Insert new handoff
            cur.execute("""
                INSERT INTO memory_service.session_handoffs 
                (id, agent_id, session_key, summary, decisions_made, open_threads, active_projects)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (str(uuid.uuid4()), agent_id, session_key, summary, decisions, open_threads, active_projects))
        
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _write_handoff_file(agent_id: str, handoff: dict):
    """Write handoff to a markdown file that memory_search can discover on cold start."""
    from datetime import datetime, timezone
    
    # Determine workspace dir based on agent
    workspace_dirs = {
        "thomas": "/root/.openclaw/workspace",
        "echo": "/root/.openclaw/workspace-memory-test",
    }
    workspace = workspace_dirs.get(agent_id, f"/root/.openclaw/workspace")
    memory_dir = os.path.join(workspace, "memory")
    os.makedirs(memory_dir, exist_ok=True)
    
    filepath = os.path.join(memory_dir, "HANDOFF.md")
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    lines = [
        f"# Session Handoff (auto-generated)",
        f"_Last updated: {now}_",
        f"",
        f"## Current State",
        f"{handoff.get('summary', 'No summary available.')}",
        f"",
        f"## Conversation Phase",
        f"{handoff.get('conversation_phase', 'Unknown')}",
        f"",
    ]
    
    decisions = handoff.get("decisions_made", [])
    if decisions:
        lines.append("## Decisions Made This Session")
        for d in decisions:
            if isinstance(d, dict):
                lines.append(f"- **{d.get('decision', '?')}** — {d.get('rationale', '')} ({d.get('who', 'unknown')}, {d.get('timestamp_approx', '')})")
            else:
                lines.append(f"- {d}")
        lines.append("")
    
    threads = handoff.get("open_threads", [])
    if threads:
        lines.append("## Open Threads")
        for t in threads:
            if isinstance(t, dict):
                lines.append(f"- **{t.get('thread', '?')}** — {t.get('context', '')} (waiting on: {t.get('waiting_on', '?')})")
            else:
                lines.append(f"- {t}")
        lines.append("")
    
    projects = handoff.get("active_projects", [])
    if projects:
        lines.append("## Active Projects")
        for p in projects:
            if isinstance(p, dict):
                lines.append(f"- **{p.get('project', '?')}**: {p.get('status', '')} → Next: {p.get('next_action', '?')}")
            else:
                lines.append(f"- {p}")
        lines.append("")
    
    key_context = handoff.get("key_context", "")
    if key_context:
        lines.append("## Key Context")
        lines.append(key_context)
        lines.append("")
    
    with open(filepath, "w") as f:
        f.write("\n".join(lines))


def get_latest_handoff(agent_id: str) -> Optional[dict]:
    """Retrieve the most recent handoff for an agent."""
    import psycopg2
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT summary, decisions_made, open_threads, active_projects, session_key, created_at
            FROM memory_service.session_handoffs 
            WHERE agent_id = %s 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (agent_id,))
        row = cur.fetchone()
        
        if row:
            return {
                "summary": row[0],
                "decisions_made": row[1] if isinstance(row[1], list) else json.loads(row[1]) if row[1] else [],
                "open_threads": row[2] if isinstance(row[2], list) else json.loads(row[2]) if row[2] else [],
                "active_projects": row[3] if isinstance(row[3], list) else json.loads(row[3]) if row[3] else [],
                "session_key": row[4],
                "created_at": str(row[5]),
            }
        return None
    finally:
        cur.close()
        conn.close()


def _call_gemini(prompt: str) -> str:
    """Call Gemini Flash for extraction."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2000,
        }
    }
    
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _extract_json(text: str) -> dict:
    """Extract JSON from a response that might contain markdown fences."""
    text = text.strip()
    
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    
    return json.loads(text)


# --- CLI ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python handoff.py get <agent_id>     — Get latest handoff")
        print("  python handoff.py test <agent_id>     — Generate handoff from recent conversation")
        sys.exit(1)
    
    cmd = sys.argv[1]
    agent_id = sys.argv[2] if len(sys.argv) > 2 else "thomas"
    
    if cmd == "get":
        handoff = get_latest_handoff(agent_id)
        if handoff:
            print(json.dumps(handoff, indent=2))
        else:
            print(f"No handoff found for {agent_id}")
    
    elif cmd == "test":
        # Load recent turns from active session
        from session_processor import find_active_session, parse_session_turns, AGENTS
        
        agent_cfg = AGENTS.get(agent_id, {})
        session_file = find_active_session(agent_cfg["session_dir"])
        if not session_file:
            print(f"No active session for {agent_id}")
            sys.exit(1)
        
        turns = parse_session_turns(session_file)
        session_key = os.path.basename(session_file).replace(".jsonl", "")
        
        # Get last 10 turns as (human, agent) tuples
        recent = [(h, a) for _, h, a in turns[-10:]]
        
        # Get current handoff
        current = get_latest_handoff(agent_id)
        
        print(f"Generating handoff from {len(recent)} recent turns...")
        handoff = generate_handoff(agent_id, session_key, recent, current)
        print(json.dumps(handoff, indent=2))
        
        save = input("\nSave to database? (y/n): ").strip().lower()
        if save == "y":
            save_handoff(agent_id, session_key, handoff)
            print("Saved!")
