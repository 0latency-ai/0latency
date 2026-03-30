# 0Latency SDKs

Official Python and JavaScript SDKs for the 0Latency memory API.

## Quick Start

### Python (PyPI)

```bash
pip install zerolatency
```

**Before:**
```python
# Manual API calls
import requests

response = requests.post(
    "https://api.0latency.ai/memories/extract",
    headers={"X-API-Key": "zl_..."},
    json={"agent_id": "my-agent", "content": "..."}
)
```

**After:**
```python
from zerolatency import ZeroLatency

client = ZeroLatency(api_key="zl_...")
client.store("my-agent", "Remember this important fact")
context = client.recall("my-agent", "What do you remember?")
```

### JavaScript/TypeScript (npm)

```bash
npm install @0latency/sdk
```

**Before:**
```javascript
// Manual fetch calls
const response = await fetch("https://api.0latency.ai/memories/extract", {
  method: "POST",
  headers: {"X-API-Key": "zl_..."},
  body: JSON.stringify({agent_id: "my-agent", content: "..."})
});
```

**After:**
```javascript
import { ZeroLatency } from '@0latency/sdk';

const client = new ZeroLatency({ apiKey: 'zl_...' });
await client.store('my-agent', 'Remember this important fact');
const context = await client.recall('my-agent', 'What do you remember?');
```

## Provider Support

| Provider | Python | JavaScript | Notes |
|----------|--------|------------|-------|
| **Anthropic** (Claude) | ✅ | ✅ | Native integration via MCP |
| **OpenAI** (GPT-4) | ✅ | ✅ | Use SDK in tool functions |
| **Google** (Gemini) | ✅ | ✅ | Use SDK in function calling |
| **Custom** | ✅ | ✅ | Works with any LLM |

## Features

- 🚀 **Sub-100ms recall** - Fast enough for real-time conversations
- 🧠 **Semantic search** - Query by meaning, not keywords
- ⏰ **Temporal decay** - Recent memories weighted higher
- 🔗 **Knowledge graphs** - Auto-extract entities and relationships
- 🔒 **Private by default** - Your data, your infrastructure

## Documentation

- **Full API docs**: https://0latency.ai/docs
- **MCP integration**: https://0latency.ai/docs/mcp
- **Examples**: https://0latency.ai/examples
- **GitHub**: https://github.com/0latency

## Get Started

1. Sign up: https://0latency.ai
2. Get your API key
3. Install the SDK
4. Start building

## Support

- **Discord**: https://discord.com/invite/clawd
- **Email**: support@0latency.ai
- **Docs**: https://0latency.ai/docs

---

**License**: MIT  
**Version**: 0.1.0
