# Zero Latency Memory API Reference

## Base URL

```
https://164.90.156.169
```

External paths use `/api/` prefix (nginx proxy). Internal/direct: port 8420 without prefix.

## Authentication

All endpoints except `/health` and `/dashboard` require:

```
X-API-Key: zl_live_<32-character-string>
```

Admin endpoints require `X-Admin-Key` header and must originate from localhost.

---

## Memory Operations

### POST /extract

Extract and store memories from a conversation turn. Enforces memory limit per tenant plan.

**Request:**
```json
{
  "agent_id": "string",           // Required
  "human_message": "string",      // Required
  "agent_message": "string",      // Required
  "session_key": "string",        // Optional
  "turn_id": "string"             // Optional
}
```

**Response (200):**
```json
{
  "memories_stored": 3,
  "memory_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

**Errors:** `401` invalid key, `429` rate limit or memory limit reached, `500` extraction failed.

**Example:**
```bash
curl -X POST https://164.90.156.169/api/extract \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "human_message": "I just moved to Berlin and started at Spotify",
    "agent_message": "Congrats on the move and the new role!"
  }'
```

---

### POST /extract/batch

Extract memories from multiple conversation turns in a single request. Up to 50 turns per batch.

**Request Body:**
```json
{
  "turns": [
    {
      "human_message": "I just moved to Berlin",
      "agent_message": "Congrats on the move!",
      "agent_id": "my_agent",
      "session_key": "session_123",
      "turn_id": "turn_1"
    },
    {
      "human_message": "Started a new job at Spotify",
      "agent_message": "Great company!",
      "agent_id": "my_agent",
      "session_key": "session_123",
      "turn_id": "turn_2"
    }
  ]
}
```

**Response (200):**
```json
{
  "turns_processed": 2,
  "memories_stored": 3,
  "memory_ids": ["uuid1", "uuid2", "uuid3"],
  "errors": null
}
```

---

### GET /memories/export

Export all active memories for an agent as JSON. For data portability and GDPR compliance.

**Query Parameters:**
- `agent_id` (required): Agent identifier

**Response (200):**
```json
{
  "agent_id": "my_agent",
  "exported_at": "2026-03-21T05:00:00Z",
  "count": 42,
  "memories": [
    {
      "id": "uuid",
      "headline": "User lives in Berlin",
      "context": "Moved to Berlin recently, started at Spotify",
      "memory_type": "fact",
      "importance": 0.7,
      "entities": ["Berlin", "Spotify"],
      "created_at": "2026-03-20T..."
    }
  ]
}
```

---

### POST /recall

Retrieve contextually relevant memories scored by semantic similarity, recency, importance, and access frequency.

**Request:**
```json
{
  "agent_id": "string",            // Required
  "conversation_context": "string", // Required
  "budget_tokens": 4000,           // Optional (500-16000)
  "dynamic_budget": false          // Optional
}
```

**Response (200):**
```json
{
  "context_block": "### Agent Identity\n...\n### Relevant Context\n...",
  "memories_used": 12,
  "tokens_used": 1850
}
```

**Scoring:** Composite of semantic similarity (0.4), recency decay (0.35), importance (0.15), access frequency (0.1). Type bonuses: identity ×1.5, correction/preference ×1.3, recent decisions ×1.2.

**Example:**
```bash
curl -X POST https://164.90.156.169/api/recall \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "conversation_context": "User asking about music for their commute",
    "budget_tokens": 2000
  }'
```

---

### GET /memories

List memories with optional filtering.

**Query Parameters:**
| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| agent_id | Yes | — | Agent identifier |
| limit | No | 50 | Max results (cap: 200) |
| memory_type | No | — | Filter: fact, preference, decision, relationship, task, correction, identity |

**Response (200):**
```json
[
  {
    "id": "uuid",
    "headline": "Lives in Berlin",
    "memory_type": "fact",
    "importance": 0.8,
    "created_at": "2026-03-20T22:15:30.123+00:00"
  }
]
```

---

### GET /memories/search

Search memories by keyword. Tenant-isolated.

**Query Parameters:**
| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| agent_id | Yes | — | Agent identifier |
| q | Yes | — | Search query (matched against headline + context) |
| limit | No | 20 | Max results (cap: 100) |

**Response (200):**
```json
[
  {
    "id": "uuid",
    "headline": "Pricing set to $20/student",
    "memory_type": "decision",
    "importance": 0.8,
    "created_at": "2026-03-20T22:15:30+00:00",
    "context": "New contracts start at $20/student, replacing the $16 legacy price."
  }
]
```

---

### DELETE /memories/{memory_id}

Delete a specific memory. Cascades to entity index and edges. Audit-logged.

**Response (200):**
```json
{"deleted": "uuid"}
```

**Errors:** `404` memory not found (or wrong tenant).

---

## Account & Usage

### GET /tenant-info

Current tenant details.

**Response (200):**
```json
{
  "id": "uuid",
  "name": "My Company",
  "plan": "pro",
  "memory_limit": 50000,
  "rate_limit_rpm": 100,
  "api_calls_count": 1542
}
```

### GET /usage

API usage breakdown for current tenant.

**Query Parameters:**
| Param | Default | Description |
|-------|---------|-------------|
| days | 7 | Lookback period |

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
    }
  ]
}
```

