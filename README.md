# 0Latency

Long-term memory for AI agents that actually works.

## Quick Start

```bash
npm install @0latency/mcp-server
```

Add to your MCP settings:

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server"],
      "env": {
        "ZEROLATENCY_API_KEY": "your-api-key"
      }
    }
  }
}
```

Get your API key at [0latency.ai](https://0latency.ai)

## Documentation

- **Full Docs**: [docs.0latency.ai](https://docs.0latency.ai)
- **Website**: [0latency.ai](https://0latency.ai)

## What is 0Latency?

0Latency is a multi-tenant memory API for AI agents. Extract, store, and recall contextual memories with semantic search, automatic deduplication, and sub-100ms retrieval.

## Features

- 🧠 Long-term memory storage across sessions
- 🔍 Semantic search with vector embeddings
- ⚡ Sub-100ms cached query performance
- 🔄 Automatic deduplication (>92% similarity)
- 📊 Knowledge graph support
- 🔐 Tenant-isolated, secure storage

## License

MIT
