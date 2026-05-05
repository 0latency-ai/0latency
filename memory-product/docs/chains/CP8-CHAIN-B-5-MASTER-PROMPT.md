**This chain conforms to docs/CC-CHAIN-FRAMEWORK.md. Estimated wall-clock: 25–35 min. Stages: 5. Tier: 1 Stage 01 (additive migration, halts at prod-apply boundary), Tier 0 Stages 02–05 (code/doc only).**

# CHAIN B-5 — Mechanical hardening + Tier 2 schema unblock

═══════════════════════════════════════════════════════════════════
EXECUTION MODEL
═══════════════════════════════════════════════════════════════════

You (CC) execute 5 stages sequentially on branch `b-5-chain`. Each stage has a verification gate, evidence file, and rollback path. You do not pause for human approval between stages.

**This chain has one legitimate halt: Stage 01.** The migration applies to staging autonomously, then halts before prod-apply per AUTONOMY-PROTOCOL Tier 2. Stages 02–05 continue regardless of Stage 01 halt status — they are independent of the migration.

**Halt conditions (the only legitimate stops):**
1. **Stage 01 staging-apply succeeds:** halt with success-report at `/tmp/b-5-stage-01-halt.md`, fire NO chime, continue Stage 02. (This is "halt at boundary," not "stop chain.")
2. **Stage 01 staging-apply fails:** halt with failure-report at `/tmp/b-5-stage-01-halt.md`, fire chime, stop chain. Stages 02–05 do NOT run.
3. **Service catastrophically down:** `systemctl restart memory-api` once, sleep 8, recheck. If still down, halt and chime.
4. **Novel correctness regression** in any stage: write `/tmp/b-5-halt-stage-NN.md` with full diagnostic, fire chime, stop.
5. **A stage commit fails to push 3× consecutively:** halt for human investigation.

**Everything else is mechanical.** A test failure in stage N triggers the rollback playbook (typically `git revert HEAD && systemctl restart memory-api`); chain advances to stage N+1 with the failure logged. Don't halt because a stage didn't ship cleanly — log it and move on.

═══════════════════════════════════════════════════════════════════
STANDING RULES (every stage)
═══════════════════════════════════════════════════════════════════

- **Workspace:** `/root/.openclaw/workspace/memory-product/` (you SSH from Mac into `root@164.90.156.169`).
- **Service surface:** memory-api (port 8420 REST), 0latency-mcp (port 3100 MCP).
- **psql pattern:** `cd /root/.openclaw/workspace/memory-product && set -a && source .env && set +a && psql "$DATABASE_URL"`.
- **Branch isolation:** all work happens on `b-5-chain`. Never touch master. Operator merges manually after chain completes.
- **Never echo secrets to stdout.** Read API keys from `.env` or DB; never print `zl_live_*` patterns.
- **Justin's tenant uuid:** `44c3080d-c196-407d-a606-4ea9f62ba0fc`.
- **Schema reminders:**
  - `memory_service.memories` has `headline`, `context` (NOT NULL), `full_content` (NOT NULL). NOT a single `content` column.
  - `memory_service.tenants` PK is `id` (uuid), NOT `tenant_id`.
- **Inner BEGIN/COMMIT in any SQL file = silent failure trap.** Write SQL with DDL only; let `db_migrate.sh` wrap the transaction.
- **After any service-restarting change:** `sleep 8 && curl -sf http://localhost:8420/health -o /dev/null -w "%{http_code}\n"` must return 200 before declaring stage complete.
- **Verify EVERY claimed end state with a real probe** (curl/journalctl/psql/git). CC self-reports without independent evidence are not trusted.
- **Forbidden-exit phrases (post-flight regex catches these):** `token budget`, `time budget`, `context budget`, `attention budget`, `running low`, `out of room`, `budget exhausted`, `getting close to`, `should stop here`, `complexity exceeds`, `implementation deferred`, `core complete`, `ready for follow-up`, `chain context`. If you reach for one of these, the framework is signaling you to halt with a halt-report instead of softening with a phrase.

═══════════════════════════════════════════════════════════════════
OUTCOME CATEGORIES (use exactly these in evidence + state log)
═══════════════════════════════════════════════════════════════════

- **SHIPPED** — code/doc landed, gate passed, commit pushed
- **SKIPPED-PREEXISTING** — work was already done before this chain; verified, no commit needed
- **BLOCKED-NEEDS-HUMAN** — Tier 2/3 boundary reached cleanly (this chain: Stage 01 prod-apply)
- **FAILED** — gate failed, rollback executed, no commit on master-relative branch
- **FAILED-NO-EVIDENCE** — stage claimed complete but evidence file missing (post-flight integrity gate)

