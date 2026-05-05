# P4.2-PATCH — Single-task autonomy scope

**Mode:** Autonomous CC, single task, no multi-stage gating.
**Branch in:** `p4-2-fix` (4 commits ahead of master, NOT YET MERGED).
**Master HEAD at handoff:** `220d95a`.
**Estimated wall-clock:** 15–25 min.
**Predecessor chain:** P4.1 (merged), P4.2 (branch shipped, blocked on this patch).

---

## Goal (one sentence)

Fix the one-line audit-emission key bug on `src/recall.py` line 785, re-verify P4.1 S02 (audit emission) and P4.2 (cross-agent synthesis) end-to-end, merge `p4-2-fix` → `master`, run the prod cluster_id backfill (closes P4.1 S03 halt), verify P4.1 V5 (`expand=cluster`), and clean up branches.

---

## In scope

- `src/recall.py` — one-line key rename: `"type"` → `"memory_type"` on line 785 (in the `selected` items dict construction).
- Verification curls + psql deltas.
- `git merge p4-2-fix → master` (fast-forward or merge commit, operator preference: standard merge commit so branch history is preserved).
- Prod execution of the cluster_id backfill script staging-validated in P4.1 S03.
- Branch deletion: `p4-2-fix` (after merge), `p4-2-investigation` (stale).

## Out of scope (DO NOT TOUCH)

- Any migration file (`migrations/*.sql`) — backfill is a script, not a migration.
- Any new endpoint or new file outside `src/recall.py`.
- Test harness env-loading repair (P4.2 S03 BLOCKED-NEEDS-HUMAN — leave as-is).
- The 6 remaining `_db_execute + split` sites — rolling cleanup, not this chain.
- The `error_logs` schema bug — known, not blocking.
- CP-SYNTHESIS-PERF — next chain.
- Phase 5 work.

---

## Inputs at start

- HEAD on master: `220d95a`.
- Branch `p4-2-fix` exists on origin, 4 commits ahead, last commit is the P4.2 chain report.
- Branch `p4-2-investigation` exists, stale (carry-forward already in `p4-2-fix`).
- Working tree must be clean. If not — halt per protocol rule 7.
- `.env` loaded via `set -a && source .env && set +a`.
- Cluster_id backfill script lives where P4.1 S03 evidence file points (CC must locate; first try `scripts/backfill_cluster_id.py` or similar — confirm via S03 evidence file at `docs/evidence/p4-1-s03-*.md` or `STATE-LOG.md`).

---

## Steps (single linear sequence — no stage gates)

### 1. Pre-flight

```bash
cd /root/.openclaw/workspace/memory-product
git fetch origin
git checkout p4-2-fix
git status                              # MUST be clean — halt if dirty
git log -1 --oneline                    # record HEAD-of-branch
git log master..p4-2-fix --oneline      # confirm 4 commits ahead
set -a && source .env && set +a
```

**Halt if:** working tree dirty, branch not at expected 4-ahead state.

### 2. Apply the one-line fix

Locate line 785 in `src/recall.py`. The fix:

```python
# BEFORE (current state on p4-2-fix branch):
"type": memory_type,

# AFTER:
"memory_type": memory_type,
```

Use `str_replace`-style edit (one match expected). After edit:

```bash
python3 -c "import ast; ast.parse(open('src/recall.py').read())"   # GATE: exit 0
git diff src/recall.py                  # confirm exactly 1 line changed
```

**Halt if:** the `"type":` literal isn't on or near line 785 (means file drifted), or syntax error.

### 3. Restart API

```bash
systemctl restart memory-api
sleep 30
systemctl is-active memory-api          # GATE: must print "active"
journalctl -u memory-api --since "1 minute ago" --no-pager \
  | grep -E "ERROR|Traceback" \
  | grep -v "analytics_events" \
  | grep -v "error_logs" \
  | head -20                            # GATE: empty modulo known noise
```

**Halt if:** service inactive or new ERRORs (excluding the two known schema-bug lines).

### 4. Verification gate A — audit emission delta (closes P4.1 S02 verification gap)

