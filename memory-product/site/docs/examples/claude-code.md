# Example 2: Claude Code Integration via MCP

Give Claude Code persistent memory using the Model Context Protocol (MCP).

**What you'll get:** Claude Desktop with:
- Persistent memory across all conversations
- Automatic context recall
- Never forgets important information

**Time:** ~10 minutes  
**Difficulty:** Intermediate

---

## What is MCP?

[Model Context Protocol](https://modelcontextprotocol.io/) is Anthropic's standard for connecting external data sources to Claude.

With 0Latency's MCP server, Claude can:
- **Store memories** from conversations automatically
- **Recall context** when relevant
- **Search memories** by keyword or semantic similarity

All without leaving Claude Desktop.

---

## Prerequisites

- Claude Desktop installed ([download here](https://claude.ai/download))
- 0Latency API key ([get one here](https://0latency.ai/dashboard))
- Node.js 18+ installed

---

## Step 1: Install the MCP Server

```bash
npm install -g @0latency/mcp-server
```

Or install locally:

```bash
npm install @0latency/mcp-server
```

---

## Step 2: Configure Claude Desktop

### macOS/Linux

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["@0latency/mcp-server"],
      "env": {
        "ZEROLATENCY_API_KEY": "zl_live_your_key_here"
      }
    }
  }
}
```

### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx.cmd",
      "args": ["@0latency/mcp-server"],
      "env": {
        "ZEROLATENCY_API_KEY": "zl_live_your_key_here"
      }
    }
  }
}
```

**💡 Tip:** Replace `"zl_live_your_key_here"` with your actual API key.

---

## Step 3: Restart Claude Desktop

1. Quit Claude Desktop completely (⌘+Q on Mac)
2. Reopen Claude Desktop
3. You should see a small 🔌 icon in the bottom-right corner

Click the 🔌 icon — you should see `0latency` listed under "Connected MCP Servers".

---

## Step 4: Test It Out

### Store a Memory

Start a new conversation with Claude:

```
You: My name is Jordan and I work at Stripe as a product manager
Claude: Nice to meet you, Jordan! Product management at Stripe must be exciting...
```

Behind the scenes, 0Latency automatically extracted and stored:
- **Fact:** User's name is Jordan
- **Fact:** User works at Stripe
- **Fact:** User's role is product manager

### Recall a Memory

Now start a **brand new conversation** (important: different session):

```
You: What's my name?
Claude: Your name is Jordan.

You: Where do I work?
Claude: You work at Stripe as a product manager.
```

**It remembers!** 🎉

---

## How It Works

### Automatic Memory Storage

When you chat with Claude, the MCP server:
1. Listens for conversation turns
2. Sends them to 0Latency for extraction
3. Stores structured memories (facts, preferences, decisions, etc.)

You don't have to do anything — it's automatic.

### Automatic Context Recall

When Claude needs context, the MCP server:
1. Analyzes the current conversation
2. Recalls relevant memories from 0Latency
3. Injects them into Claude's context window

Again, fully automatic.

### Manual Controls (Optional)

You can also explicitly ask Claude to use memory tools:

```
You: Use the memory tool to search for all mentions of "Stripe"
Claude: [searches memory] I found 3 mentions of Stripe...
```

Available MCP tools:
- `memory_recall` — Get relevant context for a query
- `memory_search` — Search memories by keyword
- `memory_list` — List recent memories
- `memory_store` — Manually store a memory

---

## Configuration Options

### Custom Agent ID

By default, the MCP server uses `agent_id = "claude_desktop"`. To customize:

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["@0latency/mcp-server"],
      "env": {
        "ZEROLATENCY_API_KEY": "zl_live_your_key_here",
        "ZEROLATENCY_AGENT_ID": "my_custom_agent"
      }
    }
  }
}
```

Useful for:
- Separate memory spaces per project
- Different agents for work vs. personal

### Token Budget

Control how much memory context to include:

```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["@0latency/mcp-server"],
      "env": {
        "ZEROLATENCY_API_KEY": "zl_live_your_key_here",
        "ZEROLATENCY_TOKEN_BUDGET": "4000"
      }
    }
  }
}
```

Default: 4000 tokens (good for most use cases)

---

## Troubleshooting

### ❌ "MCP server failed to start"

**Check logs:**

```bash
# macOS/Linux
tail -f ~/Library/Logs/Claude/mcp-server-0latency.log

