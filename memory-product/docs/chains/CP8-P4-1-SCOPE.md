# CP8 P4.1 — Phase 4 closure chain

**Naming:** P{phase}.{chain} → this is Phase 4, chain 1.
**Branch:** `p4-1-chain` (cut from `master` at HEAD `3e7b677`).
**Target:** 6 stages, 30–40 min wall-clock, framework-conformant.
**Goal:** Close CP8 Phase 4 (synthesis-aware read path) cleanly. Land the P0 protocol fix from B-5 incident first so the chain itself is safe.

**Standing rules (carry forward from B-5, with B-3.5/B-5 lessons baked in):**

1. **Branch isolation.** All work on `p4-1-chain`. Operator merges to master manually after chain completes.
2. **Stage cap 6.** Do not add stages mid-run. If a stage discovers additional work, file it for P4.2 — do not absorb it.
3. **Category discipline.** Every stage is Phase-4-closure work. No new write paths, no new schema, no Phase 5 pre-staging.
4. **No questionnaires.** CC makes the call inside scope. At any out-of-scope boundary → halt and write `CP8-P4-1-S{NN}-BLOCKED.md`.
5. **Outcome categories** (use exactly one per stage): `SHIPPED` | `SKIPPED-PREEXISTING` | `SKIPPED-OUT-OF-SCOPE` | `BLOCKED-NEEDS-HUMAN` | `FAILED`. Do not invent new categories.
6. **Halt-at-boundary, continue chain.** A Tier-2 prod-apply halt (Stages 01 and 03 are candidates) is `BLOCKED-NEEDS-HUMAN` — write the halt note, but DO NOT exit the chain. Subsequent stages that don't depend on the halted change continue. End-of-chain chime fires only after the final stage attempts.
7. **Evidence file per stage.** Each stage writes `docs/chains/p4-1/stage-NN-evidence.md` containing: commit SHA (or "no commit — halted"), files touched, verification commands run, last 20 lines of verification output, outcome category. Each stage also appends one line to `docs/chains/p4-1/STATE-LOG.md`: `<timestamp> | stage-NN | <outcome> | stage-NN-evidence.md`.
8. **No multi-line inline python heredocs.** All file edits via `str_replace`/`view` against repo files. Verification via single-line commands or pre-written scripts in `scripts/`. No `python3 -c '<heredoc>'` in stage bodies (B-3.5 lesson — markdown round-trip is not transparent).
9. **No `&&` chains past a verification gate.** If a parse/test step fails, subsequent commands must not run. Use explicit `set -e` at script top, or split into separate command blocks.
10. **Forbidden-exit regex** (post-flight grep against STATE-LOG and all commit messages — match = chain marked bailed):
    ```
    token budget|time budget|context budget|attention budget|running low|out of room|budget exhausted|getting close to|should stop here|I'll get back to|TODO|skipping for now|will fix later|punting|come back to this
    ```
    If CC reaches a structural limit, write SHIPPED for completed stages, `BLOCKED-NEEDS-HUMAN` with reason `structural-limit-reached` for the current stage, and stop. Do NOT euphemize.
11. **Audio chime is operator-fired**, not CC-fired. End-of-chain chime is a standalone tool call by operator after `CP8-P4-1-COMPLETE.md` is reviewed. Chain itself does not call `afplay`.
12. **Production write boundary.** Per AUTONOMY-PROTOCOL: no Tier-2 migrations from autonomous runs, no prod backfills outside `memory_service.memories`/`raw_turns` test fixtures. Stage 03's backfill is the explicit halt-at-boundary candidate (see Stage 03 for handling).

**Pre-flight (before any stage):**
```bash
cd /root/.openclaw/workspace/memory-product
git status                                    # GATE: clean tree
git log -1 --oneline                          # record: should be 3e7b677 or descendant
git checkout -b p4-1-chain                    # GATE: branch created
mkdir -p docs/chains/p4-1                     # GATE: chain dir exists
echo "# P4.1 STATE LOG" > docs/chains/p4-1/STATE-LOG.md
echo "" >> docs/chains/p4-1/STATE-LOG.md
echo "Format: \`<UTC timestamp> | stage-NN | <outcome> | <evidence-file>\`" >> docs/chains/p4-1/STATE-LOG.md
echo "" >> docs/chains/p4-1/STATE-LOG.md
git add docs/chains/p4-1/STATE-LOG.md
git commit -m "P4.1 pre-flight: initialize chain state log"
set -a && source .env && set +a               # GATE: env loaded
psql "$DATABASE_URL" -c "SELECT version_num FROM alembic_version;" -t \
  | grep -q ce42a2cd8bff                      # GATE: prod alembic head matches handoff
curl -sS http://localhost:8420/health | grep -q '"status".*"ok"'  # GATE: services healthy
```

