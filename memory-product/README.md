<p align="center">
  <h1 align="center">0Latency</h1>
  <p align="center"><strong>Memory Layer for AI Agents</strong></p>
  <p align="center"><em>It just works. Zero latency. No configuration.</em></p>
</p>

<p align="center">
  <a href="https://github.com/0latency-ai/0latency/actions"><img src="https://img.shields.io/github/actions/workflow/status/0latency-ai/0latency/ci.yml?branch=main&label=tests&style=flat-square" alt="Tests"></a>
  <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License"></a>
  <a href="https://pypi.org/project/0latency/"><img src="https://img.shields.io/pypi/pyversions/0latency?style=flat-square" alt="Python"></a>
  <a href="https://www.npmjs.com/package/@0latency/sdk"><img src="https://img.shields.io/npm/v/@0latency/sdk?style=flat-square&label=npm" alt="npm"></a>
  <a href="https://discord.gg/0latency"><img src="https://img.shields.io/discord/000000000000000000?style=flat-square&label=discord" alt="Discord"></a>
</p>

---

## Philosophy

**We decide how memory works. You build your agent.**

0Latency is opinionated by design. There are no latency settings to tune, no performance knobs to configure, no scoring parameters to adjust. Sub-100ms recall, always, by default. Extraction is always async under the hood — your agent never waits. These aren't features you enable. They're how the system works.

Three rules:
1. **Recall is always sync, always fast.** Sub-100ms. Every time.
2. **Extraction accepts instantly, processes in background.** Your agent never blocks.
3. **Partial results beat blocking.** If extraction is still processing, recall returns what's ready.

## The Problem

AI agents forget everything between sessions. Context windows compress and discard. Sessions reset to zero. The "memory" solutions that exist today — vector databases for raw embeddings, flat files, chat log replay — solve the wrong problem. They store text. They don't understand what matters, what changed, or what your agent actually needs to know right now.

**Agents don't need a database. They need a memory.**

## What 0Latency Does

Everything below happens automatically. You don't configure any of it.

- **Automatic memory extraction** — Memories are extracted from conversations asynchronously. Your agent calls `.add()` and gets an instant acknowledgment. Processing happens in the background.
- **6 structured memory types** — Facts, preferences, decisions, corrections, tasks, and relationships. Not a blob of embeddings — typed, queryable, composable memory.
- **Temporal dynamics** — Memories aren't static. Reinforcement strengthens frequently-accessed memories. Time-based decay fades what's no longer relevant. Your agent's memory evolves like a human's.
- **Proactive recall with context budgets** — L0 (always loaded), L1 (session-relevant), L2 (on-demand). Context budgets are managed automatically so your agent gets the right memories without blowing its context window.
- **Graph memory via Postgres** — Relationship traversal through recursive CTEs. Entity graphs, connection paths, influence mapping — all in Postgres. No Neo4j. No extra infrastructure.
- **Negative recall** — Your agent knows what it *doesn't* know. "I have no memory of their dietary preferences" is more useful than silence.
- **Contradiction detection** — When new information conflicts with existing memory, 0Latency detects it, resolves it, and cascades corrections to dependent memories.
- **Session handoff** — Memories survive context compaction, session restarts, and agent swaps. The next session picks up where the last one left off.
- **Webhooks & batch ops** — Subscribe to memory events. Bulk import/export. Memory versioning with full history.

## Quick Start

### Install

```bash
pip install 0latency
```

### Use

```python
from zero_latency import Memory

mem = Memory("your-api-key")

# Store a memory — returns instantly, extracts in background
mem.add("User is allergic to shellfish and prefers window seats")

# Recall — sub-100ms, always
memories = mem.recall("Book a flight and dinner for the user")
# → [fact] User is allergic to shellfish
# → [preference] User prefers window seats
```

That's it. No configuration. No tuning. No schema. It just works.

## Architecture

