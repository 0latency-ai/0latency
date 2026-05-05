# CP8 P4.2 — Recall-empty-results structural fix

**Branch:** `p4-2-fix` (cut from `master`, NOT from `p4-2-investigation`).
**Diagnosis source of truth:** `docs/chains/p4-2/stage-01-recall-empty-diagnosis.md` (already on `p4-2-investigation` branch).
**Target:** 3 stages, 25-40 min wall-clock.
**Goal:** Fix the structural bug where synthesis rows are hidden from `/recall` because they're agent-scoped at the SQL level. Per CP8 v3 architecture: synthesis is **tenant + role-tag + redaction scoped**, NOT agent scoped.

---

## Architectural decision (locked, do not re-litigate)

**Synthesis rows are cross-agent by design.** They are L2+ pyramid abstractions that emerge from clusters spanning multiple agents. No single agent "owns" a synthesis row. The fact that current synthesis rows have `agent_id` values (`user-justin`, `system_consensus`, etc.) is a write-path artifact — those values record *who triggered the write*, not *who owns the row*.

**Therefore:** the per-agent equality filter in `recall.py` CTEs must NOT apply to synthesis rows.

**Access control for synthesis flows through:**
1. `tenant_id` (existing)
2. `role_tag` (B-3.5 / B-4 S01)
3. `redaction_state` (existing in code, awaiting Phase 5 state machine)

**Atoms remain agent-scoped.** Only synthesis rows bypass.

**Fix shape:** modify the three CTEs (vector, importance, bm25) so the agent filter becomes:
```sql
WHERE (agent_id = %s OR memory_type = 'synthesis')
  AND tenant_id = %s::UUID
  ...
```

This is one-line-per-CTE. Structural, not a band-aid. Aligns with CP8 v3.

---

## Standing rules (carry forward unchanged from P4.1)

All 12 rules from P4.1 apply. Highlights:
- Branch isolation: all work on `p4-2-fix`.
- Stage cap 3 (this chain).
- No multi-line python heredocs in commands.
- No `&&` chains past verification gates.
- Outcome categories: SHIPPED | SKIPPED-PREEXISTING | SKIPPED-OUT-OF-SCOPE | BLOCKED-NEEDS-HUMAN | FAILED.
- Forbidden-exit regex applies post-flight on commits AND state log.
- Audio chime is operator-fired, not CC-fired.
- Per-stage evidence files at `docs/chains/p4-2/stage-NN-evidence.md`.
- STATE-LOG.md continues from Stage 01 (already exists from p4-2-investigation; needs to be carried forward to p4-2-fix branch).

**Pre-flight:**
```bash
cd /root/.openclaw/workspace/memory-product
git status                                    # GATE: clean tree
git checkout master
git pull origin master                        # GATE: synced (220d95a or descendant)
git checkout -b p4-2-fix                      # GATE: branch created
mkdir -p docs/chains/p4-2

# Carry the diagnosis doc + state log from p4-2-investigation onto p4-2-fix
git checkout p4-2-investigation -- docs/chains/p4-2/
ls docs/chains/p4-2/                          # GATE: stage-01-recall-empty-diagnosis.md present
git add docs/chains/p4-2/
git commit -m "P4.2 pre-flight: carry forward Stage 01 diagnosis from p4-2-investigation"

set -a && source .env && set +a               # GATE: env loaded
curl -sS http://localhost:8420/health | grep -q '"status".*"ok"'  # GATE: services healthy
```

If any gate fails → halt, write `CP8-P4-2-PREFLIGHT-BLOCKED.md`, exit (no chime).

---

## Stage 02 — SQL fix in src/recall.py

**Tier:** 0 (code refactor, no schema, no data writes).

**In scope:**
- `src/recall.py` — modify the three CTEs (vector_results, importance_results, bm25_results) so the `agent_id = %s` equality becomes `(agent_id = %s OR memory_type = 'synthesis')`.
- Verify each CTE keeps the same parameter order (the change adds zero new bind params; agent_id and tenant_id remain the same two %s values).

**Out of scope:**
- Any other recall.py changes (no role filter touching, no redaction filter touching, no synthesis-aware ranker).
- Any schema changes.
- Any data writes.
- Changing how synthesis rows are written (write path stays as-is; this is read-path only).

**Steps:**

1. **Locate the three CTEs:**
   ```bash
   grep -nE "WHERE agent_id = %s AND tenant_id" src/recall.py
   ```
   Expect 3 hits. Document line numbers in evidence file.

2. **Read context around each hit** (use `view` tool — NO heredoc):
   ```bash
   sed -n '450,475p' src/recall.py    # vector_results (line 457 per diagnosis)
   sed -n '470,495p' src/recall.py    # importance_results
   # Locate bm25_results CTE similarly
   grep -n "bm25_results AS" src/recall.py
   ```

