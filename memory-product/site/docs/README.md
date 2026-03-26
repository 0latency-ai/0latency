# 0Latency Documentation

**Welcome to 0Latency** — the memory layer for AI agents.

Your agent stores memories from conversations, recalls relevant context in sub-100ms, and never forgets between sessions.

---

## 🚀 Getting Started

**New to 0Latency?** Start here:

1. **[Quick Start Guide](./quick-start.md)** — 5-minute setup walkthrough
   - Get your API key
   - Store your first memory
   - Recall context automatically
   - Understand memory types and scoring

---

## 📘 Examples & Guides

### Beginner
- **[Simple Chatbot](./examples/chatbot.md)** — Build a chatbot with memory (15 min)
  - Full working code (copy-paste ready)
  - Understand key concepts
  - Multi-user support
  - Python & JavaScript examples

### Intermediate
- **[Claude Code Integration](./examples/claude-code.md)** — Add memory to Claude via MCP (10 min)
  - Step-by-step setup with screenshots
  - Troubleshooting common issues
  - Privacy & security considerations

- **[Customer Support Agent](./examples/customer-support.md)** — Support tickets with context (20 min)
  - Remember customer history
  - Detect recurring issues
  - Integrations: Zendesk, Intercom, Slack
  - Production best practices

---

## 📖 Reference

- **[API Reference](./api-reference.md)** — Complete endpoint documentation
  - Authentication & rate limits
  - Memory operations (extract, recall, search)
  - Graph API (relationships)
  - Sentiment analysis
  - Usage & analytics
  - Error handling

---

## 🎯 Use Cases

### Personal Assistants
- Remember user preferences
- Track tasks and reminders
- Maintain conversation history

### Customer Support
- Recall previous tickets
- Detect recurring issues
- Personalize responses

### Sales & CRM
- Remember prospect context
- Track deal history
- Personalize outreach

### Education & Learning
- Track student progress
- Personalized tutoring
- Learning path optimization

### Healthcare
- Patient history
- Treatment preferences
- Medical context

---

## 🔑 Key Features

| Feature | Description |
|---------|-------------|
| **Structured Extraction** | 6 memory types: facts, preferences, decisions, corrections, tasks, relationships |
| **Sub-100ms Recall** | Median 12ms. Composite scoring: semantic + recency + importance + frequency |
| **Temporal Dynamics** | Memory decay and reinforcement. Stale info fades. Frequently accessed info strengthens |
| **Knowledge Graph** | Entity relationships via Postgres CTEs. Multi-hop traversal. No Neo4j required |
| **Self-Correcting** | When facts change, old memories get superseded with correction cascading |
| **Negative Recall** | Knows what it doesn't know. No hallucinated context |
| **Webhooks** | HMAC-signed event notifications with retry logic |
| **GDPR Compliant** | Full data export, memory deletion, audit trails |

---

## 💡 Core Concepts

### Memory Types

0Latency extracts 6 types of memories automatically:

- **fact** — Biographical info, statements of truth
- **preference** — Likes, dislikes, opinions
- **decision** — Choices made, commitments
- **relationship** — People, connections, social graph
- **task** — Action items, todos, reminders
- **correction** — Updates to previous memories, contradictions

### Memory Scoring

Recall uses composite scoring:

| Factor | Weight | Description |
|--------|--------|-------------|
| Semantic Similarity | 40% | Embedding match to current context |
| Recency | 35% | Exponential decay over time |
| Importance | 15% | Manually set or auto-determined |
| Access Frequency | 10% | How often this memory is used |

**Type bonuses:**
- Identity facts: ×1.5
- Preferences & corrections: ×1.3
- Recent decisions: ×1.2

### Token Budgets

Control how much context to include:

```python
# Tight budget for quick queries
context = mem.recall(agent_id="my_agent", 
                     conversation_context="What's my name?",
                     budget_tokens=500)

# Larger budget for detailed context
context = mem.recall(agent_id="my_agent",
                     conversation_context="Tell me about my life",
                     budget_tokens=8000)
```