═══════════════════════════════════════════════════════════════════
PRE-FLIGHT (run once before Stage 01)
═══════════════════════════════════════════════════════════════════

```bash
cd /root/.openclaw/workspace/memory-product

# 1. Master HEAD must be 8720c2a (B-4 chain report) or descendant
git status --porcelain | head -1   # EXPECT: empty (no uncommitted changes)
git fetch origin master
git log --oneline -1 master | tee /tmp/b-5-pre-head.log
# EXPECT: starts with 8720c2a or later

# 2. Branch isolation: create b-5-chain from master
git checkout -b b-5-chain
git log --oneline -1   # confirm same as master HEAD

# 3. Migration head clean
set -a && source .env && set +a
alembic current 2>&1 | tail -1
# EXPECT: 3f06f969c94f (head)

# 4. Services active and healthy
systemctl is-active memory-api 0latency-mcp   # EXPECT: active\nactive
curl -sf http://localhost:8420/health -o /dev/null -w "api=%{http_code}\n"   # EXPECT: 200
curl -sf http://localhost:3100/health -o /dev/null -w "mcp=%{http_code}\n"   # EXPECT: 200

# 5. Disk
df -h / | awk 'NR==2 {print $4}'   # EXPECT: > 5G

# 6. db_migrate.sh executable
test -x /root/.openclaw/workspace/memory-product/scripts/db_migrate.sh && echo "OK"   # EXPECT: OK

# 7. Stage 01 target constraint exists with current values
psql "$DATABASE_URL" -t -c "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'synthesis_audit_events_event_type_check';" | tee /tmp/b-5-pre-constraint.log
# EXPECT: contains 'synthesis_written'::text but NOT 'read'::text

# 8. Initialize state log + evidence directory
mkdir -p docs/chains/b-5
echo "# B-5 STATE LOG" > docs/chains/b-5/STATE-LOG.md
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> docs/chains/b-5/STATE-LOG.md
echo "Pre-HEAD: $(git log --oneline -1)" >> docs/chains/b-5/STATE-LOG.md
echo "" >> docs/chains/b-5/STATE-LOG.md
git add docs/chains/b-5/STATE-LOG.md
git commit -m "B-5: chain init, empty state log"

# 9. Touch /tmp state file
echo "B-5 PREFLIGHT PASSED $(date -u +%Y-%m-%dT%H:%M:%SZ)" > /tmp/b-5-chain-state.log
```

If pre-flight passes: proceed to Stage 01.
If pre-flight fails on item 1, 3, 4, 6, or 7: write `/tmp/b-5-halt-preflight.md` with details, fire chime, stop.

═══════════════════════════════════════════════════════════════════
STAGE 01 — Migration 026: add 'read' to synthesis_audit_events.event_type
═══════════════════════════════════════════════════════════════════

**Tier:** 2 (CHECK constraint replacement). Staging-apply autonomous; prod-apply halts.
**Estimated:** 8–12 min including staging verification.
**Goal:** unblock B-4's deferred Stage 04 (audit-aware reads) by adding `'read'` to the allowed event types.

### Background

B-4 Stage 04 was BLOCKED because `synthesis_audit_events.event_type` CHECK constraint does not include `'read'`. The constraint was captured at pre-flight (`/tmp/b-5-pre-constraint.log`). Adding a value to a CHECK constraint requires DROP + ADD CONSTRAINT — Tier 2 per AUTONOMY-PROTOCOL.

Migration is fully reversible: down-migration restores the original constraint definition.

### Steps

1. **Determine next migration number.** Current alembic head is `3f06f969c94f`. List existing migrations:
   ```bash
   ls migrations/versions/ | tail -5
   ```
   Identify the next sequential migration number (likely `026_*` based on prior conventions — verify against actual filenames).

