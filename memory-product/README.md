# ⚡ Zero Latency Memory

Structured memory extraction, storage, and recall for AI agents. Your agent remembers everything — across sessions, compactions, and restarts.

## The Problem

Every AI agent has the same memory problem: context windows fill up, compaction loses important details, and the agent wakes up each session as a blank slate. We measured a **36% loss rate** on critical decisions and facts after a single compaction event.

## The Solution

Zero Latency Memory extracts structured memories from conversations in real-time, stores them with semantic embeddings, and recalls the most relevant ones on demand — all within a token budget you control.

### Key Capabilities

- **Automatic extraction** — facts, preferences, decisions, relationships, corrections identified from natural conversation
- **Smart recall** — composite scoring: semantic similarity (0.4) + recency (0.35) + importance (0.15) + access frequency (0.1)
- **Contradiction detection** — new info automatically supersedes old info
- **Multi-tenant** — full Row Level Security isolation between tenants
- **Budget-aware** — never exceeds your token limit; tiered loading (L0 headlines, L1 full context)
- **Self-correcting** — corrections cascade, old facts are superseded, not deleted

## Quick Start

```bash
# Store a memory
curl -X POST https://your-server/api/v1/extract \
  -H "X-API-Key: zl_live_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "human_message": "I live in Portland and my dog is named Kona",
    "agent_message": "Portland is great! What breed is Kona?"
  }'

# Recall relevant context
curl -X POST https://your-server/api/v1/recall \
  -H "X-API-Key: zl_live_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "conversation_context": "pet-friendly restaurant recommendations",
    "budget_tokens": 1000
  }'
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /extract | API key | Extract memories from a conversation turn |
| POST | /extract/batch | API key | Extract from multiple turns at once (up to 50) |
| POST | /recall | API key | Recall relevant memories within token budget |
| GET | /memories | API key | List memories with pagination and type filter |
| GET | /memories/search | API key | Search memories by keyword |
| GET | /memories/export | API key | Export all memories as JSON (GDPR) |
| DELETE | /memories/{id} | API key | Delete a specific memory |
| GET | /usage | API key | Per-endpoint usage breakdown |
| GET | /tenant-info | API key | Current tenant details |
| GET | /health | None | DB connectivity + pool + Redis status |
| GET | /dashboard | None | Browser-based tenant dashboard |

### Admin Endpoints (localhost only)

| Method | Path | Description |
|--------|------|-------------|
| POST | /api-keys | Create tenant |
| POST | /admin/rotate-key/{id} | Rotate API key (old key immediately invalid) |
| POST | /admin/revoke-key/{id} | Revoke access |
| POST | /admin/reactivate/{id} | Restore access |
| GET | /admin/tenants | List all tenants |

## Architecture

```
Client → nginx (HTTPS + /api/v1/) → FastAPI (uvicorn, 2 workers)
                                        ↓
                                   psycopg2 pool (2-10 conns)
                                        ↓
                                   Supabase PostgreSQL + pgvector
                                        ↓
                                   Row Level Security per tenant
```

### Security

- **SQL injection**: Parameterized queries (psycopg2) on all paths — storage, recall, API layer
- **Tenant isolation**: PostgreSQL RLS + verified via cross-tenant penetration test
- **Credentials**: Environment variables only, zero hardcoded secrets
- **Auth**: SHA-256 hashed API keys with Redis-cached lookups (30s TTL)
- **Rate limiting**: Redis-backed, survives restarts, per-tenant
- **CORS**: Configurable origin allowlist (not `*`)
- **Input validation**: Pydantic models with length limits on all fields
- **Error sanitization**: No DB internals in error responses
- **Swagger**: Restricted to localhost via nginx
- **Admin endpoints**: Localhost IP allowlist + admin key

### Performance

- **Embedding cache**: 5-minute TTL, 500-entry LRU (37% faster repeat queries)
- **Response cache**: 1-minute TTL for identical recall queries
- **Tenant auth cache**: 30-second Redis-backed (eliminates DB lookup per request)
- **Connection pool**: psycopg2 ThreadedConnectionPool (min 2, max 10)
- **Concurrency**: Load tested with 10 parallel health, 5 parallel recall, 3 parallel extract

## Plans

| | Free | Pro | Enterprise |
|---|---|---|---|
| Memories | 1,000 | 50,000 | 500,000 |
| Rate limit | 20/min | 100/min | 500/min |
| Price | $0 | $19/mo | Custom |

## Running Tests

```bash
python3 tests/test_api_full.py
# 58 tests: health, auth, CRUD, recall, SQL injection, tenant isolation,
# key lifecycle, validation, dashboard — all automated
```

## Docs

- [Quickstart](docs/QUICKSTART.md)
- [API Reference](docs/API_REFERENCE.md)
- [Dashboard](https://your-server/dashboard)

---

*Built from a compaction failure. Hardened through four gap analyses. Shipping this week.*
