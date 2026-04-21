---
name: memory-engine
description: "Production-grade structured agent memory with zero-latency recall. Auto-extracts memories from conversations via secure multi-tenant API, stores with vector embeddings, and injects relevant context on session start. Survives compaction. Enterprise-ready with authentication, rate limiting, and tenant isolation."
metadata:
  {
    "openclaw":
      {
        "emoji": "🧠",
        "requires": { "bins": ["python3", "curl"] },
        "install":
          [
            {
              "id": "python-deps",
              "kind": "shell",
              "command": "pip3 install --break-system-packages requests urllib3",
              "label": "Install Python dependencies",
            },
            {
              "id": "workspace-setup",
              "kind": "shell", 
              "command": "mkdir -p memory && touch memory/RECALL.md memory/HANDOFF.md",
              "label": "Create memory workspace files",
            },
            {
              "id": "script-permissions",
              "kind": "shell",
              "command": "chmod +x scripts/*.py",
              "label": "Make scripts executable",
            },
          ],
      },
  }
---

# Memory Engine

Production-grade structured agent memory with zero-latency recall.

## What It Does

Every conversation turn is automatically extracted into structured memories (facts, decisions, preferences, tasks, corrections, relationships, identities) via a secure multi-tenant API. Memories are stored with vector embeddings for semantic search and recall. On session start, the most relevant memories are injected into your context — not everything, just what matters for the current conversation.

**The problem it solves:** After compaction, vanilla OpenClaw agents lose context. They forget decisions, mix up facts, and need to be re-taught. Memory Engine means your agent wakes up knowing what happened, with enterprise-grade security and tenant isolation.

## Features

- **Automatic extraction** — every turn, no agent intervention needed
- **Multi-turn inference** — catches information implied across messages
- **Typed memories** — facts, decisions, preferences, tasks, corrections, identities, relationships
- **Contradiction detection** — catches when new info conflicts with stored memories
- **Conversation state tracking** — rolling summary of active threads, decisions, open items
- **Dynamic context budget** — scales recall based on conversation complexity
- **Identity permanence** — names, roles, preferences never decay
- **Ephemeral memories** — time-limited memories with TTL (auto-expire)
- **Structured list preservation** — checklists and ordered plans stored as coherent units
- **Deduplication** — two-tier similarity check prevents redundant storage
- **Hybrid recall** — semantic similarity + keyword search for comprehensive retrieval
- **Negative recall** — knows what it doesn't know (topic coverage tracking)
- **Memory health dashboard** — stats on memory count, types, recall effectiveness
- **Historical import** — ingest conversations from Claude, ChatGPT, Gemini exports

## Requirements

- **Zero Latency Memory API key** (get from your administrator)
- **Python 3.10+** with `requests` library
- **Network access** to the Memory API endpoint

## Quick Start

### 1. Get Your API Key

Request an API key from your administrator. Keys follow the format:
```
zl_live_<32-character-string>
```

### 2. Configure

Add to your workspace environment or `.bashrc`:

```bash
export MEMORY_API_KEY="zl_live_your_api_key_here"
export MEMORY_API_URL="https://164.90.156.169"  # Default endpoint
```

### 3. Test connection

```bash
cd skills/memory-engine/scripts
python3 health.py
```

This verifies your API access and shows your tenant information.

### 4. Start the daemon

```bash
# Run in background
nohup python3 scripts/session_processor.py daemon > /tmp/memory-engine.log 2>&1 &
```

The daemon watches your active session and extracts memories from every conversation turn automatically, sending them to the Memory API for secure storage and processing.

### 5. Verify it's working

```bash
python3 scripts/health.py
```

You should see your tenant info, API usage stats, and memory counts.

## How Recall Works

On session start, the agent reads `memory/HANDOFF.md` (auto-generated) for instant orientation on where the last conversation left off. The `RECALL.md` file contains the most relevant memories for the current conversation, auto-regenerated on every conversation state change.

The recall system uses a composite score:
- **Semantic similarity** (40%) — how related is this memory to the current conversation?
- **Recency** (35%) — how recently was this memory created or accessed?
- **Importance** (15%) — how critical is this memory? (identity = highest, ephemeral = lowest)
- **Access frequency** (10%) — memories that are frequently recalled get boosted

## Commands

### Check tenant info and memory health
```bash
python3 scripts/health.py [agent_id]
```

### List memories for an agent
```bash
python3 scripts/list_memories.py [agent_id] [--type preference] [--limit 20]
```

### Import historical conversations
```bash
python3 scripts/historical_import.py /path/to/export.json [agent_id]
```

### View latest handoff
```bash
python3 scripts/handoff.py get [agent_id]
```

### Test API connection
```bash
python3 scripts/test_api.py
```

## Architecture

```
Conversation Turn
       ↓
[Extraction Layer] — Gemini Flash 2.0 extracts structured memories
       ↓
[Storage Layer] — Postgres + pgvector, dedup check, contradiction detection
       ↓
[Handoff Layer] — Rolling conversation state snapshot (updates on state change)
       ↓
[Recall Layer] — Composite scoring, dynamic budget, hybrid search
       ↓
RECALL.md + HANDOFF.md → injected into agent context
```

## Troubleshooting

**"No memories being extracted"**
- Check the daemon is running: `ps aux | grep session_processor`
- Check logs: `tail -50 /tmp/memory-engine.log`
- Verify MEMORY_API_KEY is set and valid
- Test API connection: `python3 scripts/test_api.py`

**"API authentication fails"**
- Verify API key format: must be `zl_live_` + 32 characters
- Check key is active: `python3 scripts/health.py`
- Contact administrator if account is suspended

**"Rate limit exceeded"**
- Check your plan limits: `python3 scripts/health.py`
- Upgrade to Pro/Enterprise for higher limits
- Implement backoff in high-frequency usage

**"Recall seems wrong"**
- Run `python3 scripts/health.py` to check memory stats
- High correction count (>25%) may indicate extraction needs tuning
- Check `memory/HANDOFF.md` is being updated

## Multi-Tenant Security

All memories are isolated by tenant. Each tenant gets their own secure namespace with:
- **API key authentication** — SHA-256 hashed keys
- **Row-level security** — Database enforces tenant isolation
- **Rate limiting** — Per-tenant request limits
- **Usage tracking** — Monitor API calls and token usage

## Cross-Agent Memory Sharing

Within a tenant, corrections automatically propagate to all agents. When one agent learns "$20/student, not $16", the stale "$16" fact gets superseded for all agents in the same tenant. No manual intervention needed.

## Cognitive Load Firewall (Coming Soon)

When your agent receives a flood of data (30 screenshots, bulk file drops), the daemon buffers and summarizes the content without saturating the agent's context window. The agent stays responsive while data is processed in the background.

## License

MIT
