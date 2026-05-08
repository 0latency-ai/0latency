# CP8 Phase 5.1 Stage 2.V — Verification & Triage

**Task:** Resolve four open verification questions from Stage 2's end-to-end run. Decide merge-readiness or write a fix plan.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** `115a79c` on branch `cp-p5-1-s2`.
**Estimated wall-clock:** 10–20 min.
**This stage writes ZERO production code.** Output is one verification report plus, conditionally, a fix-up commit on the same branch.

---

## Goal

One sentence: Verify Stage 2's end-to-end run was actually correct (cascade count, audit chain integrity, migration file presence, endpoint test viability) and either declare the branch merge-ready or document exactly what's broken and how to fix it.

Stage 2's chat-summary triage surfaced four flags. Each has a concrete check. CC runs each check, records findings, and produces a verdict.

---

## In scope

**Files to READ:**
- `migrations/versions/` directory (find migration 024)
- `tests/synthesis/test_redaction_endpoint.py` (assess import issue severity)
- Any migration file related to `024` wherever it lives in the repo

**Files to WRITE:**
- `docs/CP8-P5-1-S2V-VERIFICATION.md` — the triage report

**Files to OPTIONALLY MODIFY (only if specific conditions met — see Step 5):**
- `tests/synthesis/test_redaction_endpoint.py` — only if the import issue is a 1-3 line trivial fix that lets the existing tests run

**Database:** Read-only.

---

## Out of scope (DO NOT TOUCH)

- Any production write, any service restart, any schema change.
- Any merge to master.
- Any modification to `redaction.py`, `resynthesis_worker.py`, `state_machine.py`, `api/main.py`, or migration 024.
- Any new feature work.
- Authoring new tests beyond fixing imports on the existing test file.

---

## Steps

### Step 1 — Snapshot starting state

```bash
cd /root/.openclaw/workspace/memory-product
git status
git log -1 --oneline    # expected 115a79c on cp-p5-1-s2
git checkout cp-p5-1-s2  # if not already there
```

If branch isn't `cp-p5-1-s2` or HEAD isn't `115a79c`, halt.

### Step 2 — Verify cascade-count correctness (Flag 1)

The end-to-end test redacted memory `58772303-7644-418e-a39d-3d55ecd3b3ae` and got `cascade_count=1`. Verify this was correct: how many syntheses on the validation cluster actually cited that source?

```bash
set -a && source .env && set +a
psql "$DATABASE_URL" -c "
SELECT COUNT(*) FROM memory_service.memories
WHERE memory_type='synthesis'
  AND metadata->>'cluster_id'='b28b7a99fd4791cb'
  AND '58772303-7644-418e-a39d-3d55ecd3b3ae'::uuid = ANY(source_memory_ids);
" -t -A
```

Capture the count.

**Verdict logic:**
- If count == 1: cascade was correct. Flag 1 RESOLVED.
- If count > 1: cascade query under-counted. Flag 1 BUG. Document the discrepancy.

Also capture the source-distribution across the cluster (which sources are cited how often):

```bash
psql "$DATABASE_URL" -c "
SELECT src::text as source_id, COUNT(*) as citations
FROM memory_service.memories,
     unnest(source_memory_ids) AS src
WHERE memory_type='synthesis'
  AND metadata->>'cluster_id'='b28b7a99fd4791cb'
GROUP BY src
ORDER BY citations DESC;
" -A
```

This shows the citation distribution. Useful context for whether `58772303...` was an unusually low-citation source.

### Step 3 — Locate migration 024 (Flag 4)

Find where migration 024 actually lives:

```bash
find /root/.openclaw/workspace/memory-product -name "024*" -type f 2>/dev/null | head -20
ls /root/.openclaw/workspace/memory-product/migrations/versions/ 2>/dev/null | tail -10
ls /root/.openclaw/workspace/memory-product/migrations/ 2>/dev/null | tail -10
```