2. **Author the migration file.** Path: `migrations/versions/026_add_read_to_synthesis_audit_event_type.py`. Use the exact pattern from prior reversible CHECK-constraint migrations (look at any existing migration that does `op.execute("ALTER TABLE ... DROP CONSTRAINT ...")` for template).

   The migration body:
   ```python
   """add read to synthesis_audit_events event_type

   Revision ID: <generate per Alembic convention>
   Revises: 3f06f969c94f
   Create Date: <ISO timestamp>
   """
   from alembic import op

   revision = '<generated>'
   down_revision = '3f06f969c94f'
   branch_labels = None
   depends_on = None

   ALLOWED_EVENT_TYPES_OLD = [
       'synthesis_written', 'redacted', 'resynthesized', 'consensus_run',
       'consensus_disagreement_logged', 'synthesis_candidate_prepared',
       'webhook_fired', 'prompt_version_changed', 'policy_changed',
       'rate_limit_blocked', 'state_transition', 'consensus_run_started',
       'consensus_skipped_insufficient_agents',
       'consensus_failed_insufficient_candidates', 'consensus_merge_failed',
       'consensus_disagreement_write_failed'
   ]
   ALLOWED_EVENT_TYPES_NEW = ALLOWED_EVENT_TYPES_OLD + ['read']

   def upgrade():
       op.execute("""
           ALTER TABLE memory_service.synthesis_audit_events
           DROP CONSTRAINT synthesis_audit_events_event_type_check;
       """)
       new_list = ", ".join(f"'{e}'::text" for e in ALLOWED_EVENT_TYPES_NEW)
       op.execute(f"""
           ALTER TABLE memory_service.synthesis_audit_events
           ADD CONSTRAINT synthesis_audit_events_event_type_check
           CHECK (event_type = ANY (ARRAY[{new_list}]));
       """)

   def downgrade():
       op.execute("""
           ALTER TABLE memory_service.synthesis_audit_events
           DROP CONSTRAINT synthesis_audit_events_event_type_check;
       """)
       old_list = ", ".join(f"'{e}'::text" for e in ALLOWED_EVENT_TYPES_OLD)
       op.execute(f"""
           ALTER TABLE memory_service.synthesis_audit_events
           ADD CONSTRAINT synthesis_audit_events_event_type_check
           CHECK (event_type = ANY (ARRAY[{old_list}]));
       """)
   ```

   **CRITICAL:** Verify the OLD list against `/tmp/b-5-pre-constraint.log` from preflight. If the captured constraint has a different value list than what's hardcoded above, USE THE CAPTURED LIST. Do not assume.

3. **Apply to staging via canonical migration command:**
   ```bash
   bash scripts/db_migrate.sh up
   ```
   This script: backs up prod → applies to staging → applies to prod with 5-sec abort window. **At the 5-sec abort prompt, ABORT.** Per AUTONOMY-PROTOCOL Tier 2, prod-apply requires human.

4. **Verify staging apply:**
   ```bash
   set -a && source .env && set +a
   # Confirm staging has new constraint
   psql "$STAGING_DATABASE_URL" -t -c "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'synthesis_audit_events_event_type_check';" | grep -q "'read'::text" && echo "STAGING_HAS_READ" || echo "STAGING_MISSING_READ"
   # Confirm prod still does NOT have new constraint (we aborted)
   psql "$DATABASE_URL" -t -c "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'synthesis_audit_events_event_type_check';" | grep -q "'read'::text" && echo "PROD_HAS_READ_UNEXPECTED" || echo "PROD_STILL_OLD_CORRECT"
   ```

   Expected output: `STAGING_HAS_READ` and `PROD_STILL_OLD_CORRECT`.

5. **Smoke test on staging:** insert a test row with `event_type='read'` to confirm the constraint accepts it, then delete it.
   ```bash
   psql "$STAGING_DATABASE_URL" -c "INSERT INTO memory_service.synthesis_audit_events (id, tenant_id, event_type, actor, payload) VALUES (gen_random_uuid(), '44c3080d-c196-407d-a606-4ea9f62ba0fc', 'read', 'b-5-test', '{}'::jsonb) RETURNING id;" | tee /tmp/b-5-stage-01-smoke.log
   psql "$STAGING_DATABASE_URL" -c "DELETE FROM memory_service.synthesis_audit_events WHERE actor='b-5-test';"
   ```
   If insert succeeds: constraint is correctly modified.
   If insert fails with check_violation: migration is broken. Run `bash scripts/db_migrate.sh down` against staging, mark stage FAILED, halt chain.

   *Note: schema fields (`actor`, `payload`, etc.) above are best-guess. If insert fails on column-not-found, inspect schema with `\d memory_service.synthesis_audit_events` and adjust the test insert. The goal is to write A row with `event_type='read'`.*

### Verification gate

