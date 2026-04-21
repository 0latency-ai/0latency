# 0Latency MCP Server

Model Context Protocol server for [0Latency](https://0latency.ai) — persistent memory for AI agents.

Add long-term memory to Claude Desktop, Claude Code, or any MCP-compatible client in under 30 seconds.

## Quick Start

```bash
npx @0latency/mcp-server@latest
```

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server@latest"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

**Get your API key:** [0latency.ai/dashboard](https://0latency.ai/dashboard)

## What It Does

Gives your AI agent actual memory:

- **Remember across sessions** — Context doesn't reset every conversation
- **Temporal decay** — Recent context matters more than old
- **Negative recall** — Learns from failures, not just successes  
- **Graph relationships** — Understands connections between concepts
- **Sentiment analysis** — Knows emotional weight of memories
- **Confidence scoring** — Tracks validated vs inferred knowledge

## Available Tools

### Core Memory Tools

**`remember`** — Store a memory
```typescript
{
  agent_id: "default",
  text: "User prefers React over Vue for frontend work"
}
```

**`memory_recall`** — Get relevant memories for current context
```typescript
{
  agent_id: "default",
  query: "frontend framework preferences",
  limit: 10
}
```

**`memory_search`** — Search memories by text
```typescript
{
  agent_id: "default",
  q: "React",
  limit: 20
}
```

**`memory_list`** — List all memories
```typescript
{
  agent_id: "default",
  limit: 50
}
```

### Bulk Operations

**`seed_memories`** — Add multiple facts at once
```typescript
{
  agent_id: "default",
  facts: [
    "User is a TypeScript developer",
    "User prefers tabs over spaces",
    "User works in VS Code"
  ]
}
```

**`import_document`** — Import from text/markdown
```typescript
{
  agent_id: "default",
  content: "Full document text here...",
  title: "Project Architecture Decisions"
}
```

**`import_conversation`** — Import chat history
```typescript
{
  agent_id: "default",
  messages: [
    { role: "user", content: "How do I..." },
    { role: "assistant", content: "You can..." }
  ]
}
```

**`load_memory_pack`** — Load pre-built memory sets
```typescript
{
  agent_id: "default",
  pack: "typescript-dev"
}
```

Available packs: `typescript-dev`, `python-dev`, `saas-founder`, `claude-power-user`

### Graph & Analytics (Pro/Scale tiers)

**`memory_graph_traverse`** — Get related memories via graph
```typescript
{
  agent_id: "default",
  memory_id: "uuid-here",
  depth: 2,
  min_strength: 0.3
}
```

**`memory_entities`** — List extracted entities
```typescript
{
  agent_id: "default",
  entity_type: "technology", // person, organization, concept, etc.
  limit: 50
}
```

**`memory_by_entity`** — Find memories mentioning an entity
```typescript
{
  agent_id: "default",
  entity_text: "React"
}
```

**`memory_sentiment_summary`** — Get sentiment breakdown
```typescript
{
  agent_id: "default"
}
```

**`memory_history`** — View memory version history
```typescript
{
  memory_id: "uuid-here"
}
```

## Configuration

### Environment Variables

**Required:**
- `ZERO_LATENCY_API_KEY` — Your API key from [0latency.ai/dashboard](https://0latency.ai/dashboard)

**Optional:**
- `ZERO_LATENCY_API_URL` — Custom API endpoint (default: `https://api.0latency.ai`)
- `ZERO_LATENCY_DEFAULT_AGENT` — Default agent ID (default: `default`)

### Config Example

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server@latest"],
      "env": {
        "ZERO_LATENCY_API_KEY": "zl_live_...",
        "ZERO_LATENCY_DEFAULT_AGENT": "my-coding-assistant"
      }
    }
  }
}
```

## How It Works

1. **Automatic extraction** — Claude calls `remember` when it learns something important
2. **Semantic storage** — Memories are embedded and indexed for fast recall
3. **Smart retrieval** — `memory_recall` pulls relevant context based on your current conversation
4. **Proactive injection** — Claude uses memories to inform responses without you asking

Your agent actually learns over time instead of forgetting everything between sessions.

## Pricing

- **Free:** 10,000 memories
- **Pro ($19/mo):** 100,000 memories
- **Scale ($89/mo):** 1,000,000 memories + graph features + sentiment analysis

All tiers include:
- Unlimited API calls
- Sub-100ms recall
- Temporal decay
- Negative recall
- Contradiction detection

[View full pricing](https://0latency.ai/pricing)

## API Direct Access

Don't want to use MCP? Access the same memory system via REST API:

```bash
# Store
curl -X POST https://api.0latency.ai/extract \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-agent", "human_message": "...", "agent_message": "..."}'

# Recall
curl "https://api.0latency.ai/memories?agent_id=my-agent&limit=10" \
  -H "X-API-Key: YOUR_KEY"
```

[Full API docs](https://0latency.ai/docs)

## Examples

### Claude Code Workflow

```
User: "Build a React component for user profiles"
Claude: [uses memory_recall to check preferences]
       [remembers: User prefers TypeScript, functional components, Tailwind CSS]
       [builds component matching those preferences]
       [calls remember to store: "Built UserProfile component with TypeScript"]
```

Next session:
```
User: "Update the user profile component"
Claude: [recalls previous UserProfile work]
       [knows the codebase context]
       [makes consistent updates]
```

Context compounds instead of resetting.

### Memory Packs

Load domain-specific knowledge instantly:

```typescript
// Load TypeScript developer knowledge
await load_memory_pack({ pack: "typescript-dev" })

// Claude now knows:
// - TypeScript best practices
// - Common patterns and anti-patterns
// - Tooling preferences (ESLint, Prettier, etc.)
// - Testing approaches (Jest, Vitest)
```

## Troubleshooting

**"Missing API key" error:**
- Verify `ZERO_LATENCY_API_KEY` is set in your MCP config
- Get a key at [0latency.ai/dashboard](https://0latency.ai/dashboard)

**"401 Unauthorized":**
- Check your API key is valid
- Free tier keys start with `zl_live_`

**"403 Forbidden" on graph tools:**
- Graph features require Pro or Scale tier
- [Upgrade here](https://0latency.ai/pricing)

**Tools not showing in Claude:**
- Restart Claude Desktop after config changes
- Verify JSON syntax in `claude_desktop_config.json`
- Check MCP server logs: `~/.claude/logs/mcp*.log`

## Development

```bash
# Clone this repo
git clone https://github.com/0latency-ai/mcp-server
cd mcp-server

# Install dependencies
npm install

# Build
npm run build

# Test locally
npm link
# Then use "0latency-mcp-server" as the command in your MCP config
```

## Contributing

Found a bug? Want a feature? [Open an issue](https://github.com/0latency-ai/mcp-server/issues)

Pull requests welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT — see [LICENSE](LICENSE)

## Links

- **Website:** [0latency.ai](https://0latency.ai)
- **API Docs:** [0latency.ai/docs](https://0latency.ai/docs)
- **Dashboard:** [0latency.ai/dashboard](https://0latency.ai/dashboard)
- **npm:** [@0latency/mcp-server](https://npmjs.com/package/@0latency/mcp-server)
- **Support:** [hello@0latency.ai](mailto:hello@0latency.ai)

---

**Built by [Justin Ghiglia](https://github.com/jghiglia2380)**

The brain layer for the agent era.
