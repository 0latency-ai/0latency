# CP8 Phase 2 Synthesis Writer — Autonomy Chain Index

**Author:** Opus, in chat, 2026-05-03 EOD
**Predecessor commit:** `410d91a` on memory-product/master
**Total scope:** 6 scope docs, 2 chains
**Total estimated wall-clock:** Chain A 60–110 min, Chain B 75–145 min

This document is the index. Each chain link is its own scope doc. CC reads the link's scope doc, executes, halts on failure, advances on success.

---

## Chain A — Foundation (3 tasks, sequential)

Order matters. T1 has no DB writes. T4 has a migration that requires human review mid-run. T8 is documentation only.

| # | Task | Scope doc | Outputs | Restart needed |
|---|---|---|---|---|
| 1 | T1: Clustering engine | `CP8-P2-T1-CLUSTERING-SCOPE.md` | `src/synthesis/clustering.py` + tests | No |
| 2 | T4: DB-backed jobs | `CP8-P2-T4-JOBS-SCOPE.md` | migration + `src/synthesis/jobs.py` + tests | No (table only) |
| 3 | T8: Verbatim guarantee doc | `CP8-P2-T8-VERBATIM-GUARANTEE-SCOPE.md` | `docs/VERBATIM-GUARANTEE.md` | No |

**Chain A halt expected mid-run:** T4 step 3 writes the migration file and stops, requesting Justin apply it manually. After Justin applies and resumes CC, T4 continues from step 4. T1 and T8 are uninterrupted.

---

## Chain B — Writer + plumbing (4 tasks, sequential)

Builds on Chain A's outputs. Run only after Chain A completes cleanly.

| # | Task | Scope doc | Outputs | Restart needed |
|---|---|---|---|---|
| 1 | T2 (+T7): Writer | `CP8-P2-T2-WRITER-SCOPE.md` | `src/synthesis/writer.py` + prompt + tests; folds T7 audit & rate-limit awareness | No |
| 2 | T3: Source-quote validation | `CP8-P2-T3-VALIDATION-SCOPE.md` | `src/synthesis/validation.py` + 1-line writer wiring + tests | No |
| 3 | T5+T6: Endpoint + cron | `CP8-P2-T5T6-TRIGGER-AND-CRON-SCOPE.md` | `POST /synthesis/run`, orchestrator, systemd units (NOT installed) | **Yes** (memory-api restart) |
| 4 | T11 hollow-pass fix | `CP8-P2-T11FIX-CONTRACT-TEST-SCOPE.md` | rewritten verbatim contract test | No |

**Chain B halt expected mid-run:** T5+T6 step 9 writes systemd units to `scripts/` but does NOT install them. Justin installs the timer at his own discretion (instructions written into a review note). The endpoint works without the timer.

---

## Chain launch instructions

### Chain A launch

On the server, in CC:

```
Read /root/.openclaw/workspace/memory-product/docs/CP8-P2-CHAIN-A-INDEX.md
and execute Chain A end-to-end:
  1. Read and execute docs/CP8-P2-T1-CLUSTERING-SCOPE.md
  2. On clean T1 commit + push, read and execute docs/CP8-P2-T4-JOBS-SCOPE.md
     (will halt mid-task for migration review — write the review note and exit)
  3. After resume by Justin, finish T4
  4. On clean T4 commit + push, read and execute docs/CP8-P2-T8-VERBATIM-GUARANTEE-SCOPE.md

Halt the entire chain if any task halts. Each scope doc's halt conditions
are authoritative for that task. Per AUTONOMY-PROTOCOL.md.
```

### Chain B launch

After Chain A is clean and pushed:

```
Read /root/.openclaw/workspace/memory-product/docs/CP8-P2-CHAIN-A-INDEX.md
and execute Chain B end-to-end:
  1. Read and execute docs/CP8-P2-T2-WRITER-SCOPE.md
  2. On clean T2 commit + push, read and execute docs/CP8-P2-T3-VALIDATION-SCOPE.md
  3. On clean T3 commit + push, read and execute docs/CP8-P2-T5T6-TRIGGER-AND-CRON-SCOPE.md
     (will halt mid-task for cron install review — write the review note and exit)
  4. After resume by Justin (or skip cron install), continue
  5. On clean T5+T6 commit + push, read and execute docs/CP8-P2-T11FIX-CONTRACT-TEST-SCOPE.md

Halt the entire chain if any task halts.
```

---

## Pre-flight checklist (Justin runs before each chain)

```bash
cd /root/.openclaw/workspace/memory-product
git status              # must be clean
git pull origin master  # confirm at expected HEAD
git log -1 --oneline
set -a && source .env && set +a
psql "$DATABASE_URL" -c "SELECT 1;" | head -3   # connection check
systemctl is-active memory-api   # must be "active"
ls docs/CP8-P2-*BLOCKED.md 2>/dev/null   # must be empty (no prior halts)
```

If any check fails, do not launch the chain.

---

## Morning review checklist (Justin runs after each chain completes or halts)

```bash
cd /root/.openclaw/workspace/memory-product
ls *BLOCKED.md docs/*BLOCKED.md 2>/dev/null    # any halt notes?
git log master --oneline -10                   # commit count matches expected?
git log -1 -p                                  # last commit's diff + receipt sanity
journalctl -u memory-api --since "<chain start>" --no-pager | grep -E "ERROR|CRITICAL" | grep -v analytics_events
```

Decision tree:
- Halt note exists → read note, decide: fix-forward, revert, or just unblock and resume
- No halt notes + N expected commits → ship (already pushed)
- No halt notes + commit count off → investigate

---

## Cross-chain dependencies (sanity check)

- T1's `find_clusters` is imported by T2 ✓
- T1's `Cluster` dataclass is imported by T2 ✓
- T2's `ValidationResult` dataclass is imported by T3 ✓
- T2's `synthesize_cluster` is imported by T5+T6's orchestrator ✓
- T4's `create_job/start_job/complete_job/fail_job` are imported by T5+T6's orchestrator ✓
- T3 wires its validator as default callback in T2's writer (1-line edit) — only known cross-task code modification
- T5+T6 only touches `api/main.py` to add the route; does not modify writer, clustering, or jobs

If any of these import paths fails at run-time, the affected chain task halts before mutating anything else.

---

## Why these splits

- **Chain A first** — T1 (read-only), T4 (one migration, easy review), T8 (docs). Lowest-risk foundation. Clean checkpoint between Chain A and Chain B for Justin to validate the substrate.
- **T7 folded into T2** — T7 ("audit-and-rate-limit-aware writes") is implicit in T2's writer; not a separable task.
- **T5+T6 combined** — they share the orchestrator code path. Splitting would duplicate `run_synthesis_for_tenant`. Combined keeps the diff coherent.
- **T11 fix at chain tail** — depends on T8's documentation existing (it cites the contract) and on the synthesis layer existing (gives confidence the verbatim path is exercised under realistic load).
- **T9, T10 NOT in this index** — they shipped 2026-05-03 morning (commits `963a5e8`, `df87493`).