```bash
# Staging has 'read' value
psql "$STAGING_DATABASE_URL" -t -c "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'synthesis_audit_events_event_type_check';" | grep -q "'read'::text"
# EXPECT: exit 0

# Prod still has OLD constraint (not yet applied)
psql "$DATABASE_URL" -t -c "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'synthesis_audit_events_event_type_check';" | grep -qv "'read'::text"
# EXPECT: exit 0 (prod does NOT contain 'read')

# Smoke insert succeeded on staging
grep -q "1 row" /tmp/b-5-stage-01-smoke.log
# EXPECT: exit 0

# Migration file exists in repo
test -f migrations/versions/026_*.py
# EXPECT: exit 0
```

### Halt protocol (this stage halts cleanly per Tier 2)

Write `/tmp/b-5-stage-01-halt.md` with:
```markdown
# B-5 Stage 01 — Tier 2 boundary halt

**Status:** STAGING APPLIED, PROD AWAITS HUMAN APPLY

## What's done
- Migration `026_add_read_to_synthesis_audit_event_type.py` authored and committed to `b-5-chain`.
- Applied to staging via `bash scripts/db_migrate.sh up`. Verified `'read'` value present in staging constraint.
- Smoke test: inserted+deleted a row with `event_type='read'` on staging. Constraint accepts the value.
- Prod constraint UNCHANGED (operator aborted at 5-sec prompt as required by AUTONOMY-PROTOCOL Tier 2).

## What's needed
Operator runs:
```
bash scripts/db_migrate.sh up
```
And does NOT abort at the 5-sec prompt this time. Migration applies to prod.

## Verification after operator apply
```bash
set -a && source .env && set +a
psql "$DATABASE_URL" -t -c "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'synthesis_audit_events_event_type_check';" | grep -q "'read'::text" && echo "PROD_NOW_HAS_READ"
```

## Rollback (if needed)
```
bash scripts/db_migrate.sh down
```

## Dependent work
B-4 Stage 04 (audit-aware reads on `/recall` for Enterprise tier) was BLOCKED on this constraint. After prod-apply, that work becomes Tier 0 mechanical and can ship in B-6 or a follow-up chain.
```

**DO NOT FIRE CHIME on this halt.** This is a "halt at boundary, continue chain" pattern. Stages 02–05 are independent of the prod-apply state and proceed regardless.

### Commit

```bash
git add migrations/versions/026_*.py docs/chains/b-5/stage-01-evidence.md
git commit -m "B-5 Stage 01: migration 026 - add 'read' to synthesis_audit_events.event_type CHECK

Tier 2 boundary stage. Migration authored, applied to staging via
db_migrate.sh, smoke-tested with insert+delete on staging. Prod
deliberately not applied — Tier 2 per AUTONOMY-PROTOCOL requires
human apply. Halt-report written to /tmp/b-5-stage-01-halt.md.

Unblocks B-4 Stage 04 (audit-aware reads on /recall) once prod
migration applied.

Outcome: BLOCKED-NEEDS-HUMAN (clean Tier 2 boundary halt)"
```

Append to STATE-LOG.md:
```
STAGE_01 BLOCKED-NEEDS-HUMAN commit=<sha> halt-report=/tmp/b-5-stage-01-halt.md
```

Append evidence file `docs/chains/b-5/stage-01-evidence.md` documenting all probes run and their outputs.

**Continue to Stage 02 regardless of halt status.**

═══════════════════════════════════════════════════════════════════
STAGE 02 — Fix analytics_events schema-qualifier bug
═══════════════════════════════════════════════════════════════════

**Tier:** 0
**Estimated:** 5–8 min
**Goal:** kill two failed-retry storms per request caused by unqualified `analytics_events` table reference. Real table is `memory_service.analytics_events`.

### Background

Per memory: "memory-api hits `analytics_events` unqualified (real table: `memory_service.analytics_events`), causing two failed retry storms per request ('relation \"analytics_events\" does not exist'). Storage and dedup unaffected."

Two valid fixes:
- (A) `SET search_path TO memory_service, public` at connection time
- (B) Schema-qualify all writes in code

**Choose B.** Reason: search_path changes are global side effects; schema-qualified writes are local and explicit. The structural-not-bandaid path.

### Steps

1. **Locate all unqualified `analytics_events` references:**
   ```bash
   cd /root/.openclaw/workspace/memory-product
   grep -rn "analytics_events" --include="*.py" | grep -v "memory_service.analytics_events" | grep -v "test_" | grep -v ".pyc"
   ```
   Expected: 1–4 sites. Capture output to `/tmp/b-5-stage-02-sites.log`.

