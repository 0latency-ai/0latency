# CP8 Phase 2 Task 4 — Autonomous Scope: DB-Backed Jobs Table

**Task:** Replace in-memory job dict with `synthesis_jobs` table; add `src/synthesis/jobs.py` module wrapping it.
**Mode:** **Hybrid autonomous** — autonomous through migration drafting, **human review required mid-run** before applying migration to prod.
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`, with the explicit migration-review halt baked in.
**Predecessor commit:** T1 commit (clustering engine).
**Estimated wall-clock:** 30–60 min for CC; +10 min for human migration review.
**Chain position:** Chain A, task 2 of 3 (T1 → **T4** → T8).

---

## Goal

One sentence: Persist synthesis job state in a new `memory_service.synthesis_jobs` table so async runs survive `memory-api` restarts; expose a clean Python API at `src/synthesis/jobs.py` for the writer (T2) to call.

This closes the long-standing in-memory-jobs-dict gap (memory #12 follow-up) and unblocks the writer's async wrapping later.

---

## In scope

**Files to create:**
- `migrations/0XX_synthesis_jobs.sql` — NEW migration (numbering: next available; check `migrations/` for current max)
- `src/synthesis/jobs.py` — NEW
- `tests/synthesis/test_jobs.py` — NEW

**Files to read (do not modify):**
- `migrations/` directory — to determine next migration number and match the file's existing pattern
- `src/storage_multitenant.py` — for `_db_execute_rows` and connection helpers
- `src/synthesis/policy.py` — for module-naming-convention reference

**Database:** **One write — the migration.** Migration is drafted autonomously; CC halts before applying. Human reviews and applies. CC resumes for code module + tests against the now-migrated DB.

---

## Out of scope (DO NOT TOUCH)

- Any other migration file
- `src/synthesis/clustering.py` (T1's territory)
- `src/synthesis/writer.py` (T2 — does not exist yet)
- `src/synthesis/policy.py`, `redaction.py`, `state_machine.py`
- The in-memory `jobs` dict elsewhere in the codebase — this task does NOT delete it. T2 or a follow-up does.
- `extract_memories()`, `recall.py`, MCP server code
- Any file in `0latency-mcp-unified/` or `mcp-server/` repos — code-side persistence only

---

## Schema contract — migration body

```sql
-- Migration 0XX: synthesis_jobs table for persistent async job state
-- Replaces in-memory dict; survives memory-api restarts.

CREATE TABLE memory_service.synthesis_jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
  agent_id        text NOT NULL,
  job_type        text NOT NULL,  -- 'synthesis_run', 'cluster_then_synthesize', 'manual_trigger'
  status          text NOT NULL DEFAULT 'queued',
                                  -- 'queued', 'running', 'succeeded', 'failed', 'cancelled'
  payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
                                  -- request params, e.g. {role_scope, recency_window, force}
  result          jsonb,          -- final output: cluster_count, synthesis_ids[], tokens_used
  error           text,           -- truncated error message on failure
  created_at      timestamptz NOT NULL DEFAULT now(),
  started_at      timestamptz,
  completed_at    timestamptz,

  CONSTRAINT synthesis_jobs_status_check CHECK (
    status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
  ),
  CONSTRAINT synthesis_jobs_job_type_check CHECK (
    job_type IN ('synthesis_run', 'cluster_then_synthesize', 'manual_trigger')
  )
);

CREATE INDEX idx_synthesis_jobs_tenant_id ON memory_service.synthesis_jobs(tenant_id);
CREATE INDEX idx_synthesis_jobs_status ON memory_service.synthesis_jobs(status)
  WHERE status IN ('queued', 'running');
CREATE INDEX idx_synthesis_jobs_created_at ON memory_service.synthesis_jobs(created_at DESC);
CREATE INDEX idx_synthesis_jobs_tenant_agent ON memory_service.synthesis_jobs(tenant_id, agent_id);
```

**Note: NO inner `BEGIN/COMMIT`.** Per memory: "SQL migration files for dry-run must NOT contain inner BEGIN/COMMIT — they break the outer transaction wrapper."

**Reversibility:** include a paired DOWN migration as comments at the bottom of the same file:

```sql
-- DOWN (manual rollback):
-- DROP INDEX IF EXISTS memory_service.idx_synthesis_jobs_tenant_agent;
-- DROP INDEX IF EXISTS memory_service.idx_synthesis_jobs_created_at;
-- DROP INDEX IF EXISTS memory_service.idx_synthesis_jobs_status;
-- DROP INDEX IF EXISTS memory_service.idx_synthesis_jobs_tenant_id;
-- DROP TABLE IF EXISTS memory_service.synthesis_jobs;
```

---

## Module contract — `src/synthesis/jobs.py`

```python
def create_job(
    tenant_id: str,
    agent_id: str,
    job_type: str,
    payload: dict,
) -> str:
    """Insert a new job in 'queued' status. Returns job_id (uuid str)."""

