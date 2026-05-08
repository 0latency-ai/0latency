# CP8 P5.3 — Decision Journals Write Path

**Tier:** 2 (schema-touching: NEW `memory_type='decision'` already in CHECK; new structured columns added; new endpoint).
**Wall-clock estimate:** 60–90 min.
**Dependencies:** None. Independent of P5.4/5/6.
**Branch:** `cp-p5-3-decision-journals`.

---

## Goal

Land `memory_type='decision'` as a first-class data primitive with structured fields. Write path + read-by-id only. **No dedicated dashboard UI** — that's deferred per Decision 4 in CHECKPOINT-8-SCOPE-v3.md. Synthesis layer (already shipped) can later cluster decisions over time once we have a corpus to work with.

---

## Why this is small

- `synthesis` was added to `memory_type` CHECK in migration 023 — that pattern is the template.
- `decision` is **already in the CHECK list** per the migration 023 verification output (line: `'synthesis'::text, 'fact'::text, 'decision'::text, ...`). No CHECK constraint change needed.
- We're adding a new endpoint `POST /memories/decision` and structured columns. That's it.
- No synthesis/cron/webhook coupling.

---

## Schema (migration 026)

Per CHECKPOINT-8-SCOPE-v3.md line 322:

```sql
-- migrations/026_add_decision_journal_columns.sql
BEGIN;

ALTER TABLE memory_service.memories
  ADD COLUMN IF NOT EXISTS decision_text text,
  ADD COLUMN IF NOT EXISTS alternatives_considered text[],
  ADD COLUMN IF NOT EXISTS rationale text,
  ADD COLUMN IF NOT EXISTS predicted_outcome text,
  ADD COLUMN IF NOT EXISTS actual_outcome text;

-- Index on decision rows for retrieval-by-type queries
CREATE INDEX IF NOT EXISTS idx_memories_decision_tenant_agent
  ON memory_service.memories (tenant_id, agent_id, created_at DESC)
  WHERE memory_type = 'decision';

-- Validation: decision rows MUST have decision_text + rationale populated.
-- Enforced via partial CHECK so non-decision rows are unaffected.
ALTER TABLE memory_service.memories
  ADD CONSTRAINT check_decision_required_fields
  CHECK (
    memory_type != 'decision'
    OR (decision_text IS NOT NULL AND rationale IS NOT NULL)
  );

COMMIT;
```

**Down migration** (rollback):

```sql
BEGIN;
ALTER TABLE memory_service.memories DROP CONSTRAINT IF EXISTS check_decision_required_fields;
DROP INDEX IF EXISTS memory_service.idx_memories_decision_tenant_agent;
ALTER TABLE memory_service.memories
  DROP COLUMN IF EXISTS actual_outcome,
  DROP COLUMN IF EXISTS predicted_outcome,
  DROP COLUMN IF EXISTS rationale,
  DROP COLUMN IF EXISTS alternatives_considered,
  DROP COLUMN IF EXISTS decision_text;
COMMIT;
```

**Tier 2 reasoning:** adds 5 nullable columns (additive, reversible) + 1 partial index + 1 partial CHECK constraint. The partial CHECK is the only thing that crosses Tier 1 territory — it can fail INSERTs of `memory_type='decision'` that omit required fields. Existing data unaffected (no current decision rows). Acceptable per AUTONOMY-PROTOCOL Tier 2: human-applied via `db_migrate.sh` with the standard 5-second abort window.

---

## API endpoint

`POST /memories/decision` — Enterprise tier only (per Decision 3 tier matrix).

**Request:**
```json
{
  "agent_id": "user-justin",
  "decision_text": "Adopt CP8 Phase 5 sub-task ordering: P5.7 → P5.3 → P5.4 → P5.5 → P5.6",
  "alternatives_considered": [
    "Defer P5.7, run P5.3-P5.6 first",
    "Run P5.3 + P5.7 in parallel"
  ],
  "rationale": "P5.7 fixes test infra blocking P5.5; landing it first prevents skipped-test debt accumulation. P5.3-P5.4 are independent and can run anytime.",
  "predicted_outcome": "Phase 5 closes in 2-3 days; CP8 fully done before May 15.",
  "headline": "P5 sequencing: test-infra-first",
  "context": "CP8 Phase 5 sub-task ordering decision",
  "importance": 0.7,
  "metadata": {}
}
```

**Required fields:** `agent_id`, `decision_text`, `rationale`, `headline`, `context`.
**Optional:** `alternatives_considered`, `predicted_outcome`, `actual_outcome`, `importance` (default 0.5), `metadata`.

