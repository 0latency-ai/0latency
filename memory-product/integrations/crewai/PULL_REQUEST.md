# Add 0Latency as a memory storage backend

## What is 0Latency?

[0Latency](https://0latency.ai) is a persistent memory layer API for AI agents. It provides:

- **Sub-100ms recall** — median 12ms response times
- **Temporal intelligence** — memory decay, reinforcement, and half-life scoring
- **Knowledge graph** — entity relationships with multi-hop traversal  
- **Contradiction detection** — automatic supersession of outdated facts
- **Zero configuration** — no vector DB, no embeddings model, no index management

Python SDK: [`pip install zerolatency`](https://pypi.org/project/zerolatency/)

## What this PR adds

A set of CrewAI-compatible storage backend classes that route memory operations through the 0Latency API:

| Class | Purpose |
|---|---|
| `ZeroLatencyStorage` | Base storage backend |
| `ZeroLatencyShortTermStorage` | For `ShortTermMemory` |
| `ZeroLatencyLongTermStorage` | For `LongTermMemory` |
| `ZeroLatencyEntityStorage` | For `EntityMemory` |

### Implementation

- **`save(key, value, metadata)`** — Stores memories via the 0Latency API with CrewAI-specific metadata
- **`search(query, limit, score_threshold)`** — Recalls relevant memories with optional relevance filtering
- **`reset()`** — No-op; 0Latency manages lifecycle automatically

## Usage

```python
from crewai import Crew
from crewai.memory import LongTermMemory
from zerolatency_storage import ZeroLatencyLongTermStorage

crew = Crew(
    agents=[...],
    tasks=[...],
    memory=True,
    long_term_memory=LongTermMemory(
        storage=ZeroLatencyLongTermStorage(api_key="zl_live_...")
    ),
)
```

## Links

- **Documentation:** https://api.0latency.ai/docs
- **PyPI:** https://pypi.org/project/zerolatency/
- **GitHub:** https://github.com/jghiglia2380/0Latency

## Checklist

- [x] Compatible with CrewAI's storage interface
- [x] Supports ShortTermMemory, LongTermMemory, and EntityMemory
- [x] Type annotations throughout
- [x] Comprehensive docstrings
- [x] README with usage examples
