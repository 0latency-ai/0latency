# Zero Latency Memory — Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        API Layer                              │
│   FastAPI + Uvicorn (2 workers) + nginx reverse proxy         │
│   Auth: API key (SHA-256 hashed) → tenant isolation           │
│   Rate limiting: Redis-backed (in-memory fallback)            │
└──────────────┬────────────────────────────┬───────────────────┘
               │                            │
   ┌───────────▼───────────┐    ┌───────────▼───────────┐
   │    Extraction Layer    │    │     Recall Layer       │
   │  Gemini Flash 2.0      │    │  Composite scoring:    │
   │  → Anthropic fallback   │    │  semantic + recency +  │
   │  → OpenAI fallback      │    │  importance + access   │
   │                         │    │  + criteria re-ranking │
   │  Multi-turn inference   │    │  + tiered loading      │
   │  Contradiction detect   │    │  (L0 headline /        │
   │  Structured list pres   │    │   L1 context /         │
   │  Custom schema support  │    │   L2 full content)     │
   └───────────┬─────────────┘    └──────────┬─────────────┘
               │                              │
   ┌───────────▼──────────────────────────────▼─────────────┐
   │                   Storage Layer                         │
   │   Supabase Postgres + pgvector (768-dim embeddings)     │
   │   Row-Level Security (tenant isolation)                 │
   │   Connection pool (psycopg2, 2-10 threads)              │
   │   100% parameterized queries                            │
   └──────────┬──────────┬──────────┬────────────────────────┘
              │          │          │
   ┌──────────▼──┐ ┌─────▼─────┐ ┌─▼──────────────┐
   │ Graph Layer  │ │ Versioning│ │ Webhooks       │
   │ Entity nodes │ │ Snapshots │ │ HMAC-signed    │
   │ Relationships│ │ Changelog │ │ Async delivery │
   │ Recursive CTE│ │ Diff track│ │ Retry + log    │
   └──────────────┘ └───────────┘ └────────────────┘
