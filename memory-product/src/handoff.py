"""
Session Handoff — Conversation State Tracker (Layer 2)

Maintains a rolling "state of the conversation" that captures:
- What we're actively discussing right now
- Decisions made this session
- Open threads (unresolved questions, pending actions)
- Active projects being worked on

SECURITY HARDENED: psycopg2 parameterized queries, no hardcoded credentials.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

import requests
import psycopg2

from config import get_google_api_key, get_db_conn
from db import execute, execute_one, get_conn

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

Recent conversation (last ~15 turns):
{recent_turns}

Current conversation state (IMPORTANT — accumulate, don't discard):
{current_handoff}

Recent memories extracted this session:
{recent_memories}

Generate a structured conversation state snapshot. Be SPECIFIC and ACTIONABLE — vague summaries are useless.

CRITICAL RULES:
- ACCUMULATE decisions from the current state. If the current state lists 3 decisions and the recent conversation adds 1 more, the output should have 4 decisions.
- Only REMOVE a decision if the conversation explicitly reversed it.
- Open threads should be updated: resolved threads removed, new threads added.
- The summary should reflect the CURRENT moment, but decisions/projects are cumulative for the session.

Respond with ONLY a JSON object:
{{
  "summary": "2-3 sentence summary of what's actively being discussed RIGHT NOW.",
  "decisions_made": [
    {{
      "decision": "What was decided",
      "rationale": "Why (brief)",
      "who": "Who made the decision",
      "timestamp_approx": "When in the conversation"
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
  "conversation_phase": "What phase is the conversation in?",
  "key_context": "Any critical context that would be lost without this snapshot"
}}"""


def _call_gemini(prompt: str) -> str:
    raise NotImplementedError("Gemini removed 2026-04-21; reintegrate with Anthropic/OpenAI when needed")


def _extract_json(text: str) -> dict:
    """Extract JSON from a response that might contain markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def detect_state_change(human_message: str, agent_message: str, recent_turns: list) -> dict:
    """Determine if this turn represents a meaningful conversation state shift."""
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
        return _extract_json(result)
    except Exception as e:
        return {"state_shifted": True, "reason": f"Error in detection: {e}"}


def generate_handoff(agent_id: str, session_key: str, recent_turns: list,
                     current_handoff: Optional[dict] = None) -> dict:
    """Generate a new conversation state snapshot."""
    turns_text = ""
    if recent_turns:
        parts = []
        for h, a in recent_turns[-15:]:
            parts.append(f"Human: {h[:500]}\nAgent: {a[:500]}")
        turns_text = "\n---\n".join(parts)

    # Get recent memories from this session
    try:
        rows = execute("""
            SELECT headline, memory_type, importance
            FROM memory_service.memories
            WHERE agent_id = %s
            AND created_at > NOW() - INTERVAL '2 hours'
            ORDER BY created_at DESC
            LIMIT 30
        """, (agent_id,))
        memories_text = "\n".join(
            f"{r['headline']} ({r['memory_type']}, {r['importance']})" for r in rows
        ) if rows else "(no recent memories)"
    except Exception:
        memories_text = "(unable to fetch)"

    current_text = json.dumps(current_handoff, indent=2) if current_handoff else "(no previous state)"

    prompt = HANDOFF_PROMPT.format(
        recent_turns=turns_text or "(no turns yet)",
        current_handoff=current_text,
        recent_memories=memories_text,
    )

    try:
        result = _call_gemini(prompt)
        return _extract_json(result)
    except Exception as e:
        return {
            "summary": f"Error generating handoff: {e}",
            "decisions_made": [],
            "open_threads": [],
            "active_projects": [],
        }


def save_handoff(agent_id: str, session_key: str, handoff: dict):
    """Save/upsert the session handoff to Postgres AND write to filesystem."""
    _write_handoff_file(agent_id, handoff)

    with get_conn() as conn:
        with conn.cursor() as cur:
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
                cur.execute("""
                    UPDATE memory_service.session_handoffs
                    SET summary = %s, decisions_made = %s, open_threads = %s,
                        active_projects = %s, created_at = NOW()
                    WHERE id = %s
                """, (summary, decisions, open_threads, active_projects, existing[0]))
            else:
                cur.execute("""
                    INSERT INTO memory_service.session_handoffs
                    (id, agent_id, session_key, summary, decisions_made, open_threads, active_projects)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (str(uuid.uuid4()), agent_id, session_key, summary, decisions, open_threads, active_projects))

            conn.commit()


def _write_handoff_file(agent_id: str, handoff: dict):
    """Write handoff to a markdown file that memory_search can discover on cold start."""
    workspace_dirs = {
        "thomas": "/root/.openclaw/workspace",
        "echo": "/root/.openclaw/workspace-memory-test",
    }
    workspace = workspace_dirs.get(agent_id, "/root/.openclaw/workspace")
    memory_dir = os.path.join(workspace, "memory")
    os.makedirs(memory_dir, exist_ok=True)

    filepath = os.path.join(memory_dir, "HANDOFF.md")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Session Handoff (auto-generated)",
        f"_Last updated: {now}_",
        "",
        "## Current State",
        f"{handoff.get('summary', 'No summary available.')}",
        "",
        "## Conversation Phase",
        f"{handoff.get('conversation_phase', 'Unknown')}",
        "",
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
    row = execute_one("""
        SELECT summary, decisions_made, open_threads, active_projects, session_key, created_at
        FROM memory_service.session_handoffs
        WHERE agent_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (agent_id,))

    if row:
        return {
            "summary": row["summary"],
            "decisions_made": row["decisions_made"] if isinstance(row["decisions_made"], list) else json.loads(row["decisions_made"]) if row["decisions_made"] else [],
            "open_threads": row["open_threads"] if isinstance(row["open_threads"], list) else json.loads(row["open_threads"]) if row["open_threads"] else [],
            "active_projects": row["active_projects"] if isinstance(row["active_projects"], list) else json.loads(row["active_projects"]) if row["active_projects"] else [],
            "session_key": row["session_key"],
            "created_at": str(row["created_at"]),
        }
    return None


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
        from session_processor import find_active_session, parse_session_turns, AGENTS

        agent_cfg = AGENTS.get(agent_id, {})
        session_file = find_active_session(agent_cfg["session_dir"])
        if not session_file:
            print(f"No active session for {agent_id}")
            sys.exit(1)

        turns = parse_session_turns(session_file)
        session_key = os.path.basename(session_file).replace(".jsonl", "")
        recent = [(h, a) for _, h, a in turns[-10:]]
        current = get_latest_handoff(agent_id)

        print(f"Generating handoff from {len(recent)} recent turns...")
        handoff = generate_handoff(agent_id, session_key, recent, current)
        print(json.dumps(handoff, indent=2))

        save = input("\nSave to database? (y/n): ").strip().lower()
        if save == "y":
            save_handoff(agent_id, session_key, handoff)
            print("Saved!")
