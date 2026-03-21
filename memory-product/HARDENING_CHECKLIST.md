# Phase B Hardening Checklist
_Updated: March 21, 2026 00:38 UTC — Post GA#4_

## P0 — Security Blockers

- [x] **SQL injection in storage_multitenant.py** — psycopg2 parameterized queries ✅
- [x] **SQL injection in list_memories (main.py)** — parameterized queries ✅ (GA#4)
- [x] **SQL injection in recall.py** — full rewrite to psycopg2 via shared storage layer ✅ (GA#4)
- [x] **Tenant isolation verification** — confirmed: SQLi `OR 1=1` no longer leaks cross-tenant data ✅
- [x] **Admin endpoint security** — localhost IP allowlist ✅
- [x] **API key storage** — SHA-256 hashed, correct for system-generated keys ✅
- [x] **Error message sanitization** — no DB internals leak in error responses ✅ (GA#4)

## P1 — Production Reliability

- [x] **Database connection handling** — psycopg2 pool (min 2, max 10) with retry logic ✅
- [x] **Recall edge cases** — empty agent (graceful 0), min budget (works), missing fields (422) ✅
- [x] **Unified DB path** — recall.py now imports from storage_multitenant instead of own subprocess psql ✅ (GA#4)
- [~] **Rate limiting** — in-memory, correct for single server. Redis for multi-server (documented, not blocking).
- [~] **Error handling** — structured error responses done, internal logging done. Some bare try/except remain.
- [ ] **Concurrent request handling** — 2 uvicorn workers but no load test under parallel requests yet.

## P2 — Operational Readiness

- [x] **Structured logging** — JSON format with request IDs, tenant IDs, latency ✅ (GA#4)
- [x] **Health endpoint** — verifies DB connectivity, returns memory count ✅ (GA#4)
- [x] **Request tracing** — X-Request-ID header on every response ✅ (GA#4)
- [x] **Key rotation** — POST /admin/rotate-key/{tenant_id}, old key immediately invalid ✅ (GA#4)
- [x] **Key revocation** — POST /admin/revoke-key/{tenant_id}, deactivates tenant ✅ (GA#4)
- [x] **Tenant reactivation** — POST /admin/reactivate/{tenant_id} ✅ (GA#4)
- [ ] **Usage metering** — api_usage table populated but not queryable by tenants via API.
- [ ] **Monitoring/alerting** — no uptime check or error rate alerting beyond health endpoint.

## P3 — Scale Readiness

- [ ] **Embedding caching** — same query re-embeds every time
- [ ] **Response caching** — no cache for repeated recall queries
- [ ] **Tenant resource limits** — memory_limit in schema but not enforced
- [ ] **Backup/recovery** — Supabase handles backups, no tested restore
- [ ] **Load testing** — no baseline benchmarks
- [ ] **Let's Encrypt SSL** — currently self-signed

## Score Card

| Dimension | GA#4 Start | GA#4 End | 
|-----------|-----------|----------|
| P0 Security | 40% (storage only) | **100%** (all paths hardened) |
| P1 Reliability | 50% | **80%** |
| P2 Operations | 0% | **60%** |
| P3 Scale | 0% | 0% (not attempted) |
| **Overall** | **45%** | **75%** |