```

## Database Schema (memory_service)

### Core Tables
| Table | Purpose | Records |
|-------|---------|---------|
| `memories` | Primary memory store with embeddings | ~600+ |
| `entity_index` | Entity → memory mapping | Auto-populated |
| `memory_edges` | Memory → memory relationships | Auto-populated |
| `session_handoffs` | Session continuity records | Per session end |
| `agent_config` | Per-agent scoring weights | Per agent |
| `memory_audit_log` | Full audit trail | Every operation |

### Multi-Tenant Infrastructure
| Table | Purpose |
|-------|---------|
| `tenants` | Tenant registry with hashed API keys |
| `api_usage` | Per-endpoint usage tracking |

### Graph Memory (new)
| Table | Purpose |
|-------|---------|
| `entity_nodes` | Named entities with types, summaries, mention counts |
| `entity_relationships` | Entity → entity edges with relationship types |

### Feature Tables (new)
| Table | Purpose |
|-------|---------|
| `memory_versions` | Full changelog per memory |
| `webhooks` | Registered webhook endpoints |
| `webhook_deliveries` | Delivery log with status tracking |
| `recall_criteria` | Custom scoring attributes |
| `memory_criteria_scores` | Cached criteria scores per memory |
| `extraction_schemas` | Developer-defined JSON Schema templates |
| `organizations` | Org registry for team memory |
| `org_memories` | Organization-scoped shared memories |

### Security
- **Row-Level Security** on all tenant-scoped tables
- **Parameterized queries** throughout (zero f-string SQL)
- **API key hashing** (SHA-256, Stripe pattern)
- **Admin endpoints** restricted to localhost
- **Error messages** never expose database internals
- **Rate limiting** survives restarts (Redis-backed)

## API Endpoints (42 total)

### Core (6)
- `POST /extract` — Extract memories from a conversation turn
- `POST /recall` — Recall relevant memories with composite scoring
- `GET /memories` — List memories with pagination + type filter
- `GET /memories/search` — Keyword search across memories
- `DELETE /memories/{id}` — Delete a specific memory
- `GET /memories/export` — Full data export (GDPR)

### Graph Memory (4)
- `GET /graph/entity` — Subgraph with multi-hop traversal
- `GET /graph/entities` — List known entities
- `GET /graph/entity/memories` — Memories for an entity
- `GET /graph/path` — Shortest path between entities

### Memory Versioning (2)
- `GET /memories/{id}/history` — Full version changelog
- `PUT /memories/{id}` — Update with auto-snapshot

### Webhooks (3)
- `POST /webhooks` — Register webhook
- `GET /webhooks` — List webhooks
- `DELETE /webhooks/{id}` — Remove webhook

### Criteria (3)
- `POST /criteria` — Create scoring criteria
- `GET /criteria` — List criteria
- `DELETE /criteria/{id}` — Remove criteria

### Schemas (3)
- `POST /schemas` — Create extraction schema
- `GET /schemas` — List schemas
- `DELETE /schemas/{id}` — Remove schema

### Batch Operations (3)
- `POST /extract/batch` — Multi-turn extraction
- `POST /memories/batch-delete` — Multi-delete
- `POST /memories/batch-search` — Multi-query search

### Organization Memory (5)
- `POST /org/memories` — Store org-level memory
- `GET /org/memories` — List org memories
- `GET /org/memories/recall` — Semantic search org memories
- `DELETE /org/memories/{id}` — Delete org memory
- `POST /memories/{id}/promote` — Promote to org level

### Admin (6)
- `POST /api-keys` — Create tenant
- `POST /admin/rotate-key/{id}` — Rotate API key
- `POST /admin/revoke-key/{id}` — Revoke access
- `POST /admin/reactivate/{id}` — Reactivate tenant
- `GET /admin/tenants` — List all tenants
- `GET /tenant-info` — Current tenant info

### Utility (4)
- `GET /health` — Health check with DB/Redis status
- `GET /usage` — Usage stats by endpoint
- `GET /dashboard` — Web dashboard
- `GET /api/v1/*` — Versioned API path (nginx proxy)

## Differentiation vs. Mem0

| Feature | Mem0 | Zero Latency | Advantage |
|---------|------|-------------|-----------|
| Temporal dynamics (decay/reinforcement) | ❌ | ✅ | **ZL** |
| Proactive context injection | ❌ (pull only) | ✅ | **ZL** |
| Context budget management | ❌ | ✅ | **ZL** |
| Negative recall ("I don't know") | ❌ | ✅ | **ZL** |
| Graph memory | ✅ (Neo4j, Pro $249/mo) | ✅ (Postgres CTEs, all plans) | **ZL** — no extra infra |
| Criteria re-ranking | ✅ | ✅ (no extra LLM call) | **ZL** — cheaper |
| Memory versioning | ✅ | ✅ | Parity |
| Webhooks | ✅ | ✅ (HMAC + delivery log) | Parity |
| Org memory | ✅ | ✅ | Parity |
| Custom schemas | ✅ | ✅ | Parity |
| Batch operations | ✅ | ✅ | Parity |
| Python SDK | ✅ | ✅ | Parity |
| SOC 2 | ✅ | ❌ | Mem0 |
| 50K GitHub stars | ✅ | ❌ | Mem0 |
| TypeScript SDK | ✅ | ❌ (planned) | Mem0 |

## Test Coverage

- **147 tests** across 2 test suites
- **86 existing** (core API, auth, SQL injection, tenant isolation, pagination)
- **61 new** (graph, webhooks, versioning, criteria, schemas, org, batch, SDK, security regression)
- **0 failures**

## Infrastructure

- **Server:** DigitalOcean 2GB, Ubuntu 24.04
- **Database:** Supabase Postgres (Session Pooler, IPv4)
- **Embeddings:** Gemini (768-dim, $0.00/1K requests free tier)
- **Cache/Rate Limiting:** Redis 7
- **Reverse Proxy:** nginx with TLS 1.2/1.3
- **Process Manager:** systemd (zerolatency-api.service)
- **Monitoring:** Structured JSON logging, request IDs, per-endpoint latency tracking
