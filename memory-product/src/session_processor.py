"""
Session Processor — Watches an OpenClaw agent's session transcripts and auto-extracts memories.
Runs as a background daemon. Processes new conversation turns as they appear.

Also regenerates the recall context file (MEMORY_CONTEXT.md) for workspace injection.
"""

import json
import os
import sys
import time
import glob
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
os.environ["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "AIzaSyAvFCk21Sz4G3AbKm9USob55DqJnpJBVmI")

from extraction import extract_memories
from storage import store_memories, _db_execute
from recall import recall

# --- Configuration ---
AGENT_ID = "echo"
SESSION_DIR = "/root/.openclaw/agents/memory-test/sessions"
WORKSPACE_DIR = "/root/.openclaw/workspace-memory-test"
STATE_FILE = "/root/.openclaw/workspace/memory-product/src/.processor_state.json"
LOG_FILE = "/root/logs/memory_processor.log"
POLL_INTERVAL = 15  # seconds between checks


def log(msg):
    """Log with timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_state():
    """Load processor state (which turns we've already processed)."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"processed_turns": {}, "last_session": None}


def save_state(state):
    """Save processor state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def find_active_session():
    """Find the most recently modified session file."""
    pattern = os.path.join(SESSION_DIR, "*.jsonl")
    files = glob.glob(pattern)
    if not files:
        return None
    # Sort by modification time, most recent first
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def parse_session_turns(session_file):
    """Parse conversation turns from a session JSONL file.
    Returns list of (turn_id, human_message, agent_message) tuples.
    """
    turns = []
    messages = []
    
    with open(session_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            if entry.get("type") != "message":
                continue
            
            msg = entry.get("message", {})
            role = msg.get("role")
            msg_id = entry.get("id", "")
            
            if role == "user":
                # Extract text content
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    content = " ".join(text_parts)
                if isinstance(content, str) and content.strip():
                    messages.append({"role": "user", "text": content.strip(), "id": msg_id})
            
            elif role == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    content = " ".join(text_parts)
                elif isinstance(content, str):
                    pass
                else:
                    continue
                
                if isinstance(content, str) and content.strip():
                    messages.append({"role": "assistant", "text": content.strip(), "id": msg_id})
    
    # Pair user messages with following assistant responses
    i = 0
    while i < len(messages) - 1:
        if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
            turn_id = f"{messages[i]['id']}_{messages[i+1]['id']}"
            turns.append((turn_id, messages[i]["text"], messages[i + 1]["text"]))
            i += 2
        else:
            i += 1
    
    return turns


def process_new_turns(session_file, state):
    """Extract memories from new conversation turns."""
    turns = parse_session_turns(session_file)
    session_key = os.path.basename(session_file).replace(".jsonl", "")
    
    new_count = 0
    for turn_id, human_msg, agent_msg in turns:
        # Skip already processed
        if turn_id in state.get("processed_turns", {}):
            continue
        
        # Skip very short exchanges
        if len(human_msg) < 15 and len(agent_msg) < 30:
            state["processed_turns"][turn_id] = {"status": "skipped", "reason": "too_short"}
            continue
        
        # Skip system/heartbeat messages
        if "HEARTBEAT" in human_msg or "NO_REPLY" in agent_msg:
            state["processed_turns"][turn_id] = {"status": "skipped", "reason": "system"}
            continue
        
        log(f"Processing turn: {human_msg[:60]}...")
        
        try:
            # Get existing headlines for dedup context
            rows = _db_execute(f"""
                SELECT headline FROM memory_service.memories
                WHERE agent_id = '{AGENT_ID}' AND superseded_at IS NULL
                ORDER BY created_at DESC LIMIT 20
            """)
            existing = "\n".join([r.split("|||")[0] if "|||" in r else r for r in rows]) if rows else ""
            
            memories = extract_memories(
                human_message=human_msg,
                agent_message=agent_msg,
                agent_id=AGENT_ID,
                session_key=session_key,
                turn_id=turn_id,
                existing_context=existing,
            )
            
            if memories:
                ids = store_memories(memories)
                log(f"  Stored {len(ids)} memories")
                state["processed_turns"][turn_id] = {
                    "status": "processed",
                    "memories": len(ids),
                    "at": datetime.now(timezone.utc).isoformat()
                }
                new_count += len(ids)
            else:
                state["processed_turns"][turn_id] = {"status": "processed", "memories": 0}
                
        except Exception as e:
            log(f"  ERROR: {e}")
            state["processed_turns"][turn_id] = {"status": "error", "error": str(e)}
    
    return new_count


def regenerate_context():
    """Generate the MEMORY_CONTEXT.md file for workspace injection."""
    
    # Run recall with a general context
    try:
        result = recall(
            agent_id=AGENT_ID,
            conversation_context="General conversation startup. What does this agent need to know?",
            budget_tokens=3000,
        )
        
        context_block = result["context_block"]
        memories_used = result["memories_used"]
        
        # Write to workspace
        context_file = os.path.join(WORKSPACE_DIR, "MEMORY_CONTEXT.md")
        with open(context_file, "w") as f:
            f.write(f"# Memory Context (auto-generated)\n")
            f.write(f"_Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n")
            f.write(f"_{memories_used} memories loaded_\n\n")
            f.write(context_block)
        
        log(f"Regenerated MEMORY_CONTEXT.md ({memories_used} memories, {result['tokens_used']} tokens)")
        
    except Exception as e:
        log(f"ERROR regenerating context: {e}")


def run_daemon():
    """Run the session processor as a daemon."""
    log("=== Memory Session Processor Started ===")
    log(f"Agent: {AGENT_ID}")
    log(f"Session dir: {SESSION_DIR}")
    log(f"Workspace: {WORKSPACE_DIR}")
    log(f"Poll interval: {POLL_INTERVAL}s")
    
    state = load_state()
    last_regen = 0
    
    while True:
        try:
            session_file = find_active_session()
            
            if session_file:
                new_memories = process_new_turns(session_file, state)
                save_state(state)
                
                # Regenerate context if new memories were added OR every 5 minutes
                now = time.time()
                if new_memories > 0 or (now - last_regen) > 300:
                    regenerate_context()
                    last_regen = now
            
        except Exception as e:
            log(f"ERROR in main loop: {e}")
        
        time.sleep(POLL_INTERVAL)


def run_once():
    """Process once and exit (for cron/manual use)."""
    log("=== Memory Session Processor (single run) ===")
    state = load_state()
    
    session_file = find_active_session()
    if session_file:
        new_memories = process_new_turns(session_file, state)
        save_state(state)
        log(f"Processed: {new_memories} new memories")
    else:
        log("No active session found")
    
    regenerate_context()
    log("Done")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        run_daemon()
    elif len(sys.argv) > 1 and sys.argv[1] == "once":
        run_once()
    else:
        print("Usage:")
        print("  python session_processor.py daemon  — Run as background daemon")
        print("  python session_processor.py once    — Process once and exit")
