# Add 0Latency as a memory provider

## What is 0Latency?

[0Latency](https://0latency.ai) is a persistent memory layer API for AI agents. It provides:

- **Sub-100ms recall** — median 12ms response times
- **Temporal intelligence** — memory decay, reinforcement, and half-life scoring
- **Knowledge graph** — entity relationships with multi-hop traversal
- **Contradiction detection** — automatic supersession of outdated facts
- **Proactive context injection** — tiered loading (L0/L1/L2) that fits context window budgets
- **Zero configuration** — no vector DB, no embeddings model selection, no index management

Python SDK: [`pip install zerolatency`](https://pypi.org/project/zerolatency/)

## What this PR adds

A new `ZeroLatencyMemory` class that extends `BaseMemory` and provides persistent, cross-session memory for any LangChain chain or agent.

### Implementation

- **`load_memory_variables(inputs)`** — Sends the human input as a recall query to 0Latency and returns relevant memories
- **`save_context(inputs, outputs)`** — Stores each conversation turn as a memory via the 0Latency API
- **`clear()`** — No-op; 0Latency manages memory lifecycle automatically

### Key features

- Works with `ConversationChain`, custom chains, and LangGraph agents
- Supports agent-scoped memories via `agent_id`
- Auto-detects input/output keys or accepts explicit configuration
- Returns memories as either a formatted string or a list
- No infrastructure setup — just an API key

## Usage

```python
from langchain_zerolatency import ZeroLatencyMemory
from langchain.chains import ConversationChain
from langchain_openai import ChatOpenAI

memory = ZeroLatencyMemory(api_key="zl_live_...")

chain = ConversationChain(llm=ChatOpenAI(), memory=memory)
chain.predict(input="I prefer Python over JavaScript")

# Later, in a new session:
chain.predict(input="What language should we use?")
# → Recalls Python preference from previous session
```

## Links

- **Documentation:** https://api.0latency.ai/docs
- **PyPI:** https://pypi.org/project/zerolatency/
- **GitHub:** https://github.com/jghiglia2380/0Latency
- **Website:** https://0latency.ai

## Testing

Unit tests included with full mock coverage. Run with:

```bash
python -m pytest test_zerolatency_memory.py -v
```

## Checklist

- [x] Extends `BaseMemory` correctly
- [x] Implements `load_memory_variables()`, `save_context()`, `clear()`
- [x] Type annotations throughout
- [x] Comprehensive docstrings
- [x] Unit tests with mocked API calls
- [x] README with usage examples