**Response:** Standard 202 with `memory_id` (matches existing `/memories/extract` shape — it's just a typed memory).

**Tier gate:** Enterprise only. Free/Pro/Scale receive 403 with `{"error": "decision_journals_enterprise_only"}`. Reuse existing tier-gate decorator from P5.2 audit endpoint.

---

## PATCH endpoint (for `actual_outcome` later)

`PATCH /memories/{memory_id}/outcome` — populates `actual_outcome` after the fact. The whole point of decision journals is closing the loop on predicted vs actual. This endpoint exists for that.

**Request:**
```json
{
  "actual_outcome": "P5.7 closed clean in one CC chain; P5.3 starting on schedule."
}
```

**Constraints:**
- Memory must be `memory_type='decision'`.
- Tenant isolation enforced.
- Audit event written: `decision_outcome_recorded` with old `actual_outcome` (likely NULL) → new value.
- Append-only audit semantics — the PATCH overwrites the column but the audit trail captures every change.

**Why a separate endpoint vs generic PATCH:** the existing memory model doesn't have a generic update endpoint, and we want `actual_outcome` writes to flow through the audit log. Cheaper to add a single targeted endpoint than retrofit a general one. Total: ~30 lines of code.

---

## Tasks (CC chain)

### Step 1 — Migration 026 dry-run
- Author SQL (above).
- Strip inner `BEGIN/COMMIT` per migration discipline.
- Run via `bash scripts/db_migrate.sh dry-run migrations/026_add_decision_journal_columns.sql`.
- Halt if dry-run output doesn't end in `ROLLBACK`.

### Step 2 — Apply migration 026 (Tier 2, 5-sec abort)
- `bash scripts/db_migrate.sh up migrations/026_add_decision_journal_columns.sql`
- Verify columns + index + constraint via `\d memory_service.memories` and `pg_constraint` query.

### Step 3 — Endpoint implementation
- Add `POST /memories/decision` to `api/main.py`.
- Add `PATCH /memories/{memory_id}/outcome` to `api/main.py`.
- Both endpoints reuse existing tenant-resolution + tier-gate machinery.
- Audit log writes for both: `decision_created`, `decision_outcome_recorded`.

### Step 4 — Integration tests
Create `tests/decisions/test_decision_endpoint.py` covering:
1. POST with all required fields → 202, memory_id returned, row in DB has all columns populated.
2. POST missing `decision_text` → 422.
3. POST missing `rationale` → 422.
4. POST as Free/Pro/Scale tier → 403.
5. POST as Enterprise → 202.
6. POST with empty `alternatives_considered` array → 202 (allowed — represents "no alternatives weighed").
7. PATCH outcome on decision row → 200, `actual_outcome` updated, audit event logged.
8. PATCH outcome on non-decision row → 400.
9. PATCH outcome cross-tenant → 404.
10. CHECK constraint blocks raw INSERT of `memory_type='decision'` without `decision_text` (DB-level).

Reuse the package-isolation conftest from P5.7. New `tests/decisions/__init__.py` + reuse parent conftest.

### Step 5 — Validation gate
- All 10 tests PASS.
- Full suite collection still 297+ tests, 4 pre-existing errors (no regression).
- `curl -X POST https://mcp.0latency.ai/memories/decision -H "X-API-Key: ..." -d '{...}'` returns 202 in prod.

### Step 6 — Commit + push
Single commit on `cp-p5-3-decision-journals` branch. Do NOT merge — operator review.

### Step 7 — Deliverable
`docs/CP8-P5-3-COMPLETE.md` with:
- Migration 026 verification (column list, constraint def, index def).
- Endpoint contract (request/response shapes).
- Tier gate behavior verified.
- Test counts.
- Audit log verification (fetch the `decision_created` event via P5.2 endpoint).
- Confirmation no other production code paths modified.

---

## Halt conditions

1. **Migration dry-run shows actual mutation.** Halt — the migration discipline rule was violated, debug.
2. **`memory_type='decision'` is NOT already in the CHECK constraint** (contradicting migration 023 evidence). Halt and add it via the migration before adding columns.
3. **Tier-gate decorator not reusable** — would require refactoring P5.2 code. Halt and document; this is Tier 2 scope creep.
4. **Existing decision-related code found.** Search `api/main.py` and `src/` for any prior `decision` memory_type handling. If found, scope-doc is stale.

---

## Out of scope (explicit)

- Decision dashboard UI (deferred to CP12+).
- Decision-aware synthesis (the synthesis layer can already cluster any memory_type — no special handling needed; it'll start picking up decisions automatically once they exist).
- Outcome reminder/nudge system ("you predicted X two weeks ago, what was the actual outcome?") — future product surface.
- Bulk decision import.
- Pro/Scale tier access (Enterprise-only per Decision 3).

---

## Standing rules (carry-forward)

1. PRIME DIRECTIVE: never request paste of secrets.
2. python3 not python.
3. Tier 2 — single migration applied via `db_migrate.sh` with 5-sec abort. No raw `psql` ALTER TABLE.
4. No `--ignore`/`--skip` workarounds. Fix structurally.
5. Re-use existing modules (tier-gate decorator, audit-log writer, tenant resolver).
6. Single commit on branch.
7. Do NOT merge to master. Operator review required.
8. Run tests, don't just collect.
9. If diagnosis points to needing CHECK constraint changes or trigger changes → halt and report.

---

## Operator notes

- This is the cleanest of the remaining Phase 5 sub-tasks. Schema is well-specified (5 nullable columns), endpoint pattern is well-trodden (mirrors `/memories/extract`), tests follow the P5.7 isolation pattern.
- The `actual_outcome` PATCH is the one design choice that wasn't pre-spec'd — operator should confirm this is acceptable scope creep (~30 LOC). The alternative is shipping P5.3 without it and adding the PATCH later when we actually have decisions whose outcomes need recording. Recommendation: ship together — the loop closure is the whole point of decision journals, and shipping without it means immediate follow-up work.
- After P5.3 closes, P5.4 (diff webhooks) is next-up. P5.4 is fully unblocked.
