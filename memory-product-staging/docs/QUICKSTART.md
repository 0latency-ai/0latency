# Zero Latency Memory — Quickstart

Get agent memory working in 5 minutes.

## 1. Get Your API Key

```bash
# Admin creates a tenant (run from the server)
curl -X POST http://127.0.0.1:8420/api-keys \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "plan": "pro"}'
```

Save the `api_key` from the response. Format: `zl_live_<32chars>`

## 2. Store a Memory

```python
import requests

API = "https://164.90.156.169/api"
KEY = "zl_live_your_key_here"
H = {"X-API-Key": KEY, "Content-Type": "application/json"}

r = requests.post(f"{API}/extract", headers=H, json={
    "agent_id": "my_agent",
    "human_message": "I live in Portland and my dog is named Kona",
    "agent_message": "Portland is great! What breed is Kona?"
}, verify=False)

print(r.json())
# {"memories_stored": 2, "memory_ids": ["uuid-1", "uuid-2"]}
```

## 3. Recall Context

```python
r = requests.post(f"{API}/recall", headers=H, json={
    "agent_id": "my_agent",
    "conversation_context": "User wants pet-friendly restaurant recommendations",
    "budget_tokens": 1000
}, verify=False)

print(r.json()["context_block"])
# Returns: location (Portland) + pet info (Kona) — relevant to the query
print(f"{r.json()['memories_used']} memories, {r.json()['tokens_used']} tokens")
```

## 4. Check Your Usage

```python
r = requests.get(f"{API}/usage", headers={"X-API-Key": KEY}, verify=False)
print(r.json())
# Shows: calls per endpoint, tokens used, memory count vs limit
```

Or open `https://164.90.156.169/dashboard` in your browser and paste your API key.

## 5. List Memories

```python
r = requests.get(f"{API}/memories", headers={"X-API-Key": KEY},
    params={"agent_id": "my_agent", "limit": 10}, verify=False)
for m in r.json():
    print(f"[{m['memory_type']}] {m['headline']}")
```

## How It Works

1. **Extract** — Send conversation turns. System automatically identifies facts, preferences, decisions, relationships. Detects contradictions with existing memories.

2. **Recall** — Send current conversation context. System returns the most relevant memories, scored by semantic similarity (0.4), recency (0.35), importance (0.15), and access frequency (0.1). Budget-aware — never exceeds your token limit.

3. **Self-correcting** — When new info contradicts old info, the system auto-supersedes. "I moved to Berlin" correctly replaces "Lives in Portland."

## Plans

| | Free | Pro | Enterprise |
|---|---|---|---|
| Memories | 1,000 | 50,000 | 500,000 |
| Rate limit | 20/min | 100/min | 500/min |
| Price | $0 | $19/mo | Custom |

## Next Steps

- [Full API Reference](./API_REFERENCE.md)
- [Dashboard](https://164.90.156.169/dashboard)
- [Swagger UI](https://164.90.156.169/docs)

*Updated March 21, 2026*