Once located, read its full contents and capture:
- File path
- Format (Alembic Python? Raw SQL?)
- The `upgrade()` body (or full SQL body)
- Whether it includes inner BEGIN/COMMIT (footgun per AUTONOMY-PROTOCOL — should NOT be present)
- The `downgrade()` body (or reversal note)

**Verdict logic:**
- If found, well-formed, no inner BEGIN/COMMIT, has reasonable downgrade: Flag 4 RESOLVED.
- If found but has inner BEGIN/COMMIT: Flag 4 = footgun-on-disk, needs cleanup. Document the exact lines.
- If not found anywhere: Flag 4 = missing migration file but applied to DB. Critical — document and halt for operator decision.

### Step 4 — Audit table schema + duplicate-event check (Flag 5)

Get the actual schema of `synthesis_audit_events`:

```bash
psql "$DATABASE_URL" -c "\d memory_service.synthesis_audit_events"
```

Identify the timestamp column (likely `event_timestamp`, `ts`, `occurred_at`, or similar). If there is NO timestamp column at all, document this as a critical audit-chain defect.

Once the timestamp column is identified (call it `<TS_COL>`), re-run the audit-chain query using it:

```bash
psql "$DATABASE_URL" -c "
SELECT event_type, COUNT(*) FROM memory_service.synthesis_audit_events
WHERE <TS_COL> > now() - interval '4 hours'
GROUP BY 1 ORDER BY 1;
" -A
```

Then examine the two `redaction_cascade_initiated` events:

```bash
psql "$DATABASE_URL" -c "
SELECT event_id, memory_id, payload, <TS_COL>
FROM memory_service.synthesis_audit_events
WHERE event_type='redaction_cascade_initiated'
ORDER BY <TS_COL> DESC
LIMIT 5;
" -A
```