### GET /dashboard

Browser-based tenant dashboard. No auth required to load — authenticates via API key input in the UI.

---

## Graph API (Pro/Scale tier)

### GET /memories/graph

Get related memories via graph traversal from a specific memory. Returns nodes (memories) and edges (relationships) within the specified depth.

**Query Parameters:**
| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| agent_id | Yes | — | Agent identifier |
| memory_id | Yes | — | Starting memory UUID |
| depth | No | 2 | Max traversal depth (1-3) |
| min_strength | No | 0.3 | Minimum relationship strength (0-1) |

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
      "sentiment": "positive",
      "sentiment_score": 0.6,
      "created_at": "2026-03-20T..."
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
curl "https://api.0latency.ai/memories/graph?agent_id=my_agent&memory_id=UUID&depth=2&min_strength=0.3" \
  -H "X-API-Key: zl_live_..."
```

**Errors:** `403` requires Pro/Scale tier, `404` memory not found.

---

## Entity API (Pro/Scale tier)

### GET /memories/entities

List all entities extracted from an agent's memories with mention counts and type information.

**Query Parameters:**
| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| agent_id | Yes | — | Agent identifier |
| entity_type | No | — | Filter by entity type (person, company, location, etc.) |
| min_mentions | No | 1 | Minimum mention count |
| limit | No | 50 | Max results (cap: 200) |

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
    }
  ],
  "total": 15
}
```

**Example:**
```bash
curl "https://api.0latency.ai/memories/entities?agent_id=my_agent&entity_type=person&limit=20" \
  -H "X-API-Key: zl_live_..."
```

---

### GET /memories/by-entity

Get all memories mentioning a specific entity.

**Query Parameters:**
| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| agent_id | Yes | — | Agent identifier |
| entity_text | Yes | — | Entity name to search for |
| limit | No | 20 | Max results (cap: 100) |

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
      "sentiment": "positive",
      "sentiment_score": 0.6,
      "created_at": "2026-03-20T..."
    }
  ],
  "total": 3
}
```

**Example:**
```bash
curl "https://api.0latency.ai/memories/by-entity?agent_id=my_agent&entity_text=Spotify&limit=10" \
  -H "X-API-Key: zl_live_..."
```

---

## Sentiment API (Pro/Scale tier)

### GET /memories/sentiment-summary

Get aggregate sentiment statistics for an agent's memories. Returns counts, averages, and distribution.

**Query Parameters:**
| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| agent_id | Yes | — | Agent identifier |

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

### Sentiment Filters on GET /memories

The `/memories` list endpoint supports sentiment filtering (Pro/Scale tier):

| Param | Description |
|-------|-------------|
| sentiment | Filter by sentiment: `positive`, `negative`, `neutral` |
| min_sentiment_score | Minimum sentiment score (-1.0 to 1.0) |
| max_sentiment_score | Maximum sentiment score (-1.0 to 1.0) |
| min_confidence | Minimum confidence score (0.0 to 1.0) |

**Example:**
```bash
# Get all positive memories with high confidence
curl "https://api.0latency.ai/memories?agent_id=my_agent&sentiment=positive&min_confidence=0.8" \
  -H "X-API-Key: zl_live_..."
```

---

## Confidence Scoring

Confidence scores (0.0–1.0) represent how trustworthy a memory is. Confidence is calculated and updated automatically:

- **Initial confidence:** Set during extraction based on the clarity and specificity of the source content (typically 0.7–0.9).
- **Recall boost:** Each time a memory is recalled and used, confidence increases slightly (up to 0.95 max). Frequently-recalled memories are considered more reliable.
- **Formula:** `confidence = min(0.95, current_confidence + 0.05 × (1 - min(recall_count, 10) / 10))`
- **Filtering:** Use `min_confidence` on `GET /memories` to filter by confidence threshold.

**Example — only high-confidence memories:**
```bash
curl "https://api.0latency.ai/memories?agent_id=my_agent&min_confidence=0.85" \
  -H "X-API-Key: zl_live_..."
