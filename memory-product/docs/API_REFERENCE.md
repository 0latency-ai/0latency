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