2. **For each site, change `analytics_events` → `memory_service.analytics_events`** in the SQL string. Do NOT change Python identifiers, comments, or log strings — only the SQL table reference.

3. **Restart memory-api:**
   ```bash
   systemctl restart memory-api
   sleep 8
   curl -sf http://localhost:8420/health -o /dev/null -w "%{http_code}\n"
   ```

4. **Drive a request** to trigger an analytics_events write:
   ```bash
   set -a && source .env && set +a
   JKEY=$(psql "$DATABASE_URL" -t -c "SELECT api_key_live FROM memory_service.tenants WHERE id='44c3080d-c196-407d-a606-4ea9f62ba0fc';" | xargs)
   # Don't echo $JKEY. Use inline.
   curl -sf -H "X-API-Key: $JKEY" -H "Content-Type: application/json" \
     -d '{"query":"b-5 stage 02 schema fix smoke","limit":1}' \
     http://localhost:8420/recall -o /dev/null -w "%{http_code}\n"
   # EXPECT: 200
   sleep 2
   ```

5. **Verify no analytics_events errors in journal:**
   ```bash
   journalctl -u memory-api --since "1 minute ago" | grep "analytics_events" | grep -iE "error|relation.*does not exist|exception" | tee /tmp/b-5-stage-02-journal.log
   wc -l /tmp/b-5-stage-02-journal.log
   ```
   EXPECT: 0 lines.

### Verification gate

```bash
# Zero analytics_events errors in last minute
[ "$(wc -l < /tmp/b-5-stage-02-journal.log)" = "0" ] && echo "GATE_PASS"
# EXPECT: GATE_PASS

# Health still 200
curl -sf http://localhost:8420/health -o /dev/null -w "%{http_code}\n"
# EXPECT: 200

# No remaining unqualified references in src/ or api/
grep -rn "analytics_events" src/ api/ --include="*.py" | grep -v "memory_service.analytics_events" | grep -v "^[^:]*:[^:]*: *#" | wc -l
# EXPECT: 0
```

### Rollback

```bash
git checkout -- src/ api/
systemctl restart memory-api
sleep 8
```

### Commit

```bash
git add -A docs/chains/b-5/stage-02-evidence.md src/ api/
git commit -m "B-5 Stage 02: schema-qualify analytics_events writes

Was: analytics_events (unqualified) → relation does not exist →
psycopg2 retry storm (2× per request). Storage/dedup unaffected
but log noise material and obscured real errors.

Fixed by qualifying all SQL references to memory_service.analytics_events.
Chose schema-qualification over SET search_path because it's local
and explicit (structural fix, not band-aid).

Verified: drove a /recall request, journalctl shows zero
analytics_events errors in last minute.

Outcome: SHIPPED"
```

Append to STATE-LOG.md: `STAGE_02 SHIPPED commit=<sha>`

═══════════════════════════════════════════════════════════════════
STAGE 03 — _db_execute + split cleanup #1 (recall.py:138)
═══════════════════════════════════════════════════════════════════

**Tier:** 0
**Estimated:** 5–8 min
**Goal:** convert one `_db_execute()` site in `recall.py` to `_db_execute_rows()` to eliminate the post-execute string-splitting parse pattern that has bitten the codebase before (the `_retrieve_candidates` bug).

### Background

Per memory: "19 remaining `_db_execute+split` sites in recall.py with same vuln class as the fixed `_retrieve_candidates` bug — documented, not blocking." B-4 confirmed 11 `_db_execute` sites total in recall.py post-merge. Pick three sites for cleanup; this stage picks the first.

### Steps

1. **View the target site:**
   ```bash
   cd /root/.openclaw/workspace/memory-product
   sed -n '130,180p' src/recall.py
   ```
   Identify the `rows = _db_execute(f"""...""")` block at line 138 and follow the post-execute logic to find any `.split()`, manual string parsing of the returned rows, or other indicators that the call should be using `_db_execute_rows` instead.

2. **Decision tree:**
   - **If the site already returns structured rows and there's no string-splitting bug:** mark as SKIPPED-PREEXISTING, write evidence, advance. (Possible — some `_db_execute` sites are not buggy.)
   - **If the site fits the `_db_execute + split` anti-pattern:** convert to `_db_execute_rows` per the canonical fix (reference the existing `_retrieve_candidates` fix in the same file or in git history for the pattern).
   - **If the site is structurally different and needs investigation:** write evidence "site differs from anti-pattern; needs scoped investigation, not mechanical fix" and mark SKIPPED-PREEXISTING. Do not attempt non-mechanical work in this chain.

