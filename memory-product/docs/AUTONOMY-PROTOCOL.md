# Autonomy Protocol

**Purpose:** Define how Claude Code (CC) executes scoped tasks unsupervised on the 0Latency server, what guardrails apply, and how a human picks up the result the next morning.

**Status:** v2 — 2026-05-04. Introduces migration tier policy (Tier 1/2/3).

---

## Why this exists

Justin cannot be the human relay between chat and SSH for the rest of the 0Latency build. The roadmap is months of work. Manual ping-pong is unsustainable and competes with PFL Academy + Project Explore revenue work. The product needs to advance during work hours and overnight.

CC running on the server in \`--dangerously-skip-permissions\` mode can execute multi-step coding tasks end-to-end. The risk is unbounded scope, silent improvisation, and shipped defects. This protocol bounds that risk by:

1. **Scope doc per task** — written in advance, in the repo, version-controlled. CC's instructions are read-only at run time.
2. **Explicit gates between tasks** — CC self-checks each gate before advancing. Failed gate = halt.
3. **Halt-and-handoff** — at the first ambiguity, CC stops, writes a \`*-BLOCKED.md\` note, and exits. No silent improvisation.
4. **Read-only first** — early autonomy experiments are read-only endpoints, additive code, no migrations.
5. **Receipts, not summaries** — every commit message carries verification receipts (DB rows, curl outputs, test results). Self-reports without receipts are rejected at morning review.

---

## The three artifacts

Every autonomous run consists of three files in the repo:

### 1. Scope doc (\`docs/CP{N}-AUTONOMY-SCOPE.md\`)

Per-task. Defines:
- **Goal** — one sentence.
- **In scope** — explicit file list, function list, endpoint list.
- **Out of scope** — explicit list of things CC must NOT touch.
- **Inputs** — what CC has at start (HEAD commit, prior task outputs, etc).
- **Steps** — numbered, each with a single verification gate.
- **Halt conditions** — list of triggers that mean "stop, write blocked note, exit."
- **Final commit** — exact form of the commit message, with receipt placeholders CC fills in.

Template lives at \`docs/SCOPE-DOC-TEMPLATE.md\`.

### 2. Halt note (\`CP{N}-BLOCKED.md\`) — only created on halt

If CC halts, it writes this file in workspace root with:
- The step it halted on.
- The exact error or ambiguity encountered.
- The state of the repo at halt (uncommitted diffs, partial work).
- A recommended next move (its best guess at what should happen).

This file's existence in the morning means autonomy failed and human review is required before the next run.

### 3. Receipts in the commit message

CC's commit message MUST include actual command outputs, not summaries:
- Curl response bodies for endpoint changes.
- \`psql\` query results for DB changes.
- Test output for new tests.
- \`git log --stat\` for file change footprint.

Morning review reads the commit message + diff. If receipts are missing, the commit gets reverted.

---

## Migration Tiers

Migrations are classified into three tiers. CC behavior differs per tier.

### Tier 1: Autonomous (additive, reversible, non-data)

**Examples:**
- New column with default value (no backfill needed)
- New index
- New table
- CHECK constraint widening (adding allowed values, never removing)
- New ENUM values appended

**CC can apply autonomously** via \`scripts/db_migrate.sh up\` after verifying all of:
1. The migration's \`downgrade()\` is non-empty (reversibility required).
2. The pre-migration backup succeeded.
3. Staging applied cleanly.
4. Rollback test passes for the new revision.

If any verification fails, CC halts.

### Tier 2: Halt for human apply (schema changes touching existing rows)

**Examples:**
- NOT NULL added to existing column (requires backfill)
- Column rename
- Type change
- FK addition with cascade
- CHECK constraint narrowing (removing allowed values)

**CC writes the migration, dry-runs on staging, runs the rollback test, then halts** with a review note. Justin runs \`db_migrate.sh up\` after reviewing the migration and staging behavior.

### Tier 3: Always human (destructive or irreversible)

**Examples:**
- DROP TABLE
- DROP COLUMN
- Data backfill that cannot be reversed mechanically
- Anything irreversible

**CC halts even if the rest of the chain succeeds.** Justin reviews, applies manually if at all. These migrations should be rare; schema should be additive where possible.

---

## Migration verification gate (Tier 1)

Before applying a Tier 1 migration autonomously, CC must run:

1. **Backup verification:**
   \`\`\`bash
   bash scripts/db_backup.sh
   # Exit 0, backup file > 1MB, gunzip -t passes
   \`\`\`

2. **Staging apply:**
   \`\`\`bash
   alembic -x env=staging upgrade head
   # Exit 0, no SQL errors
   \`\`\`

3. **Rollback test:**
   \`\`\`bash
   pytest tests/migrations/test_rollback.py::test_revision_round_trip[<rev>] -v
   # PASSED
   \`\`\`

All three gates MUST pass. If any fails, halt and write blocked note.

---

## Gate types

A **gate** is a binary check between steps. CC runs the check, parses the result, and advances or halts. Three gate types:

### G1 — Endpoint contract gate

\`\`\`
curl -sS -X <METHOD> http://localhost:8420/<path> -H "X-API-Key: $ZEROLATENCY_API_KEY" \\
  -H "Content-Type: application/json" -d '<payload>' \\
  | python3 -c "import sys, json; r=json.load(sys.stdin); assert <condition>, f'gate failed: {r}'"
\`\`\`

Pass = clean exit code. Fail = AssertionError → CC halts.

### G2 — DB shape gate

\`\`\`
psql "$DATABASE_URL" -c "<SELECT>" -t | grep -qE '<expected_pattern>'
\`\`\`

Pass = grep finds the pattern. Fail = halt.

### G3 — Test gate

\`\`\`
pytest <path> -v --tb=short 2>&1 | tee /tmp/gate-output.txt
grep -q "passed" /tmp/gate-output.txt && ! grep -q "failed" /tmp/gate-output.txt
\`\`\`

Pass = tests passed, none failed. Fail = halt.

---

## Halt-and-handoff rules

CC halts and writes \`CP{N}-BLOCKED.md\` if ANY of:

1. **Gate fails twice in a row.** First failure: re-read scope, retry once. Second failure: halt.
2. **Tier 2 or 3 migration needed.** CC writes the migration, dry-runs on staging, runs the rollback test, then halts with a review note. Tier 1 migrations proceed autonomously after verification gates pass.
3. **More than 3 files modified outside scope doc's "in scope" list.** Strict.
4. **Any file in scope doc's "out of scope" list is touched.** Immediate halt.
5. **Production database write outside \`memory_service.memories\` and \`memory_service.raw_turns\`** in read-only-task experiments. (Lifted in later autonomy versions.)
6. **Any error CC cannot resolve in <5 min.** Better to halt and ask than improvise.
7. **The git working tree had unexpected modifications at start.** Means a prior session left state. Halt.
8. **Migration verification gate failure (Tier 1).** Backup fails, staging apply fails, or rollback test fails → halt.
9. **Migration tier escalation.** If implementation reveals the migration is actually a higher tier than scoped, halt.

When halting, CC must:
- Stage NO changes (\`git status\` should show all work uncommitted).
- Write the BLOCKED note with full context.
- Exit cleanly.

---

## Launch protocol

Per autonomous run, on the server:

\`\`\`bash
cd /root/.openclaw/workspace/memory-product
git status                  # must be clean
git log -1 --oneline        # record HEAD for the run
# Open Claude Code with the scope doc as the initial prompt
claude --dangerously-skip-permissions
# In CC's first turn, paste:
#   "Read /root/.openclaw/workspace/memory-product/docs/CP{N}-AUTONOMY-SCOPE.md and execute it end-to-end. Halt per the protocol if any gate fails or any halt condition triggers."
\`\`\`

CC then runs. Justin walks away.

---

## Morning review checklist

When Justin returns, in order:

1. **Check for halt notes.** \`ls /root/.openclaw/workspace/memory-product/CP*-BLOCKED.md\`. If any exist → autonomy halted, read note, decide next move.
2. **Check git log.** \`git log master --oneline -10\`. New commits should match the scope doc's expected commit count.
3. **Read commit message receipts.** \`git log -1 -p\`. Receipts should be concrete (actual outputs), not narrative.
4. **Run the scope doc's "verification suite"** if defined. (Most scope docs end with a final smoke test that proves the change works.)
5. **Check journal logs.** \`journalctl -u memory-api --since "<run start>" --no-pager | grep -E "ERROR|CRITICAL"\`. Should be clean modulo pre-existing known-issue lines.
6. **Decide:** ship (push), revert (\`git reset --hard <prior HEAD>\`), or fix-forward (manual cleanup, then push).

---

## Scaling up

This protocol starts with **single-task** runs (CP9 tonight). Once the pattern is proven:

**v2 — Chained tasks.** A "run plan" file lists 3-5 scope docs in order. CC executes each in sequence; failure of any one halts the chain. Earlier tasks remain committed. 10-12 hour runs become possible because each chain link is small.

**v3 — Branched tasks.** Independent tasks run in parallel CC sessions on the same repo via separate worktrees. (Not soon. Adds complexity.)

**v4 — Cross-surface.** CC on server + scripted hand-off to local dev environment for tasks that genuinely need it. Most don't.

Stay on v1 until v1 is boring.

---

## What this protocol explicitly does NOT do

- **No Tier 2 or 3 migrations from autonomous runs.** Tier 1 (additive, reversible) migrations are autonomous after verification. Tier 2/3 require human review and apply.
- **No secret rotation from autonomous runs.** Anthropic key, Stripe key, DB password — manual only.
- **No customer-facing endpoint deletions or breaking changes.** Additions are fine; removals require human signoff.
- **No commits to non-master branches without explicit instruction.** Default is always master.
- **No npm publishes, no DNS changes, no infra changes.** Code only.
- **No deployments to staging from autonomous runs in v1.** Code lands on master; deploy is manual until v2 establishes confidence.
