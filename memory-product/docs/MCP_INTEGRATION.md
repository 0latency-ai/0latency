# MCP Integration Guide

Model Context Protocol (MCP) integration allows Claude Desktop and other MCP-compatible clients to access 0Latency memory directly.

## Status

✅ **Functional** - MCP server is working and tested  
⚠️ **Auto-recall on connect not yet implemented**

## What Works

- ✅ Memory storage via MCP tools
- ✅ Memory search via MCP tools
- ✅ Manual recall via `memory_recall` tool
- ✅ Memory listing and management
- ✅ Agent-specific namespaces

## What's Coming

- ⏳ Auto-recall on session start
- ⏳ Proactive context injection
- ⏳ Conversation state preservation
- ⏳ Multi-agent memory coordination

## Setup

### 1. Install MCP Server

**From npm:**
```bash
npm install -g @0latency/mcp-server
```

**From source:**
```bash
git clone https://github.com/0latency/mcp-server.git
cd mcp-server
npm install
npm run build
```

### 2. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "0latency-memory": {
      "command": "node",
      "args": ["/path/to/mcp-server/build/index.js"],
      "env": {
        "ZERO_LATENCY_API_KEY": "zl_live_your_api_key_here",
        "ZERO_LATENCY_AGENT_ID": "claude-desktop"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

After saving the config, restart Claude Desktop. The MCP server should connect automatically.

**Verify connection:**
1. Start new conversation
2. Type: "List available tools"
3. You should see: `memory_store`, `memory_recall`, `memory_search`

## Available MCP Tools

### memory_store

**Purpose:** Store a new memory for the agent.

**Parameters:**
- `content` (required): The memory content to store
- `agent_id` (optional): Override default agent_id from config
- `metadata` (optional): Additional metadata as JSON object

**Example usage in Claude:**
```
User: Remember that I prefer Oxford commas in all writing.

Claude: [Uses memory_store tool]
{
  "content": "User prefers Oxford commas in all writing",
  "metadata": {
    "category": "writing-preferences",
    "importance": "high"
  }
}
```

### memory_recall

**Purpose:** Retrieve relevant memories for current conversation context.

**Parameters:**
- `conversation_context` (required): Current conversation summary or query
- `agent_id` (optional): Override default agent_id
- `budget_tokens` (optional): Max tokens to use (default: 4000)

**Example usage in Claude:**
```
User: What are my writing preferences?

Claude: [Uses memory_recall tool]
{
  "conversation_context": "User asking about writing preferences and style",
  "budget_tokens": 2000
}

[Returns memories about writing preferences, style guide, etc.]
```

**Important:** Until auto-recall ships, you must explicitly call this tool or instruct Claude to use it at session start.

### memory_search

**Purpose:** Search memories by keyword or semantic similarity.

**Parameters:**
- `query` (required): Search query
- `agent_id` (optional): Override default agent_id
- `limit` (optional): Max results (default: 10)

**Example usage in Claude:**
```
User: Search my memories for anything about "deployment"

Claude: [Uses memory_search tool]
{
  "query": "deployment procedures infrastructure",
  "limit": 20
}

[Returns all memories matching "deployment"]
```

### memory_list

**Purpose:** List recent memories with pagination.

**Parameters:**
- `agent_id` (optional): Override default agent_id
- `limit` (optional): Max results (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Example usage:**
```
Claude: [Uses memory_list tool]
{
  "limit": 10,
  "offset": 0
}

[Returns 10 most recent memories]
```

## Current Limitation: No Auto-Recall

### What This Means

**Currently:**
- MCP server connects successfully
- Tools are available
- But Claude doesn't automatically load your memory at session start

**You must manually trigger recall:**

```
User: Recall my memories to get context for this conversation.

Claude: Let me retrieve your memories...
[Uses memory_recall tool]
```

### Workaround: Custom Instructions

Add to your Claude Desktop custom instructions:

```
At the start of every conversation, use the memory_recall tool 
to load my relevant memories. Pass a summary of what we're 
discussing as the conversation_context parameter.

Always pass agent_id explicitly - do not omit it, as omitting 
it uses the tenant default which may not be my intended namespace.
```

**Example:**
```
User: Let's work on the deployment guide.

Claude: Let me first recall your relevant memories...
[Calls memory_recall with context="deployment guide work session"]
[Loads memories about deployment, previous work, preferences]

Now I'm ready. Based on your memories, I see you prefer...
```

### Why It's Not Automatic Yet

**Technical reasons:**
- MCP spec doesn't have "on_connect" hook yet
- Need conversation context to make recall useful
- Proactive recall requires first user message

**Coming soon:**
- Auto-recall after first user message
- Conversation state detection
- Smart context building

## Best Practices

### 1. Agent ID Management

**Set once in config:**
```json
{
  "env": {
    "ZERO_LATENCY_AGENT_ID": "claude-desktop"
  }
}
```

**Don't change unless intentional.** Changing agent_id creates a new namespace, orphaning previous memories.

**Verify namespace:**
```bash
curl "https://api.0latency.ai/memories?agent_id=claude-desktop&limit=5" \
  -H "X-API-Key: your_api_key"
```

### 2. Explicit agent_id in Tool Calls

**Always pass agent_id explicitly:**
```json
{
  "conversation_context": "deployment discussion",
  "agent_id": "claude-desktop",
  "budget_tokens": 4000
}
```

**Don't omit agent_id:**
```json
// ❌ BAD - uses tenant default, may be wrong namespace
{
  "conversation_context": "deployment discussion",
  "budget_tokens": 4000
}
```

**Why:** Omitting agent_id falls back to tenant default (usually `"justin"`), which may not be your Claude Desktop namespace.

### 3. Conversation Context Quality

**Good context:**
```
"User asking about deployment procedures for memory-product API"
```

**Bad context:**
```
"help"
```

**Tips:**
- Include topic: "deployment", "writing", "research"
- Include intent: "asking about", "working on", "debugging"
- Include specifics: "memory-product API", "PFL Academy", "technical docs"

### 4. Budget Management

**Small queries:** 1000-2000 tokens
```json
{
  "conversation_context": "quick fact check",
  "budget_tokens": 1000
}
```

**Standard queries:** 4000 tokens (recommended)
```json
{
  "conversation_context": "general discussion",
  "budget_tokens": 4000
}
```

**Deep context:** 8000-12000 tokens
```json
{
  "conversation_context": "complex technical work requiring full context",
  "budget_tokens": 10000
}
```

## Troubleshooting

### MCP Server Not Connecting

**Check:**
1. Path to `index.js` is correct in config
2. Node.js version >= 18
3. API key is valid and not expired
4. Claude Desktop has been restarted

**Test manually:**
```bash
cd /path/to/mcp-server
ZERO_LATENCY_API_KEY="your_key" \
ZERO_LATENCY_AGENT_ID="test" \
node build/index.js
```

Should output:
```
MCP Server started successfully
Connected to 0Latency API
Agent ID: test
```

### Tools Not Available in Claude

**Symptoms:**
- "I don't have access to that tool"
- Memory tools not in tool list

**Fix:**
1. Check `claude_desktop_config.json` syntax (valid JSON)
2. Verify file location: `~/Library/Application Support/Claude/`
3. Restart Claude Desktop completely (Cmd+Q, not just close window)
4. Check Claude Desktop logs: `~/Library/Logs/Claude/`

### Memory Not Recalling

**Check:**
1. Correct agent_id in tool parameters
2. Memories exist for that agent_id
3. API key has read permissions
4. Conversation context is meaningful (not empty)

**Verify memories exist:**
```bash
curl "https://api.0latency.ai/memories?agent_id=claude-desktop&limit=10" \
  -H "X-API-Key: your_api_key"
```

**Test recall directly:**
```bash
curl -X POST "https://api.0latency.ai/recall" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "claude-desktop",
    "conversation_context": "test recall",
    "budget_tokens": 2000
  }'
```

### Wrong Namespace Being Used

**Symptoms:**
- Recall returns 0 memories despite having data
- Storing to wrong agent_id

**Cause:** Agent ID mismatch between config and tool calls.

**Fix:**
1. Check `claude_desktop_config.json` for `ZERO_LATENCY_AGENT_ID`
2. Ensure tool calls pass same agent_id explicitly
3. List all agent namespaces:
```bash
curl "https://api.0latency.ai/list_agents" \
  -H "X-API-Key: your_api_key"
```

## Advanced Usage

### Multiple MCP Servers

You can configure multiple 0Latency MCP servers for different contexts:

```json
{
  "mcpServers": {
    "memory-personal": {
      "command": "node",
      "args": ["/path/to/mcp-server/build/index.js"],
      "env": {
        "ZERO_LATENCY_API_KEY": "zl_live_...",
        "ZERO_LATENCY_AGENT_ID": "claude-personal"
      }
    },
    "memory-work": {
      "command": "node",
      "args": ["/path/to/mcp-server/build/index.js"],
      "env": {
        "ZERO_LATENCY_API_KEY": "zl_live_...",
        "ZERO_LATENCY_AGENT_ID": "claude-work"
      }
    }
  }
}
```

Claude will have access to both namespaces via different tool sets.

### Custom MCP Server

Build your own MCP server with 0Latency:

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { ZeroLatencyClient } from "@0latency/sdk";

const server = new Server({
  name: "custom-memory-server",
  version: "1.0.0",
});

const client = new ZeroLatencyClient({
  apiKey: process.env.ZERO_LATENCY_API_KEY,
});

server.tool("custom_recall", async (params) => {
  const result = await client.recall({
    agent_id: params.agent_id,
    conversation_context: params.context,
    budget_tokens: 4000,
  });
  
  return {
    content: [{
      type: "text",
      text: result.context_block,
    }],
  };
});
```

## Migration from Other Memory Systems

### From Mem0

Mem0 uses `user_id` instead of `agent_id`:

**Mem0:**
```python
memory.add("content", user_id="alice")
```

**0Latency:**
```python
client.extract(content="content", agent_id="alice")
```

### From LangChain Memory

LangChain memory is session-based. 0Latency is persistent:

**LangChain:**
```python
memory = ConversationBufferMemory()
memory.save_context({"input": "hi"}, {"output": "hello"})
```

**0Latency:**
```python
# Store conversation explicitly
client.extract(
    agent_id="langchain-agent",
    content="User said hi, assistant replied hello"
)

# Recall later
result = client.recall(
    agent_id="langchain-agent",
    conversation_context="current conversation"
)
```

## Roadmap

**Q2 2026:**
- ✅ Basic MCP integration
- ✅ Memory CRUD operations
- ⏳ Auto-recall on session start
- ⏳ Proactive context injection

**Q3 2026:**
- ⏳ Multi-agent coordination
- ⏳ Shared memory namespaces via MCP
- ⏳ Memory graph visualization in Claude Desktop
- ⏳ Real-time memory sync across devices

**Q4 2026:**
- ⏳ Conversation state preservation across sessions
- ⏳ Intelligent memory prioritization
- ⏳ Cross-platform memory sync (VS Code, JetBrains)

## Support

**Issues:**
- GitHub: https://github.com/0latency/mcp-server/issues
- Email: support@0latency.ai

**Documentation:**
- MCP Spec: https://spec.modelcontextprotocol.io/
- 0Latency API: https://0latency.ai/docs
- Examples: https://github.com/0latency/examples/mcp

**Community:**
- Discord: https://discord.gg/0latency
- Twitter: @0latency_ai
