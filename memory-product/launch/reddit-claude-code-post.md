# r/ClaudeCode Launch Post

**Title:** I built a universal memory layer for AI agents — works with Claude Code, GPT, Cursor, everything

---

**One memory layer. Every AI platform.**

Your agents forget everything between sessions. Every tool handles memory differently (or not at all). I built **0Latency** — persistent memory infrastructure that works with Claude Code, ChatGPT, Cursor, any agent framework. One API, every platform. Not locked to one tool.

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

## Why a universal memory layer?

Most memory solutions lock you into one platform. 0Latency works everywhere:

- ✅ Claude Code, Claude Desktop, any MCP client
- ✅ ChatGPT, GPT API
- ✅ Cursor
- ✅ Any custom agent framework
- ✅ Full API access — your data, your control
- ✅ Export everything anytime

One memory layer. Every AI platform. Your context follows you.

## The actual technical bits

- **PostgreSQL + pgvector** (not SQLite, actual production infra)
- **Auto-consolidation** — merges duplicate memories automatically
- **Temporal decay** — recent memories weigh more
- **Contradiction detection** — updates stale facts instead of duplicating
- **Graph relationships** — entities + semantic links (Pro/Scale tiers)
- **Sentiment analysis** — understands emotional context (Pro/Scale)
- **Confidence scoring** — tracks which memories are validated vs inferred

Free tier: 10K memories. Pro: 100K at $29/mo. Scale: 1M + graph features at $89/mo.

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
- **GitHub:** https://github.com/0latency-ai/0latency

Feedback welcome. Especially if you find bugs — I want this bulletproof before the wider launch.

---

**TL;DR:** Claude Code + persistent memory = agents that actually learn. Free tier, 30-second install, works today.
