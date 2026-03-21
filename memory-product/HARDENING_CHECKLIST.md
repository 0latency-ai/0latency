# Phase B Hardening Checklist
_Updated: March 21, 2026 00:42 UTC — Post GA#4 sprint_

## P0 — Security ✅ COMPLETE

- [x] SQL injection in storage_multitenant.py — psycopg2 parameterized queries
- [x] SQL injection in list_memories (main.py) — parameterized queries
- [x] SQL injection in recall.py — full rewrite to psycopg2 via shared storage layer
- [x] Tenant isolation — confirmed cross-tenant SQLi vector closed
- [x] Admin endpoint security — localhost IP allowlist
- [x] API key storage — SHA-256 hashed
- [x] Error message sanitization — no DB internals leak

## P1 — Reliability ✅ MOSTLY COMPLETE

- [x] Database connection handling — psycopg2 pool (min 2, max 10) + retry (3x)
- [x] Recall edge cases — empty agent, min budget, missing fields all handled
- [x] Unified DB path — recall imports from storage_multitenant
- [x] Concurrent requests — load tested: 10 health, 5 recall, 3 extract parallel — all 200
- [x] Memory limit enforcement — 429 when tenant hits limit
- [~] Rate limiting — in-memory, correct for single server. Redis documented for multi.
- [~] Error handling — structured responses, some bare try/except remain

## P2 — Operations ✅ MOSTLY COMPLETE

- [x] Structured logging — JSON with request ID, tenant, latency
- [x] Health endpoint — verifies DB connectivity, returns memory count
- [x] Request tracing — X-Request-ID on every response
- [x] Key rotation — /admin/rotate-key/{id}
- [x] Key revocation — /admin/revoke-key/{id}
- [x] Tenant reactivation — /admin/reactivate/{id}
- [x] Usage metering — GET /usage with per-endpoint breakdown, memory usage %
- [ ] Monitoring/alerting — no uptime check beyond health endpoint

## P3 — Scale (not attempted — Seb decision)

- [ ] Embedding caching
- [ ] Response caching
- [ ] Let's Encrypt SSL
- [ ] Backup/recovery testing
- [ ] Benchmarks (baseline: 10 concurrent health in 2s, 5 concurrent recall in 5s)

## Score

| Dimension | GA#4 Start | GA#4 End |
|-----------|-----------|----------|
| P0 Security | 40% | **100%** |
| P1 Reliability | 50% | **90%** |
| P2 Operations | 0% | **75%** |
| P3 Scale | 0% | 0% |
| **Overall** | **45%** | **85%** |

## Endpoints (complete inventory)

| Method | Path | Auth | Status |
|--------|------|------|--------|
| POST | /extract | API key | ✅ Hardened |
| POST | /recall | API key | ✅ Hardened |
| GET | /memories | API key | ✅ Hardened |
| GET | /health | None | ✅ DB-verified |
| GET | /tenant-info | API key | ✅ |
| GET | /usage | API key | ✅ New |
| POST | /api-keys | Admin | ✅ Localhost only |
| POST | /admin/rotate-key/{id} | Admin | ✅ New |
| POST | /admin/revoke-key/{id} | Admin | ✅ New |
| POST | /admin/reactivate/{id} | Admin | ✅ New |
| GET | /admin/tenants | Admin | ✅ Localhost only |
| GET | /docs | None | ✅ Swagger UI |