3. **Apply the fix to each of the three CTEs.** The pattern is identical for all three:

   **Before:**
   ```sql
   WHERE agent_id = %s AND tenant_id = %s::UUID
   ```

   **After:**
   ```sql
   WHERE (agent_id = %s OR memory_type = 'synthesis') AND tenant_id = %s::UUID
   ```

   Use `str_replace` per CTE. Three separate edits — do NOT try to do a global find-replace, because each CTE has slightly different surrounding context and a global replace risks unintended matches.

4. **Critical verification: parameter order unchanged.**
   The fix adds zero new `%s` bind sites. The SQL still has exactly two `%s` substitutions in the WHERE clause: one for agent_id, one for tenant_id. Confirm by counting `%s` in the diff:
   ```bash
   git diff src/recall.py | grep -cE "^\+.*%s|^\-.*%s"
   ```
   Number of additions and deletions should match (each modified line is one `+` and one `-` containing `%s`).

5. **Restart memory-api:**
   ```bash
   sudo systemctl restart memory-api
   sleep 35
   curl -sS http://localhost:8420/health
   ```
   Expect `{"status":"ok",...}`.

6. **Functional gate — synthesis now appears in recall:**
   ```bash
   set -a && source .env && set +a
   curl -sS -X POST http://localhost:8420/recall \
     -H "X-API-Key: $ZEROLATENCY_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query": "User navigating CLI", "limit": 10}' > /tmp/p4-2-s02-recall.json
   python3 -c "
   import json
   r = json.load(open('/tmp/p4-2-s02-recall.json'))
   types = [m.get('memory_type') for m in r.get('results', [])]
   syn_count = types.count('synthesis')
   print(f'total results: {len(types)}')
   print(f'synthesis count: {syn_count}')
   print(f'memory_types: {types[:10]}')
   assert syn_count > 0, 'V-S02 FAIL: no synthesis rows in recall result'
   print('V-S02 PASS')
   "
   ```
   The query "User navigating CLI" was the guaranteed-match query from the Stage 01 diagnosis; if synthesis still doesn't appear, the fix is wrong.

7. **Regression check — atoms still respect agent scope:**
   ```bash
   curl -sS -X POST http://localhost:8420/recall \
     -H "X-API-Key: $ZEROLATENCY_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"agent_id": "thomas", "query": "test", "limit": 5}' > /tmp/p4-2-s02-thomas.json
   python3 -c "
   import json
   r = json.load(open('/tmp/p4-2-s02-thomas.json'))
   results = r.get('results', [])
   atoms = [m for m in results if m.get('memory_type') != 'synthesis']
   syntheses = [m for m in results if m.get('memory_type') == 'synthesis']
   print(f'atoms returned: {len(atoms)}')
   print(f'syntheses returned: {len(syntheses)}')
   # All atoms should belong to thomas; syntheses can be cross-agent
   non_thomas_atoms = [a for a in atoms if a.get('agent_id') != 'thomas']
   assert len(non_thomas_atoms) == 0, f'V-S02 REGRESSION: atom from wrong agent leaked: {non_thomas_atoms[0]}'
   print('V-S02 atom-scope regression check PASS')
   "
   ```

8. **Audit emission re-verification (closes the P4.1 S02 verification gap):**
   ```bash
   BEFORE=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM memory_service.synthesis_audit_events WHERE event_type='read'" | tr -d ' \n')
   curl -sS -X POST http://localhost:8420/recall \
     -H "X-API-Key: $ZEROLATENCY_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query": "themes", "limit": 5}' > /dev/null
   sleep 2
   AFTER=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM memory_service.synthesis_audit_events WHERE event_type='read'" | tr -d ' \n')
   echo "Audit read events: $BEFORE -> $AFTER  (delta: $((AFTER - BEFORE)))"
   [ "$AFTER" -gt "$BEFORE" ] && echo "V-S02 audit emission PASS" || echo "V-S02 audit emission FAIL"
   ```

9. **Journal sanity:**
   ```bash
   journalctl -u memory-api --since "5 minutes ago" --no-pager | grep -E "ERROR|CRITICAL" | head -20
   ```
   Expect zero new errors (pre-existing `error_logs` schema noise tolerated; one occurrence per hour is the baseline).