```bash
BEFORE=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM memory_service.synthesis_audit_events WHERE event_type='read'" | tr -d ' \n')
curl -sS -X POST http://localhost:8420/recall \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "themes and patterns", "limit": 5}' > /tmp/p4-2-patch-recall.json
python3 -c "
import json
r = json.load(open('/tmp/p4-2-patch-recall.json'))
results = r.get('results', [])
syntheses = [m for m in results if m.get('memory_type') == 'synthesis']
print(f'recall returned {len(results)} results, {len(syntheses)} synthesis')
assert len(syntheses) > 0, 'GATE A FAIL: no synthesis rows in recall — audit will not fire'
"
sleep 2
AFTER=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM memory_service.synthesis_audit_events WHERE event_type='read'" | tr -d ' \n')
echo "Audit read events: $BEFORE -> $AFTER (delta: $((AFTER - BEFORE)))"
[ "$AFTER" -gt "$BEFORE" ] && echo "GATE A PASS" || (echo "GATE A FAIL"; exit 1)
```

**Halt if:** GATE A FAIL — root cause was wrong, do not proceed to merge.

### 5. Verification gate B — atom-scope regression (must still respect agent_id)

```bash
curl -sS -X POST http://localhost:8420/recall \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "thomas", "query": "test", "limit": 10}' > /tmp/p4-2-patch-thomas.json
python3 -c "
import json
r = json.load(open('/tmp/p4-2-patch-thomas.json'))
results = r.get('results', [])
atoms = [m for m in results if m.get('memory_type') != 'synthesis']
non_thomas = [a for a in atoms if a.get('agent_id') and a.get('agent_id') != 'thomas']
assert len(non_thomas) == 0, f'GATE B FAIL: atom from wrong agent leaked: {non_thomas[0]}'
print(f'GATE B PASS (atoms={len(atoms)}, all thomas-scoped)')
"
```

**Halt if:** GATE B FAIL — fix introduced atom-scope regression.

### 6. Verification gate C — cross-agent synthesis still works (P4.2 regression)

```bash
curl -sS -X POST http://localhost:8420/recall \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "user-justin", "query": "User navigating CLI", "limit": 10}' > /tmp/p4-2-patch-cross.json
python3 -c "
import json
r = json.load(open('/tmp/p4-2-patch-cross.json'))
results = r.get('results', [])
syntheses = [m for m in results if m.get('memory_type') == 'synthesis']
print(f'cross-agent recall: {len(results)} total, {len(syntheses)} synthesis')
assert len(syntheses) > 0, 'GATE C FAIL: P4.2 cross-agent synthesis regressed'
print('GATE C PASS')
"
```

**Halt if:** GATE C FAIL.

### 7. Commit the patch on p4-2-fix

```bash
git add src/recall.py
git status                              # only src/recall.py staged
git diff --cached --stat
```

Commit message (write to `/tmp/p4-2-patch-commit-msg.txt`):

```
P4.2-PATCH: fix audit-emission key mismatch on recall.py:785

Root cause: src/recall.py line 785 stored "type" key in the selected
items dict, but the audit-emission conditional on line ~815 read
"memory_type" with default "fact". Result: every recall result reported
memory_type=fact regardless of actual type, so P4.1 S02's audit-aware
read conditional (memory_type == 'synthesis') never fired.

Fix: rename the dict key from "type" to "memory_type" so the audit
conditional reads the actual value.

This closes:
- P4.1 S02 verification gap (audit emission was code-correct but
  end-to-end-ungated due to key mismatch).
- P4.2 end-to-end verification (cross-agent synthesis was working
  at SQL level but audit gate needed this key fix).

Verification receipts:
[CC fills in: BEFORE/AFTER counts, recall payloads, journal sanity]

Files: src/recall.py (1 line changed)
```

```bash
git commit -F /tmp/p4-2-patch-commit-msg.txt
git log -1 --stat
git push origin p4-2-fix
```

### 8. Merge p4-2-fix → master

```bash
git checkout master
git pull origin master                  # confirm at 220d95a
git merge --no-ff p4-2-fix -m "Merge p4-2-fix: cross-agent synthesis recall + audit-emission patch (P4.2 + P4.2-PATCH)"
git log master --oneline -10
git push origin master
```

**Halt if:** merge conflicts (should be impossible — operator can re-pull and retry).

### 9. Cluster_id prod backfill (closes P4.1 S03 halt)

Operator authorization recorded in handoff doc — this is the green light.

```bash
# Locate the staging-validated backfill script per P4.1 S03 evidence file
ls -la scripts/backfill_cluster_id*.py 2>/dev/null
ls -la scripts/*cluster*.py 2>/dev/null
cat docs/evidence/p4-1-s03-*.md 2>/dev/null | head -50
```