If any gate fails → halt, write `CP8-P4-1-PREFLIGHT-BLOCKED.md`, exit (no chime).

---

## Stage 01 — `db_migrate.sh` real human gate (P0)

**Tier:** 0 (script edit only, no migration runs).
**Why P0:** B-5 incident — `sleep 5` is not a human gate. CC ran non-interactively, script proceeded to prod. Must land before any future Tier 2 migration.

**In scope:**
- `scripts/db_migrate.sh` — replace the `sleep 5` confirmation with a real stdin read.

**Out of scope:**
- Running any migration.
- Changing Tier classification logic elsewhere.
- Touching `docs/AUTONOMY-PROTOCOL.md` (text already correct; only the script was wrong).

**Steps:**
1. Read `scripts/db_migrate.sh` lines 35-60 (around the prod confirmation block). Identify the exact `echo`/`sleep 5` lines.
2. Replace with:
   ```bash
   echo ""
   echo "Staging apply complete. About to apply to PRODUCTION."
   echo "Type 'apply' (lowercase, exact) to confirm prod migration."
   read -r -p "> " REPLY < /dev/tty
   if [ "$REPLY" != "apply" ]; then
     echo "Aborted. Reply was: '$REPLY'"
     exit 1
   fi
   ```
   The `< /dev/tty` is the critical bit — forces a real terminal even when the script is piped/redirected. Non-interactive runs (CC) will fail closed instead of bypassing.

3. **G2-style verification gate:**
   ```bash
   grep -c 'sleep 5' scripts/db_migrate.sh    # GATE: returns 0
   grep -c '/dev/tty' scripts/db_migrate.sh   # GATE: returns 1
   grep -q 'Type .apply.' scripts/db_migrate.sh && echo G2-S01 PASS
   ```

4. **Commit (single, on `p4-1-chain`):**
   ```
   P4.1 S01: db_migrate.sh real human gate

   B-5 incident root cause: `sleep 5` is not a human gate. CC ran
   non-interactively, script proceeded to prod after 5 seconds. Migration
   027 applied to prod outside the AUTONOMY-PROTOCOL Tier 2 boundary.

   Fix: replace sleep with `read -r -p "> " REPLY < /dev/tty`. Requires
   exact string "apply" to proceed. Non-interactive runs fail closed.

   Verification:
   $ grep -c 'sleep 5' scripts/db_migrate.sh
   0
   $ grep -c '/dev/tty' scripts/db_migrate.sh
   1

   Files: scripts/db_migrate.sh
   ```

**Halt conditions:**
- `scripts/db_migrate.sh` not found at expected path → halt.
- The `sleep 5` confirmation block doesn't match the documented shape (e.g. someone else already partial-fixed it) → halt and report what was found.

---

## Stage 02 — Audit-aware reads on Enterprise `/recall`

**Tier:** 0 (mechanical — migration 027 already on prod, constraint accepts `'read'`).
**Why:** B-4 Stage 04 was deferred until the constraint was unblocked. Now it is.

**In scope:**
- `api/recall.py` (or wherever `/recall` writes audit events — likely a helper in `synthesis/audit.py`).
- New audit emission path: when `/recall` returns ≥1 synthesis row AND tenant tier == `enterprise`, write a row to `synthesis_audit_events` with `event_type='read'`.

**Out of scope:**
- Audit emission for non-Enterprise tiers (cost discipline per CP8 v3 — Scale audit on read is non-trivial at scale).
- Schema changes (none needed; constraint already accepts `'read'`).
- Changing recall ranking, BM25/vector weights, RRF, etc.

**Audit row shape:**
```sql
INSERT INTO memory_service.synthesis_audit_events
  (tenant_id, target_memory_id, event_type, actor, occurred_at, event_payload)
VALUES
  ($tenant_id, NULL, 'read', $actor, NOW(),
   jsonb_build_object(
     'query', $query_text,
     'returned_synthesis_ids', $synthesis_ids_array,
     'role_filter', $role_filter,
     'expand', $expand_param
   ));
```
- `target_memory_id` = NULL (event is query-scoped, not row-scoped).
- `actor` = the agent_id from the request, or `'api'` if unauthenticated path.
- `returned_synthesis_ids` = uuid[] of synthesis rows returned (from the recall result before serialization).
- `role_filter` = the role_tag used in the query (or `'public'` default).
- `expand` = whichever expand param was set (`'evidence'` / `'cluster'` / null).

**Steps:**
1. Locate the `/recall` handler. Identify the point AFTER candidates are merged but BEFORE response serialization where we know:
   - tenant tier
   - which returned rows are syntheses (memory_type='synthesis')
   - the original query string and params
