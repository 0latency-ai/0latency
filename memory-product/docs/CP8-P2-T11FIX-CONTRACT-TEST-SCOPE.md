# CP8 Phase 2 T11 Hollow-Pass Fix — Autonomous Scope

**Task:** Fix the nightly verbatim contract test (shipped this morning as commit `4eb70ab`) so it actually exercises the verbatim path instead of always passing on 0 atoms.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** T5+T6 commit.
**Estimated wall-clock:** 10–20 min for CC.
**Chain position:** Chain B, task 4 of 4 (T2 → T3 → T5+T6 → **T11-fix**).

---

## Goal

One sentence: The verbatim contract test currently passes vacuously when zero atoms exist; switch it to write a sentinel atom via `/memories/seed`, run extraction, and assert the sentinel string round-trips through `GET /memories/{id}/source` byte-for-byte.

This converts T11 from a hollow assertion into a real contract verifier.

---

## In scope

**Files to modify:**
- The T11 contract test file (location TBD by Step 1; likely `tests/contract/test_verbatim_nightly.py` or `scripts/verbatim_contract_test.py`)

**Files to read (do not modify):**
- The T11 commit's changeset (`git show 4eb70ab`) — to understand what's there now
- `api/main.py` — `/memories/seed` route shape
- `src/extraction.py` — to confirm the `/memories/extract` round-trip path
- `docs/VERBATIM-GUARANTEE.md` (from Chain A T8) — to align test assertions with documented contract

**Database:** Writes one sentinel atom per run, deletes it after. No migrations.

---

## Out of scope (DO NOT TOUCH)

- The actual extraction logic
- `GET /memories/{id}/source` handler
- T8's `VERBATIM-GUARANTEE.md` (already documents the contract; fixing the test does not change the contract)
- Any synthesis-layer code (T1–T6)
- Any other file beyond the test itself and a possible cron entry update

---

## Test contract

The fixed test must:

1. Generate a unique sentinel string per run: `f"VERBATIM-CONTRACT-TEST-{datetime.now(timezone.utc).isoformat()}-{secrets.token_hex(8)}"`
2. POST the sentinel as a memory via `/memories/seed`:
   ```
   POST /memories/seed
   Body: {
     "agent_id": "verbatim-contract-test",  // dedicated agent for these
     "memory_type": "fact",
     "content": "<SENTINEL>"
   }
   ```
3. Capture the returned memory_id.
4. GET `/memories/{memory_id}/source` and parse JSON.
5. Assert: `response["source_text"] == SENTINEL` exactly. Byte-for-byte; no whitespace stripping, no normalization.
6. **Also test the extraction path:** POST a turn via `/memories/extract` containing a different sentinel embedded in conversational text (e.g. `f"Human: Please remember the phrase '{SENTINEL2}'\n\nAgent: Got it."`). Capture the resulting `raw_turn_id`.
7. GET `/memories/{raw_turn_id}/source` — assert sentinel2 substring is present in `source_text`.
8. Cleanup: delete both memories via the existing delete path (or the test's own cleanup hook).
9. On any assertion failure: log to stderr with the full request/response trace AND exit with non-zero code so the cron job's exit reflects failure.

---

## Steps

### Step 1 — Locate the existing T11 test

```bash
cd /root/.openclaw/workspace/memory-product
git show --stat 4eb70ab
```

**Gate G2:** find the file path(s) added/modified by T11. Record. If the changeset includes a systemd timer or cron entry, note that location too.

### Step 2 — Read the existing test

```bash
cat <test_file_from_step_1>
```

**Gate G2:** confirm the hollow-pass diagnosis — the test should currently iterate atoms, find zero, and pass without checking anything. If the test does NOT match this description, halt — diagnosis is wrong; need fresh investigation.

### Step 3 — Rewrite the test per contract

Replace the test body with the seed + extract round-trip described in the contract section. Preserve:
- The cron-entry-point shape (don't break the systemd unit if one exists)
- The exit-code semantics (cron must see non-zero on failure)
- Existing logging format if a downstream alert hook reads from journalctl

Add: clear docstring stating that the test makes real DB writes (one or two rows per run) under a dedicated `verbatim-contract-test` agent_id so production memories are never touched.

### Step 4 — Run the test once locally

```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
python3 <test_file_from_step_1>; echo "Exit code: $?"
```

**Gate G2:**
- Exit code 0 (test passes against current prod)
- Stdout/stderr clearly states which sentinels were tested and that round-trip succeeded
- A second run completes cleanly (idempotent — cleanup works)

If exit non-zero: the verbatim contract is **actually broken** in prod. Halt and write BLOCKED with the failure trace. Do NOT commit the test fix; the underlying contract issue is a higher-priority halt.

### Step 5 — Verify no orphan rows from test runs

```bash
psql "$DATABASE_URL" -c "
SELECT COUNT(*) AS test_atoms
FROM memory_service.memories
WHERE agent_id = 'verbatim-contract-test'
  AND created_at > NOW() - INTERVAL '15 minutes';
"
```

**Gate G2:** result is 0 or low single digits (one running test in flight). If counter climbs across runs, cleanup is broken — halt.

### Step 6 — Commit

```bash
git add <test_file_from_step_1>
git status
git diff --cached --stat
```

Commit message:

```
CP8 Phase 2 T11-fix: verbatim contract test no longer hollow-passes

The test shipped in 4eb70ab iterated atoms and passed without checking
the verbatim contract because justin's namespace had zero atoms matching
the iteration filter. This commit replaces the hollow iteration with a
seed-and-round-trip pattern that actually exercises the contract.

Test now:
- POSTs a sentinel string via /memories/seed
- GETs /memories/{id}/source and asserts byte-for-byte equality
- Repeats via /memories/extract for the extraction path
- Cleans up both memories via the dedicated 'verbatim-contract-test' agent
- Exits non-zero on contract violation so cron alerting fires

Closes the carry-forward note in HANDOFF-2026-05-03-EOD.md.

Verification receipts:
[CC fills in: exit code 0, sentinel echo, orphan count from step 5]

Files: <test_file_from_step_1> (rewrite, ~N lines)
```

```bash
git commit -F /tmp/cp8-p2-t11fix-commit-msg.txt
git log -1 --stat
git push origin master
```

**Final gate:** push exit 0.

### Step 7 — One more run to confirm idempotency post-commit

```bash
python3 <test_file_from_step_1>; echo "Exit: $?"
```

**Gate G2:** exit 0 again. Two clean runs in a row.

---

## Halt conditions (specific to this task)

1. **Step 1 cannot find files modified by 4eb70ab.** Halt — commit hash may be wrong; check handoff.
2. **Step 2 reveals the existing test is NOT a hollow-pass** (e.g., it's already exercising the contract somehow). Halt — diagnosis is wrong; do not "fix" what isn't broken.
3. **Step 4 fails with the verbatim contract actually broken.** This is a P0 halt — `GET /memories/{id}/source` doesn't return verbatim, OR `/memories/seed` lossily transforms input. Write BLOCKED note with the exact diff between sentinel-sent and source-text-returned.
4. **Step 5 shows orphan rows accumulating.** Cleanup logic is broken — halt.
5. **`/memories/seed` and `/memories/extract` not in `api/main.py` at the expected paths.** Halt — endpoint paths drifted; rescope.

---

## Definition of done

1. T11 contract test rewritten to actually exercise the contract.
2. Two clean runs in a row, both exit 0.
3. No orphan rows from test runs.
4. Single commit pushed with real receipts.
5. No `CP8-P2-T11FIX-BLOCKED.md`.

**No deploy needed** — test only.