Once located, capture BEFORE counts and run on prod:

```bash
psql "$DATABASE_URL" -c "SELECT COUNT(*) AS missing_cluster_id FROM memory_service.memories WHERE memory_type='synthesis' AND (metadata->>'cluster_id') IS NULL;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) AS total_synthesis FROM memory_service.memories WHERE memory_type='synthesis';"

# Run the backfill (use whichever invocation pattern the script expects — most likely:)
python3 scripts/backfill_cluster_id.py 2>&1 | tee /tmp/p4-2-patch-backfill.log

# AFTER counts
psql "$DATABASE_URL" -c "SELECT COUNT(*) AS missing_cluster_id FROM memory_service.memories WHERE memory_type='synthesis' AND (metadata->>'cluster_id') IS NULL;"
```

**Halt if:** backfill script not found, or script errors, or AFTER count > 0 (not all rows backfilled).

### 10. Verification gate D — P4.1 V5 (expand=cluster populated)

Pick one synthesis memory_id from the backfilled set:

```bash
SYNTH_ID=$(psql "$DATABASE_URL" -t -c "SELECT id FROM memory_service.memories WHERE memory_type='synthesis' AND (metadata->>'cluster_id') IS NOT NULL LIMIT 1" | tr -d ' \n')
echo "Test synthesis ID: $SYNTH_ID"

curl -sS "http://localhost:8420/memories/${SYNTH_ID}/source?expand=cluster" \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" > /tmp/p4-2-patch-expand.json
python3 -c "
import json
r = json.load(open('/tmp/p4-2-patch-expand.json'))
chain = r.get('source_chain', [])
print(f'expand=cluster returned {len(chain)} items')
assert len(chain) > 0, 'GATE D FAIL: expand=cluster returned empty chain'
print('GATE D PASS')
"
```

**Halt if:** GATE D FAIL.

### 11. Branch cleanup

```bash
git branch -d p4-2-fix                              # local delete (already merged)
git push origin --delete p4-2-fix                   # remote delete
git push origin --delete p4-2-investigation         # stale branch (per handoff)
git branch -a                                        # confirm both gone
```

**Halt if:** delete fails for non-fast-forward reasons (means branches diverged unexpectedly).

### 12. Final state log entry

Append to `STATE-LOG.md`:

```
## 2026-05-05 — P4.2-PATCH SHIPPED

- src/recall.py:785 audit-emission key fix (1 line).
- p4-2-fix → master merged at <new HEAD>.
- Prod cluster_id backfill applied (N rows).
- P4.1 V5 expand=cluster verified populated.
- p4-2-fix and p4-2-investigation branches deleted.
- Verification gates A/B/C/D all PASS.

Closes: P4.1 S02 verification gap, P4.1 S03 halt, P4.2 end-to-end verification.
Phase 4 fully closed.

Next chain: CP-SYNTHESIS-PERF.
```

```bash
git add STATE-LOG.md
git commit -m "STATE-LOG: P4.2-PATCH shipped, Phase 4 fully closed"
git push origin master
```

---

## Halt note format

If halting, write `/root/.openclaw/workspace/memory-product/P4-2-PATCH-BLOCKED.md` with:
- Step number halted at
- Trigger
- HEAD at halt
- What CC tried (exact commands + outputs)
- Recommended next move

Do NOT stage or commit any work-in-progress on halt. Leave branch in last-committed state.

---

## Definition of done

All of:

1. `src/recall.py` line 785 reads `"memory_type": memory_type,`.
2. Gates A, B, C, D all PASS with concrete numeric evidence in commit messages.
3. `p4-2-fix` merged into `master` and pushed.
4. Cluster_id backfill applied to prod with AFTER count = 0 missing.
5. `p4-2-fix` and `p4-2-investigation` branches deleted locally and on origin.
6. STATE-LOG.md updated and pushed.
7. No `P4-2-PATCH-BLOCKED.md` exists.
8. journalctl shows no new ERRORs (modulo `analytics_events` and `error_logs` known noise).

---

## End-of-run signal

Final command at the end of the run:

```bash
afplay /System/Library/Sounds/Glass.aiff
```

(Or equivalent — CC end-of-task chime per standing rule 11.)
