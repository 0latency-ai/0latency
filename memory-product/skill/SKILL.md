---
name: memory-engine
description: "Structured agent memory with zero-latency recall. Auto-extracts memories from every conversation turn, stores in Postgres with embeddings, and injects relevant context on session start. Survives compaction. Replaces flat markdown memory files. Use when: agent forgets things after compaction, needs persistent memory across sessions, or you want structured recall instead of raw notes."
metadata:
  {
    "openclaw":
      {
        "emoji": "🧠",
        "requires": { "bins": ["python3", "psql"] },
        "install":
          [
            {
              "id": "python-deps",
              "kind": "shell",
              "command": "pip3 install psycopg2-binary requests",
              "label": "Install Python dependencies",
            },
          ],
      },
  }
---

# Memory Engine

Structured agent memory with zero-latency recall after compaction.

## What It Does

Every conversation turn is automatically extracted into structured memories (facts, decisions, preferences, tasks, corrections, relationships, identities) stored in Postgres with vector embeddings. On session start, the most relevant memories are injected into your context — not everything, just what matters for the current conversation.

**The problem it solves:** After compaction, vanilla OpenClaw agents lose context. They forget decisions, mix up facts, and need to be re-taught. Memory Engine means your agent wakes up knowing what happened.

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

- **Postgres database** with pgvector extension (Supabase free tier works perfectly)
- **Gemini API key** (for extraction — uses Gemini Flash 2.0, ~$0.93/month at normal usage)
- **Python 3.10+** with `psycopg2-binary` and `requests`

## Quick Start

### 1. Set up Supabase (2 minutes)

1. Go to [supabase.com](https://supabase.com) and create a free project
2. Go to Settings → Database → Connection string → Session pooler
3. Copy the connection string

### 2. Configure

Add to your shell environment (`.bashrc` or `.zshrc`):

```bash
export MEMORY_DB_CONN="postgresql://postgres.[your-ref]:[your-password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
export GOOGLE_API_KEY="your-gemini-api-key"
```

### 3. Initialize the database

```bash
cd skills/memory-engine/scripts
python3 setup.py
```

This creates the `memory_service` schema with all required tables.

### 4. Start the daemon

```bash
# Run in background
nohup python3 scripts/session_processor.py daemon > /tmp/memory-engine.log 2>&1 &
```

The daemon watches your active session and extracts memories from every conversation turn automatically.

### 5. Verify it's working

```bash
python3 scripts/health.py
```

You should see memory counts, type distribution, and extraction stats.

## How Recall Works

On session start, the agent reads `memory/HANDOFF.md` (auto-generated) for instant orientation on where the last conversation left off. The `MEMORY_CONTEXT.md` file contains the most relevant memories for the current conversation, auto-regenerated every 5 minutes.

The recall system uses a composite score:
- **Semantic similarity** (40%) — how related is this memory to the current conversation?
- **Recency** (35%) — how recently was this memory created or accessed?
- **Importance** (15%) — how critical is this memory? (identity = highest, ephemeral = lowest)
- **Access frequency** (10%) — memories that are frequently recalled get boosted

## Commands

### Check memory health
```bash
python3 scripts/health.py [agent_id]
```

### Import historical conversations
```bash
python3 scripts/historical_import.py /path/to/export.json [agent_id]
```

### View latest handoff
```bash
python3 scripts/handoff.py get [agent_id]
```

### Run memory decay (usually on cron)
```bash
python3 scripts/decay.py [agent_id]
```

### Run compaction (cluster similar memories)
```bash
python3 scripts/compaction.py [agent_id]
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
MEMORY_CONTEXT.md + HANDOFF.md → injected into agent context
```

## Troubleshooting

**"No memories being extracted"**
- Check the daemon is running: `ps aux | grep session_processor`
- Check logs: `tail -50 /tmp/memory-engine.log`
- Verify GOOGLE_API_KEY is set and valid

**"Recall seems wrong"**
- Run `python3 scripts/health.py` to check memory stats
- High correction count (>25%) may indicate extraction prompt needs tuning
- Check `memory/HANDOFF.md` is being updated

**"Database connection fails"**
- Verify MEMORY_DB_CONN is set correctly
- Supabase session pooler (not direct) required if server lacks IPv6
- Run `psql $MEMORY_DB_CONN -c "SELECT 1"` to test

## License

MIT
