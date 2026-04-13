# 0Latency Python SDK

A lightweight Python client for the [0Latency](https://0latency.ai) agent memory API, with drop-in wrappers for Anthropic, OpenAI, and Gemini clients.

## Installation

```bash
pip install zerolatency
```

## Features

### 🎯 Drop-in Memory Wrappers (NEW in v0.2.0)
Add persistent memory to your LLM applications with **zero code changes** - just swap your client initialization:

```python
# Instead of:
# from anthropic import Anthropic
# client = Anthropic(api_key="...")

# Use:
from zerolatency import AnthropicWithMemory
client = AnthropicWithMemory(
    api_key="your-anthropic-key",
    zl_api_key="your-0latency-key",
    agent_id="my-agent"
)

# Everything else works exactly the same!
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Supported Providers:**
- ✅ **Anthropic Claude** - `AnthropicWithMemory`
- ✅ **OpenAI GPT** - `OpenAIWithMemory`
- ✅ **Google Gemini** - `GeminiWithMemory`

### 🧠 Direct Memory API
- **Extract**: Automatically extract and store memories from conversations
- **Recall**: Semantic search to find relevant memories
- **Search**: Keyword-based text search
- **Seed**: Bulk import existing facts or notes
- **Graph**: Explore memory relationships and connections
- **Entities**: Extract and track people, places, concepts
- **Sentiment**: Analyze emotional tone across memories
- **Consolidate**: Merge and deduplicate similar memories

## Quick Start

### Option 1: Drop-in Wrappers (Easiest)

#### Anthropic Claude
```python
from zerolatency import AnthropicWithMemory

client = AnthropicWithMemory(
    api_key="your-anthropic-key",
    zl_api_key="your-0latency-key",
    agent_id="support-bot"
)

# First conversation
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "My favorite color is blue"}]
)

# Later - the agent remembers!
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "What's my favorite color?"}]
)
# Response references blue from memory
```

#### OpenAI
```python
from zerolatency import OpenAIWithMemory

client = OpenAIWithMemory(
    api_key="your-openai-key",
    zl_api_key="your-0latency-key",
    agent_id="gpt-assistant"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

#### Google Gemini
```python
from zerolatency import GeminiWithMemory

client = GeminiWithMemory(
    api_key="your-gemini-key",
    zl_api_key="your-0latency-key",
    agent_id="gemini-agent"
)

model = client.GenerativeModel("gemini-pro")
response = model.generate_content("Tell me about Python")
```

### Option 2: Direct Memory API

```python
from zerolatency import Memory

# Initialize the client
memory = Memory(api_key="your_api_key_here")

# Extract memories from a conversation
result = memory.extract(
    agent_id="my-agent",
    human_message="I love hiking in the mountains",
    agent_message="That's great! Mountain hiking is wonderful exercise."
)

# Recall relevant memories
memories = memory.recall(
    agent_id="my-agent",
    conversation_context="What outdoor activities does the user enjoy?",
    budget_tokens=4000
)

print(memories["context_block"])
```

## Drop-in Wrapper Configuration

All wrappers support these parameters:

```python
client = AnthropicWithMemory(
    api_key="your-llm-api-key",          # Required: LLM provider API key
    zl_api_key="your-0latency-key",      # Required: 0Latency API key
    agent_id="my-agent",                 # Required: Unique agent ID
    zl_base_url="https://api.0latency.ai",  # Optional: API base URL
    recall_enabled=True,                 # Optional: Enable memory recall
    store_enabled=True,                  # Optional: Enable memory storage
    budget_tokens=4000,                  # Optional: Max tokens for memory context
)
```

### How Wrappers Work

1. **Before each API call**: Relevant memories are retrieved via semantic search
2. **Context injection**: Memories are automatically added to the system prompt
3. **LLM call**: Your request is sent with enhanced context
4. **After response**: The conversation is stored as memory (non-blocking, zero latency)
5. **Return**: Original response returned unmodified

### Performance

- ⚡ **Zero added latency** - Memory storage runs in background threads
- 🔍 **Fast recall** - Typically <100ms to retrieve relevant memories
- 🎯 **Smart context** - Configurable token budget for memory injection
- 🔄 **Non-blocking** - Never slows down your LLM responses

## Direct Memory API Methods

### `extract(agent_id, human_message, agent_message)`
Extract and store memories from a conversation turn.

### `recall(agent_id, conversation_context, budget_tokens=4000)`
Recall relevant memories using semantic search.

### `search(agent_id, q, limit=20)`
Search memories by keyword.

### `list_memories(agent_id, limit=50)`
List all memories for an agent.

### `seed(agent_id, facts)`
Bulk import a list of facts.

### `delete_memory(memory_id)`
Delete a specific memory.

## Error Handling

```python
from zerolatency import Memory, AuthenticationError, RateLimitError, ZeroLatencyError

try:
    memory = Memory(api_key="your-key")
    memory.add("test")
except AuthenticationError:
    print("Invalid API key")
except RateLimitError:
    print("Rate limit exceeded")
except ZeroLatencyError as e:
    print(f"API error: {e}")
```

## Documentation

Full documentation available at [docs.0latency.ai](https://docs.0latency.ai)

## Examples

See the [examples directory](https://github.com/0latency/python-sdk/tree/main/examples) for complete working examples.

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: [docs.0latency.ai](https://docs.0latency.ai)
- Email: justin@0latency.ai
- Issues: [GitHub Issues](https://github.com/0latency/python-sdk/issues)

---

Built with ❤️ by [0Latency](https://0latency.ai)