3. **Apply the fix** (only if anti-pattern confirmed). The conversion pattern:
   - Change `rows = _db_execute(...)` → `rows = _db_execute_rows(...)`
   - Update the row-handling code to consume structured tuples instead of split-strings
   - Preserve all existing behavior; this is a mechanical refactor, not a logic change

4. **Restart and smoke-test:**
   ```bash
   systemctl restart memory-api
   sleep 8
   curl -sf -H "X-API-Key: $JKEY" -H "Content-Type: application/json" \
     -d '{"query":"b-5 stage 03 smoke","limit":3}' \
     http://localhost:8420/recall -o /dev/null -w "%{http_code}\n"
   # EXPECT: 200
   ```

5. **Run any existing recall.py tests:**
   ```bash
   pytest tests/ -k "recall" --tb=short -x 2>&1 | tail -20 | tee /tmp/b-5-stage-03-pytest.log
   ```
   If tests pass: gate passes. If tests fail: ROLLBACK and mark FAILED.

### Verification gate

```bash
# Code parses
python3 -c "import ast; ast.parse(open('src/recall.py').read())" && echo "PARSE_OK"

# Health 200 after restart
curl -sf http://localhost:8420/health -o /dev/null -w "%{http_code}\n"
# EXPECT: 200

# /recall request succeeds
curl -sf -H "X-API-Key: $JKEY" -H "Content-Type: application/json" \
  -d '{"query":"b-5 stage 03 final","limit":1}' \
  http://localhost:8420/recall -o /dev/null -w "%{http_code}\n"
# EXPECT: 200

# Pytest pass (if tests exist for the affected code path)
grep -E "passed|no tests ran" /tmp/b-5-stage-03-pytest.log && ! grep "failed" /tmp/b-5-stage-03-pytest.log
```

### Rollback

```bash
git checkout -- src/recall.py
systemctl restart memory-api
sleep 8
```

### Commit (if SHIPPED)

```bash
git add src/recall.py docs/chains/b-5/stage-03-evidence.md
git commit -m "B-5 Stage 03: convert recall.py:138 _db_execute → _db_execute_rows

Eliminates one of 11 remaining _db_execute+split anti-pattern sites
in recall.py. Same vuln class as the fixed _retrieve_candidates bug
(memory: '19 remaining _db_execute+split sites with same vuln class').

Mechanical refactor: structured tuple consumption replaces post-execute
string parsing. Behavior preserved. Tests + smoke /recall pass.

Outcome: SHIPPED"
```

If SKIPPED-PREEXISTING: commit only the evidence file with that outcome documented.

Append to STATE-LOG.md: `STAGE_03 <outcome> commit=<sha>`

═══════════════════════════════════════════════════════════════════
STAGE 04 — _db_execute + split cleanup #2 (recall.py:292)
═══════════════════════════════════════════════════════════════════

**Tier:** 0
**Estimated:** 5–8 min
**Goal:** same as Stage 03, target line 292.

### Steps

Identical pattern to Stage 03 but targeting line 292:

1. View the site: `sed -n '285,330p' src/recall.py`
2. Decision tree same as Stage 03 (SKIPPED-PREEXISTING if not anti-pattern, SHIPPED if mechanically fixable, FAILED if rollback needed)
3. Apply fix, restart, smoke-test
4. Verification gate same shape

### Commit (if SHIPPED)

```bash
git add src/recall.py docs/chains/b-5/stage-04-evidence.md
git commit -m "B-5 Stage 04: convert recall.py:292 _db_execute → _db_execute_rows

Second of three _db_execute+split anti-pattern cleanups in B-5.

Outcome: SHIPPED"
```

Append to STATE-LOG.md: `STAGE_04 <outcome> commit=<sha>`

═══════════════════════════════════════════════════════════════════
STAGE 05 — _db_execute cleanup #3 (recall.py:343) + author docs/VERBATIM-GUARANTEE.md
═══════════════════════════════════════════════════════════════════

**Tier:** 0
**Estimated:** 8–12 min
**Goal:** ship the third cleanup AND author the long-pending verbatim-guarantee doc (T8 from CP8 Phase 1, plus negative-scope and public-claim sections that B-3.5 Stage 15 evidence flagged as missing).

### Part A — recall.py:343 cleanup

Same shape as Stage 03/04. View line 343 area, decide, fix or skip.

