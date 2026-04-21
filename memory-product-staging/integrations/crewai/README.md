# 0Latency × CrewAI Integration

Persistent memory storage backend for CrewAI crews — powered by [0Latency](https://0latency.ai).

## What is 0Latency?

0Latency is a persistent memory layer API for AI agents. Sub-100ms recall, temporal intelligence, knowledge graphs, contradiction detection — no infrastructure to manage. Your crew remembers everything across sessions.

## Installation

```bash
pip install zerolatency crewai
```

## Quick Start

```python
from crewai import Crew, Agent, Task
from crewai.memory import LongTermMemory
from zerolatency_storage import ZeroLatencyLongTermStorage

# Use 0Latency as CrewAI's long-term memory backend
crew = Crew(
    agents=[...],
    tasks=[...],
    memory=True,
    long_term_memory=LongTermMemory(
        storage=ZeroLatencyLongTermStorage(api_key="zl_live_...")
    ),
)

crew.kickoff()
```

## Storage Classes

| Class | Use Case |
|---|---|
| `ZeroLatencyStorage` | General-purpose storage backend |
| `ZeroLatencyShortTermStorage` | Short-term memory (within a crew run) |
| `ZeroLatencyLongTermStorage` | Long-term memory (across crew runs) |
| `ZeroLatencyEntityStorage` | Entity memory (people, places, things) |

## Configuration

```python
from zerolatency_storage import ZeroLatencyStorage

storage = ZeroLatencyStorage(
    api_key="zl_live_...",       # Required: your API key
    agent_id="research-crew",    # Optional: scope memories per crew/agent
    type="long_term",            # Memory type label
)
```

## Direct Usage

```python
from zerolatency_storage import ZeroLatencyStorage

storage = ZeroLatencyStorage(api_key="zl_live_...")

# Store a memory
storage.save(
    key="user_preference",
    value="User prefers detailed technical explanations",
    metadata={"confidence": 0.95},
)

# Search for relevant memories
results = storage.search(
    query="How should I explain this concept?",
    limit=5,
    score_threshold=0.7,
)

for result in results:
    print(f"{result['context']} (score: {result['score']:.2f})")
```

## Full Crew Example

```python
from crewai import Crew, Agent, Task
from crewai.memory import ShortTermMemory, LongTermMemory, EntityMemory
from zerolatency_storage import (
    ZeroLatencyShortTermStorage,
    ZeroLatencyLongTermStorage,
    ZeroLatencyEntityStorage,
)

API_KEY = "zl_live_..."

researcher = Agent(
    role="Senior Researcher",
    goal="Find and analyze information",
    backstory="Expert research analyst",
)

writer = Agent(
    role="Content Writer",
    goal="Create compelling content",
    backstory="Experienced technical writer",
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[
        Task(description="Research AI memory systems", agent=researcher),
        Task(description="Write a summary report", agent=writer),
    ],
    memory=True,
    short_term_memory=ShortTermMemory(
        storage=ZeroLatencyShortTermStorage(api_key=API_KEY)
    ),
    long_term_memory=LongTermMemory(
        storage=ZeroLatencyLongTermStorage(api_key=API_KEY)
    ),
    entity_memory=EntityMemory(
        storage=ZeroLatencyEntityStorage(api_key=API_KEY)
    ),
)

result = crew.kickoff()
```

## Why 0Latency?

- **Persistent** — Memories survive across crew runs and sessions
- **Fast** — Sub-100ms recall, no cold starts
- **Smart** — Temporal decay, contradiction detection, knowledge graphs
- **Simple** — No vector DB, no embeddings config, no infrastructure

## Links

- **Docs:** https://api.0latency.ai/docs
- **PyPI:** https://pypi.org/project/zerolatency/
- **GitHub:** https://github.com/jghiglia2380/0Latency

## License

MIT
