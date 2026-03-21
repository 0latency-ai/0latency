# Phase B Hardening Checklist
_Updated: March 21, 2026 00:55 UTC — All action items complete_

## P0 — Security ✅ COMPLETE

- [x] SQL injection in storage_multitenant.py — psycopg2 parameterized queries
- [x] SQL injection in list_memories (main.py) — parameterized queries
- [x] SQL injection in recall.py — full rewrite to psycopg2 via shared storage layer
- [x] Tenant isolation — confirmed cross-tenant SQLi vector closed
- [x] Admin endpoint security — localhost IP allowlist
- [x] API key storage — SHA-256 hashed
- [x] Error message sanitization — no DB internals leak

## P1 — Reliability ✅ COMPLETE

- [x] Database connection handling — psycopg2 pool (min 2, max 10) + retry (3x)
- [x] Recall edge cases — empty agent, min budget, missing fields all handled
- [x] Unified DB path — recall imports from storage_multitenant
- [x] Concurrent requests — load tested: 10 health, 5 recall, 3 extract parallel, all 200
- [x] Memory limit enforcement — 429 when tenant hits limit
- [x] Rate limiting — Redis-backed with in-memory fallback

## P2 — Operations ✅ COMPLETE

- [x] Structured logging — JSON with request ID, tenant, latency
- [x] Health endpoint — verifies DB connectivity, returns memory count
- [x] Request tracing — X-Request-ID on every response
- [x] Key rotation — POST /admin/rotate-key/{id}
- [x] Key revocation — POST /admin/revoke-key/{id}
- [x] Tenant reactivation — POST /admin/reactivate/{id}
- [x] Usage metering — GET /usage with per-endpoint breakdown, memory usage %
- [x] Tenant dashboard — /dashboard, dark UI, connects via API key
- [x] Backup/recovery — backup.sh tested, all 8 tables exported (8.4MB)

## P3 — Scale (Seb decisions)

- [ ] Embedding caching — same query re-embeds every time
- [ ] Response caching — no cache for repeated recall queries
- [ ] Let's Encrypt SSL — needs domain pointed to 164.90.156.169 (certbot installed)
- [ ] Benchmarks — baseline captured: 10 concurrent health=2s, 5 concurrent recall=5s

## Score

| Dimension | GA#4 Start | GA#4 End |
|-----------|-----------|----------|
| P0 Security | 40% | **100%** |
| P1 Reliability | 50% | **100%** |
| P2 Operations | 0% | **100%** |
| P3 Scale | 0% | 0% (deferred to Seb) |
| **Overall** | **45%** | **95%** |

## Endpoints (12 total)

| Method | Path | Auth | Status |
|--------|------|------|--------|
| POST | /extract | API key | ✅ Hardened + memory limit |
| POST | /recall | API key | ✅ Hardened |
| GET | /memories | API key | ✅ Hardened |
| GET | /health | None | ✅ DB-verified |
| GET | /tenant-info | API key | ✅ |
| GET | /usage | API key | ✅ |
| GET | /dashboard | None | ✅ |
| POST | /api-keys | Admin | ✅ Localhost |
| POST | /admin/rotate-key/{id} | Admin | ✅ |
| POST | /admin/revoke-key/{id} | Admin | ✅ |
| POST | /admin/reactivate/{id} | Admin | ✅ |
| GET | /admin/tenants | Admin | ✅ Localhost |
| GET | /docs | None | ✅ Swagger |
