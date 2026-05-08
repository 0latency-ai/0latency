# CP8 P5.2 — Audit Log Read Endpoint (autonomy scope)

**Date:** 2026-05-06
**Tier:** Sonnet, autonomous mechanical execution per AUTONOMY-PROTOCOL v2.
**Branch:** `cp-p5-2-audit-read` (NEW, branched from current master `24ab859`).
**Wall-clock estimate:** 30–60 min.

---

## Context

P5.1 (redaction cascade) closed and merged to master at `24ab859`. Phase 5 now picks up P5.2: the audit log read endpoint. The schema for `memory_service.synthesis_audit_events` already exists (CP8 P1, migration 014). Cascade events (`redaction_cascade_initiated`, `redaction_cascade_overflow`) and `state_transition` events are actively being written by P5.1 code. P5.2 ships the **read surface** so Enterprise tenants can query that audit chain.

This is an Enterprise-tier feature (per CP8 Decision 3). Scale/Pro/Free tiers receive 403 on this endpoint — cost discipline (audit log query response sizes are non-trivial).

P5.2 is **read-only**. Zero schema changes, zero migrations, no writes to prod data. Trigger that = halt.

---

## Goal (single sentence)

Ship `GET /audit/events` (Enterprise-tier-gated) that supports filtering by `event_type`, time range, `target_memory_id`, `actor`, and `tenant_id` (implicit from API key), with cursor pagination and a hard cap, plus integration tests proving filters work and tier gating rejects non-Enterprise.

---

## Scope (in)

1. **Endpoint:** `GET /audit/events` on `api/main.py`.
2. **Tier gate:** reject non-Enterprise with 403 + body `{"error": "audit_read_requires_enterprise", "tenant_tier": "<tier>"}`. Tier read from `memory_service.tenants.tier` column (verify column exists during introspection step — see Step 0).
3. **Query parameters (all optional except as noted):**
   - `event_type` (repeatable, e.g. `?event_type=redacted&event_type=resynthesized`) — filter to one or more event types. If omitted, return all event types.
   - `target_memory_id` (UUID) — filter to events targeting this specific memory.
   - `actor` (string) — filter to events by this actor (agent_id or `system`).
   - `since` (ISO 8601 datetime) — events with `occurred_at >= since`.
   - `until` (ISO 8601 datetime) — events with `occurred_at <= until`.
   - `limit` (int, default 100, hard max 500) — clamp silently if user passes higher.
   - `cursor` (opaque base64) — for pagination; encodes `(occurred_at, id)` of the last returned row.
4. **Response:**
   ```json
   {
     "events": [
       {
         "id": "<uuid>",
         "tenant_id": "<uuid>",
         "target_memory_id": "<uuid|null>",
         "event_type": "<str>",
         "actor": "<str>",
         "occurred_at": "<iso8601>",
         "event_payload": { ... }
       }
     ],
     "next_cursor": "<base64|null>",
     "returned": <int>,
     "has_more": <bool>
   }
   ```
5. **Sort order:** `occurred_at DESC, id DESC` (newest first, deterministic tiebreak by UUID).
6. **Index strategy:** verify existing indexes on `synthesis_audit_events` (per CP8 P1 schema spec: `tenant_id`, `target_memory_id`, `event_type`, `occurred_at`). If composite `(tenant_id, occurred_at DESC)` index is missing, add it via a NEW migration `025_audit_events_query_index.sql` (Tier 1, additive, reversible). Otherwise, skip migration.
7. **Audit-log-of-the-audit-log:** when an Enterprise tenant calls this endpoint, write a `read` event to `synthesis_audit_events` itself. Payload includes the filter params used. This is consistent with CP8 P4 design (audit-aware queries on Enterprise) and gives auditors visibility into who-read-what-when.
8. **Tests:**
   - Tier gate: Free/Pro/Scale tenant → 403; Enterprise tenant → 200.
   - Filter by single `event_type` → only matching rows.
   - Filter by multiple `event_type` → union.
   - Filter by `target_memory_id` → only matching rows.
   - Filter by `since`/`until` → only rows in window.
   - Pagination: insert ≥150 events, page through with limit=50, verify all 150 returned exactly once with no overlap.
   - Limit clamp: request limit=10000 → returns at most 500.
   - Self-audit: Enterprise call writes a `read` event with filter payload.
9. **Integration with prod:** validate against the validation cluster `b28b7a99fd4791cb` on `user-justin` tenant. After endpoint ships, run `GET /audit/events?event_type=redaction_cascade_initiated&event_type=resynthesized&target_memory_id=58772303-7644-418e-a39d-3d55ecd3b3ae` and confirm at least one of each event type returns (P5.1 verification cluster has these).

## Scope (out)