```
Conversation → Extraction → Storage → Recall → Agent Context
                  │              │          │
            Gemini Flash    Postgres    Composite
              2.0          + pgvector    Scoring
                                            │
                                    ┌───────┴────────┐
                                    │  semantic sim   │
                                    │  recency decay  │
                                    │  importance wt  │
                                    │  access freq    │
                                    └────────────────┘
```

**Extraction** — Gemini Flash 2.0 identifies and classifies memories from raw conversation. Fast, cheap, accurate.

**Storage** — Postgres with pgvector. Memories are stored with embeddings, metadata, timestamps, type classifications, and relationship edges. One database. No graph DB tax.

**Recall** — Composite scoring blends semantic similarity, recency, importance weight, and access frequency. Context budget management ensures you only load what fits.

## How It's Different

| Feature | 0Latency | Mem0 | Zep | Letta |
|---|:---:|:---:|:---:|:---:|
| Structured memory types | ✅ 6 types | ❌ Flat | ⚠️ Limited | ⚠️ Limited |
| Temporal dynamics (decay + reinforcement) | ✅ | ❌ | ❌ | ❌ |
| Context budget management (L0/L1/L2) | ✅ | ❌ | ❌ | ❌ |
| Proactive recall | ✅ | ❌ | ⚠️ | ❌ |
| Graph memory | ✅ Postgres CTEs | ❌ | ❌ | ❌ |
| Negative recall | ✅ | ❌ | ❌ | ❌ |
| Contradiction detection | ✅ | ❌ | ⚠️ | ❌ |
| No extra infra (Neo4j, Redis, etc.) | ✅ Postgres only | ⚠️ | ⚠️ | ❌ |
| Session handoff / compaction survival | ✅ | ❌ | ⚠️ | ✅ |
| Self-hosted option | ✅ | ✅ | ✅ | ✅ |

## API Reference

Full documentation: [0latency.ai/docs](https://0latency.ai/docs)

| Endpoint | Method | Description |
|---|---|---|
| `/v1/extract` | `POST` | Extract memories from a conversation |
| `/v1/recall` | `POST` | Retrieve relevant memories for a query |
| `/v1/memories` | `GET` | List memories for an agent (filterable) |
| `/v1/memories/{id}` | `GET` | Get a specific memory with history |
| `/v1/memories/{id}` | `PATCH` | Update a memory manually |
| `/v1/memories/{id}` | `DELETE` | Delete a memory |
| `/v1/health` | `GET` | Service health check |

### Example: Extract

```bash
curl -X POST https://api.0latency.ai/v1/extract \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "messages": [
      {"role": "user", "content": "My birthday is March 15th"}
    ]
  }'
```

### Example: Recall

```bash
curl -X POST https://api.0latency.ai/v1/recall \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "query": "When is the users birthday?",
    "max_tokens": 500
  }'
```

## SDKs

### Python

```bash
pip install 0latency
```

```python
from zero_latency import Memory
mem = Memory("your-api-key")
```

### TypeScript / JavaScript

```bash
npm install @0latency/sdk
```

```typescript
import { Memory } from '@0latency/sdk';
const mem = new Memory('your-api-key');
```

## Pricing

| Plan | Price | Memories | Features |
|---|---|---|---|
| **Free** | $0/mo | 50 memories | 1 agent, core API, community support |
| **Pro** | $9/mo | 10,000 memories | Unlimited agents, webhooks, priority support |
| **API** | $19–49/mo | 100K–1M memories | Volume pricing, SLA, batch operations, dedicated support |

> **Pro tip:** The Pro plan is available as an [OpenClaw](https://openclaw.com) skill — plug memory into your agent in one line.

## Links

- 🌐 **Website:** [0latency.ai](https://0latency.ai)
- 📖 **Docs:** [0latency.ai/docs](https://0latency.ai/docs)
- 💬 **Discord:** [discord.gg/0latency](https://discord.gg/0latency)
- 🐦 **Twitter:** [@0latency_ai](https://twitter.com/0latency_ai)
- 🐙 **GitHub:** [github.com/0latency-ai](https://github.com/0latency-ai)

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built for agents that need to remember.</strong><br>
  <a href="https://0latency.ai">Get started →</a>
</p>
