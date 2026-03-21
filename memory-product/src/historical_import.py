"""
Historical Import — Ingest past conversations from Claude, ChatGPT, Gemini
into the structured memory system.

Supports:
- ChatGPT: JSON export (conversations.json from Settings > Data controls > Export)
- Claude: JSON export (from claude.ai Settings > Export Data)
- Gemini: JSON export (from Google Takeout)
- Raw text/markdown transcripts

Key design decisions:
1. Extract ONLY from human messages (AI responses used as context, not as facts)
2. Historical imports get lower default importance (0.4 vs 0.6 for live)
3. All imports tagged with source platform and approximate date
4. Dedup against existing memories before storing
5. Batch processing with checkpoints
"""

import os
import sys
import json
import glob
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
# GOOGLE_API_KEY must be set in environment

from extraction import extract_memories
from storage import store_memories, _db_execute
from negative_recall import update_topic_coverage

LOG_FILE = "/root/logs/historical_import.log"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def parse_chatgpt_export(file_path: str) -> list[dict]:
    """
    Parse ChatGPT's conversations.json export.
    Returns list of conversation threads, each with turns.
    """
    with open(file_path) as f:
        data = json.load(f)
    
    threads = []
    for conv in data:
        title = conv.get("title", "Untitled")
        create_time = conv.get("create_time")
        
        turns = []
        mapping = conv.get("mapping", {})
        
        # Walk the conversation tree
        for node_id, node in mapping.items():
            msg = node.get("message")
            if not msg:
                continue
            
            role = msg.get("author", {}).get("role", "")
            content_parts = msg.get("content", {}).get("parts", [])
            content = " ".join(str(p) for p in content_parts if isinstance(p, str))
            
            if content.strip() and role in ("user", "assistant"):
                turns.append({
                    "role": role,
                    "content": content,
                    "timestamp": msg.get("create_time"),
                })
        
        if turns:
            threads.append({
                "title": title,
                "platform": "chatgpt",
                "created_at": create_time,
                "turns": sorted(turns, key=lambda t: t.get("timestamp") or 0),
            })
    
    return threads


