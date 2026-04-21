# Gap Analysis #4 — Seb-Ready Audit
**Date:** March 21, 2026 00:30 UTC
**Scope:** Would Phase B survive 30 minutes of senior engineer scrutiny?
**Verdict:** No. Two critical security holes remain. One is worse than what we "fixed."

---

## CRITICAL — Seb stops here and doesn't look further

### 1. SQL Injection in `list_memories` endpoint (main.py lines ~138-148)
**Severity:** CRITICAL — confirmed cross-tenant data leak
**What:** The `/memories` endpoint uses f-string SQL for `agent_id`, `tenant_id`, AND `memory_type`. All three are user-controlled inputs.
**Proof:** Sending `memory_type=fact' OR 1=1--` returned 50 memories including Thomas's 697 production memories. The test API key only has access to 5 memories. `OR 1=1` bypassed both `tenant_id` and `agent_id` filters.
**Impact:** Any authenticated user can read every other tenant's memories. Full data breach with a single curl command.
**Irony:** We hardened `storage_multitenant.py` with parameterized queries, then the API endpoint that calls it builds its own f-string SQL and bypasses all of it.

### 2. SQL Injection in `recall.py` — entire file unhardened
**Severity:** CRITICAL
**What:** recall.py has 27 f-string SQL queries using subprocess psql. Zero parameterized queries. The hardening sprint never touched this file.
**Impact:** The `/recall` endpoint passes `conversation_context` (user-provided text) into `_retrieve_candidates()` which does keyword extraction and ILIKE searches with those keywords. Crafted conversation_context = arbitrary SQL execution.
**Additional:** `_load_agent_config()` and `_build_always_include()` also use f-string agent_id directly in SQL.

---

## HIGH — Seb flags these in the first pass

### 3. Tenant isolation is RLS-on-paper only
The SQL injection test proved RLS isn't protecting the `/memories` endpoint. The f-string query runs outside the RLS policy because it constructs its own WHERE clause. RLS only works if ALL queries go through the tenant-context-setting path in `_db_execute()`.

### 4. Health endpoint is hollow
Returns `memories_total: null`. Doesn't verify DB connectivity. Seb will ask "how do you know the API is actually healthy?" and there's no answer.

### 5. Rate limiting resets on restart
In-memory Python dict. Service restarts (deploys, crashes) = rate limits gone. Not a blocker for demo, but Seb will note it.

### 6. Two separate DB execution paths
`storage_multitenant.py` uses psycopg2 connection pool (hardened). `recall.py` uses subprocess psql (unhardened). Same database, two completely different access patterns. This is how the hardening missed recall — they don't share infrastructure.

---

## MEDIUM — Seb mentions but doesn't block on

### 7. No key rotation or revocation
One key per tenant forever. Compromised key = permanently compromised tenant.

### 8. No structured logging
Print statements only. No request IDs, no tenant IDs in logs, no way to trace a request through the system.

### 9. Error messages leak internals
The SQL injection test returned the raw Postgres error: `"DB error after 3 retries: syntax error at or near \"ORDER\""`. Production APIs should never expose DB error details.

### 10. Self-signed SSL
Fine for demo, but Seb will ask about the cert plan for production (Let's Encrypt / Cloudflare).

---

## What's Actually Solid

- **storage_multitenant.py** — parameterized queries, connection pool, retry logic. Genuinely hardened.
- **Tenant creation + API key hashing** — SHA-256 for system-generated keys is correct (Stripe pattern).
- **Admin endpoint localhost restriction** — IP allowlist works.
- **Extract endpoint** — works end-to-end, stores with embeddings, dedup logic functional.
- **Recall scoring algorithm** — multi-signal composite (semantic + recency + importance + access) is well-designed.
- **systemd + nginx** — service survives restarts, HTTPS works, security headers present.

---

## Fix Priority for Saturday

| # | Fix | Time | Impact |
|---|-----|------|--------|
| 1 | Parameterize `list_memories` in main.py | 20 min | Closes cross-tenant leak |
| 2 | Port recall.py to psycopg2 (same pattern as storage) | 2-3 hrs | Closes last SQL injection surface |
| 3 | Unify DB execution — recall imports from storage_multitenant | 1 hr | Eliminates dual-path problem |
| 4 | Sanitize error responses | 30 min | Stop leaking DB internals |
| 5 | Health endpoint hits DB | 15 min | Proves actual connectivity |

Fixes 1-4 are what separates "demo" from "Seb doesn't immediately say don't ship this."

---

## Score

| Dimension | GA#3 | GA#4 | Delta |
|-----------|------|------|-------|
| Security | Unaudited | 40% — storage hardened, API layer and recall wide open | New baseline |
| Tenant isolation | Untested | BROKEN — confirmed cross-tenant read via SQLi | Regression from claimed |
| Recall quality | ~62% | Functional but unhardened | Same |
| Production readiness | 0% | 25% — infra works, security doesn't | +25% |
| Overall | ~62% | 45% | Different dimensions measured |

**Bottom line:** The storage layer is solid work. But two of three user-facing code paths (list_memories, recall) still have the exact vulnerability we spent an hour fixing in storage. Fix #1 is 20 minutes. Fix #2 is the real work.