0Latency **never exceeds** your budget. It packs the most relevant memories into available space.

---

## 🛠️ SDKs

### Python

```bash
pip install zerolatency
```

```python
from zerolatency import Memory

mem = Memory("zl_live_your_key")

# Store
mem.add(agent_id="my_agent",
        human_message="I live in Portland",
        agent_message="Portland is great!")

# Recall
context = mem.recall(agent_id="my_agent",
                     conversation_context="Recommend coffee shops")

print(context["context_block"])
```

### JavaScript/TypeScript

```bash
npm install @0latency/sdk
```

```javascript
import { Memory } from '@0latency/sdk';

const mem = new Memory('zl_live_your_key');

// Store
await mem.add({
  agentId: 'my_agent',
  humanMessage: 'I live in Portland',
  agentMessage: 'Portland is great!'
});

// Recall
const context = await mem.recall({
  agentId: 'my_agent',
  conversationContext: 'Recommend coffee shops'
});

console.log(context.contextBlock);
```

---

## 📊 Pricing

| Plan | Price | Memories | API Calls/Min |
|------|-------|----------|---------------|
| **Free** | $0 | 100 | 20 |
| **Pro** | $19/mo | 50,000 | 100 |
| **Scale** | $99/mo | Unlimited | 500 |

Free tier is generous enough to build real projects — no credit card needed.

[View pricing details →](https://0latency.ai/pricing)

---

## 🔒 Security & Privacy

- **Encryption:** All data encrypted at rest (AES-256) and in transit (TLS 1.3)
- **Isolation:** Tenant data is strictly isolated via API keys
- **Secret Detection:** Inbound content scanned for API keys/tokens — blocked before storage
- **GDPR Compliant:** Full data export, right to deletion, audit trails
- **Self-Hosting:** Run 0Latency on your own infrastructure

[Read security details →](https://0latency.ai/security)

---

## 🤝 Contributing

We're building 0Latency in the open, and we take care of contributors:

| Contribution | Reward |
|---|---|
| **Report a confirmed bug** | Lifetime Pro access ($19/mo value) |
| **Submit a PR that gets merged** | Lifetime Scale access ($99/mo value) |
| **Build something with 0Latency and share it** (blog, tutorial, OSS) | Lifetime Scale access ($99/mo value) |

→ [Report a bug](https://github.com/jghiglia2380/0Latency/issues/new?template=bug_report.md)  
→ [View open issues](https://github.com/jghiglia2380/0Latency/issues)  
→ [Read contribution guidelines](https://github.com/jghiglia2380/0Latency/blob/main/CONTRIBUTING.md)

---

## 🆘 Support

- 💬 **Discord:** [discord.gg/0latency](https://discord.gg/0latency)
- 📧 **Email:** support@0latency.ai
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/jghiglia2380/0Latency/issues)
- 🐦 **Twitter:** [@0latencyai](https://twitter.com/0latencyai)
- 📖 **Docs:** [0latency.ai/docs](https://0latency.ai/docs)

---

## 🔗 Links

- 🌐 **Website:** [0latency.ai](https://0latency.ai)
- 📦 **PyPI:** [pypi.org/project/zerolatency](https://pypi.org/project/zerolatency/)
- 📦 **npm:** [npmjs.com/package/@0latency/sdk](https://www.npmjs.com/package/@0latency/sdk)
- 🐙 **GitHub:** [github.com/jghiglia2380/0Latency](https://github.com/jghiglia2380/0Latency)
- 🎬 **API Docs:** [api.0latency.ai/docs](https://api.0latency.ai/docs)

---

## 📝 License

MIT — see [LICENSE](https://github.com/jghiglia2380/0Latency/blob/main/LICENSE)

---

<p align="center">
  <strong>Your agent remembers everything. Zero latency.</strong><br>
  <a href="https://0latency.ai">Get started →</a>
</p>