# Windows
type %APPDATA%\Claude\logs\mcp-server-0latency.log
```

**Common issues:**

1. **Invalid API key**
   - Error: `401 Unauthorized`
   - Fix: Double-check your API key in `claude_desktop_config.json`

2. **Node.js not found**
   - Error: `command not found: npx`
   - Fix: Install Node.js from [nodejs.org](https://nodejs.org)

3. **Package not installed**
   - Error: `Cannot find module '@0latency/mcp-server'`
   - Fix: Run `npm install -g @0latency/mcp-server`

### ❌ "Memory not being recalled"

**Check if memories are being stored:**

1. Go to [0latency.ai/dashboard](https://0latency.ai/dashboard)
2. Enter your API key
3. Check the memory count

If count is 0, memories aren't being stored.

**Possible causes:**

- API key is invalid or inactive
- Rate limit exceeded (free tier: 20/min)
- Memory limit reached (free tier: 100 memories)

### ❌ "Claude isn't seeing the 🔌 icon"

**Fix:**

1. Quit Claude Desktop completely (don't just close the window)
2. Verify the config file is valid JSON (use [jsonlint.com](https://jsonlint.com))
3. Restart Claude Desktop

If still not working, check:

```bash
# macOS/Linux - config file location
ls -la ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows
dir "%APPDATA%\Claude\claude_desktop_config.json"
```

---

## Example Use Cases

### 1. Personal Assistant

```
You: I have a dentist appointment on Friday at 2pm
Claude: Got it, I'll remember that.

[3 days later, new conversation]

You: What's on my calendar this Friday?
Claude: You have a dentist appointment at 2pm.
```

### 2. Project Context

```
You: I'm building a SaaS product called "TaskFlow" using Next.js and Supabase
Claude: Sounds interesting! [stores project info]

[Next day, new conversation]

You: Can you help me with the authentication flow?
Claude: Sure! For TaskFlow (your Next.js + Supabase project), here's how you can set up auth...
```

### 3. Learning Companion

```
You: I'm learning Spanish. I'm a beginner, around A2 level.
Claude: Great! I'll keep that in mind.

[Later]

You: Can you recommend some reading material?
Claude: Since you're at A2 level Spanish, I'd recommend...
```

---

## Privacy & Security

### What gets stored?

- Conversation content you share with Claude
- Extracted facts, preferences, decisions, relationships
- No sensitive data (API keys, passwords, credit cards) — auto-filtered

### What doesn't get stored?

- Claude's internal reasoning
- System prompts
- Tool call internals

### Where is data stored?

- 0Latency servers (US-based, encrypted at rest)
- You can self-host the API if needed (see [Self-Hosting Guide](../self-hosting.md))

### Can I delete memories?

Yes:

1. Go to [0latency.ai/dashboard](https://0latency.ai/dashboard)
2. Search for memories
3. Click "Delete" on any memory

Or use the API:

```bash
curl -X DELETE https://api.0latency.ai/memories/{memory_id} \
  -H "X-API-Key: zl_live_your_key_here"
```

---

## Advanced: Multiple Memory Spaces

Run different memory spaces for different contexts:

```json
{
  "mcpServers": {
    "0latency-work": {
      "command": "npx",
      "args": ["@0latency/mcp-server"],
      "env": {
        "ZEROLATENCY_API_KEY": "zl_live_work_key",
        "ZEROLATENCY_AGENT_ID": "claude_work"
      }
    },
    "0latency-personal": {
      "command": "npx",
      "args": ["@0latency/mcp-server"],
      "env": {
        "ZEROLATENCY_API_KEY": "zl_live_personal_key",
        "ZEROLATENCY_AGENT_ID": "claude_personal"
      }
    }
  }
}
```

Now Claude has separate memory for work vs. personal conversations.

---

## Performance

### Latency

- **Memory recall:** ~50-200ms (median 95ms)
- **Memory storage:** ~100-300ms (async, non-blocking)

Claude's response time is **not significantly impacted** by memory recall.

### Context Window Usage

0Latency recall uses ~500-2000 tokens depending on:
- How many memories are relevant
- Token budget setting
- Conversation complexity

Claude 3.5 Sonnet has a 200K context window, so memory usage is minimal.

---

## Pricing

| Plan | Price | Memories | API Calls/Min |
|------|-------|----------|---------------|
| Free | $0 | 100 | 20 |
| Pro | $19/mo | 50,000 | 100 |
| Scale | $99/mo | Unlimited | 500 |

Free tier is enough for:
- Personal assistant use
- Light project context
- Learning companion

Upgrade if you hit limits.

---

## Next Steps

### 📘 More Examples
- [Simple Chatbot](./chatbot.md) — Build a chatbot from scratch
- [Customer Support Agent](./customer-support.md) — Support tickets with memory

### 📖 Advanced
- [Memory Types](../memory-types.md) — What gets extracted
- [Scoring & Ranking](../scoring.md) — How recall prioritizes
- [Self-Hosting](../self-hosting.md) — Run 0Latency on your own server

---

## Questions?

- 💬 [Discord Community](https://discord.gg/0latency)
- 📧 Email: support@0latency.ai
- 🐛 [Report a Bug](https://github.com/jghiglia2380/0Latency/issues)

---

**Claude now remembers everything.** Build fearlessly.

