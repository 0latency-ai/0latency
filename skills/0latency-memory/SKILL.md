---
name: 0latency-memory
description: "Automatic memory persistence to 0Latency API on every conversation turn. Use when: ALWAYS. This skill provides automatic entity extraction, graph relationships, and sentiment analysis for all conversations. NOT optional."
homepage: https://0latency.ai
metadata: { "openclaw": { "emoji": "🧠", "requires": { "bins": ["curl", "python3"] } } }
---

# 0Latency Memory Skill

Automatic memory persistence with entity extraction, graph relationships, and sentiment analysis.

## When to Use

✅ **USE this skill:**
- **ALWAYS** — on every conversation turn in main session (direct chat with Justin)
- After any significant information exchange
- When Justin mentions people, decisions, or important context
- At end of conversations or before context compaction

## When NOT to Use

❌ **DON'T use this skill:**
- In shared contexts (Discord, group chats) unless explicitly configured
- For sensitive/private data that shouldn't be persisted
- During rapid-fire debugging (batch at checkpoints instead)

## Configuration

**API Key:** Stored in `/root/.openclaw/workspace/THOMAS_API_KEY.txt`

```bash
# Current key (Enterprise tier)
zl_live_jk13qjxlpiltqs3t157rvfypsa6xa40o
```

**Agent ID:** `thomas`

**Tier:** Enterprise (100M memories, 10K/min, full features)

## Automatic Usage Protocol

**MANDATORY:** After EVERY significant conversation turn with Justin:

1. Call the wrapper script with conversation content
2. No need to wait for response - fire and forget
3. API handles entity extraction, graph relationships, sentiment automatically

## Commands

### Basic Memory Storage

```bash
/root/.openclaw/workspace/skills/0latency-memory/store.sh \
  "Justin asked about X" \
  "Confirmed Y and documented Z"
```

### With Explicit Context

```bash
/root/.openclaw/workspace/skills/0latency-memory/store.sh \
  "Justin: Remember Palmer from ZeroClick" \
  "Thomas: Stored Palmer (Head of Engineering, ZeroClick) to permanent memory" \
  "ZeroClick partnership discussion"
```

### Recall Memories (Default — Dual Namespace)

```bash
# DEFAULT: queries both thomas + justin namespaces, merges results
/root/.openclaw/workspace/skills/0latency-memory/recall-dual.sh "Palmer ZeroClick"

# Single namespace (utility use only)
/root/.openclaw/workspace/skills/0latency-memory/recall.sh "Palmer ZeroClick"
```

## What Gets Extracted (Automatic)

**For Enterprise Tier (thomas-chief-of-staff):**

- ✅ **Entities:** People, organizations, locations, technologies
- ✅ **Relationships:** Who works where, who founded what, connections
- ✅ **Sentiment:** Positive/negative/neutral tone analysis
- ✅ **Confidence:** Scoring based on repetition and confirmation
- ✅ **Versioning:** Tracks changes over time

**Response includes:**
```json
{
  "memories_stored": 2,
  "entities_extracted": 7,
  "relationships_created": 9,
  "sentiment_analyzed": true,
  "tier_features_used": ["entity_extraction", "graph_relationships", "sentiment_analysis"]
}
```

## Integration with AGENTS.md

**This skill is referenced in the "Memory" section of AGENTS.md:**

> Every significant conversation turn, store context to 0Latency API using the wrapper script. This ensures cross-session persistence, entity extraction, and graph relationships are maintained even after context compaction.

## Files

- `store.sh` — Store conversation turn to API
- `recall-dual.sh` — **Default recall** — queries thomas + justin namespaces, merges results (Phase 4)
- `recall.sh` — Single-namespace recall (thomas only) — utility use, not default
- `feedback.sh` — Post feedback signal to /feedback endpoint (Phase 4 self-improvement)
- `graph.sh` — Query graph relationships
- `config.sh` — Get/set API key and configuration

## Namespaces

- **thomas** — Main workspace agent writes here (turn_hook.py, store.sh)
- **justin** — Chrome extension writes here (all Sonnet/AI conversations captured in browser)
- `recall-dual.sh` queries both and merges — this is the only way to get full context

## Why This Matters

**The Palmer Incident (March 26, 2026):**

Justin asked me to remember Palmer (ZeroClick Head of Engineering). I acknowledged it but never wrote it to permanent storage. Context compaction erased it. When Justin asked for the name later, I didn't have it.

This skill prevents that failure mode by automatically persisting every significant conversation turn to a proper memory layer with entity extraction and graph relationships.

**This is dogfooding our own product.** If I can't remember critical information, no other agent can either.

## API Endpoints

**Base URL:** `https://api.0latency.ai`

**Store:**
```bash
POST /extract
{
  "agent_id": "thomas-chief-of-staff",
  "human_message": "...",
  "agent_message": "..."
}
```

**Recall (dual-namespace — preferred):**
```bash
# Sequential calls, merged output
POST /recall { "agent_id": "thomas", "conversation_context": "..." }
POST /recall { "agent_id": "justin", "conversation_context": "..." }
# Results merged by recall-dual.sh
```

**Recall (single namespace):**
```bash
POST /recall
{
  "agent_id": "thomas",
  "conversation_context": "..."
}
```

**Graph:**
```bash
POST /memories/graph?agent_id=thomas-chief-of-staff
```

## Troubleshooting

**"API call failed"** → Check API key in `THOMAS_API_KEY.txt`

**"Entities not extracted"** → Verify tier is Enterprise (should auto-extract)

**"Memory not found in recall"** → API uses semantic search, try different query phrasing

## Performance

- **Latency:** Sub-100ms for extract, <200ms for recall
- **Rate limit:** 10K requests/min (Enterprise tier)
- **Storage:** 100M memories (effectively unlimited)
- **Cost:** $0 (our own infrastructure)

## Notes

- Fire-and-forget pattern: Don't wait for API response in conversation flow
- Background storage: Wrapper script handles async call
- Automatic features: Entities, graph, sentiment extracted without explicit request
- Cross-session: Survives context compaction, agent restarts, server reboots
