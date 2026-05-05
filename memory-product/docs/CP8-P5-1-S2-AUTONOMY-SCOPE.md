# CP8 Phase 5.1 Stage 2 — Redaction Cascade: Implementation

**Task:** Wire end-to-end redaction cascade. Add HTTP endpoint, complete cascade for evidence-chain depth, implement async resynthesis worker, ship migration to backfill `synthesis_state`, integration test on validation cluster.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** `c5f8630` (Stage 1 inventory).
**Estimated wall-clock:** 60–90 min.
**Branch:** `cp-p5-1-s2` (created at start, merged manually by operator).

---

## Goal

One sentence: A tenant calls `POST /memories/{id}/redact`, the source memory transitions to `redacted`, every synthesis whose evidence chain cites that memory transitions to `pending_resynthesis`, and a background worker rebuilds those syntheses without the redacted source — with audit events written for every step.

When this stage merges, the validation cluster `b28b7a99fd4791cb` can have one of its 8 source memories redacted via HTTP, the cascade fires across all 21 affected syntheses, and within a few minutes new synthesis rows exist with `superseded_by` pointing forward from the originals.

---

## Architecture decisions (locked — do not re-litigate)

These were called by the operator before this scope was written. CC does not deviate; if implementation hits a wall against any of these, halt and write a BLOCKED note.

