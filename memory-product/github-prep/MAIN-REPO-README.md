# 0Latency

**Persistent memory infrastructure for AI agents.**

Sub-100ms recall. Graph relationships. Sentiment analysis. Confidence scoring. Works everywhere.

[![npm](https://img.shields.io/npm/v/@0latency/mcp-server)](https://npmjs.com/package/@0latency/mcp-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

Every AI session starts from zero.

You give context. Agent builds something great. Session ends.

Next time: **"I don't have access to that information."**

You're re-explaining the same codebase, the same preferences, the same bugs you've already hit.

## The Solution

**0Latency gives agents actual memory.**

Not just a vector database. Not just RAG. **Cognitive memory** that understands:
- What matters more (temporal decay, confidence scoring)
- What didn't work (negative recall)
- How concepts relate (graph relationships)
- Emotional context (sentiment analysis)

And it's **portable** — works with Claude, GPT, Cursor, any agent framework.

## Quick Start

### Claude Desktop / Claude Code (MCP)

```bash
npx @0latency/mcp-server@latest
```

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server@latest"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your_key_here"
      }
    }
  }
}
```

[Get your API key](https://0latency.ai/dashboard) • [MCP Server Docs](https://github.com/0latency-ai/mcp-server)

### REST API (Any Framework)

```bash
# Store a memory
curl -X POST https://api.0latency.ai/extract \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "human_message": "I prefer React over Vue",
    "agent_message": "Got it, storing that preference"
  }'

# Recall memories
curl "https://api.0latency.ai/memories?agent_id=my-agent&limit=10" \
  -H "X-API-Key: YOUR_KEY"
```

[Full API Documentation](https://0latency.ai/docs)

## Features

### Core Memory

- ✅ **Sub-100ms recall** — Fast enough for real-time conversations
- ✅ **Temporal decay** — Recent context weighs more than old
- ✅ **Negative recall** — Remembers failures, not just successes
- ✅ **Contradiction detection** — Updates stale facts instead of accumulating conflicts

### Advanced (Pro/Scale tiers)

- ✅ **Graph relationships** — Maps entities and semantic connections
- ✅ **Sentiment analysis** — Understands emotional context
- ✅ **Confidence scoring** — Tracks validated vs inferred memories
- ✅ **Entity extraction** — Identifies people, organizations, concepts, technologies
- ✅ **Memory versioning** — Full history of how memories evolve

### Cross-Platform

- ✅ Claude Desktop
- ✅ Claude Code
- ✅ GPT (via API)
- ✅ Cursor (via API)
- ✅ LangChain
- ✅ CrewAI
- ✅ AutoGen
- ✅ Any MCP client
- ✅ Any custom agent framework

**Your memory follows you. Not locked to one platform.**

## How It Works

```
┌─────────────┐
│   Agent     │
│ (Claude,    │
│  GPT, etc)  │
└──────┬──────┘
       │
       │ Conversation turn
       │
       ▼
┌─────────────────────┐
│  0Latency Extract   │  ◄── LLM-powered extraction
│  • Facts            │
│  • Preferences      │
│  • Events           │
│  • Relationships    │
└──────┬──────────────┘
       │
       │ Store (embedded + indexed)
       │
       ▼
┌─────────────────────┐
│   PostgreSQL +      │
│     pgvector        │  ◄── Sub-100ms semantic search
│  • Memories         │
│  • Embeddings       │
│  • Graph edges      │
│  • Entities         │
└──────┬──────────────┘
       │
       │ Recall (relevance-ranked)
       │
       ▼
┌─────────────┐
│  Agent uses │
│  memories   │  ◄── Proactive context injection
│  in next    │
│  response   │
└─────────────┘
```

**Key difference:** We extract structured memories from conversations, not just embed raw text. The agent learns *what matters*, not just *what was said*.

## Use Cases

### Software Development
- Remember architecture decisions
- Recall bugs you've hit before
- Track code patterns you prefer
- Learn your style over time

### Personal Assistants
- Remember user preferences
- Track important dates and events
- Build understanding of relationships
- Learn communication style

### Customer Support
- Remember customer history
- Track resolved vs ongoing issues
- Learn product knowledge
- Build institutional knowledge

### Research & Analysis
- Track findings and insights
- Connect related concepts
- Remember contradictory information
- Build knowledge graphs

## Pricing

| Tier | Memories | Price | Features |
|------|----------|-------|----------|
| **Free** | 10,000 | $0 | Core memory, unlimited API calls |
| **Pro** | 100,000 | $19/mo | Everything in Free |
| **Scale** | 1,000,000 | $89/mo | Graph, sentiment, confidence, entities |
| **Enterprise** | Unlimited | Custom | SSO, audit logs, custom deployment |

**64% cheaper than Mem0** for equivalent graph features ($89 vs $249/mo)

[View Full Pricing](https://0latency.ai/pricing)

## Architecture

**Backend:**
- PostgreSQL + pgvector (semantic search)
- FastAPI (Python)
- LLM-powered extraction (multi-model support)
- OpenAI embeddings (text-embedding-3-small)

**Infrastructure:**
- DigitalOcean (primary)
- Supabase (database)
- Cloudflare (CDN + edge)

**Integrations:**
- MCP server (TypeScript)
- Python SDK
- TypeScript SDK
- REST API

## Repository Structure

- **[mcp-server](https://github.com/0latency-ai/mcp-server)** — Model Context Protocol server
- **[python-sdk](https://github.com/0latency-ai/python-sdk)** — Python client library
- **[typescript-sdk](https://github.com/0latency-ai/typescript-sdk)** — TypeScript/JavaScript client
- **examples/** — Integration examples (LangChain, CrewAI, AutoGen, etc.)
- **docs/** — Additional documentation

## Documentation

- **[Getting Started Guide](https://0latency.ai/docs)**
- **[API Reference](https://api.0latency.ai/docs)**
- **[MCP Integration](https://github.com/0latency-ai/mcp-server)**
- **[Python SDK Docs](https://github.com/0latency-ai/python-sdk)**
- **[Integration Examples](examples/)**

## Examples

### LangChain

```python
from langchain_0latency import ZeroLatencyMemory