2. Add the audit emission. Use existing DB connection / pool. Single INSERT, fire-and-forget on a try/except — failure to write audit must NOT break recall (log a warning, continue).
3. **Gate (G1 + G2 combined):**
   ```bash
   # Provoke a recall that returns synthesis rows on user-justin (Enterprise)
   curl -sS -X POST http://localhost:8420/recall \
     -H "X-API-Key: $ZEROLATENCY_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query": "what are my themes", "limit": 10}' \
     | python3 -c "import sys,json; r=json.load(sys.stdin); assert any(m.get('memory_type')=='synthesis' for m in r.get('results',[])), 'no synthesis row in result'"

   # Verify audit row written within last 60s
   psql "$DATABASE_URL" -c "
     SELECT COUNT(*) FROM memory_service.synthesis_audit_events
     WHERE event_type='read' AND occurred_at > NOW() - INTERVAL '60 seconds';
   " -t | grep -qE '\s+[1-9]'
   echo G-S02 PASS
   ```

4. **Negative-path gate** (Scale tenant must NOT emit `read` audit):
   - If a Scale tenant fixture exists, run the same recall against it and assert no new `read` row appears.
   - If no Scale tenant fixture exists in the DB → SKIPPED-PREEXISTING with note (positive path proves Enterprise emission; tier-gate logic verified by code review of the conditional).

5. **Commit:**
   ```
   P4.1 S02: audit-aware reads on Enterprise /recall

   When /recall returns >=1 synthesis row AND tenant tier == enterprise,
   emit synthesis_audit_events row with event_type='read'. Migration 027
   constraint already accepts 'read'.

   Tier-gated: Scale and below do not emit (cost discipline, CP8 v3).
   Failure to write audit logs a warning; does not break recall.

   Files: api/recall.py, synthesis/audit.py (or equivalent)
   ```

**Halt conditions:**
- The `/recall` handler structure has drifted from what's expected (no clear post-merge / pre-serialize point) → halt.
- Tenant tier resolution doesn't exist on the request context → halt (means the tier-gate logic is missing globally; out of scope to add here).

---

## Stage 03 — Cluster ID backfill (HALT-AT-BOUNDARY pattern)

**Tier:** 1 staging-only inside CC. Prod apply is operator-side (halt at boundary).

**Why:** `expand=cluster` returns empty arrays today because existing synthesis rows don't have `metadata.cluster_id` populated. New rows being written by the writer SHOULD populate it; existing rows from B-2 onward need backfill.

