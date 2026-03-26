# r/ClaudeCode Launch Post

**Title:** I built cross-platform memory consolidation (like Auto Dream, but works everywhere)

---

**Update:** Anthropic just shipped Auto Dream for Claude Code — memory consolidation that runs in the background. It's great if you only use Claude Code. But what if you use GPT? Cursor? Custom agents?

That's why I built **0Latency** — cross-platform memory that works with Claude Code, ChatGPT, Cursor, any agent framework. Not locked to one tool.

## What it does

Your agent remembers:
- Code patterns you prefer
- Bugs you've hit before
- Architecture decisions
- What you tried that didn't work (negative recall)
- Relationships between concepts (graph memory)
- Your preferences and style

All under 100ms. No manual "memory.txt" files. No copy-pasting context.

## How it works

**MCP server (install in 30 seconds):**
```bash
npx @0latency/mcp-server
```

Add to your `claude_desktop_config.json`:
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

Now Claude can use the `remember` tool. Every session, it recalls what matters. Your context compounds instead of resetting.

## What's different from Auto Dream?

Auto Dream is built into Claude Code. 0Latency is an API:

| Feature | Auto Dream | 0Latency |
|---------|-----------|----------|
| Memory consolidation | ✅ | ✅ |
| Works with Claude Code | ✅ | ✅ |
| Works with ChatGPT | ❌ | ✅ |
| Works with Cursor | ❌ | ✅ |
| Works with custom agents | ❌ | ✅ |
| API access | ❌ | ✅ |
| Export your data | ❌ | ✅ |

Think of us as "Auto Dream for everyone else."

## The actual technical bits

- **PostgreSQL + pgvector** (not SQLite, actual production infra)
- **Auto-consolidation** — merges duplicate memories, like Auto Dream
- **Temporal decay** — recent memories weigh more
- **Contradiction detection** — updates stale facts instead of duplicating
- **Graph relationships** — entities + semantic links (Pro/Scale tiers)
- **Sentiment analysis** — understands emotional context (Pro/Scale)
- **Confidence scoring** — tracks which memories are validated vs inferred

Free tier: 10K memories. Pro: 100K at $19/mo. Scale: 1M + graph features at $89/mo.

## Why I built this

I'm building two products (PFL Academy + 0Latency) and needed agents that actually remember context across days. The existing tools either:
- Don't work with Claude Code
- Cost $249/mo for basic features (looking at you, Mem0)
- Require vendor lock-in

So I built the portable layer. Works with Claude Desktop, Claude Code, any MCP client, any agent framework. Your memory follows you.

## Try it

- **Docs:** https://0latency.ai/docs
- **API:** https://api.0latency.ai
- **npm:** `@0latency/mcp-server` (https://npmjs.com/package/@0latency/mcp-server)
- **GitHub:** Coming soon (open-sourcing after launch)

Feedback welcome. Especially if you find bugs — I want this bulletproof before the wider launch.

---

**TL;DR:** Claude Code + persistent memory = agents that actually learn. Free tier, 30-second install, works today.