(If `event_id` isn't a column, use `id` or whatever the PK column actually is — adapt per the `\d` output.)

**Verdict logic:**
- If the two `redaction_cascade_initiated` events have the same `memory_id` and very close timestamps (<60s apart): duplicate-emit BUG in `cascade_to_synthesis`. Document with line-level reference to where the duplicate emit likely happens. Flag 5 = BUG.
- If the two events have different `memory_id` values OR are minutes apart: Step 9 was simply run twice during CC iterations. Flag 5 RESOLVED, no bug.
- If there's no timestamp column at all: Flag 5 = critical audit defect, blocks P5.2. Document this prominently.

### Step 5 — Endpoint test triage (Flag 2)

Read the import section of the test file:

```bash
head -50 tests/synthesis/test_redaction_endpoint.py
```

Try running it to see the actual failure:

```bash
cd /root/.openclaw/workspace/memory-product
pytest tests/synthesis/test_redaction_endpoint.py -v --tb=short 2>&1 | head -60
```

**Verdict logic:**
- If imports succeed and tests run (some may fail on substantive logic): Flag 2 RESOLVED. Document test results in the report.
- If import error is a trivial sys.path / module path fix (e.g., wrong relative import, missing `__init__.py`, single-line typo): fix it inline, re-run, capture results. This is the ONE conditional code modification permitted in this stage. Document exactly what was changed in 1-3 lines.
- If import error reveals deeper problem (auth helper signature changed, fixtures don't exist, models renamed): Flag 2 = needs P5.1 Stage 2.F follow-up scope. Do NOT attempt the fix. Document the error verbatim.

**Modification limit:** if any fix attempted exceeds 5 lines of changes, revert and document as needs-follow-up.

### Step 6 — Author the verification report

Write `docs/CP8-P5-1-S2V-VERIFICATION.md` with this exact structure:

```
# CP8 P5.1 Stage 2.V — Verification Report

**Date:** 2026-05-05
**Branch:** cp-p5-1-s2
**Predecessor commit:** 115a79c
**HEAD at verification:** <sha>

## Verdict
ONE OF: MERGE-READY | MERGE-READY-WITH-CARRY-FORWARD | NEEDS-FIX-BEFORE-MERGE | BLOCKED

(One paragraph rationale.)

## Flag 1 — cascade_count correctness
- Citations of redacted memory: <count>
- Cascade count from endpoint: 1
- Verdict: RESOLVED | BUG
- Source citation distribution:
  <verbatim psql output>

## Flag 4 — Migration 024 location and shape
- File path: <full path or NOT FOUND>
- Format: Alembic Python | Raw SQL | other
- Inner BEGIN/COMMIT present: yes/no
- upgrade() body: <verbatim>
- downgrade() body: <verbatim or "missing">
- Verdict: RESOLVED | NEEDS-CLEANUP | CRITICAL

## Flag 5 — Audit table schema + duplicate event
- Schema (relevant columns): <verbatim from \d>
- Timestamp column: <name or NONE>
- redaction_cascade_initiated events in last 4h:
  <verbatim psql output>
- Two-event analysis: same memory_id? timestamp delta?
- Verdict: RESOLVED | BUG | CRITICAL-AUDIT-DEFECT

## Flag 2 — Endpoint test viability
- Import issue type: <description>
- Pytest output (first 30 lines):
  <verbatim>
- Fix attempted: yes/no
- If yes, exact diff: <show>
- If yes, post-fix pytest result: <pass/fail counts>
- Verdict: RESOLVED | RESOLVED-WITH-INLINE-FIX | NEEDS-FOLLOW-UP-CHAIN

## Carry-forward items (if any)
<bullet list of work that should land in a future chain but does not block merge>

## Recommended operator action
ONE OF:
- Merge cp-p5-1-s2 to master, proceed to P5.2.
- Merge cp-p5-1-s2 to master, schedule P5.1.F follow-up for: <list>.
- Do not merge. P5.1.S2 has bugs requiring Stage 2.B: <list of bugs>.
```

### Step 7 — Commit decision

**If Flag 2 was fixed inline (and only if):**

```bash
git add tests/synthesis/test_redaction_endpoint.py docs/CP8-P5-1-S2V-VERIFICATION.md
git commit -m "P5.1 Stage 2.V: verification + endpoint test import fix

<paste Verdict paragraph from report>

Receipts:
- Flag 1: <one-line verdict>
- Flag 2: fixed inline (<N> lines), tests now run: <pass/fail>
- Flag 4: <one-line verdict>
- Flag 5: <one-line verdict>

Test fix diff: <verbatim 1-3 line diff>
"
git push origin cp-p5-1-s2
```

**Otherwise (no inline fix):**

```bash
git add docs/CP8-P5-1-S2V-VERIFICATION.md
git commit -m "P5.1 Stage 2.V: verification report (no code changes)

<paste Verdict paragraph from report>

Receipts:
- Flag 1: <one-line verdict>
- Flag 2: <one-line verdict>
- Flag 4: <one-line verdict>
- Flag 5: <one-line verdict>
"
git push origin cp-p5-1-s2
```

Either way, single commit. Do NOT merge to master.

---

## Halt conditions

CC halts and writes `CP8-P5-1-S2V-BLOCKED.md` if:

1. Working tree dirty at start, or HEAD is not `115a79c`, or branch is not `cp-p5-1-s2`.
2. Any psql query fails with auth or connection error.
3. Migration 024 file genuinely cannot be found anywhere in the repo (Flag 4 = critical).
4. `synthesis_audit_events` has no timestamp column at all (Flag 5 = critical audit defect).
5. Endpoint test fix attempt exceeds 5 lines of diff.
6. CC is tempted to fix the cascade query, the worker, or any production code.
7. CC is tempted to apply a new migration to address any finding.

On halt: stage nothing, write the BLOCKED note, exit.

---

## Definition of done

All of:

1. `docs/CP8-P5-1-S2V-VERIFICATION.md` exists with all required sections filled in.
2. The Verdict line at the top is one of the four allowed values.
3. Single commit on `cp-p5-1-s2`, pushed to origin.
4. No `CP8-P5-1-S2V-BLOCKED.md` exists.
5. Branch NOT merged to master.