**Why halt-at-boundary:** Per AUTONOMY-PROTOCOL §"What this protocol explicitly does NOT do" — no production data writes from autonomous runs outside test fixtures. CC validates on staging; operator runs on prod manually after reviewing the script + staging receipts. Chain continues past this stage regardless (Stages 04, 05, 06 don't depend on prod backfill being applied).

**In scope (CC):**
- Author the backfill script `scripts/backfill_cluster_id.py`.
- Read-only verify the writer already populates `metadata.cluster_id` on new writes.
- Apply backfill to staging DB and capture receipts.
- Halt at the prod-apply line. Write halt note. Continue chain.

**Out of scope (CC):**
- Running `python3 scripts/backfill_cluster_id.py` against the prod `DATABASE_URL`.
- Schema migration (this is data-only on an existing jsonb column).
- Changing the writer.

**Cluster ID derivation:**
- Cluster identity = the set of `parent_memory_ids` on the synthesis row (those ARE the cluster members).
- `cluster_id` = SHA-256 hex of sorted-and-comma-joined parent UUIDs, first 16 chars.
- Deterministic: same parent set → same cluster_id, regardless of write order.

**Steps:**

1. **Read-only writer check** (halt if writer missing the field):
   ```bash
   grep -n "cluster_id" synthesis/writer.py
   ```
   If zero matches → halt with `CP8-P4-1-S03-BLOCKED.md` (writer missing the field; backfill alone won't suffice; chain still continues to Stage 04).

2. **Author backfill script** at `scripts/backfill_cluster_id.py` using `view`/`create_file` tool (NOT inline heredoc):
   ```python
   #!/usr/bin/env python3
   """One-shot backfill of metadata.cluster_id for existing synthesis rows."""
   import os, hashlib
   import psycopg2
   from psycopg2.extras import Json

   def cluster_id(parent_ids):
       sorted_ids = sorted(parent_ids)
       return hashlib.sha256(",".join(sorted_ids).encode()).hexdigest()[:16]

   def main():
       conn = psycopg2.connect(os.environ["DATABASE_URL"])
       cur = conn.cursor()
       cur.execute("""
           SELECT id, metadata
           FROM memory_service.memories
           WHERE memory_type = 'synthesis'
             AND (metadata->>'cluster_id' IS NULL OR metadata->>'cluster_id' = '')
       """)
       rows = cur.fetchall()
       updated = 0
       for memory_id, metadata in rows:
           parents = metadata.get("parent_memory_ids") or []
           if not parents:
               continue
           cid = cluster_id(parents)
           new_metadata = {**metadata, "cluster_id": cid}
           cur.execute(
               "UPDATE memory_service.memories SET metadata = %s WHERE id = %s",
               (Json(new_metadata), memory_id)
           )
           updated += 1
       conn.commit()
       print(f"Backfilled cluster_id on {updated} synthesis rows")

   if __name__ == "__main__":
       main()
   ```

3. **Staging dry-run** (CC runs this):
   ```bash
   # Run against staging DB explicitly
   PGDATABASE=memory_service_staging python3 scripts/backfill_cluster_id.py
   psql -d memory_service_staging -c "
     SELECT
       COUNT(*) FILTER (WHERE metadata->>'cluster_id' IS NOT NULL) as with_cid,
       COUNT(*) FILTER (WHERE metadata->>'cluster_id' IS NULL) as without_cid
     FROM memory_service.memories WHERE memory_type='synthesis';
   "
   ```
   Capture both counts in evidence file.

4. **Halt at prod-apply boundary.** CC writes `CP8-P4-1-S03-PROD-APPLY-PENDING.md`:
   ```markdown
   # Stage 03 — Cluster ID backfill: STAGING SHIPPED, PROD APPLY PENDING

   Script authored, validated on staging.
   Operator must run on prod manually:

       cd /root/.openclaw/workspace/memory-product
       set -a && source .env && set +a
       python3 scripts/backfill_cluster_id.py

   Staging receipt:
   <psql output from Step 3>

   This is a halt-at-boundary, not a chain bail. Stages 04+ continue.
   ```

5. **Commit (script + halt note, not the prod backfill itself):**
   ```bash
   git add scripts/backfill_cluster_id.py CP8-P4-1-S03-PROD-APPLY-PENDING.md
   git commit -F- <<'EOF'
   P4.1 S03: cluster_id backfill script (staging-validated, prod pending)

   `expand=cluster` returned empty before because existing synthesis rows
   pre-dated cluster_id field. Backfill derives cluster_id deterministically
   from parent_memory_ids (SHA-256 hex first 16 chars of sorted-joined IDs).

   Writer (synthesis/writer.py) populates cluster_id on new writes.
   This script handles legacy rows.

   Staging receipt: <N> rows updated, 0 remaining without cluster_id.
   Prod apply: pending operator review and execution.

   Files: scripts/backfill_cluster_id.py (NEW),
          CP8-P4-1-S03-PROD-APPLY-PENDING.md (halt note)
   EOF
   ```

6. **Outcome category:** `BLOCKED-NEEDS-HUMAN` (halt-at-boundary by design, not a failure).

7. **Evidence file** `docs/chains/p4-1/stage-03-evidence.md` notes: "Halt-at-boundary by design. Prod backfill ships when operator runs script. Stage 06 V5 verification will run AFTER operator applies; mark V5 as PENDING in interim closure doc."

**Halt conditions (true halts, beyond the designed boundary):**
- Writer doesn't populate `cluster_id` on new writes (halt; writer fix is a separate scope).
- `parent_memory_ids` not at `metadata.parent_memory_ids` (halt; schema drift).
- Staging backfill leaves any synthesis-row-with-parents at NULL cluster_id (halt; script bug).
- No staging DB available (`memory_service_staging` doesn't exist) → halt.

---

## Stage 04 — nginx fix for `api.0latency.ai/recall` 502

**Tier:** 1 (config change, reversible, no DB).

**Why:** `/recall` works on `localhost:8420` but returns 502 via the public `api.0latency.ai` subdomain. Likely missing upstream block, missing `proxy_pass` for the route, or stale config not reloaded.

**In scope:**
- nginx config under `/etc/nginx/sites-available/` (or wherever `api.0latency.ai` is configured).
- nginx reload.

**Out of scope:**
- Adding new endpoints to nginx beyond what already exists at `localhost:8420`.
- TLS/SSL config changes.
- DNS changes.

**Steps:**
1. **Diagnose:**
   ```bash
   # Confirm 502 from public, 200 from local
   curl -sS -o /dev/null -w "%{http_code}\n" https://api.0latency.ai/health
   curl -sS -o /dev/null -w "%{http_code}\n" -X POST https://api.0latency.ai/recall \
     -H "X-API-Key: $ZEROLATENCY_API_KEY" -H "Content-Type: application/json" \
     -d '{"query":"test","limit":1}'
   curl -sS -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8420/recall \
     -H "X-API-Key: $ZEROLATENCY_API_KEY" -H "Content-Type: application/json" \
     -d '{"query":"test","limit":1}'
   ```
   Record exact status codes.

2. **Identify nginx config:**
   ```bash
   grep -rn "api.0latency.ai" /etc/nginx/sites-enabled/ /etc/nginx/sites-available/
   grep -rn "proxy_pass" /etc/nginx/sites-enabled/ | grep -i 8420
   ```

3. **Common causes and fixes** (CC picks the matching one):
   - **No location block for `/recall`** → add `location /recall { proxy_pass http://localhost:8420; ...standard headers... }` or confirm the catch-all `location /` already proxies everything.
   - **Upstream block missing** → add `upstream memory_api { server localhost:8420; }` and reference it.
   - **Wrong port** → fix to 8420.
   - **Config file edited but nginx not reloaded** → `nginx -t && systemctl reload nginx`.

4. **Apply fix on staging-equivalent first** if a non-prod nginx exists; otherwise edit prod config carefully:
   ```bash
   # Always test config before reloading
   nginx -t
   # Only reload if test passes
   systemctl reload nginx
   ```

5. **Gate:**
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" -X POST https://api.0latency.ai/recall \
     -H "X-API-Key: $ZEROLATENCY_API_KEY" -H "Content-Type: application/json" \
     -d '{"query":"test","limit":1}'
   # GATE: must return 200 (or 4xx for auth/payload, NOT 502/504)
   ```

6. **Commit** (config file lives outside the repo; instead, copy the patched config into `infra/nginx/api.0latency.ai.conf` in the repo for version-controlled record):
   ```
   P4.1 S04: nginx fix for api.0latency.ai /recall 502

   Public subdomain returned 502 on /recall while localhost:8420 returned
   200. Root cause: <fill in based on diagnosis — missing location block /
   wrong upstream / not reloaded>.

   Fix applied to /etc/nginx/sites-available/api.0latency.ai.
   Snapshot copied to infra/nginx/ for repo record.

   Verification:
   $ curl -sS -o /dev/null -w "%{http_code}\n" -X POST https://api.0latency.ai/recall ...
   200

   Files: infra/nginx/api.0latency.ai.conf (NEW or UPDATED)
   ```

**Halt conditions:**
- nginx config files not at expected paths → halt with discovery.
- `nginx -t` fails on the patched config → halt and revert (do NOT reload a broken config).
- Public still 502 after reload → halt; deeper issue (TLS termination, firewall, upstream timeouts).

---

## Stage 05 — Memory edit correction + 2 `_db_execute + split` cleanups

**Tier:** 0 (code refactor + memory housekeeping).

**Why:** Two cleanup items that are cheap to ship together. B-5 verified the `analytics_events` schema bug is fixed in code; userMemories still claims it's open. And `recall.py` has 8 remaining `_db_execute + split` sites with the same vuln class as the one B-5 fixed.

**In scope:**
- `recall.py` — refactor 2 of the 8 remaining `_db_execute + split` call sites to use proper parameterized queries (same pattern as B-5's fix).
- Memory edit (handled by the operator outside CC; CC just notes it in the chain summary).

**Out of scope:**
- The other 6 `_db_execute + split` sites (rolling P4.x cleanup).
- Any logic change beyond the call-site refactor.

**Steps:**
1. **Inventory remaining sites:**
   ```bash
   # Pattern: _db_execute with a string-formatted IN clause (the vuln class B-5 fixed)
   grep -nE "_db_execute.*\.join\(|_db_execute.*format\(.*IN" recall.py
   # Also broader sweep showing all _db_execute call sites for cross-reference:
   grep -n "_db_execute" recall.py
   ```
   Document both outputs in evidence file. Expected: ~6-8 vulnerable sites (was 11 before B-5 fixed 3).

2. **Pick 2 sites** by lowest risk (smallest blast radius, no edge-case branching). Document which 2 in the commit message.

3. **Refactor pattern** (same as B-5):
   ```python
   # OLD (vulnerable):
   rows = _db_execute(f"SELECT ... WHERE id IN ({','.join(ids)})")

   # NEW (safe):
   rows = _db_execute(
       "SELECT ... WHERE id = ANY(%s::uuid[])",
       (ids,)
   )
   ```
   Per userMemories: psycopg2 binds `list[str]` as `text[]`; cast to `uuid[]` SQL-side.

4. **Test gate (G3):**
   ```bash
   pytest tests/test_recall.py -v --tb=short 2>&1 | tee /tmp/s05-test.txt
   grep -q "passed" /tmp/s05-test.txt && ! grep -q "failed" /tmp/s05-test.txt && echo G-S05 PASS
   ```
   If `tests/test_recall.py` doesn't exist or doesn't cover the refactored paths → CC writes a minimal regression test for each refactored site (single `def test_...` per site) and adds them to the commit.

5. **Smoke test** against prod recall to ensure no behavioral regression:
   ```bash
   curl -sS -X POST http://localhost:8420/recall \
     -H "X-API-Key: $ZEROLATENCY_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query": "test", "limit": 5}' \
     | python3 -c "import sys,json; r=json.load(sys.stdin); assert 'results' in r"
   ```

6. **Commit:**
   ```
   P4.1 S05: 2x _db_execute split cleanup in recall.py

   Continues B-5's work. 11 -> 8 -> 6 remaining sites with this vuln class.
   Sites refactored: <line numbers / function names>.

   Pattern: replace string-formatted IN clause with %s::uuid[] parameterized
   binding. psycopg2 binds list[str] as text[]; SQL-side cast to uuid[].

   Verification: <pytest receipt>, <smoke curl receipt>

   Files: recall.py, tests/test_recall.py (if regression test added)
   ```

**Halt conditions:**
- Inventory shows fewer than 8 sites (drift from documented state) → halt and report.
- Any refactored site causes test regression → revert that site, halt with details.

**Memory edit (operator-side, NOT CC):**
After chain merges, operator runs:
```
memory_user_edits — find the line claiming analytics_events schema bug is open;
replace with: "analytics_events schema bug RESOLVED (B-5 Stage 02): zero unqualified
refs in code; storage/dedup confirmed unaffected throughout."
```
Note in chain summary so operator doesn't miss it.

---

## Stage 06 — Phase 4 closure verification gate

**Tier:** 0 (verification + documentation; no code changes).

**Why:** CP8 v3 Phase 4 closure criteria are: (1) synthesis-aware recall, (2) role-filtered queries, (3) redaction-respecting reads, (4) audit-aware queries on Enterprise. All four must verify before declaring Phase 4 done.

**In scope:**
- Run the four closure checks, capture receipts.
- Write `docs/CHECKPOINT-8-PHASE-4-COMPLETE.md` with receipts inline.

**Out of scope:**
- Fixing anything that fails verification — that's a halt + carry into P4.2.

**Verification suite:**

**V1 — synthesis-aware recall:**
```bash
curl -sS -X POST http://localhost:8420/recall \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "what are my recurring themes", "limit": 10}' \
  | python3 -m json.tool > /tmp/v1-synthesis-aware.json
# GATE: at least one result has memory_type='synthesis'
python3 -c "
import json
r = json.load(open('/tmp/v1-synthesis-aware.json'))
assert any(m.get('memory_type')=='synthesis' for m in r.get('results',[])), 'V1 FAIL'
print('V1 PASS')"
```

**V2 — role-filtered queries:**
```bash
# Query with role_tag='public' — default; should work
curl -sS -X POST http://localhost:8420/recall \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "themes", "role_tag": "public", "limit": 5}' \
  > /tmp/v2-public.json

# Query with role_tag='engineering' — should return engineering-tagged or public
curl -sS -X POST http://localhost:8420/recall \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "themes", "role_tag": "engineering", "limit": 5}' \
  > /tmp/v2-engineering.json

# GATE: both return 200 with results array; no row leaks across role boundaries
# (CC verifies via inspecting role_tag on each returned synthesis row)
python3 -c "
import json
for f in ['/tmp/v2-public.json', '/tmp/v2-engineering.json']:
    r = json.load(open(f))
    assert 'results' in r, f'{f} V2 FAIL'
print('V2 PASS')"
```

**V3 — redaction-respecting reads:**
- If any synthesis row in the DB has `redaction_state='redacted'`, verify it does NOT appear in recall.
- If none exist (likely — Phase 5 hasn't shipped redaction yet), V3 = SKIPPED-PREEXISTING with note "redaction state machine ships in Phase 5; read-side exclusion code path is in place per code review of recall.py L<N>".
```bash
psql "$DATABASE_URL" -c "
  SELECT id FROM memory_service.memories
  WHERE memory_type='synthesis' AND metadata->>'redaction_state' = 'redacted'
  LIMIT 1;
" -t | grep -qE '[a-f0-9]{8}-' && {
  REDACTED_ID=$(psql "$DATABASE_URL" -c "..." -t | tr -d ' \n')
  curl -sS -X POST http://localhost:8420/recall ... \
    | python3 -c "import sys,json,os; r=json.load(sys.stdin); rid=os.environ['REDACTED_ID']; assert not any(m.get('id')==rid for m in r.get('results',[])), 'V3 FAIL: redacted row appeared'"
  echo V3 PASS
} || echo "V3 SKIPPED-PREEXISTING (no redacted rows in DB)"
```

**V4 — audit-aware queries on Enterprise (proves Stage 02):**
```bash
BEFORE=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM memory_service.synthesis_audit_events WHERE event_type='read'" | tr -d ' \n')
curl -sS -X POST http://localhost:8420/recall \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "themes", "limit": 5}' > /dev/null
AFTER=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM memory_service.synthesis_audit_events WHERE event_type='read'" | tr -d ' \n')
[ "$AFTER" -gt "$BEFORE" ] && echo "V4 PASS (read events: $BEFORE -> $AFTER)" || echo "V4 FAIL"
```

**V5 — `expand=cluster` populated (proves Stage 03 — but ONLY if operator has applied prod backfill):**
```bash
# First: was prod backfill applied?
PROD_BACKFILLED=$(psql "$DATABASE_URL" -t -c "
  SELECT COUNT(*) FROM memory_service.memories
  WHERE memory_type='synthesis' AND metadata->>'cluster_id' IS NOT NULL;
" | tr -d ' \n')

if [ "$PROD_BACKFILLED" -gt 0 ]; then
  curl -sS -X POST "http://localhost:8420/recall?expand=cluster" \
    -H "X-API-Key: $ZEROLATENCY_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"query": "themes", "limit": 5}' \
    | python3 -c "import sys,json; r=json.load(sys.stdin); assert any(m.get('cluster_members') for m in r.get('results',[])), 'V5 FAIL'"
  echo "V5 PASS"
else
  echo "V5 PENDING — operator has not yet run scripts/backfill_cluster_id.py against prod (S03 halt-at-boundary)"
fi
```

**Halt-on-fail policy for Stage 06:**
- V1, V2, V4 must PASS for Phase 4 to be declared closed.
- V3 may be SKIPPED-PREEXISTING (Phase 5 dependency).
- V5 may be PENDING (Stage 03 prod-apply boundary). Closure doc notes V5 will validate after operator applies backfill; Phase 4 still considered CLOSED on the basis of V1, V2, V4.
- Any of V1/V2/V4 failing → halt, write `CP8-P4-1-S06-PHASE4-NOT-CLOSED.md` with which check failed and why. Phase 4 stays open into P4.2.

**Authoring step (after all gates pass):**

Write `docs/CHECKPOINT-8-PHASE-4-COMPLETE.md`:
```markdown
# CP8 Phase 4 — Read path closure

**Date:** <run date>
**Closing chain:** P4.1
**Master HEAD at close:** <git rev-parse HEAD>

## Closure criteria (per CP8 v3)

| # | Criterion | Status | Receipt |
|---|---|---|---|
| 1 | Synthesis-aware recall | ✅ PASS | <V1 receipt> |
| 2 | Role-filtered queries | ✅ PASS | <V2 receipt> |
| 3 | Redaction-respecting reads | ⏳ Phase 5 dep | Code path verified at recall.py L<N>; data-side test deferred until redaction state machine ships |
| 4 | Audit-aware queries (Enterprise) | ✅ PASS | <V4 receipt> |

## Bonus: cluster expansion (Stage 03)
| Status | Note |
|---|---|
| <PASS or PENDING> | <V5 receipt or "operator backfill pending; will validate after script runs"> |

## What shipped across P4.1
- Stage 01: db_migrate.sh real human gate (P0 protocol fix from B-5)
- Stage 02: audit-aware reads on Enterprise /recall
- Stage 03: cluster_id backfill on existing synthesis rows
- Stage 04: nginx fix for api.0latency.ai/recall 502
- Stage 05: 2x _db_execute split cleanup in recall.py (8 → 6 remaining)
- Stage 06: Phase 4 closure verification gate (this doc)

## Forward to P4.2
- MCP server npm + Smithery deployment (memory_synthesize tool, updated recall description)
- mcp.0latency.ai/authorize page UI polish
- 6 remaining _db_execute + split sites in recall.py (rolling cleanup)

## Phase 4 status: CLOSED
```

**Commit:**
```
P4.1 S06: Phase 4 closure verification + completion doc

All four CP8 v3 Phase 4 closure criteria verified (V3 deferred to Phase 5
per scope). docs/CHECKPOINT-8-PHASE-4-COMPLETE.md captures receipts.

Files: docs/CHECKPOINT-8-PHASE-4-COMPLETE.md (NEW)
```

---

## Post-flight (after Stage 06 commit)

```bash
git log p4-1-chain --oneline ^master         # GATE: 6-7 commits (preflight + 6 stages)
git diff master..p4-1-chain --stat            # GATE: diff scope sane (no surprises)

# Forbidden-exit regex sweep — both commit messages AND state log
git log p4-1-chain ^master --format='%B' \
  | grep -iE "token budget|time budget|context budget|attention budget|running low|out of room|budget exhausted|getting close to|should stop here|I'll get back to|TODO|skipping for now|will fix later|punting|come back to this" \
  && { echo "FORBIDDEN EXIT PHRASE FOUND IN COMMITS"; exit 1; } \
  || echo "Commit-message forbidden-exit sweep clean"

grep -iE "token budget|time budget|context budget|attention budget|running low|out of room|budget exhausted|getting close to|should stop here|I'll get back to|TODO|skipping for now|will fix later|punting|come back to this" \
  docs/chains/p4-1/STATE-LOG.md \
  && { echo "FORBIDDEN EXIT PHRASE FOUND IN STATE-LOG"; exit 1; } \
  || echo "State-log forbidden-exit sweep clean"

# Sanity: every SHIPPED stage in STATE-LOG must have a corresponding commit
grep "SHIPPED" docs/chains/p4-1/STATE-LOG.md | wc -l
git log p4-1-chain ^master --format='%s' | grep -c "^P4.1 S0"

# Push branch
git push origin p4-1-chain
```

**Author CHAIN-REPORT.md:**

Write `docs/chains/p4-1/CHAIN-REPORT.md`:
```markdown
# P4.1 Chain Report

**Branch:** p4-1-chain
**Started from master HEAD:** <preflight HEAD>
**Final HEAD:** <git rev-parse HEAD>
**Wall clock:** <start time> → <end time>

## Stages

| Stage | Outcome | Commit | Evidence |
|---|---|---|---|
| 01 | <SHIPPED|...> | <sha> | docs/chains/p4-1/stage-01-evidence.md |
| 02 | <...> | <sha> | docs/chains/p4-1/stage-02-evidence.md |
| 03 | BLOCKED-NEEDS-HUMAN (by design) | <sha> | docs/chains/p4-1/stage-03-evidence.md |
| 04 | <...> | <sha> | docs/chains/p4-1/stage-04-evidence.md |
| 05 | <...> | <sha> | docs/chains/p4-1/stage-05-evidence.md |
| 06 | <...> | <sha> | docs/chains/p4-1/stage-06-evidence.md |

## Outcome category counts
- SHIPPED: <N>
- BLOCKED-NEEDS-HUMAN: <N> (incl. Stage 03 by design)
- SKIPPED-PREEXISTING: <N>
- FAILED: <N>

## Forbidden-exit sweep
<grep result, should be CLEAN>

## Operator action items
1. Run `python3 scripts/backfill_cluster_id.py` against prod to complete S03.
2. After backfill, re-run V5 from Stage 06 to confirm `expand=cluster` populated.
3. Update userMemories: replace stale `analytics_events` open-bug claim with B-5 resolution note.
4. Merge p4-1-chain to master if all gates above are green.

## Phase 4 status
<CLOSED | OPEN — needs P4.2>

## Recommendations for P4.2
- MCP server npm + Smithery deployment (memory_synthesize tool, recall description update)
- mcp.0latency.ai/authorize page UI polish
- Recall-empty-results bug investigation (Handoff B carry-over)
- Remaining 6 _db_execute + split sites (rolling cleanup)
```

If any gate fails → halt, write `CP8-P4-1-POSTFLIGHT-BLOCKED.md`.

If all gates pass → write `CP8-P4-1-COMPLETE.md` to workspace root summarizing the chain. Operator merges manually and fires the chime.

---

## Definition of done (chain-level)

All of:
1. 7 commits on `p4-1-chain` pushed to remote (1 preflight + 6 stages).
2. All stage-level gates passed OR cleanly halted at boundary (S03 specifically allowed) OR `SKIPPED-PREEXISTING` with valid receipt.
3. Per-stage evidence files at `docs/chains/p4-1/stage-NN-evidence.md` (6 of them).
4. `docs/chains/p4-1/STATE-LOG.md` populated with one row per stage attempt.
5. `docs/chains/p4-1/CHAIN-REPORT.md` exists with outcome counts and operator action items.
6. `docs/CHECKPOINT-8-PHASE-4-COMPLETE.md` exists with V1, V2, V4 receipts (V3 SKIPPED, V5 PASS or PENDING).
7. No `CP8-P4-1-*-BLOCKED.md` files in workspace root EXCEPT `CP8-P4-1-S03-PROD-APPLY-PENDING.md` (by design).
8. Forbidden-exit sweep clean on commits AND state log.
9. `journalctl -u memory-api --since "<chain start>"` shows no new ERRORs (pre-existing analytics_events errors should be ZERO post-B-5; if any reappear, halt — Stage 05 territory).
