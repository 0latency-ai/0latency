"""
Session Processor — Watches an OpenClaw agent's session transcripts and auto-extracts memories.
Runs as a background daemon. Processes new conversation turns as they appear.

Also regenerates the recall context file (RECALL.md) for workspace injection.
"""

import json
import os
import sys
import time
import glob
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
# GOOGLE_API_KEY must be set in environment (systemd service or .env)

from extraction import extract_memories
from storage import store_memories, _db_execute
from recall import recall_fixed as recall
from negative_recall import update_topic_coverage
from handoff import detect_state_change, generate_handoff, save_handoff, get_latest_handoff

# --- Configuration ---
AGENTS = {
    "echo": {
        "session_dir": "/root/.openclaw/agents/memory-test/sessions",
        "workspace_dir": "/root/.openclaw/workspace-memory-test",
    },
    "thomas": {
        "session_dir": "/root/.openclaw/agents/main/sessions",
        "workspace_dir": "/root/.openclaw/workspace",
    },
}
STATE_FILE = "/root/.openclaw/workspace/memory-product/src/.processor_state.json"
LOG_FILE = "/root/logs/memory_processor.log"
POLL_INTERVAL = 3  # seconds between checks — near-real-time extraction
REGEN_INTERVAL = 300  # seconds between context regeneration (5 min)


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


def find_active_session(session_dir):
    """Find the most recently modified session file."""
    pattern = os.path.join(session_dir, "*.jsonl")
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


def process_new_turns(session_file, state, agent_id):
    """Extract memories from new conversation turns with multi-turn sliding window.
    Also triggers Layer 2 (conversation state handoff) on meaningful state shifts.
    """
    turns = parse_session_turns(session_file)
    session_key = os.path.basename(session_file).replace(".jsonl", "")
    
    # Per-agent state key
    agent_state_key = f"processed_turns_{agent_id}"
    if agent_state_key not in state:
        state[agent_state_key] = {}
    # Backward compat: migrate old "processed_turns" for echo
    if agent_id == "echo" and "processed_turns" in state and agent_state_key not in state:
        state[agent_state_key] = state["processed_turns"]
    
    new_count = 0
    handoff_needed = False
    
    for idx, (turn_id, human_msg, agent_msg) in enumerate(turns):
        # Skip already processed
        if turn_id in state[agent_state_key]:
            continue
        
        # Skip very short exchanges
        if len(human_msg) < 15 and len(agent_msg) < 30:
            state[agent_state_key][turn_id] = {"status": "skipped", "reason": "too_short"}
            continue
        
        # Skip system/heartbeat messages
        if "HEARTBEAT" in human_msg or "NO_REPLY" in agent_msg:
            state[agent_state_key][turn_id] = {"status": "skipped", "reason": "system"}
            continue
        
        log(f"[{agent_id}] Processing turn: {human_msg[:60]}...")
        
        # Build sliding window of recent turns (up to 4 prior)
        window_start = max(0, idx - 4)
        recent_turns = [(turns[i][1], turns[i][2]) for i in range(window_start, idx)]
        
        try:
            # Get existing headlines for dedup context
            rows = _db_execute(f"""
                SELECT headline FROM memory_service.memories
                WHERE agent_id = '{agent_id}' AND superseded_at IS NULL
                ORDER BY created_at DESC LIMIT 20
            """)
            existing = "\n".join([r.split("|||")[0] if "|||" in r else r for r in rows]) if rows else ""
            
            memories, raw_turn_id = extract_memories(
                human_message=human_msg,
                agent_message=agent_msg,
                agent_id=agent_id,
                session_key=session_key,
                turn_id=turn_id,
                existing_context=existing,
                recent_turns=recent_turns if recent_turns else None,
            )
            
            if memories:
                ids = store_memories(memories)
                log(f"  [{agent_id}] Stored {len(ids)} memories")
                # Update topic coverage for negative recall
                try:
                    update_topic_coverage(agent_id, memories)
                except Exception as e:
                    log(f"  [{agent_id}] Topic coverage update error (non-fatal): {e}")
                state[agent_state_key][turn_id] = {
                    "status": "processed",
                    "memories": len(ids),
                    "at": datetime.now(timezone.utc).isoformat()
                }
                new_count += len(ids)
            else:
                state[agent_state_key][turn_id] = {"status": "processed", "memories": 0}
            
            # Layer 2: Check if conversation state shifted
            try:
                change = detect_state_change(human_msg, agent_msg, recent_turns)
                if change.get("state_shifted", False):
                    handoff_needed = True
                    log(f"  [{agent_id}] State shift detected: {change.get('reason', 'unknown')}")
            except Exception as e:
                log(f"  [{agent_id}] State change detection error (non-fatal): {e}")
                
        except Exception as e:
            log(f"  [{agent_id}] ERROR: {e}")
            state[agent_state_key][turn_id] = {"status": "error", "error": str(e)}
    
    # Layer 2: Generate handoff if state shifted during this batch
    if handoff_needed and new_count > 0:
        try:
            # Get recent turns as (human, agent) tuples for handoff generation
            recent_for_handoff = [(h, a) for _, h, a in turns[-10:]]
            current_handoff = get_latest_handoff(agent_id)
            
            log(f"  [{agent_id}] Generating conversation state handoff...")
            handoff = generate_handoff(
                agent_id=agent_id,
                session_key=session_key,
                recent_turns=recent_for_handoff,
                current_handoff=current_handoff,
            )
            save_handoff(agent_id, session_key, handoff)
            log(f"  [{agent_id}] Handoff saved: {handoff.get('summary', '')[:100]}...")
        except Exception as e:
            log(f"  [{agent_id}] Handoff generation error (non-fatal): {e}")
    
    return new_count


