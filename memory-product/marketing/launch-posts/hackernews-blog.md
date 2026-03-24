# Building 0Latency: A Biologically-Inspired Memory Layer for AI Agents

*How we got sub-100ms recall, why temporal decay matters more than vector similarity, and what happened when we built an entire startup on 624 memories.*

---

## The Problem Everyone Is Duct-Taping Around

If you've built anything serious with LLM agents, you've hit the memory wall. Not the context window limit — that's a known quantity you can engineer around. I mean the deeper problem: **agents have no persistent memory**.

Every session starts from zero. Your agent doesn't know what it decided yesterday, what architecture choices led to the current codebase, or why you chose Postgres over DynamoDB three weeks ago. The context window is working memory — the equivalent of what you can hold in your head right now. But there's no long-term memory. No hippocampus.

The workarounds are familiar:

- **Context files:** Manually maintained docs you paste into every session. Works until they're 5,000 words and half-stale.
- **RAG pipelines:** Retrieve chunks from a vector store. Better, but retrieval quality is inconsistent, and there's no concept of memory aging or relevance decay.
- **Conversation summaries:** Compress past conversations into summaries. Lossy by design — summaries discard the details that turn out to matter later.

I was using all three. I run an EdTech company (PFL Academy) with deployments across 36 US states, and I was building AI agents to help manage the complexity. Every morning, I'd paste the same 2,000-word context document into Claude, watch 30% of my context window disappear before I'd asked a single question, and start re-explaining decisions I'd already made.

That's when I started building 0Latency.

## Why Biological Memory Is the Right Model

Human memory doesn't work like a database. You don't `SELECT * FROM memories WHERE topic = 'work'`. Instead:

- **Memories decay over time** unless reinforced. What you had for lunch last Tuesday is probably gone. The architecture decision that's guided six months of development is crystal clear.
- **Frequently accessed memories strengthen.** The more you recall something, the more durable it becomes. This is Hebbian learning — "neurons that fire together wire together."
- **You can remember that something is false.** "We do NOT use MongoDB anymore" is a memory. It actively prevents you from acting on outdated information. This is negative recall.
- **Context triggers recall.** You don't search your memory — relevant memories surface when the right context appears. Walking into your kitchen triggers cooking-related memories without conscious effort.

Every existing agent memory system I looked at ignored these properties. They're vector databases with a timestamp column. Store everything, retrieve by similarity, hope for the best.

0Latency is built around these biological principles from the ground up.

## Architecture Decisions

### Temporal Decay

Every memory in 0Latency has a **salience score** that decays over time. The decay function isn't linear — it follows a power curve inspired by Ebbinghaus's forgetting curve. A memory created yesterday has high salience. A memory from two weeks ago that hasn't been accessed is significantly faded. A memory from two months ago that you recall weekly is stronger than ever.

This means your agent's memory is self-curating. You don't need to manually prune stale context. The system does it by modeling how relevance actually works over time.

When a memory's salience drops below a threshold, it doesn't get deleted — it gets deprioritized. It's still there if you explicitly search for it, but it won't be proactively injected into context. Just like how you *could* remember what you wore last Thursday if someone really pushed you on it, but it's not taking up active cognitive bandwidth.

### Reinforcement

Every time a memory is recalled — either explicitly by the agent or proactively by the system — its salience score gets a boost. The boost magnitude decreases with frequency (diminishing returns, like biological habituation), but the net effect is clear: **important memories get stronger over time, unimportant ones fade.**

This creates an emergent property that's surprisingly powerful: your agent's most critical context naturally rises to the top without any manual curation. After a few weeks of use, the memories that survive and strengthen are exactly the ones that matter for your workflow.

### Negative Recall

This was the feature that surprised me most in practice. Negative recall lets you explicitly store that something is *not* true, *no longer* valid, or *should not* be done.

"We do NOT support Internet Explorer."
"The old API endpoint /v1/users is DEPRECATED — use /v2/users."
"Redis was replaced by Memcached in the caching layer."

Without negative recall, an agent will happily suggest the old API endpoint if it shows up in retrieval. With negative recall, the system catches the contradiction and surfaces the correction.

This is critical for long-lived agent workflows where decisions get revised. In my EdTech deployment, pricing changed three times in two months. Without negative recall, agents would confidently quote outdated prices. With it, they know the current price *and* know the old ones are wrong.

### Contradiction Detection

Related to negative recall but distinct: when you store a new memory that conflicts with an existing one, 0Latency flags it. It doesn't silently overwrite or blindly store both.

If you stored "we use PostgreSQL for the user database" in January and then store "we use MySQL for the user database" in March, the system asks: is this a correction, or are these two different databases? This prevents the slow accumulation of contradictory context that plagues every "just append to the knowledge base" approach.

### Secret Scanning

This one's pragmatic. Agents deal with API keys, tokens, connection strings, and passwords constantly. A naive memory system will happily store `STRIPE_SECRET_KEY=sk_live_...` as a memory, creating a persistent credential leak.

