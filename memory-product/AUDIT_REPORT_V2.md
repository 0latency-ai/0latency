# Zero Latency Memory Product — Re-Audit Report

**Date:** 2026-03-21
**Scope:** `memory-product/` — verification of fixes from initial audit + updated scoring
**Baseline:** Initial audit scored 7.5/10 with 3 critical, 8 high, 12 medium findings

---

## Updated Score: 8.5/10

| Category | Before | After | Delta | Notes |
|----------|--------|-------|-------|-------|
| SQL Injection Defense | 9/10 | 9/10 | — | Already strong; no change needed |
| Authentication | 8/10 | 8.5/10 | +0.5 | Hardcoded key removed (C3) |
| Tenant Isolation | 7/10 | 9/10 | +2.0 | WITH CHECK on all 11 tables (C1) |
| Error Handling | 6/10 | 6/10 | — | No changes to error handling |
| Test Quality | 5/10 | 6/10 | +1.0 | CI pipeline added (H6), secret scanner |
| Production Readiness | 6/10 | 7.5/10 | +1.5 | SSRF protection (C2), CORS fix (H2), IVFFLAT index |

---

## Fix Verification

### C1. RLS WITH CHECK — VERIFIED FIXED

**File:** `migrations/003_audit_fixes.sql`, lines 8-90

All 11 tenant-scoped tables now have `WITH CHECK` clauses:
- memories, entity_index, memory_edges, memory_clusters, topic_coverage
- memory_audit_log, session_handoffs, agent_config, api_usage
- memory_versions, entity_nodes, entity_relationships

Properly drops old policies before creating replacements. Wrapped in transaction. Clean implementation.

**One note:** The `webhooks` and `webhook_deliveries` tables (created in migration 002) are not covered. If these have RLS enabled, they need WITH CHECK too. If RLS isn't enabled on them, this is fine — but verify.

---

### C2. Webhook SSRF Protection — VERIFIED FIXED

**File:** `src/webhooks.py`, lines 30-61 (`_validate_webhook_url`)

Solid implementation:
- HTTPS-only enforcement (line 39)
- Blocked hostname list: localhost, 127.0.0.1, 0.0.0.0, 169.254.169.254, metadata.google.internal (line 47)
- DNS resolution + private IP check via `ipaddress` module (lines 52-57)
- Checks `is_private`, `is_loopback`, `is_link_local`, `is_reserved` (line 56)
- Called at registration time (line 68), blocking bad URLs before they're stored

**Remaining gap — DNS rebinding:** An attacker could register a webhook with a hostname that resolves to a public IP at registration time, then change the DNS record to point to an internal IP before delivery. The URL is only validated at `register_webhook()` (line 68), not at `_deliver_webhook()` (line 220).

**Recommendation:** Also call `_validate_webhook_url(delivery["url"])` at delivery time (before `requests.post()` on line 220), or resolve the hostname yourself and pass the IP directly to `requests.post()`.

---

### C3. Hardcoded Admin Key — VERIFIED FIXED

**File:** `tests/test_feature_parity.py`, lines 14-16

```python
ADMIN_KEY = os.environ.get("MEMORY_ADMIN_KEY", "")
if not ADMIN_KEY:
    print("⚠️  MEMORY_ADMIN_KEY not set. Admin tests will be skipped.")
```

Default fallback is now empty string. Tests skip gracefully when env var is unset. The CI pipeline also includes a `grep`-based secret scanner (`.github/workflows/ci.yml`, lines 43-52) as a regression guard.

**Note:** The old key `zl_admin_thomas_server_2026` is still in git history. If this was a real credential, it must be rotated (not just removed from HEAD).

---

### H2. CORS PUT Method — VERIFIED FIXED

**File:** `api/main.py`, line 67

```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
```

PUT now included. Browser-based calls to `PUT /memories/{memory_id}` will pass CORS preflight.

---

### H6. CI Pipeline — VERIFIED FIXED

**File:** `.github/workflows/ci.yml` (68 lines)

Two jobs:
1. **lint-and-import** — Python 3.11, installs deps, verifies all module imports, scans for hardcoded secrets
2. **typescript-check** — Node 20, TypeScript compile check on SDK

Triggers on push/PR to master for `memory-product/**` paths.