def regenerate_context(agent_id, workspace_dir):
    """Generate the RECALL.md file for workspace injection."""
    
    # Build conversation context from recent turns for dynamic budget
    agent_cfg = AGENTS.get(agent_id, {})
    session_dir = agent_cfg.get("session_dir", "")
    recent_context = "General conversation startup. What does this agent need to know?"
    
    if session_dir:
        session_file = find_active_session(session_dir)
        if session_file:
            turns = parse_session_turns(session_file)
            if turns:
                # Use last 3 turns as context for recall
                recent = turns[-3:]
                parts = []
                for _, h, a in recent:
                    parts.append(f"Human: {h[:300]}\nAgent: {a[:300]}")
                recent_context = "\n\n".join(parts)
    
    # Run recall with dynamic budget
    try:
        result = recall(
            agent_id=agent_id,
            conversation_context=recent_context,
            budget_tokens=4000,
        )
        
        context_block = result["context_block"]
        memories_used = result["memories_used"]
        
        # Write to workspace
        context_file = os.path.join(workspace_dir, "RECALL.md")
        with open(context_file, "w") as f:
            f.write(f"# Recall Context (auto-generated by memory daemon)\n")
            f.write(f"_Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n")
            f.write(f"_{memories_used} memories loaded_\n\n")
            f.write(context_block)
        
        # Clean up old MEMORY_CONTEXT.md if it exists
        old_file = os.path.join(workspace_dir, "MEMORY_CONTEXT.md")
        if os.path.exists(old_file):
            os.remove(old_file)
        
        log(f"[{agent_id}] Regenerated RECALL.md ({memories_used} memories, {result['tokens_used']} tokens)")
        
    except Exception as e:
        log(f"[{agent_id}] ERROR regenerating context: {e}")


def run_daemon():
    """Run the session processor as a daemon."""
    log("=== Memory Session Processor Started ===")
    log(f"Agents: {list(AGENTS.keys())}")
    log(f"Poll interval: {POLL_INTERVAL}s")
    
    state = load_state()
    # Migrate legacy state
    if "processed_turns" in state and "processed_turns_echo" not in state:
        state["processed_turns_echo"] = state.pop("processed_turns")
        save_state(state)
    
    last_regen = {}
    
    while True:
        try:
            for agent_id, agent_cfg in AGENTS.items():
                session_file = find_active_session(agent_cfg["session_dir"])
                
                if session_file:
                    new_memories = process_new_turns(session_file, state, agent_id)
                    save_state(state)
                    
                    # Regenerate context if new memories were added OR every REGEN_INTERVAL
                    now = time.time()
                    agent_last = last_regen.get(agent_id, 0)
                    if new_memories > 0 or (now - agent_last) > REGEN_INTERVAL:
                        regenerate_context(agent_id, agent_cfg["workspace_dir"])
                        last_regen[agent_id] = now
            
        except Exception as e:
            log(f"ERROR in main loop: {e}")
        
        time.sleep(POLL_INTERVAL)


def run_once(target_agent=None):
    """Process once and exit (for cron/manual use). Optionally target a single agent."""
    log("=== Memory Session Processor (single run) ===")
    state = load_state()
    # Migrate legacy state
    if "processed_turns" in state and "processed_turns_echo" not in state:
        state["processed_turns_echo"] = state.pop("processed_turns")
    
    agents_to_process = {target_agent: AGENTS[target_agent]} if target_agent else AGENTS
    
    for agent_id, agent_cfg in agents_to_process.items():
        session_file = find_active_session(agent_cfg["session_dir"])
        if session_file:
            new_memories = process_new_turns(session_file, state, agent_id)
            save_state(state)
            log(f"[{agent_id}] Processed: {new_memories} new memories")
        else:
            log(f"[{agent_id}] No active session found")
        
        regenerate_context(agent_id, agent_cfg["workspace_dir"])
    
    log("Done")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        run_daemon()
    elif len(sys.argv) > 1 and sys.argv[1] == "once":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        run_once(target)
    else:
        print("Usage:")
        print("  python session_processor.py daemon     — Run as background daemon (all agents)")
        print("  python session_processor.py once        — Process once, all agents")
        print("  python session_processor.py once thomas — Process once, Thomas only")
