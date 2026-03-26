# Show HN: 0Latency – Cross-platform memory consolidation (like Auto Dream, for any AI)

**Update:** Anthropic just shipped Auto Dream — memory consolidation built into Claude Code. It's great if you only use Claude Code. I built the cross-platform version that works everywhere.

**The problem:** Every AI session starts from zero. You give context, the agent builds something great, session ends. Next time: "I don't have access to that information." You're re-explaining the same codebase, the same preferences, the same bugs you've already hit.

Auto Dream solves this for Claude Code users. But what if you use GPT? Cursor? Custom agents? That's where 0Latency comes in.

**What I built:**

0Latency is persistent memory infrastructure for agents. It extracts, stores, and recalls memories in under 100ms with:

- **Temporal decay** — recent context weighs more than old
- **Negative recall** — remembers what didn't work, not just what did
- **Graph relationships** — entities + semantic links between memories
- **Sentiment analysis** — understands emotional context
- **Confidence scoring** — tracks which memories are validated vs inferred
- **Contradiction detection** — updates stale facts instead of accumulating conflicting ones

**Tech stack:**

- PostgreSQL + pgvector for semantic search
- FastAPI backend
- LLM-powered extraction (supports multiple models)
- MCP server for Claude Desktop/Claude Code integration
- Cross-platform (works with Claude, GPT, Cursor, any agent framework)

**Why I built this:**

I'm building two products (PFL Academy + 0Latency itself) and needed agents that remember context across days/weeks. Existing tools either:
- Don't work with Claude Code
- Cost $249/mo for features we include at $89 (Mem0)
- Lock you into their platform

So I built the portable layer. Your memory follows you everywhere.

**MCP integration (30 seconds):**

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
        "ZERO_LATENCY_API_KEY": "your_key"
      }
    }
  }
}
```

Now Claude can use the `remember` tool. Context compounds instead of resetting.

**API (if you don't use MCP):**

```bash
# Store a memory
curl -X POST https://api.0latency.ai/extract \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "human_message": "I prefer React over Vue",
    "agent_message": "Noted, storing your framework preference"
  }'

# Recall memories
curl "https://api.0latency.ai/memories?agent_id=my-agent&limit=10" \
  -H "X-API-Key: YOUR_KEY"
```

**Pricing:**

- Free: 10K memories
- Pro: 100K memories, $19/mo
- Scale: 1M memories + graph features, $89/mo (64% cheaper than Mem0's equivalent tier)

**What's different:**

Most memory tools are just vector databases with a fancy wrapper. We built actual cognitive memory:
- Knows what matters more (temporal decay, confidence scoring)
- Learns from failures (negative recall)
- Understands relationships (graph)
- Works everywhere (not locked to one platform)

The brain layer isn't Notion. It's infrastructure.

**Try it:**
- Docs: https://0latency.ai/docs
- API: https://api.0latency.ai
- npm: @0latency/mcp-server

**Open questions for HN:**

1. How are you handling agent memory today? (manual context files? built-in features? nothing?)
2. What memory features matter most to you? (We built what I needed, curious what others prioritize)
3. For those using Claude Code: would you actually use this, or is session-to-session context not a pain point for you?

Feedback welcome. Especially bugs — I want this bulletproof before scaling.

---

Built in public over the last 2 weeks. Graph + sentiment + confidence features shipped in the last 8 hours while I've been at my night job (thanks to Opus coding agents doing the heavy lifting).

The irony: building a memory system for agents while using agents to build it. Meta, but it works.
