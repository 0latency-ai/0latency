# 0Latency × AutoGen Integration

Persistent memory for AutoGen agents — powered by [0Latency](https://0latency.ai).

## What is 0Latency?

0Latency is a persistent memory layer API for AI agents. Sub-100ms recall, temporal intelligence, knowledge graphs, contradiction detection — no infrastructure. Your AutoGen agents remember everything across sessions.

## Installation

```bash
pip install zerolatency pyautogen
```

## Quick Start

```python
from autogen import ConversableAgent
from zerolatency_memory import ZeroLatencyMemory

# Initialize memory
memory = ZeroLatencyMemory(api_key="zl_live_...")

# Store knowledge
memory.add("User is a Python developer working on AI applications")
memory.add("User prefers concise, technical explanations")

# Recall context for a new conversation
context = memory.get_context("How should I explain transformers?")
print(context)
# → Relevant context from memory:
# → - User is a Python developer working on AI applications
# → - User prefers concise, technical explanations
```

## With ConversableAgent

```python
from autogen import ConversableAgent
from zerolatency_memory import ZeroLatencyMemory

memory = ZeroLatencyMemory(api_key="zl_live_...")

# Augment system message with recalled context
base_system_message = "You are a helpful coding assistant."
enhanced_message = memory.augment_system_message(
    system_message=base_system_message,
    context_query="coding preferences and past projects",
)

assistant = ConversableAgent(
    name="assistant",
    system_message=enhanced_message,
    llm_config={"model": "gpt-4"},
)
```

## With Teachable Agents

```python
from autogen import ConversableAgent
from zerolatency_memory import ZeroLatencyMemory

memory = ZeroLatencyMemory(api_key="zl_live_...", auto_learn=True)

assistant = ConversableAgent(
    name="teachable_assistant",
    system_message="You are a helpful assistant that learns from conversations.",
    llm_config={"model": "gpt-4"},
)

# Register a hook that injects memory context into incoming messages
hook = memory.create_teachable_hook()
assistant.register_hook("process_last_received_message", hook)

# After conversations, extract and store learnings
memory.process_conversation([
    {"role": "user", "content": "I'm working on a FastAPI project"},
    {"role": "assistant", "content": "Great! What kind of API are you building?"},
    {"role": "user", "content": "A memory service for AI agents"},
])
```

## Configuration

```python
memory = ZeroLatencyMemory(
    api_key="zl_live_...",        # Required: your API key
    agent_id="research-agent",    # Optional: scope memories per agent
    recall_threshold=0.5,         # Minimum relevance score (0.0-1.0)
    max_recall=5,                 # Max memories per query
    auto_learn=True,              # Auto-store conversation messages
)
```

## API Reference

| Method | Description |
|---|---|
| `add(content, metadata)` | Store a fact or piece of knowledge |
| `query(question, limit)` | Recall relevant memories |
| `get_context(question)` | Get formatted context string for prompts |
| `process_message(message, role)` | Process and store a single message |
| `process_conversation(messages)` | Extract memories from a conversation |
| `augment_system_message(msg, query)` | Add recalled context to system message |
| `create_teachable_hook()` | Create a message hook for AutoGen agents |

## Multi-Agent Conversations

```python
from autogen import ConversableAgent, GroupChat, GroupChatManager
from zerolatency_memory import ZeroLatencyMemory

# Each agent can have its own memory scope
researcher_memory = ZeroLatencyMemory(api_key="zl_live_...", agent_id="researcher")
writer_memory = ZeroLatencyMemory(api_key="zl_live_...", agent_id="writer")

researcher = ConversableAgent(
    name="researcher",
    system_message=researcher_memory.augment_system_message(
        "You research topics thoroughly.",
        "research methodology and past findings",
    ),
)

writer = ConversableAgent(
    name="writer",
    system_message=writer_memory.augment_system_message(
        "You write clear technical content.",
        "writing style and past articles",
    ),
)

# Memories persist independently per agent
```

## Links

- **Docs:** https://api.0latency.ai/docs
- **PyPI:** https://pypi.org/project/zerolatency/
- **GitHub:** https://github.com/jghiglia2380/0Latency

## License

MIT
