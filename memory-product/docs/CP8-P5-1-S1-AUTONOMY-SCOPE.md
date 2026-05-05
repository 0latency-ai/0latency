# CP8 Phase 5.1 Stage 1 — Redaction Cascade: Diagnosis & Inventory

**Task:** Audit current state of redaction cascade implementation. Produce a written inventory that scopes Stages 2–5.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** post-CP-SYNTHESIS-PERF master HEAD.
**Estimated wall-clock:** 15–25 min.
**This stage writes ZERO production code.** Output is one markdown file. No commits to master.

---

## Goal

One sentence: Determine exactly what part of the redaction-cascade pipeline is already implemented, what is stubbed, and what is missing — so Stages 2–5 can be scoped against ground truth instead of memory.

We have signal that some pieces exist (`src/synthesis/redaction.py` exists, `redaction_state` and `superseded_by` columns landed in CP8 P1, the `transition_source_state` cascade rule is partially wired, audit writer exists). We have no current signal on whether the pieces are connected end-to-end. This stage finds out.

---

## Why diagnosis-only

Per the lessons reinforced in CP-SYNTHESIS-PERF: profile first, optimize second. The equivalent here is *inventory first, design second*. If `redaction.py` already implements 80% of the cascade and we just need to wire an endpoint, that's a 30-min Stage 2. If `redaction.py` is mostly stub, that's a multi-stage chain. We do not know which, and guessing wrong wastes a CC chain.

Stage 1 produces the inventory. Stage 2 scope is authored against the inventory. Same posture that worked for CP-SYNTHESIS-PERF Stage 1 (profile) → Stage 2.A (diagnosis) → Stage 2.B (fix).

---

## In scope

**Files to READ (no modifications):**
- `src/synthesis/redaction.py` — primary subject; document what exists
- `src/synthesis/audit.py` — document audit event vocabulary and writer signature
- `src/synthesis/writer.py` — find the synthesis-write entry point that resynthesis would re-call
- `src/synthesis/jobs.py` — find the job-orchestration shape (cron? queue? in-memory?)
- `src/recall.py` — verify whether `pending_resynthesis` is actually filtered (Phase 4 claim)
- `api/main.py` — search for any existing redact endpoint, any cascade trigger surface
- `migrations/` — find the migration that added `redaction_state`, `superseded_by`, and `source_memory_ids` columns; record the column types and constraints exactly
- `tests/synthesis/` — find any existing redaction tests; note coverage gaps

**File to WRITE:**
- `docs/CP8-P5-1-S1-INVENTORY.md` — the deliverable.

**Database:** Read-only. Two read-only `psql` queries (see Step 2).

---

## Out of scope (DO NOT TOUCH)

- Any `.py` file modification.
- Any migration file (`migrations/*.sql`).
- Any commit to master. (Only `docs/CP8-P5-1-S1-INVENTORY.md` will be added; even that is committed in the SAME commit that includes a STATE-LOG.md entry — single commit, doc-only.)
- Any production database write.
- Any service restart.
- Any branching — work happens directly on master because this stage produces only docs.

---

## Steps

### Step 1 — Snapshot starting state

```bash
cd /root/.openclaw/workspace/memory-product
git status                         # MUST be clean
git log -1 --oneline               # record HEAD
```

**Halt if working tree dirty.**

### Step 2 — DB shape inventory (read-only)

Two queries, output captured verbatim:

```bash
set -a && source .env && set +a
psql "$DATABASE_URL" -c "
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema='memory_service'
  AND table_name='memories'
  AND column_name IN ('redaction_state','superseded_by','source_memory_ids','synthesis_version')
ORDER BY column_name;
" -A
```

```bash
psql "$DATABASE_URL" -c "
SELECT memory_type, redaction_state, COUNT(*)
FROM memory_service.memories
GROUP BY 1, 2
ORDER BY 1, 2;
" -A
```

Capture both outputs verbatim into the inventory doc. **Safe to paste:** YES — column metadata and aggregate counts only, no row content.

### Step 3 — Code-surface audit

For each file in the "in scope" READ list, produce an inventory entry that answers:

1. **Does it exist?** (file path, byte size, last-modified commit)
2. **What functions/classes are defined?** (signature only — not bodies)
3. **What's actually implemented vs. `NotImplementedError` / `pass` / TODO?**
4. **What does it import?** (the import list reveals what it expects to call into)
5. **Are there tests?** (yes/no, count of test functions)

Use grep + head, not full file reads where possible. The inventory should be skimmable.

For `src/synthesis/redaction.py` specifically, produce a function-by-function table with three columns: name, status (implemented / stub / not-found), one-line behavior.

### Step 4 — Endpoint surface audit

```bash
grep -nE "redact|/redact|redaction" api/main.py | head -40
grep -nE "redact|/redact|redaction" src/recall.py | head -40
```

Document any endpoint that mentions redact, plus its method, path, auth gate, and one-line behavior.

### Step 5 — Recall filter verification

