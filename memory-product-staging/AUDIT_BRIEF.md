# Zero Latency Memory API — Code Audit Brief

## What This Is
A multi-tenant REST API for AI agent memory: automatic extraction from conversations, structured Postgres storage with pgvector, and budget-aware semantic recall. Built in ~48 hours.

## Architecture
```
Client → nginx (SSL terminator) → FastAPI (uvicorn, 2 workers) → Postgres (Supabase, RLS)
                                       ↕
                                   Redis (rate limiting, caching)
```

## Codebase Overview (~12,500 lines Python)

### Critical Path (audit these thoroughly)
- `api/main.py` (794 lines) — FastAPI app. 18 endpoints. Auth, rate limiting, CRUD, admin.
- `src/storage_multitenant.py` (715 lines) — Tenant-isolated storage. psycopg2 connection pool, RLS, embedding generation, entity graph.
- `src/recall.py` (479 lines) — 4-signal composite scoring (semantic + recency + importance + access). Budget-aware tiered loading. Keyword fallback search.
- `src/extraction.py` (447 lines) — Gemini Flash 2.0 extraction pipeline. JSON schema enforcement. Multi-turn context window.

### Supporting Modules (audit for patterns, not line-by-line)
- `src/config.py` (49 lines) — Centralized env-var config, no hardcoded secrets
- `src/db.py` (58 lines) — Shared psycopg2 module for utility scripts
- `src/feedback.py` (196 lines) — Recall feedback loop (reinforce/demote)
- `src/negative_recall.py` (167 lines) — Gap detection ("know what you don't know")
- `src/compaction.py` (214 lines) — Memory clustering + summarization at scale
- `src/handoff.py` (366 lines) — Session state tracking (Layer 2)
- `src/session_processor.py` (367 lines) — Daemon that watches conversation transcripts

### Skill Scripts (ships to users via ClawHub)
- `skill/scripts/` — Self-contained versions of core modules for plugin distribution
- Should contain ZERO hardcoded credentials (verified clean as of March 21)

### Tests
- `tests/test_api_full.py` (565 lines) — 24 endpoint tests, all passing
- `test_*.py` (root) — Unit tests for individual components

## What's Already Been Hardened
1. ✅ All API queries use psycopg2 parameterized queries (SQL injection tested)
2. ✅ Row Level Security on Postgres (tenant isolation)
3. ✅ API key auth (SHA-256 hashed, `zl_live_` prefix)
4. ✅ Rate limiting (Redis-backed, in-memory fallback)
5. ✅ CORS locked down (not wildcard)
6. ✅ Request size limits (50K message, 128 agent_id, 500 search query)
7. ✅ Admin endpoints restricted to localhost
8. ✅ Zero hardcoded credentials in source (env-var only)
9. ✅ Bandit scan: 0 High, 0 Medium on critical path
10. ✅ HNSW vector index (was doing sequential scans)
11. ✅ Structured JSON logging with request IDs
12. ✅ Key rotation, revocation, and reactivation endpoints
13. ✅ Embedding + auth + response caching

## What to Focus The Audit On

### Security (P0)
- Is the tenant isolation actually airtight? Can tenant A access tenant B's data?
- Are there any remaining SQL injection vectors (especially the keyword search in recall.py line ~194)?
- Is the API key generation (uuid4 + secrets.token_hex) cryptographically sufficient?
- Are error messages leaking internal state?

### Architecture (P1)
- Is the connection pool management correct? (ThreadedConnectionPool in async FastAPI)
- Is there a race condition in the Redis rate limiter?
- Should extraction be async/background instead of synchronous in the request path?
- Is the psycopg2 ↔ async FastAPI combination correct, or should we use asyncpg?

### Scale Concerns (P2)
- Recall does 4 DB queries per call (semantic, high-importance, recent, keyword). Too many?
- Entity graph (memory_edges) does N+1 queries in the momentum loop. Problem at scale?
- Connection pool: min=2, max=10. Right for 2 workers?
- What happens when a tenant has 100K memories? 1M?

### Code Quality (P3)
- Are there dead code paths or unused imports?
- Is the `skill/scripts/` directory too much duplication of `src/`?
- Are the try/except patterns appropriate (7 Low findings from Bandit)?
- Type annotations completeness

## Database Schema
```sql
-- Core tables (memory_service schema)
memories          -- Main store. pgvector embeddings, RLS by tenant_id
agent_config      -- Per-agent scoring weights, identity, user profile
session_handoffs  -- Conversation state snapshots
memory_edges      -- Entity relationship graph
entity_index      -- Entity → memory mapping
topic_coverage    -- "What do we know about" tracking
memory_clusters   -- Compaction summaries
memory_audit_log  -- Change tracking
api_keys          -- Tenant auth (SHA-256 hashed)
tenants           -- Multi-tenant config
```

## Running the Audit
```bash
cd /root/.openclaw/workspace/memory-product

# Tests
python3 -m pytest tests/ -v

# Bandit security scan
python3 -m bandit -r api/ src/config.py src/db.py src/feedback.py src/negative_recall.py src/compaction.py src/handoff.py src/recall.py src/storage_multitenant.py src/extraction.py -q

# API health
curl -sk https://164.90.156.169/health | python3 -m json.tool

# Credential check (should return 0)
grep -rn "AIzaSy\|jcYlwEhuHN9VcOuj\|fuojxlabvhtmysbsixdn" --include="*.py" | grep -v __pycache__ | wc -l
```

## Known Limitations
- SSL uses self-signed cert (no domain pointing here yet)
- No Docker runtime on server (Dockerfile untested in-situ)
- 26 utility scripts still use subprocess psql (non-API, not security-critical)
- No load testing done yet
- psycopg2 (sync) in async FastAPI — works but not optimal at scale