**Gaps in CI:**
- No actual test execution (`pytest` not run) — only import verification
- No coverage reporting
- No linting (flake8/ruff/mypy)
- No Docker build test
- Secret scanner uses `grep` which can miss obfuscated patterns

**Recommendation:** Add a `test` job that runs `pytest tests/` against a test database. This is the most important missing piece.

---

### IVFFLAT Index — VERIFIED FIXED

**File:** `migrations/003_audit_fixes.sql`, lines 92-94

```sql
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memory_service.memories
    USING ivfflat (embedding extensions.vector_cosine_ops) WITH (lists = 50);
```

Good. `lists = 50` is reasonable for initial scale. Will need tuning when row count exceeds ~50K (rule of thumb: lists ≈ sqrt(rows)).

---

## Remaining Open Issues

### HIGH (still unfixed)

| ID | Issue | Impact |
|----|-------|--------|
| **H1** | Prompt injection in `extraction.py:245-250` — user messages injected via `.format()` without escaping | Attacker can manipulate memory extraction, leak existing context |
| **H3** | Thread-unsafe `_recall_cache` in `recall.py:261` — no lock | Data corruption under concurrent load |
| **H4** | Redis on `0.0.0.0:6379` with no auth in `docker-compose.yml:22` | Network-accessible cache/rate-limit flush |
| **H5** | Webhook secrets stored plaintext in DB (`webhooks.py:79-82`) | Credential exposure if DB compromised |
| **H7** | `/dashboard` endpoint unauthenticated (`main.py:219-224`) | Potential information leakage |
| **H8** | `verify=False` in `test_api_full.py:486` | Normalizes insecure TLS practices |

### MEDIUM (still unfixed)

| ID | Issue |
|----|-------|
| M1 | Dynamic SQL UPDATE pattern (`main.py:733-739`) |
| M2 | ValueError message exposed to client (`main.py:770`) |
| M3 | Pipe-delimited DB result parsing (`recall.py:36,96`) |
| M4 | Cache key truncated to 500 chars (`recall.py:286-293`) |
| M5 | Division by zero risk on `half_life_days` (`recall.py:351`) |
| M6 | Confidence threshold 0.3 too low (`extraction.py:306`) |
| M7 | Fragile markdown code block parsing (`extraction.py:258-261`) |
| M8 | Non-atomic version snapshot (`versioning.py:33-50`) |
| M9 | N+1 query in graph traversal (`graph.py:108-113`) |
| M10 | DB error leaks schema details (`storage_multitenant.py:202`) |
| M11 | Secrets in docker-compose env vars |
| M12 | Unpinned dependency versions |

### NEW finding from this audit

| ID | Issue | Severity |
|----|-------|----------|
| **N1** | DNS rebinding bypass in webhook SSRF protection — URL validated at registration but not at delivery time (`webhooks.py:220`) | MEDIUM-HIGH |
| **N2** | CI pipeline doesn't run tests — only checks imports and greps for secrets | MEDIUM |
| **N3** | Webhooks/webhook_deliveries tables may be missing WITH CHECK RLS policies (not in migration 003) | MEDIUM |

---

## Prioritized Next Steps

### Round 2 fixes (recommended)

1. **H1** — Prompt injection mitigation (highest remaining risk)
2. **H3** — Add `threading.RLock` to recall cache (5-minute fix)
3. **H4** — Bind Redis to localhost + add requirepass (5-minute fix)
4. **N1** — Re-validate webhook URL at delivery time (5-minute fix)
5. **N2** — Add `pytest` job to CI pipeline

### Before GA

6. H5, H7, H8 — Remaining high findings
7. M1-M12 — Medium findings
8. N3 — Verify webhook table RLS coverage
9. Unit tests for recall scoring and extraction parsing
10. Load testing with k6

---

## Summary

You closed all 3 criticals and 2 highs cleanly. The RLS fix is thorough (11 tables), the SSRF protection is well-implemented (with one DNS rebinding gap), and the credential removal is proper. The CI pipeline is a good start but needs actual test execution.

**Score moved from 7.5 → 8.5.** To reach 9+, fix H1 (prompt injection) and the three 5-minute fixes (H3, H4, N1). To reach 9.5+, add pytest to CI and address the remaining mediums.

---

*Generated by Claude Code re-audit — session https://claude.ai/code/session_01ERECg1srA7xY6a6siRqsGu*
