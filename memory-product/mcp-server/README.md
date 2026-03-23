# 0Latency MCP Server

Model Context Protocol (MCP) server for [0Latency](https://0latency.ai) — the persistent memory layer for AI agents.

Give Claude, Cursor, or any MCP-compatible AI tool long-term memory in **one config change**.

## Tools

| Tool | Description |
|------|-------------|
| `memory_add` | Extract and store memories from a conversation turn |
| `memory_recall` | Recall relevant memories for a conversation context |
| `memory_search` | Full-text search across stored memories |
| `memory_list` | List memories with type/pagination filters |
| `memory_delete` | Delete a specific memory by ID |
| `memory_graph` | Query the knowledge graph (entities, relationships, paths) |

## Quick Start

### 1. Get an API Key

Sign up at [0latency.ai](https://0latency.ai) and grab your API key from the dashboard.

### 2. Install & Build

```bash
git clone https://github.com/0latency/mcp-server.git
cd mcp-server
npm install
npm run build
```

Or install globally from npm (when published):

```bash
npm install -g @0latency/mcp-server
```

### 3. Configure Your AI Tool

#### Claude Desktop / Claude Code

Add to your Claude configuration (`~/.claude/claude_desktop_config.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "0latency": {
      "command": "node",
      "args": ["/path/to/mcp-server/dist/index.js"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

#### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "0latency": {
      "command": "node",
      "args": ["/path/to/mcp-server/dist/index.js"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

#### If installed globally via npm

Replace the `command` / `args` with:

```json
{
  "command": "0latency-mcp",
  "env": {
    "ZERO_LATENCY_API_KEY": "your-api-key-here"
  }
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ZERO_LATENCY_API_KEY` | ✅ | — | Your 0Latency API key |
| `ZERO_LATENCY_API_URL` | — | `https://api.0latency.ai` | API base URL (for self-hosted) |

## Usage Examples

Once configured, your AI assistant can use 0Latency tools natively:

**Store a memory:**
> "Remember that the user prefers dark mode and uses TypeScript."

The assistant calls `memory_add` with the conversation context, and 0Latency extracts and stores the relevant facts.

**Recall memories:**
> "What do you know about my coding preferences?"

The assistant calls `memory_recall` with the conversation context and gets back relevant memories.

**Search memories:**
> "Find all memories about deployment."

The assistant calls `memory_search` with the query and returns matching results.

**Explore the knowledge graph:**
> "What entities are connected to the 'auth-service' project?"

The assistant calls `memory_graph` with `action: "entity_detail"` to explore relationships.

## Development

```bash
npm install
npm run dev     # Watch mode
npm run build   # Production build
npm start       # Run the server
```

## License

MIT