- No write/update/delete on audit events. Append-only is enforced at schema level (existing trigger or PG role).
- No CSV/export endpoint. Just JSON. Export is its own future surface.
- No dashboard UI. API only.
- No new event types beyond `read`. P5.1 handled the cascade event types.
- No MCP tool wrapping this endpoint yet — defer to a later P5 sub-task or P5.7.
- No schema changes other than the optional index migration in Step 6 (Tier 1 only, only if missing).
- No changes to `recall.py`, `redaction.py`, `consensus.py`, or any synthesis writer. This is a pure read-side feature on `api/main.py`.

---

## Step 0 — Pre-flight introspection (READ-ONLY, paste-safe)

Before writing any code, CC must SSH into the server and verify the actual schema. Run these queries and capture output. **No DDL, no DML, no ALTER, no INSERT/UPDATE/DELETE.**

```bash
ssh root@164.90.156.169
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
```

Then in psql:

```sql
-- 1. Confirm table and columns
\d memory_service.synthesis_audit_events

-- 2. Confirm tier column on tenants
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema='memory_service' AND table_name='tenants'
  AND column_name IN ('tier', 'plan', 'subscription_tier');

-- 3. Confirm indexes on audit table
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='memory_service' AND tablename='synthesis_audit_events';

-- 4. Confirm event_type CHECK constraint includes 'read' (CP8 P1 should have it)
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'memory_service.synthesis_audit_events'::regclass
  AND contype = 'c';

-- 5. Confirm append-only enforcement
SELECT trigger_name, event_manipulation, action_statement
FROM information_schema.triggers
WHERE event_object_schema='memory_service'
  AND event_object_table='synthesis_audit_events';

-- 6. Sample a few rows to confirm payload shape
SELECT event_type, actor, occurred_at, jsonb_typeof(event_payload) AS payload_type
FROM memory_service.synthesis_audit_events
ORDER BY occurred_at DESC LIMIT 5;
```

Save the output of all six queries to `/tmp/p52-introspection.txt` on the server. Reference it when implementing.

**Halt conditions for Step 0:**

- If `tenants` has no tier-like column under any of the three names tried → halt, write `docs/CP8-P5-2-BLOCKED.md`, do not proceed. Tier gating is foundational.
- If `synthesis_audit_events` table does not exist → halt, write blocked doc.
- If `read` is NOT in the event_type CHECK constraint → ship migration `025_audit_event_read_type.sql` (Tier 1) adding it as the FIRST commit on the branch, applied via `bash scripts/db_migrate.sh up`. Then proceed. Document this as a finding.

---

## Step 1 — Branch and migration (if needed)

```bash
cd /root/.openclaw/workspace/memory-product
git checkout master
git pull --ff-only origin master
git checkout -b cp-p5-2-audit-read
```

If introspection showed that `read` is missing from the event_type CHECK or the composite index `(tenant_id, occurred_at DESC)` is missing, write migration `migrations/025_audit_events_query_index.sql` now. Use the canonical wrapper:

```bash
bash scripts/db_migrate.sh up
```

NOT `alembic upgrade head` directly. (Reinforced rule from P5.1 recovery.)

If introspection showed both already exist, skip the migration step entirely.

Commit the migration (if any) before writing code. Single-purpose commit.

---

## Step 2 — Implement endpoint

In `api/main.py`, add `GET /audit/events`. Suggested location: after the existing `POST /memories/{id}/redact` endpoint (P5.1) for logical grouping.

Key implementation notes:

