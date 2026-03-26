# Quick Start Guide

Get your first AI agent with memory running in 5 minutes.

## What You'll Build

By the end of this guide, you'll have an AI agent that:
- Stores memories from conversations
- Recalls relevant context automatically
- Remembers everything between sessions

No prior experience with memory APIs needed. Let's go.

---

## Step 1: Get Your API Key (30 seconds)

Head to [0latency.ai/dashboard](https://0latency.ai/dashboard) and sign up. You'll get an API key instantly — no credit card required.

Your key looks like this: `zl_live_abc123...`

**💾 Save it somewhere safe.** You'll need it for the next steps.

---

## Step 2: Install the SDK (30 seconds)

### Python

```bash
pip install zerolatency
```

### JavaScript/TypeScript

```bash
npm install @0latency/sdk
```

---

## Step 3: Store Your First Memory (1 minute)

### Python

```python
from zerolatency import Memory

# Initialize with your API key
mem = Memory("zl_live_your_key_here")

# Store a conversation turn
result = mem.add(
    agent_id="my_first_agent",
    human_message="My name is Sarah and I live in Portland",
    agent_message="Nice to meet you, Sarah! Portland is beautiful."
)

print(f"✅ Stored {result['memories_stored']} memories")
# ✅ Stored 2 memories
```

**What just happened?**

0Latency automatically extracted structured memories:
- **Fact:** User's name is Sarah
- **Fact:** User lives in Portland

No manual tagging. No schemas. Just natural language → structured memory.

### JavaScript

```javascript
import { Memory } from '@0latency/sdk';

const mem = new Memory('zl_live_your_key_here');

const result = await mem.add({
  agentId: 'my_first_agent',
  humanMessage: 'My name is Sarah and I live in Portland',
  agentMessage: 'Nice to meet you, Sarah! Portland is beautiful.'
});

console.log(`✅ Stored ${result.memoriesStored} memories`);
// ✅ Stored 2 memories
```

---

## Step 4: Recall Context (1 minute)

Now let's recall relevant memories based on a new conversation context:

### Python

```python
# Later in a new conversation...
context = mem.recall(
    agent_id="my_first_agent",
    conversation_context="The user is asking about good coffee shops nearby"
)

print(context["context_block"])
```

**Output:**
```
### Relevant Context
- User's name: Sarah
- Location: Portland

[2 memories used, 85 tokens]
```

0Latency automatically:
1. Found the most relevant memories (location matters for coffee shop recommendations)
2. Ranked by semantic similarity + recency + importance
3. Formatted them for your agent's context

### JavaScript

```javascript
const context = await mem.recall({
  agentId: 'my_first_agent',
  conversationContext: 'The user is asking about good coffee shops nearby'
});

console.log(context.contextBlock);
```

---

## Step 5: Add More Memories (2 minutes)

Let's build up a richer memory profile:

```python
# Store preferences
mem.add(
    agent_id="my_first_agent",
    human_message="I'm allergic to dairy, so I always get oat milk",
    agent_message="Good to know! Oat milk lattes it is."
)

# Store a decision
mem.add(
    agent_id="my_first_agent",
    human_message="I've decided to work remotely on Fridays",
    agent_message="Great plan for work-life balance!"
)

# Store a relationship
mem.add(
    agent_id="my_first_agent",
    human_message="My sister Emma lives in Seattle and visits every month",
    agent_message="It's nice to have family nearby!"
)
```

Now recall with a richer context:

```python
context = mem.recall(
    agent_id="my_first_agent",
    conversation_context="User wants to grab coffee this Friday and her sister is visiting"
)

print(context["context_block"])
```

**Output:**
```
### Relevant Context
- Name: Sarah
- Location: Portland
- Dietary preference: Allergic to dairy, uses oat milk
- Work schedule: Works remotely on Fridays
- Relationship: Sister Emma lives in Seattle, visits monthly

[5 memories used, 178 tokens]
```

**See what happened?** 

All the relevant memories were recalled automatically:
- ☕ Dairy allergy (important for coffee recommendation)
- 📅 Friday remote work (context for timing)
- 👯 Sister visiting (social context)

---

## Understanding Memory Types

0Latency extracts 6 types of memories automatically:

| Type | Example | When It Matters |
|------|---------|-----------------|
| **fact** | "Lives in Portland" | Grounding, biographical info |
| **preference** | "Prefers oat milk" | Personalization, recommendations |
| **decision** | "Works remotely on Fridays" | Understanding choices, context |
| **relationship** | "Sister Emma in Seattle" | Social context, who's who |
| **task** | "Needs to buy concert tickets by Friday" | Action items, follow-ups |
| **correction** | "Actually moved to Seattle (was Portland)" | Self-correcting, keeping facts current |

You don't specify the type — 0Latency figures it out.

---

## Memory Scoring: How Recall Works

When you call `recall()`, memories are scored by:

1. **Semantic similarity** (40%) — How relevant to the current context?
2. **Recency** (35%) — Was this mentioned recently?
3. **Importance** (15%) — How significant is this memory?
4. **Access frequency** (10%) — Is this frequently recalled?

Memories also get **type bonuses**:
- Identity facts: ×1.5 (your name matters more than your coffee order)
- Preferences & corrections: ×1.3 (personalization is key)
- Recent decisions: ×1.2 (current choices matter)

The top-scoring memories fill your token budget. No more, no less.

---

## Token Budgets

By default, `recall()` uses a 4000-token budget. You can adjust:

```python
# Tight budget for quick context
context = mem.recall(
    agent_id="my_first_agent",
    conversation_context="Quick: what's the user's name?",
    budget_tokens=500
)

# Larger budget for detailed context
context = mem.recall(
    agent_id="my_first_agent",
    conversation_context="Detailed conversation about user's life",
    budget_tokens=8000
)
```

0Latency **never exceeds your budget**. It packs the most relevant memories into the available space.

---

## Self-Correcting Memory

What happens when facts change?

```python
# Original fact
mem.add(
    agent_id="my_first_agent",
    human_message="I live in Portland",
    agent_message="Portland is great!"
)

# Later... the user moves
mem.add(
    agent_id="my_first_agent",
    human_message="I just moved to Seattle last week",
    agent_message="Big change! How's Seattle treating you?"
)
```

0Latency detects the contradiction and automatically:
1. Creates a **correction** memory: "User moved to Seattle"
2. **Supersedes** the old "lives in Portland" memory
3. Keeps the old memory in version history (audit trail)

Next time you recall, you'll get "Lives in Seattle" — the current truth.

---

## Next Steps

You now know the basics! Here's where to go next:

### 📘 Guides & Examples
- [Build a Simple Chatbot](./examples/chatbot.md) — Full working example
- [Customer Support Agent](./examples/customer-support.md) — Real-world use case
- [Claude Code Integration](./examples/claude-code.md) — Add memory to Claude

### 📖 Reference
- [API Reference](./api-reference.md) — All endpoints, parameters, responses
- [Memory Types Deep Dive](./memory-types.md) — Understanding memory classification
- [Scoring & Ranking](./scoring.md) — How recall really works

### 🛠️ Advanced
- [Graph API](./graph-api.md) — Navigate relationships between memories
- [Webhooks](./webhooks.md) — React to memory events
- [Org Memory](./org-memory.md) — Share memory across team agents

---

## Need Help?

- 💬 [Discord Community](https://discord.gg/0latency)
- 📧 Email: support@0latency.ai
- 🐦 Twitter: [@0latencyai](https://twitter.com/0latencyai)
- 🐛 [Report a Bug](https://github.com/jghiglia2380/0Latency/issues)

---

**You're ready.** Go build something that remembers.

