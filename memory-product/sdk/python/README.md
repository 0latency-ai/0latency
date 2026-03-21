# Zero Latency Memory SDK — Python

Structured memory extraction, storage, and recall for AI agents.

## Install

```bash
pip install zerolatency
```

## Quick Start

```python
from zerolatency import ZeroLatencyClient

client = ZeroLatencyClient(api_key="zl_live_your_key_here")

# Extract memories from conversation
result = client.extract(
    agent_id="my-agent",
    human_message="My name is Justin and I prefer direct communication",
    agent_message="Got it, Justin. I'll keep things concise."
)
print(f"Stored {result['memories_stored']} memories")

# Recall relevant context
context = client.recall(
    agent_id="my-agent",
    conversation_context="How should I communicate with the user?"
)
print(context["context_block"])

# Search memories
results = client.search(agent_id="my-agent", query="communication style")

# Knowledge graph
graph = client.get_entity_graph(agent_id="my-agent", entity="Justin")

# Batch operations
results = client.batch_extract([
    {"agent_id": "my-agent", "human_message": "msg1", "agent_message": "resp1"},
    {"agent_id": "my-agent", "human_message": "msg2", "agent_message": "resp2"},
])

# Custom criteria for recall re-ranking
client.create_criteria(
    agent_id="my-agent",
    name="urgency",
    weight=0.8,
    description="How urgent is this memory"
)

# Organization-level shared memory
client.store_org_memory(
    headline="Company uses Python 3.11+",
    context="All new projects must use Python 3.11 or newer",
    importance=0.9
)
```

## Features

- **Extract** — Automatic memory extraction from conversation turns
- **Recall** — Composite-scored retrieval with temporal decay and reinforcement
- **Graph Memory** — Entity relationships and multi-hop traversal
- **Memory Versioning** — Full changelog per memory
- **Batch Operations** — Bulk extract, search, and delete
- **Custom Criteria** — Developer-defined scoring attributes for re-ranking
- **Organization Memory** — Shared memory across team agents
- **Custom Schemas** — Developer-defined extraction templates
- **Webhooks** — Real-time notifications on memory events