def start_job(job_id: str) -> None:
    """Set status='running', started_at=now(). Idempotent if already running."""

def complete_job(job_id: str, result: dict) -> None:
    """Set status='succeeded', completed_at=now(), result=<dict>."""

def fail_job(job_id: str, error: str) -> None:
    """Set status='failed', completed_at=now(), error=<msg> (truncated to 4000 chars)."""

def cancel_job(job_id: str) -> None:
    """Set status='cancelled', completed_at=now(). Only works on queued/running jobs."""

def get_job(job_id: str, tenant_id: str) -> Optional[dict]:
    """Tenant-scoped fetch. Returns full row as dict or None if not found."""

def list_jobs(
    tenant_id: str,
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List recent jobs scoped to tenant; optional agent + status filters."""

def claim_next_queued_job(tenant_id: Optional[str] = None) -> Optional[dict]:
    """
    Atomically claim one queued job for processing using SELECT...FOR UPDATE SKIP LOCKED.
    Sets status='running', started_at=now(), returns the row.
    Returns None if no queued jobs.
    Used by the cron worker (T6, future task).
    """
```

All functions tenant-scoped where applicable. Use `_db_execute_rows`. No string-splitting on results — use native tuples.

**Error truncation:** errors are truncated to 4000 chars before storage to prevent unbounded payloads.

**Status transition rules:**
- `queued` → `running` (start)
- `queued` → `cancelled` (cancel before pickup)
- `running` → `succeeded` (complete)
- `running` → `failed` (fail)
- `running` → `cancelled` (cancel mid-run, rare)
- Any other transition: raise `InvalidJobStateTransition` exception.

---

## Steps

### Step 1 — Determine next migration number

```bash
cd /root/.openclaw/workspace/memory-product
ls migrations/ | grep -E '^[0-9]+' | sort -n | tail -3
```

**Gate G2:** output shows existing migration files; the new migration uses `MAX+1` zero-padded to 3 digits. Update `migrations/0XX_synthesis_jobs.sql` filename in the actual migration draft to use the real number.

### Step 2 — Draft the migration file

Write `migrations/0XX_synthesis_jobs.sql` with the schema body above. Do NOT apply it.

### Step 3 — **HALT for human review of migration**

```bash
echo "=== T4 MIGRATION REVIEW REQUIRED ==="
echo "Wrote migrations/0XX_synthesis_jobs.sql; requires human application."
echo "HEAD: $(git rev-parse HEAD)"
echo "Migration file diff:"
git diff migrations/
```

Write `CP8-P2-T4-MIGRATION-REVIEW.md` (NOT a `BLOCKED` note — this is a planned halt):

```markdown
# CP8 Phase 2 T4 — Migration ready for review

**Status:** Awaiting human application of migration before module + tests can be written.
**HEAD:** <sha>
**Migration file:** migrations/0XX_synthesis_jobs.sql
**To apply:**

  cd /root/.openclaw/workspace/memory-product
  set -a && source .env && set +a
  # Dry-run first:
  psql "$DATABASE_URL" -1 -v ON_ERROR_STOP=1 -c "BEGIN; \i migrations/0XX_synthesis_jobs.sql; \dt memory_service.synthesis_jobs; ROLLBACK;"
  # If clean:
  psql "$DATABASE_URL" -1 -v ON_ERROR_STOP=1 -c "BEGIN; \i migrations/0XX_synthesis_jobs.sql; COMMIT;"

**To resume CC autonomy after applying:**
  Re-launch CC with prompt:
  "Migration 0XX_synthesis_jobs.sql has been applied to prod.
   Resume CP8-P2-T4-JOBS-SCOPE.md from Step 4."
```

CC exits cleanly. **This is a halt by design, not a failure.**

### Step 4 — (Resumed run) Verify migration applied

```bash
psql "$DATABASE_URL" -c "\d memory_service.synthesis_jobs" | head -30
```

**Gate G2:** table exists with all columns from the contract. If not present → halt with BLOCKED note (true halt this time, not planned).

### Step 5 — Implement `src/synthesis/jobs.py`

Per module contract above. Module docstring documents:
- Status state machine (allowed transitions)
- `claim_next_queued_job` semantics (FOR UPDATE SKIP LOCKED)
- Tenant scoping requirements
- Error truncation policy

### Step 6 — Implement `tests/synthesis/test_jobs.py`

Eight tests:
1. `test_create_job_returns_uuid_in_queued_status`
2. `test_full_lifecycle_succeed` — create → start → complete → get
3. `test_full_lifecycle_fail` — create → start → fail → get
4. `test_cancel_queued_job` — create → cancel → get shows cancelled
5. `test_invalid_transition_raises` — try to complete a queued job (not started); expect `InvalidJobStateTransition`
6. `test_list_jobs_tenant_scoped` — create jobs in 2 tenants, verify list only returns one tenant's
7. `test_claim_next_queued_atomic` — create 3 queued jobs, claim_next 3 times concurrently (threading), verify each thread gets a different job, no double-claims
8. `test_error_truncation` — fail with a 10000-char error string, verify stored is ≤4000

Mark `@pytest.mark.integration`. Real DB. Tenant-scoped cleanup.

### Step 7 — Test gate (G3)

```bash
pytest tests/synthesis/test_jobs.py -v --tb=short 2>&1 | tee /tmp/t4-test-output.txt
grep -q "passed" /tmp/t4-test-output.txt && ! grep -q "failed" /tmp/t4-test-output.txt && echo 'T4 GATE PASS'
```

**HALT** on any test failure. The concurrency test (test #7) is the most likely to flake — if it does, halt and dump the actual claim distribution.

### Step 8 — Commit

```bash
git add migrations/0XX_synthesis_jobs.sql src/synthesis/jobs.py tests/synthesis/test_jobs.py
git status  # GATE: exactly those 3 files staged
git diff --cached --stat
```

Commit message:

```
CP8 Phase 2 T4: synthesis_jobs DB-backed persistence

Replaces in-memory jobs dict with persistent table.
Survives memory-api restarts. Closes long-standing job persistence gap.

Schema:
- memory_service.synthesis_jobs (id, tenant_id, agent_id, job_type,
  status, payload, result, error, created_at, started_at, completed_at)
- Status enum: queued|running|succeeded|failed|cancelled
- Indexes: tenant_id, status (partial), created_at, (tenant,agent)

Module:
- create_job, start_job, complete_job, fail_job, cancel_job
- get_job (tenant-scoped), list_jobs (tenant-scoped)
- claim_next_queued_job (atomic FOR UPDATE SKIP LOCKED)
- InvalidJobStateTransition raised on illegal transitions
- Errors truncated to 4000 chars

Migration applied to prod by Justin (review checkpoint).

Verification receipts:
[CC fills in: \d output from step 4, test results from step 7]

Files: migrations/0XX_synthesis_jobs.sql (NEW),
       src/synthesis/jobs.py (NEW, +N lines),
       tests/synthesis/test_jobs.py (NEW, 8 tests)
```

```bash
git commit -F /tmp/cp8-p2-t4-commit-msg.txt
git log -1 --stat
git push origin master
```

**Final gate:** `git push` exit code 0.

### Step 9 — Verify no service regression

```bash
journalctl -u memory-api --since "5 minutes ago" --no-pager | grep -E "ERROR|CRITICAL" | grep -v "analytics_events"
```

**Gate G2:** zero unexpected errors (the known `analytics_events` noise is tolerated).

---

## Halt conditions (specific to this task)

In addition to the protocol's standard halts:

1. **Migration number conflict** — picked number already exists. Halt and re-pick.
2. **Migration dry-run errors** — if Justin's dry-run during the review step fails, the resume prompt should NOT advance — Justin halts manually.
3. **`InvalidJobStateTransition` test fails on what should be a valid transition** — module logic bug. Halt.
4. **Concurrency test shows non-atomic claims** — `FOR UPDATE SKIP LOCKED` not working as expected. Halt.
5. **Service errors during step 9** that don't exist in pre-run logs. Halt and revert.

---

## Definition of done

All of:

1. Migration applied to prod (by Justin, mid-run).
2. `src/synthesis/jobs.py` exists per module contract.
3. All 8 tests pass.
4. Single commit on master pushed to remote.
5. Commit message contains real receipts.
6. No `CP8-P2-T4-BLOCKED.md` exists. (`CP8-P2-T4-MIGRATION-REVIEW.md` is expected to exist temporarily during the review halt and can be removed post-resume.)
7. `journalctl` clean post-commit.

**No deploy needed** — module not yet imported by `memory-api`. T2 imports it.
