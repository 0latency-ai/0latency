# r/ClaudeCode Post

**Title:** I gave Claude Code persistent memory across sessions — here's the MCP server and what changed

---

Every time I start a new Claude Code session, I lose everything. Architecture decisions from yesterday? Gone. That weird edge case we debugged for an hour? Never happened. The reasoning behind why we chose Postgres over DynamoDB? Hope you wrote it down somewhere.

I got tired of re-explaining my own codebase to my own AI, so I built something about it.

## What it is

[0Latency](https://0latency.ai) is an MCP server that gives Claude Code persistent memory across sessions. Not "dump everything into a giant context file" memory — actual structured recall with temporal decay, reinforcement, and sub-100ms retrieval.

When you mention something important, it gets stored. When it's relevant again — even weeks later — it gets injected into context automatically. Things you use frequently get reinforced. Things that stop being relevant fade, like they should.

## Setup (literally 30 seconds)

Add this to your Claude Code MCP config:

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

That's it. No code changes. No SDK integration. Claude gets these tools automatically:

- `memory_store` — save a memory with tags and importance
- `memory_recall` — retrieve relevant memories by query
- `memory_search` — semantic search across all stored memories
- `memory_forget` — explicitly remove something (negative recall)
- `memory_context` — get proactive context for current task

## What actually changed for me

I'm building an EdTech platform across ~36 state deployments. Before 0Latency, every session started with me pasting the same 2000-word context dump. Now:

**Session 1 (Monday):** "The Oklahoma deployment uses a different pricing tier because of their bulk purchase agreement — $16/student instead of $20."

**Session 2 (Thursday):** I ask Claude to draft a pricing proposal for a new Oklahoma district. It already knows the state-specific pricing without me mentioning it. It recalls the bulk agreement context and factors it in.

**Session 3 (next week):** Debugging a deploy issue. Claude remembers that Oklahoma's config diverges from the standard template and checks those differences first.

That's not retrieval-augmented generation bolted on. That's memory that works like memory should — it surfaces when relevant, not when prompted.

## The technical bits

- **Temporal decay:** Memories lose salience over time unless reinforced. This prevents your context from becoming a landfill of stale decisions.
- **Contradiction detection:** If you store "we're using Redis for caching" and later store "we switched to Memcached," it flags the conflict instead of holding both as true.
- **Secret scanning:** API keys, tokens, passwords — they get caught before storage. Your memory layer shouldn't be a credential leak vector.
- **Negative recall:** Explicitly mark something as wrong or outdated. "We do NOT support IE11 anymore" stays as a negative memory that prevents Claude from suggesting IE11 fixes.

## What it costs

Free tier gets you 10,000 memories, which is honestly a lot. I built an entire product launch — 5 AI agents coordinating across a 36-state deployment — on 624 memories over 5 days. The paid tiers ($19/mo Pro, $89/mo Scale) are for teams and heavy usage.

For context: Mem0 charges $249/mo for their graph-based memory. Zep is $475/mo. Our $89 Scale tier covers everything Mem0's $249 plan includes.

## Not trying to sell you anything

The free tier is genuinely useful. I built this because I was mass-pasting context into every session like a caveman, and I figured other Claude Code users were too. The MCP server is open, the SDK is `pip install zerolatency`, and the setup is one config edit.

If you've been maintaining CLAUDE.md files or elaborate project context docs just to keep Claude oriented — this replaces that workflow entirely.

Happy to answer questions about the architecture or how specific memory patterns work.

**Link:** [0latency.ai](https://0latency.ai)
