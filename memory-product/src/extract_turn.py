#!/usr/bin/env python3
"""
Real-time single-turn extraction — called by the OpenClaw hook on every message:sent.
Reads a queue file, extracts memories, stores them, and cleans up.
Also maintains a sliding window of recent turns per agent for multi-turn inference.
"""
import sys
import os
import json
import glob
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
os.environ["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "AIzaSyAvFCk21Sz4G3AbKm9USob55DqJnpJBVmI")

from extraction import extract_memories
from storage import store_memories, _db_execute

LOG_FILE = "/root/logs/memory_realtime.log"
WINDOW_DIR = "/root/.openclaw/hooks/memory-extract/windows"

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_recent_turns(agent_id, max_turns=4):
    """Load recent turns from the sliding window file for multi-turn inference."""
    os.makedirs(WINDOW_DIR, exist_ok=True)
    window_file = os.path.join(WINDOW_DIR, f"{agent_id}_window.json")
    if os.path.exists(window_file):
        try:
            with open(window_file) as f:
                turns = json.load(f)
            return turns[-max_turns:]
        except (json.JSONDecodeError, KeyError):
            return []
    return []


def save_to_window(agent_id, human_msg, agent_msg, max_window=10):
    """Append turn to the sliding window file."""
    os.makedirs(WINDOW_DIR, exist_ok=True)
    window_file = os.path.join(WINDOW_DIR, f"{agent_id}_window.json")
    turns = []
    if os.path.exists(window_file):
        try:
            with open(window_file) as f:
                turns = json.load(f)
        except (json.JSONDecodeError, KeyError):
            turns = []
    
    turns.append([human_msg[:1000], agent_msg[:1000]])
    # Keep only recent turns
    turns = turns[-max_window:]
    
    with open(window_file, "w") as f:
        json.dump(turns, f)


def main():
    if len(sys.argv) < 2:
        print("Usage: extract_turn.py <queue_file.json>")
        sys.exit(1)
    
    queue_file = sys.argv[1]
    
    if not os.path.exists(queue_file):
        log(f"Queue file not found: {queue_file}")
        sys.exit(1)
    
    with open(queue_file) as f:
        turn = json.load(f)
    
    agent_id = turn["agent_id"]
    human_msg = turn["human_message"]
    agent_msg = turn["agent_message"]
    session_key = turn.get("session_key", "unknown")
    turn_id = turn.get("turn_id", f"rt_{datetime.now(timezone.utc).timestamp()}")
    
    # Skip very short exchanges
    if len(human_msg) < 15 and len(agent_msg) < 30:
        os.remove(queue_file)
        return
    
    # Skip heartbeats/system
    if "HEARTBEAT" in human_msg or "NO_REPLY" in agent_msg or agent_msg.strip() == "HEARTBEAT_OK":
        os.remove(queue_file)
        return
    
    log(f"[{agent_id}] RT extraction: {human_msg[:60]}...")
    
    try:
        # Get existing headlines for dedup
        rows = _db_execute(f"""
            SELECT headline FROM memory_service.memories
            WHERE agent_id = '{agent_id}' AND superseded_at IS NULL
            ORDER BY created_at DESC LIMIT 20
        """)
        existing = "\n".join([r.split("|||")[0] if "|||" in r else r for r in rows]) if rows else ""
        
        # Load sliding window for multi-turn inference
        recent = load_recent_turns(agent_id)
        recent_tuples = [tuple(t) for t in recent] if recent else None
        
        memories = extract_memories(
            human_message=human_msg,
            agent_message=agent_msg,
            agent_id=agent_id,
            session_key=session_key,
            turn_id=turn_id,
            existing_context=existing,
            recent_turns=recent_tuples,
        )
        
        if memories:
            ids = store_memories(memories)
            log(f"  [{agent_id}] RT stored {len(ids)} memories")
        else:
            log(f"  [{agent_id}] RT no memories extracted")
        
        # Save to sliding window
        save_to_window(agent_id, human_msg, agent_msg)
        
    except Exception as e:
        log(f"  [{agent_id}] RT ERROR: {e}")
    
    # Clean up queue file
    try:
        os.remove(queue_file)
    except OSError:
        pass


if __name__ == "__main__":
    main()