### Part B — VERBATIM-GUARANTEE.md

Path: `docs/VERBATIM-GUARANTEE.md`. Required sections:

```markdown
# Verbatim Guarantee

## What we promise

When 0Latency stores a memory atom, the original text is preserved verbatim and is retrievable byte-identical via the verification slice.

## How it's enforced

1. Atom write path: original `full_content` is hashed at write time; hash stored alongside.
2. Verification slice: `GET /memories/{id}/source` returns the verbatim atom and its stored hash.
3. CLI verification: `cli/verify.py` re-hashes the returned content and compares.
4. Contract test: `scripts/contract_test.py` runs nightly at 03:15 UTC, exercises the entire chain end-to-end against production.
5. Hollow-pass guard (T11): contract test exits non-zero if zero atoms were exercised — catches the case where the test "passed" only because there was nothing to test.

## What's covered

- All four atom write paths (CP8 Phase 2 T11 verification): MCP `memory_add`, REST `POST /memories`, the synthesis writer's source-atom store, and the bulk import path.

## What's NOT covered (negative scope)

- **Synthesis rows** — these are derived content, not source atoms. They have their own provenance (`source_memory_ids`) and lineage (`superseded_by`), but they are not byte-identical to any input. The verbatim guarantee applies only to atoms.
- **Embeddings** — these are vector representations, derived from atoms. Not part of the verbatim contract.
- **Redacted atoms** — once redacted (`redaction_state='redacted'`), the original content is removed. The audit trail proves the redaction happened, but the original text is by design unrecoverable.
- **Atoms older than the verification slice's existence** — atoms written before T9 (`GET /memories/{id}/source`) shipped were stored without the hash column populated. They are still byte-identical to what was written, but the contract test cannot verify them. (If this matters, a backfill is straightforward: re-hash existing `full_content` and write to `verbatim_hash`.)

## Public claim

0Latency claims: "every atom you store can be retrieved byte-identical, and we run a contract test against production every night to prove it." This claim is supported by the four-path coverage, the verification slice endpoint, and the nightly contract test with hollow-pass guard. We do NOT claim verbatim preservation for synthesis rows, embeddings, or redacted content.

## Verification

```
# As an operator, prove the guarantee right now:
ATOM_ID=$(curl -sf -H "X-API-Key: $KEY" "https://api.0latency.ai/recall?query=test&limit=1" | jq -r '.results[0].id')
curl -sf -H "X-API-Key: $KEY" "https://api.0latency.ai/memories/$ATOM_ID/source" | python3 cli/verify.py
# Output: VERIFIED if hashes match
```

## Cron

```
15 3 * * * /root/.openclaw/workspace/memory-product/scripts/contract_test.sh
```

Last successful run: see `/var/log/0latency/contract_test.log`.
```

### Verification gate

```bash
# Doc exists with all required sections
test -f docs/VERBATIM-GUARANTEE.md && \
  grep -q "Negative scope\|NOT covered" docs/VERBATIM-GUARANTEE.md && \
  grep -q "Public claim" docs/VERBATIM-GUARANTEE.md && \
  grep -q "Verification" docs/VERBATIM-GUARANTEE.md && \
  echo "DOC_GATE_PASS"

# If recall.py edited, parse + health
python3 -c "import ast; ast.parse(open('src/recall.py').read())" && echo "PARSE_OK"
curl -sf http://localhost:8420/health -o /dev/null -w "%{http_code}\n"
# EXPECT: 200
```

### Commit

```bash
git add docs/VERBATIM-GUARANTEE.md src/recall.py docs/chains/b-5/stage-05-evidence.md
git commit -m "B-5 Stage 05: third _db_execute cleanup + VERBATIM-GUARANTEE.md authored

Part A: recall.py:343 _db_execute → _db_execute_rows (or SKIPPED-PREEXISTING
per per-site decision tree).

Part B: docs/VERBATIM-GUARANTEE.md — closes T8 from CP8 Phase 1.
Sections: what we promise, enforcement (4-path coverage, verification slice,
CLI tool, nightly contract test, hollow-pass guard), negative scope
(synthesis/embeddings/redacted/legacy excluded), public claim, operator
verification snippet. Negative-scope and public-claim sections close
the gaps B-3.5 Stage 15 evidence flagged as missing.

Outcome: SHIPPED"
```

Append to STATE-LOG.md: `STAGE_05 SHIPPED commit=<sha>`

