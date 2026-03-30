# ZeroLatency

Drop-in memory wrappers for Anthropic, OpenAI, and Gemini clients. Add persistent memory to your LLM applications with zero code changes.

## Installation

```bash
pip install zerolatency
```

## Features

- **Drop-in replacement** - No code changes required, just swap the import
- **Automatic memory recall** - Relevant memories are retrieved and injected into context
- **Automatic memory storage** - Conversations are stored as memories in the background
- **Non-blocking** - Memory operations run in background threads, zero latency impact
- **Multi-provider** - Works with Anthropic Claude, OpenAI GPT, and Google Gemini

## Quick Start

### Anthropic Claude

```python
from zerolatency import AnthropicWithMemory

# Replace this:
# from anthropic import Anthropic
# client = Anthropic(api_key="your-api-key")

# With this:
client = AnthropicWithMemory(
    api_key="your-anthropic-key",
    zl_api_key="your-0latency-key",
    agent_id="my-agent"
)

# Use exactly as before
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### OpenAI

```python
from zerolatency import OpenAIWithMemory

# Replace this:
# from openai import OpenAI
# client = OpenAI(api_key="your-api-key")

# With this:
client = OpenAIWithMemory(
    api_key="your-openai-key",
    zl_api_key="your-0latency-key",
    agent_id="my-agent"
)

# Use exactly as before
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Google Gemini

```python
from zerolatency import GeminiWithMemory

# Replace this:
# import google.generativeai as genai
# genai.configure(api_key="your-api-key")
# model = genai.GenerativeModel("gemini-pro")

# With this:
client = GeminiWithMemory(
    api_key="your-gemini-key",
    zl_api_key="your-0latency-key",
    agent_id="my-agent"
)
model = client.GenerativeModel("gemini-pro")

# Use exactly as before
response = model.generate_content("Hello!")
```

## How It Works

1. **Memory Recall**: Before each API call, relevant memories are retrieved using semantic search
2. **Context Injection**: Memories are automatically injected into the system prompt
3. **API Call**: Your request is sent to the LLM provider with enhanced context
4. **Memory Storage**: The conversation turn is stored as a memory (non-blocking, zero latency)
5. **Response**: The original response is returned unmodified

## Configuration

All wrappers support the following parameters:

```python
client = AnthropicWithMemory(
    api_key="your-llm-api-key",          # Required: Your LLM provider API key
    zl_api_key="your-0latency-key",      # Required: Your 0Latency API key
    agent_id="my-agent",                 # Required: Unique agent identifier
    zl_base_url="https://api.0latency.ai",  # Optional: 0Latency API base URL
    recall_enabled=True,                 # Optional: Enable/disable memory recall
    store_enabled=True,                  # Optional: Enable/disable memory storage
    budget_tokens=4000,                  # Optional: Max tokens for memory context
)
```

## Get Your API Key

1. Sign up at [0latency.ai](https://0latency.ai)
2. Generate your API key from the dashboard
3. Start building with memory!

## Examples

### Multi-turn conversation with memory

```python
from zerolatency import AnthropicWithMemory

client = AnthropicWithMemory(
    api_key="your-anthropic-key",
    zl_api_key="your-0latency-key",
    agent_id="customer-support-bot"
)

# First conversation
response1 = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "My favorite color is blue"}]
)

# Later conversation - the agent remembers!
response2 = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "What's my favorite color?"}]
)
# Response: "Based on our previous conversation, your favorite color is blue."
```

### Disable memory for specific calls

```python
# Create client with recall disabled
client = AnthropicWithMemory(
    api_key="your-anthropic-key",
    zl_api_key="your-0latency-key",
    agent_id="my-agent",
    recall_enabled=False,  # Don't recall memories
    store_enabled=True,    # But still store them
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Application                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               ZeroLatency Wrapper (This Package)             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Recall    │  │   Inject     │  │  Store (async)   │  │
│  │  Memories   │→ │   Context    │→ │    Memories      │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
    ┌──────────────────┐        ┌─────────────────┐
    │  LLM Provider    │        │  0Latency API   │
    │  (Anthropic/     │        │  (Memory Store) │
    │   OpenAI/Gemini) │        └─────────────────┘
    └──────────────────┘
```

## Performance

- **Zero added latency** - Memory storage happens in background threads
- **Fast recall** - Memory retrieval typically adds <100ms
- **Configurable budget** - Control memory context size with `budget_tokens`
- **Smart caching** - Frequently accessed memories are cached for speed

## Requirements

- Python 3.8+
- `anthropic>=0.18.0`
- `openai>=1.0.0`
- `google-generativeai>=0.3.0`
- `requests>=2.25.0`

## License

MIT License - see LICENSE file for details

## Support

- Documentation: [docs.0latency.ai](https://docs.0latency.ai)
- Issues: [GitHub Issues](https://github.com/0latency/zerolatency-py/issues)
- Email: support@0latency.ai

## Contributing

Contributions are welcome! Please open an issue or PR on GitHub.

---

Built with ❤️ by the [0Latency](https://0latency.ai) team