0Latency scans memories before storage and catches common secret patterns. Keys, tokens, passwords, and connection strings get flagged and blocked. Your memory layer shouldn't be your biggest security liability.

### Sub-100ms Retrieval

Speed matters for agent memory in a way it doesn't for traditional RAG. When an agent is mid-task and needs context, even 500ms of retrieval latency creates a noticeable pause in the interaction. At 2-3 seconds (common with naive vector search over large collections), the user experience degrades significantly.

We achieve sub-100ms retrieval through a combination of approaches: pre-computed embeddings, aggressive indexing on temporal and tag dimensions, and a tiered retrieval strategy that checks high-salience memories first. Most recalls hit the "hot" tier and return in under 50ms. Deep searches across faded memories take longer but are rare in practice.

## The 624-Memory Stress Test

I didn't want to launch 0Latency based on toy examples. So I used it to build... 0Latency.

Over 5 days, I ran 5 AI agents coordinating the full product launch:
- **Product agent:** Architecture decisions, feature specs, technical tradeoffs
- **Marketing agent:** Positioning, copy, competitive analysis
- **Ops agent:** Deployment pipeline, 36-state configuration management
- **Finance agent:** Pricing strategy, competitive pricing research, margin analysis
- **Coordination agent:** Cross-agent context, decision tracking, blocker resolution

All five agents shared a memory pool. Total memories created: 624. That's it — 624 discrete memories to coordinate a full product launch across five agents over five days.

What worked:
- The marketing agent knew about technical constraints without being told. When product decided to drop a feature, marketing's copy updated in the next session.
- The ops agent remembered state-specific deployment quirks across sessions. Oklahoma's pricing exception? Remembered on day 4 without re-prompting.
- The coordination agent could reconstruct the full decision history at any point. "Why did we choose this pricing model?" produced a coherent narrative spanning three days of cross-agent decisions.

What I learned:
- 624 memories is a lot more than it sounds. Most of what agents "need to know" compresses into surprisingly few discrete facts and decisions.
- Temporal decay was the most valuable feature. By day 5, early brainstorming memories had naturally faded, and the final decisions were dominant. The agents weren't confused by outdated context.
- Contradiction detection caught 11 conflicts over the 5 days. Every one was a legitimate decision change that would have caused bugs or inconsistencies without the flag.

## The Market Gap

I looked at the existing agent memory landscape before building this:

**Mem0** ($249/mo for graph memory): Good product, but the pricing is aimed at enterprise. Their graph-based approach is powerful but complex. For most agent workflows, you don't need a full knowledge graph — you need fast, decaying, reinforceable memory.

**Zep** ($475/mo): Focused on conversation memory for chatbots. Solid engineering but narrow use case and eye-watering pricing for indie developers and small teams.

**Anthropic Memory Beta:** Basic fact storage, locked to Anthropic's ecosystem. No decay, no reinforcement, no negative recall. It's a start, but it's a feature, not a product.

0Latency's Scale tier ($89/mo) includes everything Mem0 charges $249/mo for. The free tier gives you 10,000 memories — enough to run the 624-memory stress test sixteen times over.

We're not competing on features against these products. We're competing on the thesis that agent memory should be **biologically inspired, fast, and accessible** — not an enterprise procurement decision.

## Getting Started

**MCP Server (Claude Desktop / Claude Code):**
```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "0latency-mcp"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your-api-key"
      }
    }
  }
}
```

**Python SDK:**
```bash
pip install zerolatency
```

```python
from zerolatency import Memory

mem = Memory(api_key="your-key")
mem.store("PostgreSQL chosen for user DB — need JSONB support and strong consistency")
results = mem.recall("what database are we using?")
```

Free tier: 10,000 memories. No credit card required.

## What's Next

We're working on:
- **Memory sharing across agents** with granular permissions (some memories are private to an agent, some are shared)
- **Memory clusters** — automatic grouping of related memories into coherent narratives
- **Audit trails** — full provenance of how a memory was created, reinforced, and used
- **Self-hosted option** for teams that need data residency

## The Bootstrapped Story

I'm building 0Latency alongside PFL Academy, an EdTech company I run. No VC, no team of 20 — just me and the agents. The irony of using AI agents to build a product for AI agents isn't lost on me.

The reason I'm building this as a separate product and not just an internal tool: every developer I talk to who's building with agents has the same memory problem. The workarounds are the same. The frustration is the same. And the existing solutions are either too expensive, too narrow, or too basic.

If agents are going to be genuinely useful — not just fancy autocomplete — they need to remember. Not everything, not forever, but the right things at the right time. That's what biological memory does. That's what 0Latency does.

---

**Site:** [0latency.ai](https://0latency.ai)
**SDK:** `pip install zerolatency`
**MCP Server:** One config edit, works with Claude Desktop and Claude Code
**Free tier:** 10,000 memories, no credit card

*Questions? I'm in the comments.*
