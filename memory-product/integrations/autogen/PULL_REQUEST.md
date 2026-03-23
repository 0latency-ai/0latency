# Add 0Latency persistent memory module

## What is 0Latency?

[0Latency](https://0latency.ai) is a persistent memory layer API for AI agents. It provides:

- **Sub-100ms recall** — median 12ms response times
- **Temporal intelligence** — memory decay, reinforcement, and half-life scoring
- **Knowledge graph** — entity relationships with multi-hop traversal
- **Contradiction detection** — automatic supersession of outdated facts
- **Zero configuration** — no vector DB, no embeddings model, no index management

Python SDK: [`pip install zerolatency`](https://pypi.org/project/zerolatency/)

## What this PR adds

A `ZeroLatencyMemory` module that gives AutoGen agents persistent, cross-session memory. Compatible with:

- **ConversableAgent** — Augment system messages with recalled context
- **Teachable agents** — Message hook for automatic context injection
- **GroupChat** — Per-agent scoped memories in multi-agent conversations
- **Conversation extraction** — Async extraction of facts from conversation logs

### Key methods

| Method | Description |
|---|---|
| `add(content)` | Store a fact |
| `query(question)` | Recall relevant memories |
| `get_context(question)` | Formatted context string for prompts |
| `augment_system_message()` | Inject memory into system messages |
| `create_teachable_hook()` | AutoGen message hook |
| `process_conversation()` | Extract memories from conversations |

## Usage

```python
from autogen import ConversableAgent
from zerolatency_memory import ZeroLatencyMemory

memory = ZeroLatencyMemory(api_key="zl_live_...")

# Augment agent with persistent memory
assistant = ConversableAgent(
    name="assistant",
    system_message=memory.augment_system_message(
        "You are a helpful assistant.",
        "user preferences and past interactions",
    ),
)

# Register teachable hook
hook = memory.create_teachable_hook()
assistant.register_hook("process_last_received_message", hook)
```

## Links

- **Documentation:** https://api.0latency.ai/docs
- **PyPI:** https://pypi.org/project/zerolatency/
- **GitHub:** https://github.com/jghiglia2380/0Latency

## Checklist

- [x] Compatible with ConversableAgent and GroupChat
- [x] Teachable agent hook support
- [x] Async conversation extraction
- [x] Per-agent memory scoping
- [x] Type annotations throughout
- [x] Comprehensive docstrings
- [x] README with usage examples
