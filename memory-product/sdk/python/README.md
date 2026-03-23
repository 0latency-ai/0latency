# zerolatency

Python SDK for the [0Latency](https://0latency.ai) memory API — persistent memory for AI agents.

## Install

```bash
pip install zerolatency
```

## Quick start

```python
from zerolatency import Memory

memory = Memory("your-api-key")

# Store a memory
memory.add("User said they prefer dark mode and work in Python")

# Recall relevant memories
context = memory.recall("What are the user's preferences?")
print(context)
```

## Usage

### Store memories

```python
memory.add(
    "User prefers concise answers",
    agent_id="agent-123",
    metadata={"source": "onboarding"},
)
```

### Recall memories

```python
results = memory.recall("communication style", agent_id="agent-123", limit=5)
for m in results["memories"]:
    print(m["content"])
```

### Extract memories from a conversation

```python
conversation = [
    {"role": "user", "content": "I'm a backend engineer who uses FastAPI."},
    {"role": "assistant", "content": "Great! I'll keep that in mind."},
]

job = memory.extract(conversation, agent_id="agent-123")
status = memory.extract_status(job["job_id"])
```

### Health check

```python
print(memory.health())
```

### Context manager

```python
with Memory("your-api-key") as memory:
    memory.add("something to remember")
```

## Error handling

```python
from zerolatency import Memory, AuthenticationError, RateLimitError, ZeroLatencyError

try:
    memory = Memory("bad-key")
    memory.add("test")
except AuthenticationError:
    print("Check your API key")
except RateLimitError:
    print("Slow down — retry after a backoff")
except ZeroLatencyError as e:
    print(f"API error {e.status_code}: {e.message}")
```

## Configuration

| Parameter  | Default                      | Description              |
|------------|------------------------------|--------------------------|
| `api_key`  | *required*                   | Your 0Latency API key    |
| `base_url` | `https://api.0latency.ai`   | API base URL override    |
| `timeout`  | `30.0`                       | Request timeout (seconds)|

## License

MIT