def parse_claude_export(file_path: str) -> list[dict]:
    """
    Parse Claude's JSON export.
    Format varies — handles both conversation-level and message-level exports.
    """
    with open(file_path) as f:
        data = json.load(f)
    
    threads = []
    
    # Handle array of conversations
    conversations = data if isinstance(data, list) else [data]
    
    for conv in conversations:
        title = conv.get("name", conv.get("title", "Untitled"))
        
        turns = []
        messages = conv.get("chat_messages", conv.get("messages", []))
        
        for msg in messages:
            role = msg.get("sender", msg.get("role", ""))
            if role == "human":
                role = "user"
            
            # Handle different content formats
            content = ""
            if isinstance(msg.get("text"), str):
                content = msg["text"]
            elif isinstance(msg.get("content"), str):
                content = msg["content"]
            elif isinstance(msg.get("content"), list):
                content = " ".join(
                    p.get("text", "") for p in msg["content"] 
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            
            if content.strip() and role in ("user", "assistant"):
                turns.append({
                    "role": role,
                    "content": content,
                    "timestamp": msg.get("created_at", msg.get("timestamp")),
                })
        
        if turns:
            threads.append({
                "title": title,
                "platform": "claude",
                "created_at": conv.get("created_at"),
                "turns": turns,
            })
    
    return threads


def parse_gemini_export(file_path: str) -> list[dict]:
    """Parse Gemini export from Google Takeout."""
    with open(file_path) as f:
        data = json.load(f)
    
    threads = []
    conversations = data if isinstance(data, list) else [data]
    
    for conv in conversations:
        title = conv.get("title", "Untitled")
        turns = []
        
        for msg in conv.get("messages", conv.get("entries", [])):
            role = msg.get("role", msg.get("author", ""))
            if role in ("model", "assistant", "CHATBOT"):
                role = "assistant"
            elif role in ("user", "USER"):
                role = "user"
            else:
                continue
            
            content = msg.get("content", msg.get("text", ""))
            if isinstance(content, list):
                content = " ".join(str(p) for p in content)
            
            if content.strip():
                turns.append({
                    "role": role,
                    "content": content,
                    "timestamp": msg.get("createTime", msg.get("timestamp")),
                })
        
        if turns:
            threads.append({
                "title": title,
                "platform": "gemini",
                "created_at": conv.get("createTime"),
                "turns": turns,
            })
    
    return threads


def parse_markdown_transcript(file_path: str) -> list[dict]:
    """
    Parse a raw markdown/text transcript.
    Expects format like:
    Human: message
    Assistant: response
    """
    with open(file_path) as f:
        content = f.read()
    
    turns = []
    current_role = None
    current_content = []
    
    for line in content.split("\n"):
        if line.startswith(("Human:", "User:", "Me:", "Justin:")):
            if current_role and current_content:
                turns.append({"role": current_role, "content": "\n".join(current_content)})
            current_role = "user"
            current_content = [line.split(":", 1)[1].strip()]
        elif line.startswith(("Assistant:", "AI:", "Claude:", "ChatGPT:", "Gemini:", "Thomas:")):
            if current_role and current_content:
                turns.append({"role": current_role, "content": "\n".join(current_content)})
            current_role = "assistant"
            current_content = [line.split(":", 1)[1].strip()]
        elif current_role:
            current_content.append(line)
    
    if current_role and current_content:
        turns.append({"role": current_role, "content": "\n".join(current_content)})
    
    if turns:
        return [{"title": Path(file_path).stem, "platform": "transcript", "turns": turns}]
    return []


def import_threads(
    threads: list[dict],
    agent_id: str = "thomas",
    importance_discount: float = 0.7,  # Historical memories get 70% of normal importance
    max_threads: int = None,
    checkpoint_file: str = "/root/logs/import_checkpoint.json",
) -> dict:
    """
    Import conversation threads into the memory system.
    
    Args:
        threads: Parsed conversation threads
        agent_id: Target agent
        importance_discount: Multiply importance by this for historical imports
        max_threads: Limit number of threads to process
        checkpoint_file: Track progress for resume
    """
    # Load checkpoint
    checkpoint = {}
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file) as f:
            checkpoint = json.load(f)
    
    processed_titles = set(checkpoint.get("processed", []))
    total_memories = checkpoint.get("total_memories", 0)
    
    if max_threads:
        threads = threads[:max_threads]
    
    stats = {
        "threads_processed": 0,
        "threads_skipped": 0,
        "memories_extracted": 0,
        "turns_processed": 0,
    }
    
    for i, thread in enumerate(threads):
        title = thread.get("title", f"thread_{i}")
        platform = thread.get("platform", "unknown")
        
        # Skip already processed
        thread_key = f"{platform}:{title}"
        if thread_key in processed_titles:
            stats["threads_skipped"] += 1
            continue
        
        log(f"[{i+1}/{len(threads)}] Processing: {title} ({platform})")
        
        turns = thread.get("turns", [])
        
        # Process in pairs (human + assistant)
        for j in range(0, len(turns) - 1, 2):
            human_turn = turns[j] if turns[j]["role"] == "user" else None
            assistant_turn = turns[j + 1] if j + 1 < len(turns) and turns[j + 1]["role"] == "assistant" else None
            
            if not human_turn:
                # Try swapping
                if turns[j]["role"] == "assistant" and j + 1 < len(turns) and turns[j + 1]["role"] == "user":
                    human_turn = turns[j + 1]
                    assistant_turn = turns[j]
                else:
                    continue
            
            human_msg = human_turn["content"]
            agent_msg = assistant_turn["content"] if assistant_turn else "(no response)"
            
            # Skip very short exchanges
            if len(human_msg) < 20:
                continue
            
            # Build sliding window from previous turns
            window_start = max(0, j - 4)
            recent = [(turns[k]["content"], turns[k + 1]["content"]) 
                      for k in range(window_start, j, 2) 
                      if k + 1 < len(turns) and turns[k]["role"] == "user"]
            
            try:
                # Get existing headlines for dedup
                rows = _db_execute(f"""
                    SELECT headline FROM memory_service.memories
                    WHERE agent_id = '{agent_id}' AND superseded_at IS NULL
                    ORDER BY created_at DESC LIMIT 20
                """)
                existing = "\n".join([r.split("|||")[0] if "|||" in r else r for r in rows]) if rows else ""
                
                memories = extract_memories(
                    human_message=human_msg,
                    agent_message=agent_msg,
                    agent_id=agent_id,
                    session_key=f"import:{platform}:{title[:50]}",
                    turn_id=f"import_{platform}_{i}_{j}",
                    existing_context=existing,
                    recent_turns=recent if recent else None,
                )
                
                if memories:
                    # Apply importance discount for historical imports
                    for mem in memories:
                        mem["importance"] = round(mem["importance"] * importance_discount, 2)
                        mem["metadata"] = mem.get("metadata", {})
                        mem["metadata"]["import_source"] = platform
                        mem["metadata"]["import_thread"] = title[:100]
                    
                    ids = store_memories(memories)
                    stats["memories_extracted"] += len(ids)
                    total_memories += len(ids)
                    
                    # Update topic coverage
                    try:
                        update_topic_coverage(agent_id, memories)
                    except Exception:
                        pass
                
                stats["turns_processed"] += 1
                
            except Exception as e:
                log(f"  Error on turn {j}: {e}")
        
        stats["threads_processed"] += 1
        processed_titles.add(thread_key)
        
        # Checkpoint every 5 threads
        if stats["threads_processed"] % 5 == 0:
            with open(checkpoint_file, "w") as f:
                json.dump({
                    "processed": list(processed_titles),
                    "total_memories": total_memories,
                    "last_update": datetime.now(timezone.utc).isoformat(),
                }, f, indent=2)
            log(f"  Checkpoint: {stats['threads_processed']} threads, {total_memories} total memories")
    
    # Final checkpoint
    with open(checkpoint_file, "w") as f:
        json.dump({
            "processed": list(processed_titles),
            "total_memories": total_memories,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)
    
    log(f"Import complete: {json.dumps(stats)}")
    return stats


def auto_detect_and_parse(file_path: str) -> list[dict]:
    """Auto-detect file format and parse."""
    ext = Path(file_path).suffix.lower()
    
    if ext == ".json":
        with open(file_path) as f:
            data = json.load(f)
        
        # Try to detect format
        if isinstance(data, list) and data:
            sample = data[0]
            if "mapping" in sample:  # ChatGPT
                return parse_chatgpt_export(file_path)
            elif "chat_messages" in sample:  # Claude
                return parse_claude_export(file_path)
            elif "messages" in sample or "entries" in sample:  # Gemini or generic
                return parse_gemini_export(file_path)
        elif isinstance(data, dict):
            if "chat_messages" in data:
                return parse_claude_export(file_path)
    
    elif ext in (".md", ".txt"):
        return parse_markdown_transcript(file_path)
    
    log(f"Could not auto-detect format for {file_path}")
    return []


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "import":
        file_path = sys.argv[2]
        agent = sys.argv[3] if len(sys.argv) > 3 else "thomas"
        max_t = int(sys.argv[4]) if len(sys.argv) > 4 else None
        
        log(f"Importing from {file_path} for agent {agent}")
        threads = auto_detect_and_parse(file_path)
        log(f"Parsed {len(threads)} threads")
        
        if threads:
            stats = import_threads(threads, agent_id=agent, max_threads=max_t)
            print(json.dumps(stats, indent=2))
    
    elif len(sys.argv) > 2 and sys.argv[1] == "scan":
        # Scan a directory for importable files
        dir_path = sys.argv[2]
        files = glob.glob(os.path.join(dir_path, "**/*.json"), recursive=True)
        files += glob.glob(os.path.join(dir_path, "**/*.md"), recursive=True)
        print(f"Found {len(files)} importable files:")
        for f in files:
            size = os.path.getsize(f)
            print(f"  {f} ({size / 1024:.1f} KB)")
    
    else:
        print("Usage:")
        print("  python historical_import.py import <file.json> [agent] [max_threads]")
        print("  python historical_import.py scan <directory>")
        print()
        print("Supported formats:")
        print("  - ChatGPT: conversations.json (from Settings > Export)")
        print("  - Claude: export JSON (from Settings > Export Data)")
        print("  - Gemini: Google Takeout JSON")
        print("  - Raw transcripts: .md or .txt with Human:/Assistant: format")