memory = ZeroLatencyMemory(
    api_key="your_key",
    agent_id="langchain-agent"
)

# Memory is automatically used in your chain
chain = ConversationChain(
    llm=llm,
    memory=memory
)
```

[Full LangChain example](examples/langchain/)

### CrewAI

```python
from crewai import Agent
from zero_latency import ZeroLatencyClient

memory_client = ZeroLatencyClient(api_key="your_key")

agent = Agent(
    role="Research Assistant",
    goal="Help with research tasks",
    memory=memory_client,
    agent_id="research-assistant"
)
```

[Full CrewAI example](examples/crewai/)

### Custom Agent

```python
from zero_latency import ZeroLatencyClient

client = ZeroLatencyClient(api_key="your_key")

# Store a memory
client.extract(
    agent_id="my-agent",
    human_message="I prefer tabs over spaces",
    agent_message="Noted, I'll remember that"
)

# Recall relevant memories
memories = client.recall(
    agent_id="my-agent",
    query="code formatting preferences",
    limit=10
)
```

[Full custom example](examples/custom-agent/)

## Contributing

We welcome contributions! Here's how you can help:

### Report Bugs
[Open an issue](https://github.com/0latency-ai/0latency/issues) with:
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python/Node version, etc.)

### Request Features
[Open a discussion](https://github.com/0latency-ai/0latency/discussions) with:
- Use case description
- Why existing features don't solve it
- Proposed API/interface

### Submit Code
1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Contributor Rewards

**Build something cool with 0Latency?**

Get **lifetime free access to Scale tier** ($89/mo value) for:
- Open-source projects using 0Latency
- Integration libraries for other frameworks
- Tutorial content / blog posts
- Useful bug reports + fixes

Email [hello@0latency.ai](mailto:hello@0latency.ai) with your contribution.

## Community

- **Discord:** [Join the community](https://discord.gg/0latency) (coming soon)
- **Twitter/X:** [@0latencyai](https://twitter.com/0latencyai)
- **Email:** [hello@0latency.ai](mailto:hello@0latency.ai)

## FAQ

**Q: How is this different from vector databases?**
A: We extract structured memories from conversations, not just embed raw text. Temporal decay, negative recall, graph relationships, and sentiment analysis make this cognitive memory, not just search.

**Q: Can I self-host?**
A: Enterprise tier includes custom deployment. Contact [hello@0latency.ai](mailto:hello@0latency.ai) for details.

**Q: Does this work with fine-tuned models?**
A: Yes. The API is model-agnostic. Works with any LLM that can call tools/functions.

**Q: What about privacy?**
A: Your memories are isolated by API key + agent_id. We don't train on your data. Enterprise tier includes SOC 2 compliance. [Privacy Policy](https://0latency.ai/privacy)

**Q: Can I delete memories?**
A: Yes. Full GDPR compliance. Delete individual memories, entire agents, or your whole account instantly.

**Q: How fast is recall?**
A: Sub-100ms p95. Typical response: 20-50ms for 10K memories, 40-80ms for 1M memories.

## Roadmap

**Shipped:**
- ✅ Core memory (store, recall, search)
- ✅ Temporal decay
- ✅ Negative recall
- ✅ Contradiction detection
- ✅ Graph relationships
- ✅ Sentiment analysis
- ✅ Confidence scoring
- ✅ Entity extraction
- ✅ Memory versioning
- ✅ MCP server
- ✅ REST API
- ✅ Python SDK
- ✅ TypeScript SDK

**Q2 2026:**
- 🚧 Auto-consolidation (merge duplicates)
- 🚧 Advanced graph queries (Cypher-style)
- 🚧 Memory analytics dashboard
- 🚧 Team collaboration features
- 🚧 Webhook notifications

**Q3 2026:**
- 📋 Multi-agent memory sharing
- 📋 Fine-tuned memory extraction models
- 📋 Real-time memory streaming
- 📋 Advanced access controls (RBAC)

[Full roadmap](https://github.com/0latency-ai/0latency/projects/1)

## License

MIT — see [LICENSE](LICENSE)

## Built By

**Justin Ghiglia** — [GitHub](https://github.com/jghiglia2380) • [Twitter](https://twitter.com/jghiglia)

Built in public. Powered by agents. Designed for the agent era.

---

**The brain layer isn't Notion. It's infrastructure.**

[Get Started](https://0latency.ai) • [Docs](https://0latency.ai/docs) • [API](https://api.0latency.ai/docs)
