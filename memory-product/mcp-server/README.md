# @0latency/mcp-server

[![npm version](https://img.shields.io/npm/v/@0latency/mcp-server.svg)](https://www.npmjs.com/package/@0latency/mcp-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**Persistent memory for AI agents.** Give Claude, Cursor, Windsurf, or any MCP-compatible tool long-term memory in one config change.

[0Latency](https://0latency.ai) automatically extracts, stores, and recalls memories across conversations — so your AI assistant actually remembers you.

## Features

- **Automatic memory extraction** — Detects facts, preferences, and relationships from conversations
- **Semantic recall** — Retrieves the right memories for the current context
- **Knowledge graph** — Tracks entities and relationships across all conversations
- **Document & conversation import** — Bulk-load context from existing docs or chat exports
- **Token-budgeted recall** — Control exactly how much context gets injected

## Quick Start

### 1. Get an API Key

Sign up at [0latency.ai](https://0latency.ai) and grab your API key from the dashboard.

### 2. Configure Your AI Tool

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

#### Claude Code

Add to your project `.mcp.json`:

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server"],
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
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

#### Windsurf / Other MCP Clients

Same pattern — just point your client's MCP config at:

```
command: npx -y @0latency/mcp-server
env: ZERO_LATENCY_API_KEY=your-api-key-here
```

### 3. Alternative: Install Globally

```bash
npm install -g @0latency/mcp-server
```

Then use `0latency-mcp` as the command instead of `npx`:

```json
{
  "command": "0latency-mcp",
  "env": {
    "ZERO_LATENCY_API_KEY": "your-api-key-here"
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `memory_add` | Extract and store memories from a conversation turn |
| `remember` | Simple interface — "remember this" for quick facts |
| `seed_memories` | Bulk-load known facts directly (bypass extraction) |
| `memory_recall` | Recall relevant memories for current conversation context |
| `memory_search` | Full-text search across stored memories |
| `memory_list` | List memories with type/pagination filters |
| `memory_delete` | Delete a specific memory by ID |
| `import_document` | Import a document and extract memories from it |
| `import_conversation` | Import a chat export and extract memories from each turn |
| `memory_graph` | Query the knowledge graph (entities, relationships, paths) |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ZERO_LATENCY_API_KEY` | ✅ | — | Your 0Latency API key |
| `ZERO_LATENCY_API_URL` | — | `https://api.0latency.ai` | API base URL (for self-hosted) |

## How It Works

1. **Your AI tool connects** to the 0Latency MCP server via stdio
2. **During conversations**, the AI calls `memory_add` or `remember` to store important facts
3. **In future conversations**, the AI calls `memory_recall` to retrieve relevant context
4. **Memories compound** — the more you use it, the better your AI knows you

No prompt engineering required. The AI tools are designed to be self-describing — your AI assistant will naturally use them when appropriate.

## Usage Examples

**Store a memory:**
> "Remember that I prefer TypeScript over JavaScript and use Vim keybindings."

**Recall memories:**
> "What do you know about my coding setup?"

**Import existing context:**
> "Import this project README as background knowledge."

**Explore the knowledge graph:**
> "What entities are connected to the auth-service project?"

## Development

```bash
git clone https://github.com/0latency-ai/mcp-server.git
cd mcp-server
npm install
npm run build
npm start
```

## Links

- 🌐 [0latency.ai](https://0latency.ai) — Product & dashboard
- 📖 [API Documentation](https://docs.0latency.ai) — Full API reference
- 🐛 [Issues](https://github.com/0latency-ai/mcp-server/issues) — Bug reports & feature requests

## License

MIT © [Justin Ghiglia](https://github.com/0latency-ai)
