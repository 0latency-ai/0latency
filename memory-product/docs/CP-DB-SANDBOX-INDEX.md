# CP-DB-SANDBOX — Chain Index

**Date:** 2026-05-04
**Goal:** Eliminate production-DB-only operation. Stand up a staging DB, integrate Alembic, automate per-migration backups, and verify rollbacks. Outcome: Tier-2 migrations become safely autonomous; Chain runs no longer halt for routine schema changes.
**Predecessor:** CP8 Phase 2 Chain B (HEAD at chain start: TBD by pre-flight)
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Estimated wall-clock (using 0.3–0.5× multiplier):** 90–180 min total.

---

## Why this chain exists

Today every DB change touches prod directly. There is no staging twin, no automated backup before migration, no tested rollback path, and no tooling that tracks which migrations have been applied. CP8 Phase 2 Task 2 halted this morning on a CHECK-constraint widening (migration 023) — a Tier-1 trivial change — purely because protocol forbids autonomous prod migrations. The protocol is correct; the infrastructure is the gap.

This chain closes that gap.

After this chain ships:
- Staging DB lives on the same DigitalOcean instance, separate database name.
- Alembic owns migration state. Existing 23 SQL migrations are imported as a baseline.
- Every migration apply runs `pg_dump` first, retains last 10 dumps.
- Every migration's down-script is verified to actually reverse the up-script on staging before prod apply.
- AUTONOMY-PROTOCOL.md v2 introduces Tier-1/2/3 migration policy. Tier-1 (additive, reversible, non-data) becomes autonomous.

---

## Tasks (sequential, single CC chain)

| # | Task | Scope doc | Outputs | Halt expected? |
|---|---|---|---|---|
| 1 | Provision staging DB | `CP-DB-SANDBOX-T1-STAGING-PROVISION-SCOPE.md` | New DB `memory_service_staging`, schema cloned, `STAGING_DATABASE_URL` in `.env` | No |
| 2 | Alembic integration + baseline import | `CP-DB-SANDBOX-T2-ALEMBIC-SCOPE.md` | `alembic/` directory, `alembic.ini`, all 23 existing migrations imported as one baseline revision, prod stamped at baseline | **Yes — baseline confirm** |
| 3 | Backup automation + rollback testing harness | `CP-DB-SANDBOX-T3-BACKUP-ROLLBACK-SCOPE.md` | `scripts/db_migrate.sh` (backup → apply → verify), `tests/migrations/test_rollback.py`, retention policy | No |
| 4 | Protocol v2 + cutover smoke | `CP-DB-SANDBOX-T4-PROTOCOL-V2-SCOPE.md` | `docs/AUTONOMY-PROTOCOL.md` v2 with Tier-1/2/3, end-to-end smoke (fake migration through new pipeline), scope-doc template update | **Yes — first real cutover confirm** |

**Two halts expected.** Both are 1–2 minute confirmations, suitable for mobile CC.

---

## Pre-flight checklist (run at chain start)

```bash
cd /root/.openclaw/workspace/memory-product
git status               # must be clean
git pull origin master
git log -1 --oneline     # record HEAD for the run
set -a && source .env && set +a
psql "$DATABASE_URL" -c "SELECT 1;" | head -3
systemctl is-active memory-api    # must be "active"
ls *BLOCKED.md 2>/dev/null         # must be empty
```

If any check fails, halt — do not start the chain.

---

## Chain launch prompt

Paste into a fresh Claude Code session (Mac or mobile, both work):

```
Read /root/.openclaw/workspace/memory-product/docs/CP-DB-SANDBOX-INDEX.md
and execute end-to-end, doing all work via SSH:

  1. Read and execute docs/CP-DB-SANDBOX-T1-STAGING-PROVISION-SCOPE.md
  2. On clean T1 commit + push, read and execute docs/CP-DB-SANDBOX-T2-ALEMBIC-SCOPE.md
     (will halt at Step 7 for baseline confirm — write
     CP-DB-SANDBOX-T2-BASELINE-REVIEW.md to workspace root and exit cleanly)
  3. After Justin's resume prompt, continue
  4. On clean T2 commit + push, read and execute docs/CP-DB-SANDBOX-T3-BACKUP-ROLLBACK-SCOPE.md
  5. On clean T3 commit + push, read and execute docs/CP-DB-SANDBOX-T4-PROTOCOL-V2-SCOPE.md
     (will halt at Step 8 for cutover smoke confirm — write
     CP-DB-SANDBOX-T4-CUTOVER-REVIEW.md to workspace root and exit cleanly)
  6. After Justin's resume prompt, continue and finish

Halt the entire chain if any task halts unexpectedly. Each scope doc's
halt conditions are authoritative for that task. Per AUTONOMY-PROTOCOL.md.
```

---

## Strategic frame

This chain is the structural fix for the "every migration is a tripwire" problem. Once it ships, autonomy budget jumps from ~30-min Sonnet chains (today) to multi-hour overnight runs (after this chain). The investment pays back across every CP after this one.

Frame: **what would Mem0 do at this stage?** Mem0 already has staging environments and migration tooling — they're 18 months ahead on infra hygiene. This chain catches us up on the one piece where being behind is dangerous (data integrity), not just slower (feature velocity).