1. **Endpoint:** `POST /memories/{id}/redact`, body `{"reason": string}`, header `X-API-Key`. Single memory only — no batch.
2. **Auth:** Standard tenant-scoped `X-API-Key`. Any holder of the tenant key can redact within that tenant. Cross-tenant disallowed.
3. **Sync/async split:** Endpoint returns 202 Accepted within 200ms after running the cascade *query* (one UPDATE that marks affected syntheses `pending_resynthesis`). The actual *resynthesis* runs in the existing `jobs.py` queue, picked up by a worker tick. Endpoint returns `{job_id, cascade_count, redacted_memory_id}`.
4. **State transitions in this stage:** Source `active → redacted` only. (`modified` is a future chain.) Synthesis `valid → pending_resynthesis → resynthesized` (terminal).
5. **Cascade fan-out cap:** 100 syntheses per cascade call. If a redaction would affect >100 syntheses, the cascade query marks the first 100 and emits a `redaction_cascade_overflow` audit event with the remaining count. A separate cleanup pass handles overflow (deferred — log it, don't queue it in this stage).
6. **`synthesis_state` backfill:** Migration 023 (or next available number — verify) sets `synthesis_state = 'valid'` for all existing synthesis rows where it is NULL. NOT NULL constraint NOT added in this stage (would require coordinated app-side change). Tier 1 migration — additive, reversible, autonomous-safe via `scripts/db_migrate.sh`.
7. **Audit event vocabulary additions:**
   - `redaction_cascade_initiated` — one per redact call, payload `{redacted_memory_id, affected_synthesis_count, affected_synthesis_ids: uuid[]}`. Capped at 100 IDs in the array; if >100 affected, the count is accurate but IDs are truncated.
   - `redaction_cascade_overflow` — emitted iff fan-out exceeds cap. Payload `{redacted_memory_id, total_affected, capped_at: 100}`.
   - `resynthesized` — one per synthesis row when worker completes its rebuild. Payload `{old_synthesis_id, new_synthesis_id, source_memory_ids_excluded: uuid[]}`.
   - Existing `state_transition` events continue to fire per-row from `transition_source_state` and `transition_synthesis_state` — do not modify their payload.
8. **No `audit.py` extraction.** `_write_audit_event` stays in `writer.py`. `redaction.py` imports it directly. If the import is awkward, factor *only* the helper to `src/synthesis/_audit.py` — do not invent a broader audit module.
9. **Policy:** Default tenant policy is `mark_pending_review` cascade action with `evidence_chain_only` depth — the only combination Phase 1 of `redaction.py` already implements. This stage does NOT implement `resynthesize_without`, `invalidate`, or `full_cluster`. If policy resolution returns a different action/depth, raise `RedactionCascadeError` (existing exception class) with a clear "out of scope for P5.1 Stage 2" message.
10. **Worker shape:** New function `process_pending_resynthesis()` in a new file `src/synthesis/resynthesis_worker.py`. It claims one `pending_resynthesis` synthesis at a time via a `SELECT ... FOR UPDATE SKIP LOCKED` pattern, rebuilds it, writes the new row, points old → new via `superseded_by`, transitions old to `resynthesized` (terminal). Idempotent — re-running on the same row is a no-op because the state has already moved past `pending_resynthesis`.
11. **Worker invocation in this stage:** Manual trigger only. New endpoint `POST /admin/resynthesis/run?limit=N` (default N=10) processes up to N rows and returns a summary. Cron wiring deferred — the existing synthesis cron infrastructure can pick this up later. Manual trigger is sufficient to validate end-to-end.

---

## In scope

**Files to MODIFY:**
- `src/synthesis/redaction.py` — add cascade-overflow detection in `cascade_to_synthesis`; emit the new audit event types
- `api/main.py` — add `POST /memories/{id}/redact` and `POST /admin/resynthesis/run` endpoints
- `src/synthesis/writer.py` — verify `_write_audit_event` accepts the new event_type values; if it has a CHECK-constraint guard, extend it. Otherwise no change.

**Files to CREATE:**
- `src/synthesis/resynthesis_worker.py` — new module with `process_pending_resynthesis(tenant_id, limit=10) -> dict`
- `migrations/023_synthesis_state_backfill.sql` — backfill NULL → 'valid' (verify the next available migration number with `ls migrations/ | sort | tail -3` — adjust filename if 023 is taken)
- `tests/synthesis/test_redaction_endpoint.py` — HTTP-level integration tests (5 tests minimum: redact happy path, cascade fan-out, auth failure, nonexistent memory, overflow detection)
- `tests/synthesis/test_resynthesis_worker.py` — worker-level integration tests (4 tests minimum: claim+rebuild happy path, idempotency, locking under concurrency simulation, terminal state transition)

**Files to READ (no modifications):**
- `src/synthesis/policy.py` — to know how policy resolution returns action/depth
- `src/synthesis/state_machine.py` — to confirm valid state transitions before coding
- `src/synthesis/jobs.py` — to understand existing job-orchestration patterns
- `src/synthesis/writer.py::synthesize_cluster` — the function the worker calls to rebuild
- `migrations/017_cp8_redaction_state_machine.sql` — to know the synthesis_audit_events CHECK constraint exact contents
- `docs/CP8-P5-1-S1-INVENTORY.md` — the Stage 1 finding doc

**Database:**
- One Tier 1 migration (additive backfill, reversible).
- Read access for cascade query and worker SELECT.
- Write access for state transitions, new synthesis rows, audit events.

---

## Out of scope (DO NOT TOUCH)

- `src/recall.py` — Phase 4 already filters correctly per Stage 1 finding.
- `src/synthesis/clustering.py` — clustering doesn't change.
- Any consensus/multi-agent path (Phase 3 territory).
- Webhooks (P5.4).
- The `modified` state transition or any `_db_execute+split` site cleanup.
- Cron wiring for the worker.
- `synthesis_state` NOT NULL constraint addition.
- New audit-module extraction beyond the optional `_audit.py` helper relocation noted in Decision 8.
- Any change to the existing `transition_source_state` or `transition_synthesis_state` payloads.
- MCP tool surface (the `memory_synthesize` tool is on the carry-list, not this chain).

---

## Steps

### Step 1 — Snapshot starting state

```bash
cd /root/.openclaw/workspace/memory-product
git status                 # MUST be clean
git log -1 --oneline       # record HEAD; expected c5f8630
git checkout -b cp-p5-1-s2
```

**Halt if working tree dirty or HEAD is not c5f8630.**

### Step 2 — Migration: backfill synthesis_state

Determine next migration number:

```bash
ls migrations/ | grep -E '^[0-9]{3}' | sort | tail -3
```

Author `migrations/0XX_synthesis_state_backfill.sql` (where XX is next available — likely 023):

```sql
-- Migration: backfill synthesis_state for pre-existing synthesis rows
-- Tier: 1 (additive, reversible)
-- Reason: Stage 1 inventory found 21 rows with synthesis_state=NULL on validation cluster.
--         Implicit-valid is a query footgun. Backfill to 'valid' explicitly.

-- NO inner BEGIN/COMMIT — wrapper handles transaction.

UPDATE memory_service.memories
SET synthesis_state = 'valid'
WHERE memory_type = 'synthesis'
  AND synthesis_state IS NULL;

-- Reversal note (for ops, not executed):
-- UPDATE memory_service.memories SET synthesis_state = NULL
-- WHERE memory_type='synthesis' AND synthesis_state='valid' AND <id IN (set captured pre-migration)>;
-- In practice we don't reverse — backfill is the correct end state.
```

Apply via the canonical wrapper:

```bash
bash scripts/db_migrate.sh up
```

**Gate G2 — DB shape gate:**

```bash
psql "$DATABASE_URL" -c "
SELECT COUNT(*) FROM memory_service.memories
WHERE memory_type='synthesis' AND synthesis_state IS NULL;
" -t -A
```

Expected output: `0`. If non-zero, halt.

```bash
psql "$DATABASE_URL" -c "
SELECT synthesis_state, COUNT(*) FROM memory_service.memories
WHERE memory_type='synthesis' GROUP BY 1;
" -t -A
```

Expected output: `valid|N` where N matches the synthesis count from Stage 1 inventory (~48 across all tenants). Capture verbatim into commit message.

### Step 3 — Cascade overflow detection in redaction.py

In `cascade_to_synthesis`, after the SELECT that finds affected syntheses, add:

```python
CASCADE_FAN_OUT_CAP = 100  # Module constant near top of file

# After the SELECT that builds affected_synthesis_ids:
total_affected = len(affected_synthesis_ids)
if total_affected > CASCADE_FAN_OUT_CAP:
    capped_ids = affected_synthesis_ids[:CASCADE_FAN_OUT_CAP]
    _write_audit_event(
        tenant_id=tenant_id,
        memory_id=redacted_memory_id,
        event_type='redaction_cascade_overflow',
        actor='system',
        payload={
            'redacted_memory_id': str(redacted_memory_id),
            'total_affected': total_affected,
            'capped_at': CASCADE_FAN_OUT_CAP,
        },
    )
    affected_synthesis_ids = capped_ids
```

After the cascade is applied (synthesis rows transitioned to `pending_resynthesis`), emit the initiated event:

```python
_write_audit_event(
    tenant_id=tenant_id,
    memory_id=redacted_memory_id,
    event_type='redaction_cascade_initiated',
    actor='system',
    payload={
        'redacted_memory_id': str(redacted_memory_id),
        'affected_synthesis_count': total_affected,
        'affected_synthesis_ids': [str(i) for i in affected_synthesis_ids[:CASCADE_FAN_OUT_CAP]],
    },
)
```

**Verify the synthesis_audit_events.event_type CHECK constraint accepts these new values.** Read `migrations/017_cp8_redaction_state_machine.sql`. If the CHECK is restrictive (whitelist) and doesn't include the new event types, this stage needs an additional migration to extend the CHECK. **If that is the case, halt** — the operator decides whether to extend the CHECK in this chain or split it out. Migration extension to a CHECK constraint is borderline Tier 1/Tier 2 and warrants human review.

If the CHECK is permissive (no whitelist), or the new event_types are already in the whitelist, proceed.

### Step 4 — Author resynthesis_worker.py

New file `src/synthesis/resynthesis_worker.py`:

```python
"""
Resynthesis worker — picks up pending_resynthesis synthesis rows,
rebuilds them without redacted sources, supersedes the originals.

Idempotent: re-running on a row that has already moved past
pending_resynthesis is a no-op.

Concurrency: uses SELECT ... FOR UPDATE SKIP LOCKED so multiple
worker invocations don't double-process.
"""

# Function signature (final body authored by CC):
def process_pending_resynthesis(tenant_id: UUID, limit: int = 10) -> dict:
    """
    Returns: {
        'processed': int,
        'succeeded': int,
        'failed': int,
        'rebuilt': [{'old_id': uuid, 'new_id': uuid}],
        'errors': [{'old_id': uuid, 'error': str}],
    }
    """
    ...
```

Implementation outline (CC fills in):

1. Open a transaction.
2. `SELECT id, source_memory_ids, role_tag, agent_id, metadata FROM memory_service.memories WHERE memory_type='synthesis' AND synthesis_state='pending_resynthesis' AND tenant_id=%s ORDER BY updated_at ASC LIMIT %s FOR UPDATE SKIP LOCKED`
3. For each row:
   a. Filter `source_memory_ids` to exclude any whose `redaction_state='redacted'`.
   b. Re-resolve cluster context (same `cluster_id` from metadata).
   c. Call `synthesize_cluster(tenant_id, cluster_id, source_memory_ids=filtered)` — the existing writer.
   d. The writer writes a new synthesis row. Capture its ID.
   e. UPDATE the old row: `synthesis_state='resynthesized'`, `superseded_by=<new_id>`.
   f. Emit `resynthesized` audit event: `{old_synthesis_id, new_synthesis_id, source_memory_ids_excluded: [the_redacted_ones]}`.
4. Commit transaction.
5. Return summary dict.

**Important:** if filtered `source_memory_ids` is empty (all sources redacted), do NOT call the writer — that's a degenerate case. Instead transition the old row directly to `resynthesized` with `superseded_by=NULL` and emit the audit event with `new_synthesis_id=null` and a payload field `degenerate=true`. The synthesis is gone because all its evidence is gone — that's the correct GDPR posture.

**Gate G3 — Worker integration test:**

Author `tests/synthesis/test_resynthesis_worker.py` with at least these tests:

1. `test_worker_rebuilds_synthesis_with_filtered_sources` — set up a synthesis with 3 source memories, redact 1, call worker, verify new synthesis exists with 2 source IDs and old row points to it.
2. `test_worker_idempotent` — call twice, verify second call processes 0 rows.
3. `test_worker_handles_all_sources_redacted` — degenerate case, verify old row marked resynthesized with superseded_by=NULL.
4. `test_worker_skip_locked_under_concurrent_calls` — spawn two worker calls in parallel, verify same row is not processed twice (use threading.Thread or similar; if Python's psycopg2 locking semantics make this hard to test deterministically, use a sleep+monkeypatch approach).

```bash
pytest tests/synthesis/test_resynthesis_worker.py -v --tb=short
```

All pass = advance. Any failure = halt.

### Step 5 — Author the redact endpoint

In `api/main.py`:

```python
@app.post("/memories/{memory_id}/redact", status_code=202)
async def redact_memory(memory_id: UUID, request: Request, body: dict):
    # 1. Validate API key, resolve tenant_id (use existing auth helper).
    # 2. Validate memory_id exists in this tenant's namespace; 404 if not.
    # 3. Validate body['reason'] is a non-empty string; 422 if not.
    # 4. Call transition_source_state(tenant_id, memory_id, new_state='redacted', reason=body['reason']).
    #    This existing function: updates source row, logs state_transition event, calls cascade_to_synthesis.
    # 5. Capture cascade_count from the cascade return value.
    # 6. Enqueue a resynthesis job via jobs.py infrastructure (reuse existing create_job).
    # 7. Return {"job_id": <uuid>, "cascade_count": <int>, "redacted_memory_id": <str>}.
```

Auth gate, error handling, and request shape mirror existing endpoints — do not invent new patterns. Read 2–3 existing POST handlers in `api/main.py` first to copy the auth/error idiom.

### Step 6 — Author the worker trigger endpoint

In `api/main.py`:

```python
@app.post("/admin/resynthesis/run")
async def run_resynthesis(request: Request, limit: int = 10):
    # 1. Validate API key, resolve tenant_id.
    # 2. Cap limit at 50 to prevent abuse.
    # 3. Call process_pending_resynthesis(tenant_id, limit=min(limit, 50)).
    # 4. Return the worker summary dict.
```

### Step 7 — Endpoint integration test

Author `tests/synthesis/test_redaction_endpoint.py` with 5 tests minimum:

1. `test_redact_happy_path` — POST /memories/{valid_id}/redact, expect 202, expect job_id present, expect cascade_count >= 0.
2. `test_redact_cascade_fan_out` — set up a memory cited by 3 syntheses, redact, expect cascade_count == 3, expect all 3 syntheses now in pending_resynthesis state.
3. `test_redact_auth_failure` — POST without X-API-Key, expect 401.
4. `test_redact_nonexistent_memory` — POST with random UUID, expect 404.
5. `test_redact_overflow_detection` — set up >100 syntheses (or mock the threshold low for the test), trigger, verify `redaction_cascade_overflow` audit event was written.

```bash
pytest tests/synthesis/test_redaction_endpoint.py -v --tb=short
```

All pass = advance.

### Step 8 — Restart memory-api

```bash
systemctl restart memory-api
sleep 3
systemctl is-active memory-api
ss -tlnp | grep 8420
journalctl -u memory-api -n 30 --no-pager 2>&1 | grep -E "ERROR|CRITICAL" || echo "no errors"
```

Expected: `active`, port 8420 held, no new ERRORs.

### Step 9 — End-to-end gate on validation cluster

**Safe to paste:** YES for the curl outputs (will contain UUIDs and counts only). NO for any psql output that includes `full_content` or `headline` columns — query only metadata.

Pick the FIRST source memory ID from the validation cluster Stage 1 inventory: `58772303-7644-418e-a39d-3d55ecd3b3ae`.

Pre-state snapshot:

```bash
psql "$DATABASE_URL" -c "
SELECT id, redaction_state FROM memory_service.memories
WHERE id='58772303-7644-418e-a39d-3d55ecd3b3ae';
" -A
```

Expected: `58772303-7644-418e-a39d-3d55ecd3b3ae|active`.

Get the tenant API key (live):

```bash
psql "$DATABASE_URL" -c "
SELECT api_key_live FROM memory_service.tenants
WHERE id=(SELECT tenant_id FROM memory_service.memories
          WHERE id='58772303-7644-418e-a39d-3d55ecd3b3ae');
" -t -A
```

**DO NOT paste — read locally.** Capture into shell variable `KEY`.

Trigger redaction:

```bash
curl -sS -X POST http://localhost:8420/memories/58772303-7644-418e-a39d-3d55ecd3b3ae/redact \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Stage 2 end-to-end verification"}'
```

Expected: 202 status, JSON body with `job_id`, `cascade_count`, `redacted_memory_id`. **Capture verbatim** into commit message.

Verify cascade applied:

```bash
psql "$DATABASE_URL" -c "
SELECT redaction_state, COUNT(*) FROM memory_service.memories
WHERE memory_type='synthesis'
  AND metadata->>'cluster_id'='b28b7a99fd4791cb'
GROUP BY 1;
" -A
```

Expected: rows with `redaction_state=pending_resynthesis` matching the cascade_count from the curl response.

Trigger resynthesis worker:

```bash
curl -sS -X POST "http://localhost:8420/admin/resynthesis/run?limit=25" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json"
```

Expected: JSON with `processed`, `succeeded`, `rebuilt` array. Capture verbatim.

Post-state snapshot:

```bash
psql "$DATABASE_URL" -c "
SELECT redaction_state, synthesis_state, COUNT(*) FROM memory_service.memories
WHERE memory_type='synthesis'
  AND metadata->>'cluster_id'='b28b7a99fd4791cb'
GROUP BY 1, 2;
" -A
```

Expected: original 21 rows now in `synthesis_state='resynthesized'` with `superseded_by` populated, plus N new rows with `synthesis_state='valid'`.

Audit chain verification:

```bash
psql "$DATABASE_URL" -c "
SELECT event_type, COUNT(*) FROM memory_service.synthesis_audit_events
WHERE memory_id='58772303-7644-418e-a39d-3d55ecd3b3ae'
   OR payload->>'redacted_memory_id'='58772303-7644-418e-a39d-3d55ecd3b3ae'
GROUP BY 1;
" -A
```

Expected: `state_transition` (1, the source's active→redacted), `redaction_cascade_initiated` (1), `resynthesized` events matching number of rebuilt syntheses.

Capture verbatim into commit message.

### Step 10 — Final commit + push

```bash
git add -A
git status                  # review
git diff --cached --stat    # review
```

Commit message template (CC fills in receipts):

```
P5.1 Stage 2: redaction cascade end-to-end

Wires HTTP redaction → state transition → cascade query → async resynthesis
worker. Stage 1 inventory closed all design questions; this stage implements.

Endpoints added:
- POST /memories/{id}/redact (202)
- POST /admin/resynthesis/run

Module added:
- src/synthesis/resynthesis_worker.py — process_pending_resynthesis()

Migration:
- 0XX_synthesis_state_backfill.sql (Tier 1, additive, reversible)
- Backfilled N rows: NULL → 'valid'

Audit events added:
- redaction_cascade_initiated
- redaction_cascade_overflow (cap=100)
- resynthesized

Validation cluster end-to-end (b28b7a99fd4791cb):
- Pre-redaction:  <verbatim psql output>
- Redact response: <verbatim curl output>
- Post-cascade:   <verbatim psql output>
- Worker run:     <verbatim curl output>
- Post-worker:    <verbatim psql output>
- Audit chain:    <verbatim psql output>

Test suite:
- tests/synthesis/test_redaction_endpoint.py: <N>/<N> passed
- tests/synthesis/test_resynthesis_worker.py: <N>/<N> passed
- Existing tests/synthesis/test_redaction.py: <N>/<N> passed (no regression)

Receipts:
- HEAD before: c5f8630
- HEAD after:  <sha>
- Files changed: <git diff --stat output>
- Service: memory-api restarted, journalctl clean
```

```bash
git push origin cp-p5-1-s2
```

**Do NOT merge to master.** Operator merges manually after morning review.

---

## Halt conditions

CC halts and writes `CP8-P5-1-S2-BLOCKED.md` if ANY of:

1. Working tree dirty at start, or HEAD is not `c5f8630`.
2. Migration dry-run or apply produces output that doesn't end with the expected ROLLBACK / COMMIT marker.
3. The synthesis_audit_events CHECK constraint rejects any of the new event types AND extending the CHECK would require its own migration. (Halt for operator to decide.)
4. Any test in Steps 4 or 7 fails twice in a row (one retry permitted after re-reading the scope).
5. memory-api fails to restart or shows new ERRORs in journalctl.
6. Step 9 end-to-end produces a cascade_count of 0 (means the cascade isn't wiring through).
7. Step 9 end-to-end produces post-worker rows where `superseded_by` is NULL on rows that should have been rebuilt.
8. CC is tempted to extract `audit.py`, modify recall.py, or implement consensus/multi-agent paths.
9. CC is tempted to implement `modified` state cascade, `resynthesize_without`/`invalidate`/`full_cluster` actions, or anything else marked out of scope.
10. More than 8 files modified outside the in-scope list.
11. Any production write outside `memory_service.memories` and `memory_service.synthesis_audit_events`.

On halt: stage nothing, commit nothing on the branch, write the BLOCKED note to workspace root, exit cleanly.

---

## Definition of done

All of:

1. Branch `cp-p5-1-s2` exists with one commit.
2. Migration 0XX applied to prod, all synthesis rows have `synthesis_state` populated.
3. Endpoints `POST /memories/{id}/redact` and `POST /admin/resynthesis/run` return correctly on the validation cluster.
4. End-to-end Step 9 produces all expected outputs (verbatim in commit message).
5. All tests pass (Steps 4 + 7).
6. memory-api restarted clean.
7. No `CP8-P5-1-S2-BLOCKED.md` exists.
8. Branch pushed to origin, NOT merged to master.

Operator merges manually after reviewing the commit, the diff, and the receipts.
