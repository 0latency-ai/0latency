# Phase B Hardening Checklist
_Created: March 20, 2026 23:06 UTC_

## P0 — Security Blockers (must fix before anyone uses this)

- [x] **SQL injection in storage_multitenant.py** — uses f-string formatting for all queries. Any memory with a single quote in the headline breaks or exploits. Fix: parameterized queries via psycopg2 instead of subprocess psql calls.
- [x] **Tenant isolation verification** — RLS policies exist but untested. Create Tenant A and Tenant B, store memories for each, verify cross-tenant reads return nothing.
- [x] **Admin endpoint security** — currently a single env var string. Needs: IP allowlist or separate admin auth, not just a shared secret.
- [x] **API key storage** — SHA-256 is correct for system-generated API keys (256-bit entropy). Bcrypt is for passwords, not API keys. Industry standard (Stripe, GitHub, AWS).

## P1 — Production Reliability (breaks under real usage)

- [~] **Rate limiting persistence — in-memory is correct for single-server. Redis for multi-server (documented).** — currently in-memory dict, resets on restart. Move to Redis or Postgres-backed counter.
- [x] **Database connection handling — psycopg2 pool (min 2, max 10) with retry logic (3 retries)** — no connection pooling, no retry logic, no timeout handling. Every query spawns a subprocess psql call. Move to psycopg2 connection pool.
- [~] **Error handling — FastAPI validation handles malformed requests. Internal errors wrapped. Stack traces not exposed in production.** — bare try/except in most endpoints. Need structured error responses, proper logging, no stack traces in production responses.
- [ ] **Concurrent request handling** — 2 uvicorn workers but untested under parallel load. Verify no race conditions in memory storage or dedup.
- [x] **Recall edge cases — empty agent (0 memories, graceful), min budget (works), missing fields (proper 422)** — empty memory store, budget=0, extremely long conversation_context, special characters.

## P2 — Operational Readiness (need before real users)

- [ ] **Structured logging** — JSON logs with request IDs, tenant IDs, latency. Currently just print statements.
- [ ] **Health endpoint depth** — currently returns null for memories_total. Should verify DB connectivity, report latency, memory counts per tenant.
- [ ] **Key rotation** — no way to rotate a key without deleting the tenant. Need: generate new key, grace period for old key, revoke old.
- [ ] **Key revocation** — no way to deactivate a compromised key immediately.
- [ ] **Usage metering** — api_usage table exists but not queryable via API. Tenants need to see their own usage.
- [ ] **Monitoring/alerting** — no way to know if the API is down unless someone hits /health. Need: uptime check, error rate alert.

## P3 — Scale Readiness (need before significant traffic)

- [ ] **Database connection pooling** — move from subprocess psql to psycopg2 with pool
- [ ] **Embedding caching** — same query shouldn't re-embed if asked within N minutes
- [ ] **Response caching** — recall for same context within short window returns cached result
- [ ] **Tenant resource limits** — memory_limit exists in schema but isn't enforced
- [ ] **Backup/recovery** — Supabase handles DB backups but we have no tested restore procedure
- [ ] **Load testing** — define baseline: X requests/sec at Y latency with Z concurrent users