```

---

## Memory Versioning

Memories evolve over time. When a memory is updated, corrected, or reinforced, its previous state is automatically saved to a version history. This provides a full audit trail of how knowledge changed.

### How it works:
1. **On reinforcement:** When a duplicate memory is detected, the existing memory's state is snapshotted before reinforcement.
2. **On correction/contradiction:** When a new memory contradicts an existing one, the old memory is snapshotted before being superseded.
3. **On manual update:** When you `PUT /memories/{id}`, the current state is snapshotted before applying changes.

### GET /memories/{memory_id}/history

Get the full version history for a specific memory.

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
      "created_at": "2026-03-20T...",
      "diff_summary": null
    },
    {
      "version": 1,
      "headline": "User lives in New York",
      "context": "Based in NYC",
      "memory_type": "fact",
      "importance": 0.6,
      "confidence": 0.8,
      "changed_by": "extraction",
      "change_reason": "superseded by correction: User lives in Berlin",
      "created_at": "2026-03-15T...",
      "diff_summary": null
    }
  ],
  "total_versions": 3
}
```

**Example:**
```bash
curl "https://api.0latency.ai/memories/UUID/history" \
  -H "X-API-Key: zl_live_..."
```

### PUT /memories/{memory_id}

Update a memory. Automatically creates a version snapshot before updating.

**Request Body:**
```json
{
  "headline": "Updated headline",
  "importance": 0.9,
  "memory_type": "decision"
}
```

**Allowed fields:** `headline`, `context`, `full_content`, `memory_type`, `importance`, `confidence`

**Response (200):**
```json
{
  "updated": "uuid",
  "version": "incremented"
}
```

**Example:**
```bash
curl -X PUT "https://api.0latency.ai/memories/UUID" \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{"headline": "User lives in San Francisco", "importance": 0.9}'
```

---

## System

### GET /health

No auth. Verifies DB connectivity.

**Response (200):**
```json
{
  "status": "ok",           // "ok" or "degraded"
  "version": "0.1.0",
  "timestamp": "2026-03-21T00:36:08.749Z",
  "memories_total": 562     // null if DB unreachable
}
```

---

## Admin Endpoints

All require `X-Admin-Key` header. Only accessible from localhost (127.0.0.1).

### POST /api-keys

Create a new tenant.

**Request:**
```json
{
  "name": "Acme Corp",
  "plan": "pro"          // free, pro, enterprise
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

### POST /admin/rotate-key/{tenant_id}

Generate new API key. Old key immediately invalidated.

**Response (200):**
```json
{
  "tenant_id": "uuid",
  "new_api_key": "zl_live_...",
  "message": "Key rotated. Old key is immediately invalid."
}
```

### POST /admin/revoke-key/{tenant_id}

Deactivate tenant. API key stops working immediately.

**Response (200):**
```json
{
  "tenant_id": "uuid",
  "status": "revoked",
  "message": "Tenant deactivated. API key no longer valid."
}
```

### POST /admin/reactivate/{tenant_id}

Re-enable a previously revoked tenant.

**Response (200):**
```json
{
  "tenant_id": "uuid",
  "status": "active"
}
```

### GET /admin/tenants

List all tenants with status and usage counts.

---

## Rate Limits

Redis-backed, survives service restarts. Per-tenant, 60-second sliding window.

| Plan | Requests/Min | Memory Limit |
|------|-------------|--------------|
| Free | 20 | 1,000 |
| Pro | 100 | 50,000 |
| Enterprise | 500 | 500,000 |

**429 Response:**
```json
{"detail": "Rate limit exceeded (100/min). Try again in 45s."}
```

---

## Response Headers

All responses include:
- `X-Request-ID`: Unique request identifier for debugging

---

## Error Responses

All errors return JSON with `detail` field. No internal details (DB errors, stack traces) are exposed.

| Code | Meaning |
|------|---------|
| 401 | Invalid/missing API key or inactive tenant |
| 403 | Admin endpoint called from non-localhost |
| 404 | Tenant not found (admin endpoints) |
| 422 | Validation error (missing/invalid fields) |
| 429 | Rate limit or memory limit exceeded |
| 500 | Internal error (generic message only) |

---

## Interactive Docs

Swagger UI: `https://164.90.156.169/docs`

---

*Updated March 21, 2026 — v0.1.0*