═══════════════════════════════════════════════════════════════════
POST-FLIGHT (run after Stage 05)
═══════════════════════════════════════════════════════════════════

```bash
cd /root/.openclaw/workspace/memory-product

# 1. Capture final state
git log --oneline master..b-5-chain | tee /tmp/b-5-chain-commits.log

# 2. Service health
systemctl is-active memory-api 0latency-mcp | tee /tmp/b-5-chain-health.log
curl -sf http://localhost:8420/health -o /dev/null -w "api=%{http_code}\n" >> /tmp/b-5-chain-health.log
curl -sf http://localhost:3100/health -o /dev/null -w "mcp=%{http_code}\n" >> /tmp/b-5-chain-health.log

# 3. Evidence file integrity gate
EVIDENCE_COUNT=$(ls docs/chains/b-5/stage-*-evidence.md 2>/dev/null | wc -l)
STATE_LINES=$(grep -E "^STAGE_0[1-5]" docs/chains/b-5/STATE-LOG.md | wc -l)
echo "EVIDENCE_FILES=$EVIDENCE_COUNT STATE_LINES=$STATE_LINES" | tee /tmp/b-5-integrity.log
# EXPECT: both = 5

# 4. Forbidden-exit phrase check on all chain artifacts
grep -iE "token budget|time budget|context budget|attention budget|running low|out of room|budget exhausted|getting close to|should stop here|complexity exceeds|implementation deferred|core complete|ready for follow.up|chain context" \
  docs/chains/b-5/STATE-LOG.md docs/chains/b-5/stage-*-evidence.md 2>/dev/null && \
  echo "=== FORBIDDEN PHRASES FOUND — DEGRADED ===" || \
  echo "=== CLEAN ==="

# 5. Journal sanity
journalctl -u memory-api --since "30 minutes ago" | grep -E "ERROR|Traceback" | grep -v analytics_events | tail -10
# EXPECT: empty (we just fixed analytics_events; if other errors appear, flag them)

# 6. Health checks (parse all touched files)
for f in src/recall.py src/storage_multitenant.py api/main.py; do
  python3 -c "import ast; ast.parse(open('$f').read())" && echo "$f PARSE OK" || echo "$f PARSE FAILED"
done
```

### Write the consolidated chain report

Path: `docs/chains/b-5/CHAIN-REPORT.md`

Required structure:
```markdown
# CP8 Chain B-5 Report

**Execution date:** <ISO>
**Branch:** b-5-chain
**Base commit:** <pre-flight HEAD>
**Final commit:** <post-flight HEAD>
**Wall-clock duration:** <minutes>
**Scope:** Mechanical hardening + Tier 2 schema unblock (audit-aware reads prerequisite)

## Executive Summary
<2–3 sentences>

## Stage Outcomes

### Stage 01 — Migration 026 (audit_events read): BLOCKED-NEEDS-HUMAN
**Reason:** Tier 2 boundary — staging applied, prod awaits operator.
**Halt-report:** /tmp/b-5-stage-01-halt.md
**Evidence:** docs/chains/b-5/stage-01-evidence.md

### Stage 02 — analytics_events schema-qualifier: <outcome>
... (same shape for all stages)

## Outcome Category Counts
- SHIPPED: <N>
- BLOCKED-NEEDS-HUMAN: 1 (Stage 01 by design)
- SKIPPED-PREEXISTING: <N>
- FAILED: <N>

## Forbidden-Exit Phrase Check
<grep result>

## Recommendations for B-6
1. **Apply migration 026 to prod** (operator, then audit-aware reads implementation becomes Tier 0 and ships in B-6)
2. **B-4 Stage 04 implementation** — audit-aware reads on /recall (now unblocked once prod migration applied)
3. Continue _db_execute cleanups: 8 remaining sites
4. Phase 5 pre-staging: webhook CRUD scaffold, pattern memory schema, decision journal write path
5. Cluster ID backfill (B-4 noted: expand=cluster works structurally but no data populates `metadata.cluster_id`)

## Health
<service status, journal sanity, parse status>

## Files Touched
<list>

## Conclusion
<2–3 sentences on whether the chain met its goals>
```

```bash
git add docs/chains/b-5/CHAIN-REPORT.md
git commit -m "B-5: chain report - <N> of 5 stages shipped"
git push origin b-5-chain
```

═══════════════════════════════════════════════════════════════════
FINAL ACTION (literal, standalone tool call, never chained)
═══════════════════════════════════════════════════════════════════

afplay /System/Library/Sounds/Glass.aiff
