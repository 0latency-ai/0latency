# 0Latency × LangChain Integration

Persistent, cross-session memory for LangChain agents — powered by [0Latency](https://0latency.ai).

## What is 0Latency?

0Latency is a persistent memory layer API for AI agents. It provides sub-100ms memory recall with temporal intelligence, knowledge graphs, contradiction detection, and proactive context injection. Your agent remembers everything across sessions — no vector DB setup, no embeddings config, no infrastructure.

## Installation

```bash
pip install zerolatency langchain-core
```

## Quick Start

```python
from zerolatency_memory import ZeroLatencyMemory
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain

# Initialize with your 0Latency API key
memory = ZeroLatencyMemory(api_key="zl_live_...")

# Use with any LangChain chain
chain = ConversationChain(
    llm=ChatOpenAI(),
    memory=memory,
)

# Conversation context persists across sessions
chain.predict(input="My name is Alice and I prefer Python")
chain.predict(input="What language do I prefer?")
# → "You prefer Python, Alice!"
```

## Configuration

```python
memory = ZeroLatencyMemory(
    api_key="zl_live_...",           # Required: your API key
    agent_id="my-agent",             # Optional: scope memories per agent
    memory_key="history",            # Key in prompt template (default: "history")
    input_key="input",               # Key for human input (auto-detected)
    output_key="output",             # Key for AI output (auto-detected)
    recall_limit=10,                 # Max memories to recall (default: 10)
    return_memories_as_list=False,    # Return list instead of joined string
)
```

## How It Works

1. **`save_context()`** — Each conversation turn is stored as a memory via the 0Latency API. Memories are automatically extracted, deduplicated, and indexed.

2. **`load_memory_variables()`** — When the chain runs, the human input is sent as a recall query. 0Latency returns the most relevant memories in <50ms.

3. **`clear()`** — No-op. 0Latency manages memory lifecycle automatically with temporal decay and reinforcement.

## With Custom Chains

```python
from langchain_core.prompts import PromptTemplate

template = """You are a helpful assistant with persistent memory.

Relevant context from previous conversations:
{history}

Current conversation:
Human: {input}
AI:"""

prompt = PromptTemplate(input_variables=["history", "input"], template=template)

chain = ConversationChain(
    llm=ChatOpenAI(),
    memory=ZeroLatencyMemory(api_key="zl_live_..."),
    prompt=prompt,
)
```

## With LangGraph Agents

```python
from zerolatency_memory import ZeroLatencyMemory

memory = ZeroLatencyMemory(api_key="zl_live_...", agent_id="research-agent")

# Before agent runs, load relevant context
context = memory.load_memory_variables({"input": user_query})
# → Inject context["history"] into your agent's system prompt

# After agent responds, persist the turn
memory.save_context(
    {"input": user_query},
    {"output": agent_response},
)
```

## Why 0Latency over built-in LangChain memory?

| Feature | LangChain Built-in | 0Latency |
|---|---|---|
| Cross-session persistence | ❌ | ✅ |
| Temporal decay & reinforcement | ❌ | ✅ |
| Contradiction detection | ❌ | ✅ |
| Knowledge graph | ❌ | ✅ |
| Sub-100ms recall | N/A | ✅ |
| Setup required | Vector DB + embeddings | `pip install zerolatency` |

## Links

- **Docs:** https://api.0latency.ai/docs
- **PyPI:** https://pypi.org/project/zerolatency/
- **GitHub:** https://github.com/jghiglia2380/0Latency

## License

MIT