- Read tenant tier via the existing tenant-lookup helper (whatever P5.1 used — re-use, don't duplicate).
- Build the SQL with parameterized query. NEVER string-interpolate user input.
- Use `_db_execute_rows` (native tuples) NOT the legacy stringify+split pattern. Per memory: `_db_execute_rows` is the post-bug-fix canonical accessor.
- Cursor encoding: base64-encoded JSON `{"occurred_at": "<iso>", "id": "<uuid>"}`. Decode on read, re-encode on write. If decode fails, return 400 `{"error": "invalid_cursor"}`.
- Self-audit write: use the same audit-event writer module already in use by P5.1 (probably `src/synthesis/audit.py` per CP8 architecture map). Re-use, don't duplicate. The `read` event payload should be:
  ```json
  {
    "filters": {
      "event_type": [...],
      "target_memory_id": "...",
      "actor": "...",
      "since": "...",
      "until": "...",
      "limit": <int>
    },
    "returned": <int>,
    "endpoint": "GET /audit/events"
  }
  ```
- Self-audit write happens AFTER successful query, BEFORE returning response. If the audit write fails, log and proceed (don't fail the user-facing request — audit-of-audit is best-effort).

---

## Step 3 — Tests

Create `tests/audit/test_audit_read_endpoint.py`. If `tests/audit/` doesn't exist, create it with `__init__.py`.

Test list (each as a separate test function):

1. `test_free_tier_blocked` — 403 with correct error body
2. `test_pro_tier_blocked` — 403
3. `test_scale_tier_blocked` — 403
4. `test_enterprise_tier_allowed` — 200, returns events
5. `test_filter_single_event_type`
6. `test_filter_multiple_event_types_union`
7. `test_filter_target_memory_id`
8. `test_filter_actor`
9. `test_filter_since_until_window`
10. `test_pagination_complete_no_overlap` — insert 150 events, page through with limit=50, assert 150 unique IDs returned
11. `test_limit_clamped_to_500`
12. `test_invalid_cursor_returns_400`
13. `test_self_audit_event_written` — Enterprise call → assert a `read` event was written with correct payload shape

Run with the existing pytest pattern. Document any test that won't pass and why in the deliverable doc — do NOT skip tests silently.

**If you hit the same `ModuleNotFoundError: No module named 'api.main'` issue from P5.1 endpoint tests:** halt and document. Do NOT spend time fixing the import-path problem here — that's P5.7 carry-forward. Worker-level tests (DB-only, no FastAPI import) should still work; prefer that level of test if endpoint-level fails to import.

---

## Step 4 — Validation against prod

After tests pass (or are documented as carry-forward), validate end-to-end on the live system. Run from server (NOT from CC's sandbox):

```bash
# Get an Enterprise API key for user-justin (the dogfood tenant)
# Source from .env. DO NOT print the key to terminal.

# Smoke test: filter to known cascade events
curl -s -H "Authorization: Bearer $JUSTIN_API_KEY" \
  "https://mcp.0latency.ai/audit/events?event_type=redaction_cascade_initiated&event_type=resynthesized&target_memory_id=58772303-7644-418e-a39d-3d55ecd3b3ae" \
  | jq '.events | length, .returned, .has_more'
```

Expected: at least 1 of each event type from the P5.1 validation cluster.

After this call, query the audit table directly to confirm a `read` event was written:

```sql
SELECT event_type, actor, event_payload, occurred_at
FROM memory_service.synthesis_audit_events
WHERE event_type='read'
ORDER BY occurred_at DESC LIMIT 1;
```

Capture both outputs into the deliverable doc.

---

## Step 5 — Commit and push

Single feature commit on `cp-p5-2-audit-read`:

```
P5.2: audit log read endpoint (Enterprise-tier-gated)

- GET /audit/events with event_type/target_memory_id/actor/since/until/limit/cursor
- Tier-gate: 403 for non-Enterprise; 200 for Enterprise with self-audit 'read' event
- Cursor pagination with deterministic (occurred_at DESC, id DESC) sort
- 13 tests in tests/audit/test_audit_read_endpoint.py
- Migration 025 (only if introspection found missing index/CHECK; otherwise no migration)
- Re-uses existing audit writer module — no duplication
- End-to-end smoke verified against validation cluster b28b7a99fd4791cb on user-justin

NOT MERGED to master. Awaits operator review.
```

Push to origin. Do NOT merge.

---

## Step 6 — Deliverable doc

Write `docs/CP8-P5-2-COMPLETE.md` with:

1. Summary of what shipped.
2. Step 0 introspection findings (paste the captured output, redact any UUIDs of unrelated tenants if present).
3. Whether migration 025 was needed (and what it added if so).
4. Test results: pass/fail count + any documented carry-forwards.
5. End-to-end smoke output from Step 4 (curl response shape + the self-audit `read` event row).
6. Branch + commit hash.
7. Open questions / things the operator should decide on review.

---

## Halt conditions (mandatory, no exceptions)

Stop and write a `docs/CP8-P5-2-BLOCKED.md` if any of these fire:

- Step 0 introspection reveals tier column missing under all three tried names.
- Step 0 reveals `synthesis_audit_events` table missing.
- Migration 025 (if needed) fails dry-run via `bash scripts/db_migrate.sh up`.
- More than 3 tests fail and the failures are not the known import-path issue.
- End-to-end smoke (Step 4) returns 0 events or 5xx.
- Any operation would touch a tenant other than `user-justin` for testing/validation.
- The `read` event self-audit write fails repeatedly during smoke (1-time best-effort failure is OK; systemic failure is halt).

If halt fires, blocked doc must include:
- Which halt condition tripped
- Captured output proving it
- Recommended next step for the operator
- Confirmation that no stray DDL/DML was executed

---

## Standing rules (carry forward verbatim)

1. PRIME DIRECTIVE: never request paste of secrets. State paste-safety upfront on every command.
2. Stale shell env: `set -a && source .env && set +a` before any DB-touching command after `.env` change.
3. Migrations via `bash scripts/db_migrate.sh up` — NOT direct `alembic upgrade head`. Hard-learned from P5.1.
4. Tier 1 only this chain. Any Tier 2/3 sighting → halt for human apply.
5. `_db_execute_rows`, never `_db_execute` + split.
6. Never re-raise broad `except Exception` — preserve semantic exceptions.
7. Re-use existing modules (audit writer, tenant-lookup helper). Do not duplicate.
8. Production NEVER modified outside the migration wrapper or normal app code path.
9. Single feature commit + optional single migration commit. No multi-commit drift.
10. Forbidden-exit regex enforced.
11. Audio chime on completion: `; afplay /System/Library/Sounds/Glass.aiff`
12. Do NOT merge to master. Operator review required.
