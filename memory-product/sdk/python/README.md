# 0Latency Python SDK

A lightweight Python client for the [0Latency](https://0latency.ai) agent memory API.

## Installation

```bash
pip install zero-latency
```

## Quick Start

```python
from zero_latency import ZeroLatencyClient

# Initialize the client
client = ZeroLatencyClient(api_key="your_api_key_here")

# Extract memories from a conversation
result = client.extract(
    agent_id="my-agent",
    human_message="I love hiking in the mountains",
    agent_message="That's great! Mountain hiking is wonderful exercise."
)

# Recall relevant memories
memories = client.recall(
    agent_id="my-agent",
    query="What outdoor activities does the user enjoy?",
    limit=5
)

for memory in memories:
    print(f"- {memory['content']} (confidence: {memory['confidence']})")
```

## Features

- **Extract**: Automatically extract and store memories from conversations
- **Recall**: Semantic search to find relevant memories
- **Search**: Keyword-based text search
- **Seed**: Bulk import existing facts or notes
- **Graph**: Explore memory relationships and connections
- **Entities**: Extract and track people, places, concepts
- **Sentiment**: Analyze emotional tone across memories
- **Consolidate**: Merge and deduplicate similar memories

## Usage

### Context Manager (Recommended)

```python
with ZeroLatencyClient(api_key="your_api_key") as client:
    memories = client.recall(agent_id="my-agent", query="user preferences")
```

### Direct Instantiation

```python
client = ZeroLatencyClient(api_key="your_api_key")
try:
    memories = client.recall(agent_id="my-agent", query="user preferences")
finally:
    client.close()
```

### Error Handling

```python
from zero_latency import ZeroLatencyClient, AuthenticationError, ValidationError

client = ZeroLatencyClient(api_key="your_api_key")

try:
    result = client.extract(
        agent_id="my-agent",
        human_message="Hello!",
        agent_message="Hi there!"
    )
except AuthenticationError:
    print("Invalid API key")
except ValidationError as e:
    print(f"Invalid request: {e}")
```

## API Methods

### `extract(agent_id, human_message, agent_message)`
Extract and store memories from a conversation turn.

### `recall(agent_id, query, limit=10)`
Recall relevant memories using semantic search.

### `search(agent_id, q, limit=20)`
Search memories by keyword.

### `list_memories(agent_id, limit=50)`
List all memories for an agent.

### `seed(agent_id, facts)`
Bulk import a list of facts.

### `get_graph(agent_id, memory_id, depth=2)`
Get memory graph traversal.

### `get_entities(agent_id, limit=50)`
List extracted entities.

### `get_sentiment_summary(agent_id)`
Get sentiment breakdown.

### `consolidate(agent_id, auto_merge=False)`
Run consolidation to merge similar memories.

### `delete_memory(memory_id)`
Delete a specific memory.

## Documentation

Full documentation available at [docs.0latency.ai](https://docs.0latency.ai)

## License

MIT License - see LICENSE file for details.

## Support

- Email: justin@0latency.ai
- Issues: [GitHub Issues](https://github.com/0latency/python-sdk/issues)