10. **Commit:**
    ```bash
    git add src/recall.py
    git commit -F- <<'EOF'
    P4.2 S02: synthesis bypasses agent_id filter in recall CTEs

    Root cause (per stage-01 diagnosis): src/recall.py CTEs hard-filter
    `WHERE agent_id = %s AND tenant_id = %s::UUID`, which excludes
    synthesis rows when caller's agent_id doesn't match. Synthesis is
    cross-agent by CP8 v3 design — it must not be agent-scoped on read.

    Fix: in vector_results, importance_results, and bm25_results CTEs,
    change the WHERE clause to:
      WHERE (agent_id = %s OR memory_type = 'synthesis')
        AND tenant_id = %s::UUID

    Synthesis access control flows through tenant_id + role_tag +
    redaction_state, not agent_id. Atoms remain agent-scoped.

    Parameter order unchanged (zero new %s bind sites added).

    Verification:
    - Stage-01 guaranteed-match query "User navigating CLI" now returns
      synthesis rows (was returning 0).
    - Atom-scope regression check: queries with agent_id=thomas return
      only thomas atoms (plus cross-agent syntheses).
    - Audit emission verified: read event count delta > 0.

    Closes the P4.1 S02 end-to-end verification gap.

    Files: src/recall.py
    EOF
    ```

**Halt conditions:**
- Fewer or more than 3 CTEs match the `WHERE agent_id = %s AND tenant_id` pattern (means schema/code drift; halt and document).
- Any of the verification gates fail.
- Atom-scope regression check finds atoms from wrong agent (means the fix accidentally widened atom scope; revert and halt).

---

## Stage 03 — Test coverage

**Tier:** 0.

**In scope:**
- Add 2-3 integration tests to `tests/test_recall.py` (or create the file if absent) covering:
  1. Recall returns synthesis rows when caller agent has none of their own atoms matching the query.
  2. Recall with explicit agent_id still scopes atoms correctly.
  3. Recall with explicit agent_id still returns cross-agent syntheses (the regression we just fixed).

**Out of scope:**
- Refactoring existing tests.
- Adding tests for unrelated paths.

**Steps:**

1. **Check if `tests/test_recall.py` exists:**
   ```bash
   ls tests/test_recall.py 2>/dev/null && echo "EXISTS" || echo "MISSING"
   ```

2. **If missing, create it.** If exists, append. Use `create_file` or `view`+`str_replace` — NO heredoc.

3. **Test bodies (illustrative; CC adapts to actual fixtures):**
   ```python
   import pytest, requests, os

   API = "http://localhost:8420"
   HEADERS = {"X-API-Key": os.environ["ZEROLATENCY_API_KEY"], "Content-Type": "application/json"}

   @pytest.mark.integration
   def test_recall_returns_cross_agent_synthesis():
       """Synthesis rows must appear regardless of caller agent_id."""
       r = requests.post(f"{API}/recall", headers=HEADERS,
                         json={"agent_id": "thomas", "query": "User navigating CLI", "limit": 10})
       r.raise_for_status()
       results = r.json().get("results", [])
       syntheses = [m for m in results if m.get("memory_type") == "synthesis"]
       assert len(syntheses) > 0, "synthesis must appear cross-agent"

   @pytest.mark.integration
   def test_recall_atoms_remain_agent_scoped():
       """Atoms must still be scoped to caller agent."""
       r = requests.post(f"{API}/recall", headers=HEADERS,
                         json={"agent_id": "thomas", "query": "test", "limit": 20})
       r.raise_for_status()
       results = r.json().get("results", [])
       atoms = [m for m in results if m.get("memory_type") != "synthesis"]
       wrong = [a for a in atoms if a.get("agent_id") and a["agent_id"] != "thomas"]
       assert len(wrong) == 0, f"atoms from wrong agent leaked: {wrong[:3]}"

   @pytest.mark.integration
   def test_recall_audit_event_emitted_on_synthesis_return():
       """Enterprise tier emits synthesis_audit_events row when syntheses returned."""
       # This requires a Postgres connection fixture; skip-if-no-fixture is acceptable
       pytest.importorskip("psycopg2")
       import psycopg2
       conn = psycopg2.connect(os.environ["DATABASE_URL"])
       cur = conn.cursor()
       cur.execute("SELECT COUNT(*) FROM memory_service.synthesis_audit_events WHERE event_type='read'")
       before = cur.fetchone()[0]
       requests.post(f"{API}/recall", headers=HEADERS,
                     json={"query": "themes", "limit": 5}).raise_for_status()
       import time; time.sleep(2)
       cur.execute("SELECT COUNT(*) FROM memory_service.synthesis_audit_events WHERE event_type='read'")
       after = cur.fetchone()[0]
       assert after > before, f"audit event not written: {before} -> {after}"
       conn.close()
   ```

