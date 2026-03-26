# API Reference

Complete reference for the 0Latency Memory API.

**Base URL:** `https://api.0latency.ai`

---

## Table of Contents

- [Authentication](#authentication)
- [Rate Limits](#rate-limits)
- [Error Handling](#error-handling)
- [Memory Operations](#memory-operations)
  - [POST /extract](#post-extract)
  - [POST /extract/batch](#post-extractbatch)
  - [POST /recall](#post-recall)
  - [GET /memories](#get-memories)
  - [GET /memories/:id](#get-memoriesid)
  - [PUT /memories/:id](#put-memoriesid)
  - [DELETE /memories/:id](#delete-memoriesid)
  - [GET /memories/search](#get-memoriessearch)
  - [GET /memories/export](#get-memoriesexport)
  - [GET /memories/:id/history](#get-memoriesidhistory)
- [Graph API](#graph-api)
  - [GET /memories/graph](#get-memoriesgraph)
  - [GET /memories/entities](#get-memoriesentities)
  - [GET /memories/by-entity](#get-memoriesby-entity)
- [Sentiment API](#sentiment-api)
  - [GET /memories/sentiment-summary](#get-memoriessentiment-summary)
- [Account & Usage](#account--usage)
  - [GET /tenant-info](#get-tenant-info)
  - [GET /usage](#get-usage)
- [Webhooks](#webhooks)
- [Admin Endpoints](#admin-endpoints)

---

## Authentication

All endpoints require an API key in the `X-API-Key` header:

```bash
curl https://api.0latency.ai/memories \
  -H "X-API-Key: zl_live_your_key_here"
```

Get your API key at [0latency.ai/dashboard](https://0latency.ai/dashboard).

---

## Rate Limits

Rate limits are per-tenant, enforced with a 60-second sliding window:

| Plan | Requests/Min | Memory Limit |
|------|-------------|--------------|
| **Free** | 20 | 100 |
| **Pro** | 100 | 50,000 |
| **Scale** | 500 | Unlimited |

**Rate limit exceeded (429 response):**
```json
{
  "detail": "Rate limit exceeded (100/min). Try again in 45s."
}
```

**Memory limit exceeded (429 response):**
```json
{
  "detail": "Memory limit reached (100/100). Upgrade plan or delete old memories."
}
```

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message here",
  "error_code": "INVALID_API_KEY",
  "request_id": "req_abc123"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_API_KEY` | 401 | API key is missing, invalid, or inactive |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests in the time window |
| `MEMORY_LIMIT_REACHED` | 429 | Memory storage limit reached for your plan |
| `RESOURCE_NOT_FOUND` | 404 | Memory/resource doesn't exist or wrong tenant |
| `VALIDATION_ERROR` | 422 | Invalid request parameters |
| `EXTRACTION_FAILED` | 500 | Memory extraction failed (retry) |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### Retry Logic

For `500` errors and rate limits:

```python
import time
import requests

def api_call_with_retry(url, headers, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 429:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
    
    raise Exception("Max retries exceeded")
```

---

## Memory Operations

### POST /extract

Extract and store memories from a conversation turn.

**Endpoint:** `POST /extract`

**Request Body:**
```json
{
  "agent_id": "string",           // Required
  "human_message": "string",      // Required
  "agent_message": "string",      // Required
  "session_key": "string",        // Optional - groups related conversations
  "turn_id": "string"             // Optional - identifies this specific turn
}
```

**Response (200):**
```json
{
  "memories_stored": 3,
  "memory_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

**Example:**

```bash
curl -X POST https://api.0latency.ai/extract \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "human_message": "I just moved to Berlin and started at Spotify",
    "agent_message": "Congrats on the move and the new role!"
  }'
```

**Python:**
```python
from zerolatency import Memory

mem = Memory("zl_live_your_key")

result = mem.add(
    agent_id="my_agent",
    human_message="I just moved to Berlin and started at Spotify",
    agent_message="Congrats on the move and the new role!"
)

print(f"Stored {result['memories_stored']} memories")
```

**What Gets Extracted:**

- **Facts:** "Lives in Berlin", "Works at Spotify"
- **Decisions:** Detected from "I decided to...", "I'm going to..."
- **Preferences:** "I prefer...", "I like...", "I hate..."
- **Relationships:** "My sister Emma...", "My boss John..."
- **Tasks:** "I need to...", "Reminder to..."
- **Corrections:** "Actually...", "I meant...", contradictions

---

### POST /extract/batch

Extract memories from multiple conversation turns in a single request.

**Endpoint:** `POST /extract/batch`

**Request Body:**
```json
{
  "turns": [
    {
      "human_message": "string",
      "agent_message": "string",
      "agent_id": "string",
      "session_key": "string",  // Optional
      "turn_id": "string"       // Optional
    }
  ]
}
```

**Limits:** Max 50 turns per batch

**Response (200):**
```json
{
  "turns_processed": 2,
  "memories_stored": 5,
  "memory_ids": ["uuid1", "uuid2", "uuid3", "uuid4", "uuid5"],
  "errors": null
}
```

**Example:**

```bash
curl -X POST https://api.0latency.ai/extract/batch \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "turns": [
      {
        "agent_id": "my_agent",
        "human_message": "I live in Portland",
        "agent_message": "Portland is beautiful!",
        "session_key": "session_1"
      },
      {
        "agent_id": "my_agent",
        "human_message": "I work at Nike",
        "agent_message": "Cool! What do you do there?",
        "session_key": "session_1"
      }
    ]
  }'
```

**Python:**
```python
result = mem.add_batch([
    {
        "agent_id": "my_agent",
        "human_message": "I live in Portland",
        "agent_message": "Portland is beautiful!"
    },
    {
        "agent_id": "my_agent",
        "human_message": "I work at Nike",
        "agent_message": "Cool! What do you do there?"
    }
])
```

**Use Cases:**
- Bulk import of historical conversations
- Batch processing for efficiency
- Initial memory seeding

---

### POST /recall

Retrieve contextually relevant memories.

**Endpoint:** `POST /recall`

**Request Body:**
```json
{
  "agent_id": "string",                 // Required
  "conversation_context": "string",     // Required
  "budget_tokens": 4000,                // Optional (500-16000)
  "dynamic_budget": false               // Optional
}
```

**Response (200):**
```json
{
  "context_block": "### Relevant Context\n- User lives in Berlin\n- Works at Spotify\n...",
  "memories_used": 5,
  "tokens_used": 187
}
```

**Scoring Algorithm:**

Memories are scored by:

| Factor | Weight | Description |
|--------|--------|-------------|
| **Semantic Similarity** | 40% | Embedding cosine similarity to context |
| **Recency** | 35% | Exponential decay: `exp(-days_since / 30)` |
| **Importance** | 15% | Manually set or auto-determined |
| **Access Frequency** | 10% | How often this memory is recalled |

**Type Bonuses:**
- Identity facts: ×1.5
- Preferences & corrections: ×1.3
- Recent decisions (< 7 days): ×1.2

**Example:**

```bash
curl -X POST https://api.0latency.ai/recall \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "conversation_context": "User asking about music for their commute",
    "budget_tokens": 2000
  }'
```

**Python:**
```python
context = mem.recall(
    agent_id="my_agent",
    conversation_context="User asking about music for their commute",
    budget_tokens=2000
)

print(context["context_block"])
print(f"{context['memories_used']} memories, {context['tokens_used']} tokens")
```

**Token Budget Recommendations:**

| LLM | Recommended Budget |
|-----|-------------------|
| GPT-3.5/4 | 2000-4000 |
| Claude 3 | 4000-8000 |
| Gemini Pro | 4000-6000 |
| Llama 3 | 2000-4000 |

---

### GET /memories

List memories with optional filtering.

**Endpoint:** `GET /memories`

**Query Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `agent_id` | Yes | — | Agent identifier |
| `limit` | No | 50 | Max results (cap: 200) |
| `memory_type` | No | — | Filter: `fact`, `preference`, `decision`, `relationship`, `task`, `correction`, `identity` |
| `sentiment` | No | — | Filter: `positive`, `negative`, `neutral` (Pro/Scale) |
| `min_confidence` | No | — | Minimum confidence (0.0-1.0) |
| `min_importance` | No | — | Minimum importance (0.0-1.0) |

**Response (200):**
```json
[
  {
    "id": "uuid",
    "headline": "Lives in Berlin",
    "context": "User moved to Berlin in 2026",
    "memory_type": "fact",
    "importance": 0.8,
    "confidence": 0.9,
    "sentiment": "positive",
    "sentiment_score": 0.6,
    "recall_count": 3,
    "created_at": "2026-03-20T22:15:30.123+00:00",
    "updated_at": "2026-03-22T10:30:00.000+00:00"
  }
]
```

**Example:**

```bash
# Get all facts
curl "https://api.0latency.ai/memories?agent_id=my_agent&memory_type=fact&limit=20" \
  -H "X-API-Key: zl_live_..."

# Get high-confidence memories
curl "https://api.0latency.ai/memories?agent_id=my_agent&min_confidence=0.8&limit=10" \
  -H "X-API-Key: zl_live_..."

# Get positive memories (Pro/Scale)
curl "https://api.0latency.ai/memories?agent_id=my_agent&sentiment=positive" \
  -H "X-API-Key: zl_live_..."
```

**Python:**
```python
# All memories
memories = mem.list_memories(agent_id="my_agent", limit=50)

# Filter by type
facts = mem.list_memories(agent_id="my_agent", memory_type="fact")

# Filter by confidence
trusted = mem.list_memories(agent_id="my_agent", min_confidence=0.85)
```

---

### GET /memories/:id

Get a single memory by ID.

**Endpoint:** `GET /memories/{memory_id}`

**Response (200):**
```json
{
  "id": "uuid",
  "headline": "Lives in Berlin",
  "context": "User moved to Berlin in 2026 for a job at Spotify",
  "full_content": "Original conversation context...",
  "memory_type": "fact",
  "importance": 0.8,
  "confidence": 0.9,
  "sentiment": "positive",
  "sentiment_score": 0.6,
  "entities": ["Berlin", "Spotify"],
  "recall_count": 5,
  "created_at": "2026-03-20T22:15:30.123+00:00",
  "updated_at": "2026-03-22T10:30:00.000+00:00"
}
```

**Example:**

```bash
curl https://api.0latency.ai/memories/uuid \
  -H "X-API-Key: zl_live_..."
```

---

### PUT /memories/:id

Update a memory. Creates a version snapshot before updating.

**Endpoint:** `PUT /memories/{memory_id}`

**Request Body:**
```json
{
  "headline": "Updated headline",          // Optional
  "context": "Updated context",            // Optional
  "importance": 0.9,                       // Optional (0.0-1.0)
  "memory_type": "decision",               // Optional
  "confidence": 0.95                       // Optional (0.0-1.0)
}
```

**Response (200):**
```json
{
  "updated": "uuid",
  "version": "incremented"
}
```

**Example:**

```bash
curl -X PUT https://api.0latency.ai/memories/uuid \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "headline": "Lives in San Francisco (moved from Berlin)",
    "importance": 0.9
  }'
```

**Python:**
```python
mem.update_memory(
    memory_id="uuid",
    headline="Lives in San Francisco",
    importance=0.9
)
```

---

### DELETE /memories/:id

Delete a memory. Cascades to entity index and graph edges.

**Endpoint:** `DELETE /memories/{memory_id}`

**Response (200):**
```json
{
  "deleted": "uuid"
}
```

**Example:**

```bash
curl -X DELETE https://api.0latency.ai/memories/uuid \
  -H "X-API-Key: zl_live_..."
```

**Python:**
```python
mem.delete_memory(memory_id="uuid")
```

**Note:** Deletion is permanent (not soft delete). Audit trail is preserved in logs.

---

### GET /memories/search

Search memories by keyword.

**Endpoint:** `GET /memories/search`

**Query Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `agent_id` | Yes | — | Agent identifier |
| `q` | Yes | — | Search query |
| `limit` | No | 20 | Max results (cap: 100) |

**Response (200):**
```json
[
  {
    "id": "uuid",
    "headline": "Prefers Python over JavaScript",
    "context": "When asked about programming languages, user said Python is more readable",
    "memory_type": "preference",
    "importance": 0.7,
    "confidence": 0.85,
    "created_at": "2026-03-18T..."
  }
]
```

**Example:**

```bash
curl "https://api.0latency.ai/memories/search?agent_id=my_agent&q=Python&limit=10" \
  -H "X-API-Key: zl_live_..."
```

**Python:**
```python
results = mem.search_memories(
    agent_id="my_agent",
    query="Python",
    limit=10
)

for memory in results:
    print(f"- {memory['headline']}")
```

**Search Behavior:**
- Case-insensitive
- Searches `headline` and `context` fields
- Partial matches supported
- Results sorted by relevance + recency

---

### GET /memories/export

Export all active memories for an agent (GDPR compliance).

**Endpoint:** `GET /memories/export`

**Query Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `agent_id` | Yes | Agent identifier |

**Response (200):**
```json
{
  "agent_id": "my_agent",
  "exported_at": "2026-03-26T10:00:00Z",
  "count": 42,
  "memories": [
    {
      "id": "uuid",
      "headline": "User lives in Berlin",
      "context": "Moved to Berlin in 2025, works at Spotify",
      "memory_type": "fact",
      "importance": 0.7,
      "confidence": 0.85,
      "entities": ["Berlin", "Spotify"],
      "created_at": "2026-03-20T...",
      "updated_at": "2026-03-22T..."
    }
  ]
}
```

**Example:**

```bash
curl "https://api.0latency.ai/memories/export?agent_id=my_agent" \
  -H "X-API-Key: zl_live_..." \
  > memories_export.json
```

**Python:**
```python
export = mem.export_memories(agent_id="my_agent")

# Save to file
import json
with open("memories.json", "w") as f:
    json.dump(export, f, indent=2)
```

---

### GET /memories/:id/history

Get version history for a memory.

**Endpoint:** `GET /memories/{memory_id}/history`

**Response (200):**
```json
{
  "memory_id": "uuid",
  "current": {
    "version": 3,
    "headline": "User lives in San Francisco",
    "memory_type": "fact",
    "importance": 0.8,
    "is_current": true
  },
  "history": [
    {
      "version": 2,
      "headline": "User lives in Berlin",
      "context": "Moved to Berlin in 2025",
      "memory_type": "fact",
      "importance": 0.7,
      "confidence": 0.85,
      "changed_by": "extraction",
      "change_reason": "superseded by correction: User moved to San Francisco",
      "created_at": "2026-03-20T..."
    },
    {
      "version": 1,
      "headline": "User lives in New York",
      "context": "Based in NYC",
      "memory_type": "fact",
      "importance": 0.6,
      "confidence": 0.8,
      "changed_by": "extraction",
      "change_reason": "superseded by correction",
      "created_at": "2026-03-15T..."
    }
  ],
  "total_versions": 3
}
```

**Example:**

```bash
curl https://api.0latency.ai/memories/uuid/history \
  -H "X-API-Key: zl_live_..."
```

**Use Cases:**
- Audit trail for compliance
- Understanding how facts changed
- Debugging contradictions
- Customer support history

---

## Graph API

**(Pro/Scale tier only)**

### GET /memories/graph

Get related memories via graph traversal.

**Endpoint:** `GET /memories/graph`

**Query Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `agent_id` | Yes | — | Agent identifier |
| `memory_id` | Yes | — | Starting memory UUID |
| `depth` | No | 2 | Max traversal depth (1-3) |
| `min_strength` | No | 0.3 | Min relationship strength (0-1) |

**Response (200):**
```json
{
  "root_memory_id": "uuid",
  "nodes": {
    "uuid-1": {
      "id": "uuid-1",
      "headline": "User lives in Berlin",
      "memory_type": "fact",
      "importance": 0.7,
      "confidence": 0.85,
      "sentiment": "positive"
    },
    "uuid-2": {
      "id": "uuid-2",
      "headline": "Works at Spotify",
      "memory_type": "fact",
      "importance": 0.8,
      "confidence": 0.9
    }
  },
  "edges": [
    {
      "source": "uuid-1",
      "target": "uuid-2",
      "relationship": "related_to",
      "strength": 0.72,
      "hop": 1
    }
  ],
  "total_nodes": 5,
  "total_edges": 4,
  "depth": 2
}
```

**Example:**

```bash
curl "https://api.0latency.ai/memories/graph?agent_id=my_agent&memory_id=uuid&depth=2" \
  -H "X-API-Key: zl_live_..."
```

**Python:**
```python
graph = mem.get_memory_graph(
    agent_id="my_agent",
    memory_id="uuid",
    depth=2,
    min_strength=0.3
)

print(f"Found {graph['total_nodes']} related memories")
```

**Use Cases:**
- Navigate customer relationships
- Find contextual clusters
- Visualize memory networks

---

### GET /memories/entities

List all entities extracted from memories.

**Endpoint:** `GET /memories/entities`

**Query Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `agent_id` | Yes | — | Agent identifier |
| `entity_type` | No | — | Filter by type (`person`, `company`, `location`, etc.) |
| `min_mentions` | No | 1 | Min mention count |
| `limit` | No | 50 | Max results (cap: 200) |

**Response (200):**
```json
{
  "agent_id": "my_agent",
  "entities": [
    {
      "name": "Spotify",
      "type": "company",
      "summary": "Tech company where user works",
      "mention_count": 7,
      "first_seen": "2026-03-18T...",
      "last_seen": "2026-03-25T..."
    },
    {
      "name": "Berlin",
      "type": "location",
      "summary": "User's current city",
      "mention_count": 12,
      "first_seen": "2026-03-18T...",
      "last_seen": "2026-03-26T..."
    }
  ],
  "total": 15
}
```

**Example:**

```bash
curl "https://api.0latency.ai/memories/entities?agent_id=my_agent&entity_type=person" \
  -H "X-API-Key: zl_live_..."
```

**Python:**
```python
entities = mem.list_entities(
    agent_id="my_agent",
    entity_type="person",
    limit=20
)
```

---

### GET /memories/by-entity

Get all memories mentioning a specific entity.

**Endpoint:** `GET /memories/by-entity`

**Query Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `agent_id` | Yes | — | Agent identifier |
| `entity_text` | Yes | — | Entity name to search for |
| `limit` | No | 20 | Max results (cap: 100) |

**Response (200):**
```json
{
  "entity": "Spotify",
  "agent_id": "my_agent",
  "memories": [
    {
      "id": "uuid",
      "headline": "Works at Spotify as senior engineer",
      "context": "Started at Spotify in March 2026",
      "memory_type": "fact",
      "importance": 0.7,
      "confidence": 0.9,
      "created_at": "2026-03-20T..."
    }
  ],
  "total": 3
}
```

**Example:**

```bash
curl "https://api.0latency.ai/memories/by-entity?agent_id=my_agent&entity_text=Spotify" \
  -H "X-API-Key: zl_live_..."
```

**Python:**
```python
memories = mem.get_memories_by_entity(
    agent_id="my_agent",
    entity_text="Spotify"
)
```

---

## Sentiment API

**(Pro/Scale tier only)**

### GET /memories/sentiment-summary

Get aggregate sentiment statistics.

**Endpoint:** `GET /memories/sentiment-summary`

**Query Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `agent_id` | Yes | Agent identifier |

**Response (200):**
```json
{
  "agent_id": "my_agent",
  "positive_count": 42,
  "negative_count": 8,
  "neutral_count": 23,
  "unanalyzed_count": 5,
  "total_count": 78,
  "avg_score": 0.312,
  "avg_intensity": 0.456,
  "avg_confidence": 0.823,
  "avg_recall_count": 2.4
}
```

**Example:**

```bash
curl "https://api.0latency.ai/memories/sentiment-summary?agent_id=my_agent" \
  -H "X-API-Key: zl_live_..."
```

**Python:**
```python
sentiment = mem.get_sentiment_summary(agent_id="my_agent")

print(f"Positive: {sentiment['positive_count']}")
print(f"Negative: {sentiment['negative_count']}")
print(f"Avg score: {sentiment['avg_score']:.2f}")
```

---

## Account & Usage

### GET /tenant-info

Get current tenant details.

**Endpoint:** `GET /tenant-info`

**Response (200):**
```json
{
  "id": "uuid",
  "name": "My Company",
  "plan": "pro",
  "memory_limit": 50000,
  "rate_limit_rpm": 100,
  "api_calls_count": 1542,
  "created_at": "2026-01-15T..."
}
```

**Example:**

```bash
curl https://api.0latency.ai/tenant-info \
  -H "X-API-Key: zl_live_..."
```

---

### GET /usage

Get API usage breakdown.

**Endpoint:** `GET /usage`

**Query Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `days` | 7 | Lookback period (1-90) |

**Response (200):**
```json
{
  "tenant_id": "uuid",
  "period_days": 7,
  "total_api_calls": 1542,
  "memories_stored": 487,
  "memory_limit": 50000,
  "memory_usage_pct": 0.97,
  "endpoints": [
    {
      "endpoint": "/recall",
      "calls": 850,
      "total_tokens": 412000,
      "avg_latency_ms": 1200,
      "errors": 3
    },
    {
      "endpoint": "/extract",
      "calls": 692,
      "avg_latency_ms": 2100,
      "errors": 1
    }
  ]
}
```

**Example:**

```bash
curl "https://api.0latency.ai/usage?days=30" \
  -H "X-API-Key: zl_live_..."
```

**Python:**
```python
usage = mem.get_usage(days=30)

print(f"Total calls: {usage['total_api_calls']}")
print(f"Memories: {usage['memories_stored']}/{usage['memory_limit']}")
```

---

## Webhooks

Subscribe to memory events (extraction, recall, updates).

See [Webhooks Guide](./webhooks.md) for full documentation.

---

## Admin Endpoints

**(Admin access only, localhost only)**

### POST /api-keys

Create a new tenant.

**Endpoint:** `POST /api-keys`

**Headers:** `X-Admin-Key: your_admin_key`

**Request Body:**
```json
{
  "name": "Acme Corp",
  "plan": "pro"  // free, pro, enterprise
}
```

**Response (200):**
```json
{
  "tenant_id": "uuid",
  "name": "Acme Corp",
  "api_key": "zl_live_...",
  "plan": "pro",
  "created_at": "2026-03-21T00:30:15Z",
  "memory_limit": 50000,
  "rate_limit_rpm": 100
}
```

---

## SDKs

### Python

```bash
pip install zerolatency
```

[GitHub](https://github.com/jghiglia2380/0Latency) | [PyPI](https://pypi.org/project/zerolatency/)

### JavaScript/TypeScript

```bash
npm install @0latency/sdk
```

[GitHub](https://github.com/jghiglia2380/0Latency/tree/main/sdk/typescript) | [npm](https://www.npmjs.com/package/@0latency/sdk)

---

## Support

- 💬 [Discord Community](https://discord.gg/0latency)
- 📧 Email: support@0latency.ai
- 🐛 [Report a Bug](https://github.com/jghiglia2380/0Latency/issues)
- 📖 [Documentation](https://0latency.ai/docs)

---

**Complete. Reliable. Fast.**

