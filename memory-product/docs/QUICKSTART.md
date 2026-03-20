# Zero Latency Memory API - Quickstart Guide

Get up and running with the Zero Latency Memory API in minutes.

## What is Zero Latency Memory?

Zero Latency Memory provides instant, intelligent memory storage and recall for AI agents. Unlike traditional databases, it understands context, handles contradictions, and surfaces the most relevant memories automatically.

**Key Features:**
- **Instant Storage**: Extract structured memories from conversations
- **Smart Recall**: Retrieve contextually relevant memories with budget control
- **Multi-Tenant**: Secure isolation between different users/organizations
- **Self-Correcting**: Automatically handles corrections and contradictions

## Getting Started

### 1. Get Your API Key

Contact your administrator to get an API key. Keys follow this format:
```
zl_live_<32-character-string>
```

### 2. Install Dependencies

```bash
pip install requests
```

### 3. Basic Usage

#### Example 1: Extract Memories from a Conversation

```python
import requests

API_KEY = "zl_live_your_api_key_here"
BASE_URL = "https://164.90.156.169/api"

# Extract memories from a conversation turn
response = requests.post(
    f"{BASE_URL}/extract",
    headers={"X-API-Key": API_KEY},
    json={
        "agent_id": "assistant_v1",
        "human_message": "I live in San Francisco and work at OpenAI. My favorite coffee shop is Blue Bottle.",
        "agent_message": "Thanks for sharing! I'll remember that you're based in SF and work at OpenAI. Blue Bottle is a great choice for coffee!",
        "session_key": "session_123",
        "turn_id": "turn_001"
    },
    verify=False  # Only needed for self-signed certificates
)

print(f"Stored {response.json()['memories_stored']} memories")
print(f"Memory IDs: {response.json()['memory_ids']}")
```

**Expected Output:**
```json
{
  "memories_stored": 3,
  "memory_ids": [
    "uuid-for-location-memory",
    "uuid-for-work-memory", 
    "uuid-for-preference-memory"
  ]
}
```

#### Example 2: Recall Relevant Context

```python
# Recall memories relevant to a new conversation
response = requests.post(
    f"{BASE_URL}/recall",
    headers={"X-API-Key": API_KEY},
    json={
        "agent_id": "assistant_v1",
        "conversation_context": "User is asking about coffee recommendations in their area.",
        "budget_tokens": 2000,
        "dynamic_budget": True
    },
    verify=False
)

print("Relevant context:")
print(response.json()["context_block"])
print(f"Used {response.json()['memories_used']} memories, {response.json()['tokens_used']} tokens")
```

**Expected Output:**
```
Relevant context:
## Remembered Context

**Location & Work:**
- Lives in San Francisco  
- Works at OpenAI

**Preferences:**
- Favorite coffee shop: Blue Bottle

Used 2 memories, 156 tokens
```

#### Example 3: List All Memories

```python
# List memories for an agent
response = requests.get(
    f"{BASE_URL}/memories",
    headers={"X-API-Key": API_KEY},
    params={
        "agent_id": "assistant_v1",
        "limit": 10,
        "memory_type": "preference"  # Optional filter
    },
    verify=False
)

for memory in response.json():
    print(f"[{memory['memory_type']}] {memory['headline']} (importance: {memory['importance']})")
```

**Expected Output:**
```
[preference] Favorite coffee shop: Blue Bottle (importance: 0.7)
[fact] Lives in San Francisco (importance: 0.8)
[fact] Works at OpenAI (importance: 0.6)
```

## Rate Limits & Pricing

### Rate Limits by Plan

| Plan | Requests/Minute | Memory Limit | Price |
|------|----------------|--------------|--------|
| **Free** | 20 | 1,000 memories | $0 |
| **Pro** | 100 | 50,000 memories | $49/month |
| **Enterprise** | 500 | 500,000 memories | Contact us |

Rate limits are enforced per tenant. Exceeded limits return `HTTP 429`.

### Token Usage

- **Extract**: ~100-200 tokens per conversation turn
- **Recall**: Varies by budget (500-16000 tokens)
- **List**: Minimal token usage

## Error Codes

| Code | Error | Description | Solution |
|------|-------|-------------|----------|
| **401** | Invalid API key | Key missing, malformed, or inactive | Check key format: `zl_live_...` |
| **429** | Rate limit exceeded | Too many requests per minute | Wait 60 seconds or upgrade plan |
| **500** | Internal error | Server-side processing error | Check request format, retry |

### Example Error Response
```json
{
  "detail": "Rate limit exceeded (100/min). Try again in 60 seconds."
}
```

## Advanced Usage

### Memory Types

The system automatically categorizes memories:

- **`fact`**: Factual information (location, age, job)
- **`preference`**: Personal preferences (favorite food, music)
- **`decision`**: Decisions made during conversations
- **`relationship`**: Information about relationships
- **`task`**: Action items or TODOs
- **`correction`**: Updates that supersede previous facts

### Session Management

Use `session_key` and `turn_id` for better memory organization:

```python
# Same session, multiple turns
for turn_num in range(3):
    response = requests.post(f"{BASE_URL}/extract", 
        headers={"X-API-Key": API_KEY},
        json={
            "agent_id": "assistant_v1",
            "session_key": "user_onboarding_session",
            "turn_id": f"turn_{turn_num:03d}",
            "human_message": "...",
            "agent_message": "..."
        },
        verify=False
    )
```

### Dynamic Budget Recall

Enable `dynamic_budget` to automatically adjust token usage based on context relevance:

```python
response = requests.post(f"{BASE_URL}/recall",
    headers={"X-API-Key": API_KEY},
    json={
        "agent_id": "assistant_v1",
        "conversation_context": "Complex multi-topic conversation...",
        "budget_tokens": 4000,
        "dynamic_budget": True  # Adapts token usage to context complexity
    },
    verify=False
)
```

## Get Your Account Info

```python
# Check your tenant information
response = requests.get(
    f"{BASE_URL}/tenant-info",
    headers={"X-API-Key": API_KEY},
    verify=False
)

info = response.json()
print(f"Plan: {info['plan']}")
print(f"API calls made: {info['api_calls_count']}")
print(f"Rate limit: {info['rate_limit_rpm']}/min")
```

## Production Tips

1. **Use HTTPS**: Always use `https://` in production
2. **Handle Rate Limits**: Implement exponential backoff for 429 errors
3. **Certificate Validation**: Set up proper SSL certificates and remove `verify=False`
4. **Error Handling**: Always check response status codes
5. **Session Organization**: Use meaningful `session_key` values for better memory organization

## Support

- **API Documentation**: https://164.90.156.169/docs  
- **Health Check**: https://164.90.156.169/health
- **Questions**: Contact your system administrator

---

**Next Steps**: See [API_REFERENCE.md](./API_REFERENCE.md) for complete endpoint documentation.