4. **Test gate:**
   ```bash
   pytest tests/test_recall.py -v --tb=short -m integration 2>&1 | tee /tmp/p4-2-s03-test.txt
   grep -q "passed" /tmp/p4-2-s03-test.txt && ! grep -q "failed" /tmp/p4-2-s03-test.txt && echo G-S03 PASS
   ```

5. **Commit:**
   ```bash
   git add tests/test_recall.py
   git commit -m "P4.2 S03: integration tests for cross-agent synthesis recall"
   ```

**Halt conditions:**
- Tests fail (means S02 fix is incomplete).
- pytest not available / fixtures broken (halt; record state for operator).

---

## Stage 04 — Chain report + close

**Tier:** 0 (documentation only).

**Steps:**

1. **Append to STATE-LOG.md** for stages 02, 03, 04.

2. **Author `docs/chains/p4-2/CHAIN-REPORT.md`:**
   ```markdown
   # P4.2 Chain Report

   **Branch:** p4-2-fix
   **Started from master HEAD:** <preflight HEAD>
   **Final HEAD:** <git rev-parse HEAD>
   **Wall clock:** <start> → <end>

   ## Stages
   | Stage | Outcome | Commit | Evidence |
   |---|---|---|---|
   | 01 | SHIPPED | <sha from p4-2-investigation> | docs/chains/p4-2/stage-01-recall-empty-diagnosis.md (carried forward) |
   | 02 | SHIPPED | <sha> | docs/chains/p4-2/stage-02-evidence.md |
   | 03 | SHIPPED | <sha> | docs/chains/p4-2/stage-03-evidence.md |
   | 04 | SHIPPED | <sha> | this file |

   ## Outcome category counts
   - SHIPPED: 4
   - All others: 0

   ## Forbidden-exit sweep
   <grep result>

   ## What this chain accomplished
   - Identified, diagnosed, and fixed the recall-empty-results bug.
   - Closed the P4.1 S02 end-to-end verification gap.
   - Synthesis is now cross-agent on read, as designed.

   ## Operator action items
   1. Merge p4-2-fix to master.
   2. Delete p4-2-investigation branch (diagnosis carried forward).
   3. Update userMemories: add resolution note for recall-empty-results (was on Handoff B carry-list since 2026-04-XX).
   4. Re-run V5 from P4.1 S06 closure doc once cluster_id backfill is applied.

   ## Forward to P4.3 (or sequenced as separate items)
   - Cluster_id backfill prod apply (carryover from P4.1 S03).
   - error_logs schema bug (1 occurrence/hour in journal; same class as analytics_events fix in B-5).
   - Remaining 6 _db_execute split sites (rolling cleanup).
   - MCP server npm + Smithery deployment.
   ```

3. **Commit:**
   ```bash
   git add docs/chains/p4-2/CHAIN-REPORT.md docs/chains/p4-2/STATE-LOG.md
   git commit -m "P4.2 S04: chain report + closure"
   git push origin p4-2-fix
   ```

4. **Forbidden-exit sweep + final receipts:**
   ```bash
   git log p4-2-fix ^master --format='%B' \
     | grep -iE "token budget|time budget|context budget|attention budget|running low|out of room|budget exhausted|getting close to|should stop here|I'll get back to|TODO|skipping for now|will fix later|punting|come back to this" \
     && { echo "FORBIDDEN-EXIT IN COMMITS"; exit 1; } \
     || echo "Commit sweep clean"

   grep -iE "token budget|time budget|context budget|attention budget|running low|out of room|budget exhausted|getting close to|should stop here|I'll get back to|TODO|skipping for now|will fix later|punting|come back to this" \
     docs/chains/p4-2/STATE-LOG.md \
     && { echo "FORBIDDEN-EXIT IN STATE-LOG"; exit 1; } \
     || echo "State-log sweep clean"

   git log p4-2-fix --oneline ^master
   git diff master..p4-2-fix --stat
   ```

5. **Write `CP8-P4-2-COMPLETE.md`** to workspace root summarizing the chain.

---

## Definition of done (chain-level)

All of:
1. 4 commits on `p4-2-fix` (1 preflight + 3 stages) pushed to remote.
2. Stage 01 diagnosis carried forward from p4-2-investigation.
3. All stage-level gates passed.
4. `docs/chains/p4-2/CHAIN-REPORT.md` exists.
5. `CP8-P4-2-COMPLETE.md` exists in workspace root.
6. Forbidden-exit sweeps clean on commits AND state log.
7. `journalctl -u memory-api --since "<chain start>"` shows no new ERRORs (pre-existing `error_logs` noise tolerated, one/hour baseline).
8. Operator-side: merge p4-2-fix → master, delete p4-2-investigation branch, fire chime, update userMemories.