Phase 4 claimed recall excludes redacted/pending_resynthesis. Verify:

```bash
grep -nE "redaction_state|pending_resynthesis|redacted" src/recall.py
```

Document which CTEs/queries actually filter, which don't. If any recall path doesn't filter, that's a finding for Stage 2.

### Step 6 — Audit event vocabulary

```bash
grep -nE "log_event|audit_event|emit_audit" src/synthesis/audit.py src/synthesis/redaction.py
grep -rnE "'redacted'|'resynthesized'|'redaction_cascade" src/ | head -20
```

Produce a table of audit event names already in the codebase, with the call-site that emits each.

### Step 7 — Validation cluster sanity check

The 21-member cluster `b28b7a99fd4791cb` on `user-justin` is our test fixture. Confirm it still exists and capture its source-memory composition (count and IDs only — no content):

```bash
psql "$DATABASE_URL" -c "
SELECT id, memory_type, redaction_state, created_at
FROM memory_service.memories
WHERE id = ANY(
  SELECT unnest(source_memory_ids)
  FROM memory_service.memories
  WHERE memory_type='synthesis'
    AND metadata->>'cluster_id' = 'b28b7a99fd4791cb'
)
ORDER BY created_at;
" -A
```

**Safe to paste:** YES — UUIDs and timestamps only.

If the cluster is gone or the synthesis row was superseded, halt — Stage 2 needs a known-good fixture and we should pick a new one before authoring.

### Step 8 — Author the inventory document

Write `docs/CP8-P5-1-S1-INVENTORY.md` with the following sections (and ONLY these sections — no recommendations, no Stage 2 design, just findings):

```
# CP8 P5.1 Stage 1 — Redaction Cascade Inventory

**Date:** 2026-05-05
**HEAD at audit:** <sha>
**Author:** CC (autonomous)

## Summary
<3–5 sentences. Just facts: what exists, what's missing, what's stubbed.>

## DB shape
<verbatim psql output from Step 2>

## redaction.py function inventory
<table from Step 3>

## Other module presence
<bullet list per file from Step 3>

## Endpoint surface
<table from Step 4>

## Recall filter verification
<findings from Step 5>

## Audit event vocabulary
<table from Step 6>

## Validation cluster status
<output from Step 7>

## Open questions for Stage 2 author
<list of questions the inventory raised but cannot answer from code alone — e.g., "if redact endpoint doesn't exist, should it accept memory_id only or memory_id + reason?">
```

NO design recommendations. NO Stage 2 scoping. Just findings + open questions.

### Step 9 — Single commit, doc-only

```bash
git add docs/CP8-P5-1-S1-INVENTORY.md STATE-LOG.md
git commit -m "P5.1 Stage 1: redaction cascade inventory (diagnosis-only, no code change)

Findings summary:
<paste the Summary section from the inventory doc>

Receipts:
- HEAD before: <sha>
- HEAD after: <sha>
- Files added: 1 (docs/CP8-P5-1-S1-INVENTORY.md)
- STATE-LOG entry: appended
- No code modifications, no DB writes, no service restarts.
"
git push origin master
```

STATE-LOG.md entry (append):
```
- 2026-05-05: P5.1 Stage 1 SHIPPED. Redaction cascade inventory authored at docs/CP8-P5-1-S1-INVENTORY.md. No code change. NEXT: P5.1 Stage 2 scope authoring (Opus, against this inventory).
```

---

## Halt conditions

CC halts and writes `CP8-P5-1-S1-BLOCKED.md` if:

1. Working tree dirty at start.
2. Any psql query in Steps 2 or 7 fails (network, auth, schema unexpected).
3. The validation cluster `b28b7a99fd4791cb` is missing or its source memories cannot be enumerated.
4. Any of the "in scope" READ files do not exist where expected (means the codebase moved).
5. CC is tempted to write code. (This is doc-only.)
6. CC is tempted to write recommendations into the inventory. (Findings only.)
7. Inventory doc would exceed 500 lines (means too verbose — re-summarize).

On halt: stage nothing, write the BLOCKED note, exit.

---

## Definition of done

All of:

1. `docs/CP8-P5-1-S1-INVENTORY.md` exists and contains all 8 required sections.
2. The inventory contains zero design recommendations and zero Stage 2 scoping.
3. STATE-LOG.md has one new entry.
4. Single commit on master, pushed.
5. `git status` clean.
6. No `CP8-P5-1-S1-BLOCKED.md` exists.

---

## Final commit message template

```
P5.1 Stage 1: redaction cascade inventory (diagnosis-only, no code change)

<Summary section verbatim>

Receipts:
- HEAD before: <sha>
- HEAD after: <sha>
- Files added: docs/CP8-P5-1-S1-INVENTORY.md (<N> lines)
- STATE-LOG entry appended
- DB queries: 3 (read-only — column metadata, aggregate counts, fixture enumeration)
- No code modifications.
- No service restarts.
- No production DB writes.
```
