# CC Chain Framework — Multi-Hour Autonomous Execution

**Purpose:** Eliminate the human-relay anti-pattern. Every CC chain prompt authored with this framework targets a minimum of 2 hours autonomous wall-clock with a working ceiling of 6–8 hours. Justin returns to a finished result, not a paused one.

**Standing rule:** No CC chain prompt leaves chat unless it conforms to this framework. If a task is too small to fill 2 hours, it gets stacked with adjacent work until it does. The unit of execution is "the chain," not "the task."

---

## The five non-negotiables

### 1. CC verifies its own output. Justin never relays SSH text.

The historical anti-pattern: chat-Claude tells Justin to run `git log --oneline -3`, Justin pastes output back, chat-Claude reads it. This is a relay. CC has SSH. CC can run the command, parse the output, and act on it without Justin in the middle.

**Every chain prompt embeds its own pre-flight, sanity, and post-flight verification.** CC runs the commands, asserts on the output, and proceeds or aborts based on its own reading. Justin never types `git log` for verification purposes again.

The *only* justification for pulling Justin in mid-chain:
- A genuinely novel finding (correctness regression, unexpected schema state, something the decision tree didn't anticipate)
- A Tier 2/3 migration that policy says requires human apply
- A secret rotation Justin must perform on a third-party surface (e.g., MCP connector update in Claude.ai)

Anything else — and especially anything that's "let me just confirm X looks right" — is a framework violation.

### 2. Decision trees are embedded, not deferred.

When CC hits a fork — predicate accepted or rejected, test passing or failing, EXPLAIN showing HNSW or btree — the prompt MUST tell it exactly what to do for every branch. If the prompt says "halt and ask Justin," the prompt is wrong. The author (chat-Claude) didn't think hard enough.

The mental discipline: before writing the prompt, enumerate every fork CC will encounter and pre-decide every branch. If a branch genuinely cannot be pre-decided, that's the *only* place a halt gate is acceptable, and the halt must produce a self-contained decision package (the question, the evidence, the proposed options) so chat-Claude can decide in one round-trip.

### 3. Chains are stacked. The unit is the session, not the task.

Single-task prompts are forbidden as the default. The default is: chain everything that's ready to ship into one prompt and let CC work for hours. Stacking pattern:

- **Stage 1:** Highest-priority task with the clearest scope.
- **Stage 2:** Adjacent task that doesn't conflict with Stage 1's file paths.
- **Stage 3:** Maintenance/cleanup work (bug fixes, doc authoring, schema qualifications) that's been sitting in the backlog.
- **Stage 4:** Stretch — work that's lower priority but ready to ship if time permits.
- **Stage 5+:** Anything else from the open-items queue that fits.

A 2-hour chain is the floor. A 6–8 hour chain is the working ceiling. There is no scenario where "scope one thing and run it" is correct unless that one thing genuinely takes 2+ hours by itself (rare — usually a benchmark run or a migration with a long verification window).

**Stack-aware authoring:** before writing a chain prompt, scan the open-items queue (from the latest handoff) and identify everything compatible with the lead task's file paths and risk profile. Pull as much in as fits. Backlog reduction is a primary goal of every chain, not a bonus.

### 4. Verification gates are internal to the chain, not external.

Every stage in a chain has its own verification gate, and the gate is part of the prompt CC reads. The gate specifies:
- What command CC runs to verify the stage.
- What output indicates success.
- What output indicates failure.
- What CC does on failure (retry, rollback, skip, halt).

CC never finishes a stage and waits for Justin to confirm it worked. CC verifies, decides, and moves to the next stage on its own.

The chain ends with a **summary verification gate** that re-checks all stages and produces a single consolidated report (commit SHAs, test results, performance numbers, any anomalies). That report is what Justin reads when he comes back, in one piece, instead of dribbled across 12 mid-chain check-ins.

### 5. Audio chime is the only signal Justin needs.

Justin's signal that a chain is done is `afplay /System/Library/Sounds/Glass.aiff`. That's it. No mid-chain pings, no "stage 2 complete" updates, no "ready for the next thing?" prompts. The chime fires once, at the end, when the consolidated report is written.

If CC genuinely cannot proceed (Tier 2 migration boundary, novel finding), it writes a halt-state report to disk *and* fires the chime. Justin reads the report when he returns.

---

## Chain anatomy

Every chain prompt has exactly these sections, in this order:

```
=== [CHAIN NAME] — [N stages, target M-hour run] ===

CONTEXT
[2–4 sentences. What's been shipped, what's blocking, what this chain
delivers. No history beyond what CC needs to make decisions.]

PLATFORM CONSTRAINTS
[Anything CC must know that's not discoverable from the repo:
pgvector version, DO managed PG quirks, model-router rules,
cron schedule conflicts, etc.]

STANDING RULES (apply to every stage)
- SSH: ssh root@164.90.156.169 → cd /root/.openclaw/workspace/memory-product
- psql: cd /root/.openclaw/workspace/memory-product && set -a && source .env && set +a && psql "$DATABASE_URL"
- Never echo secrets. Read from .env or DB; never print.
- Inner BEGIN/COMMIT in migration SQL = silent failure trap. Don't introduce.
- Self-verify every claimed end state with a real probe (curl/journalctl/git/psql) before declaring a stage done.
- On any unrecoverable failure: write halt-report to /tmp/chain-halt-<stage>.md, fire chime, stop.
- This chain is Tier [0/1/2]: [code-only / additive-migration / risky-migration].
  Tier 0 and Tier 1 are autonomous. Tier 2 halts at the migration boundary.

PRE-FLIGHT (CC runs, decides, proceeds or aborts)
[Concrete commands. Concrete pass/fail thresholds. Abort actions.]
Example:
  - Verify HEAD == <expected SHA>; if not, abort with halt-report.
  - Verify alembic current == <expected revision>; if not, abort.
  - Verify services active; if not, restart once, recheck, abort if still down.
  - Verify disk space > 5GB free; if not, abort.

STAGE 1 — [name]
  Goal: [one sentence]
  Files: [paths CC will touch]
  Steps: [numbered, concrete, command-level]
  Decision tree: [every fork pre-decided]
  Verification gate: [exact commands, exact thresholds, action on fail]
  Commit: [exact commit message format]
  Push: yes/no

STAGE 2 — [name]
  ... same shape

STAGE N — ...

POST-FLIGHT (CC runs after final stage)
  - Re-run pre-flight checks (HEAD now should be the final commit).
  - Run the chain's consolidated verification suite (smoke tests, benchmarks).
  - Write /tmp/chain-report-<chain-name>-<timestamp>.md with:
    * Stage-by-stage outcome (shipped / skipped / halted)
    * Commit SHAs pushed
    * Performance deltas vs baseline
    * Any anomalies observed
    * Recommended next-chain stages

FINAL ACTION (literal, standalone tool call, never chained)
  afplay /System/Library/Sounds/Glass.aiff
```

---

## The stacking heuristic

When chat-Claude sits down to author a chain, the order of operations is:

1. **Identify the lead task** — the highest-priority open item that's ready to ship.
2. **Estimate raw execution time** — be honest. EXPLAIN ANALYZE runs are seconds. Migrations are minutes. Benchmarks are 10s of minutes.
3. **If lead task is < 2 hours:** scan the open-items queue for compatible work. "Compatible" = doesn't touch the same files in conflicting ways, doesn't share a verification surface that would mask failures, isn't gated on the lead task shipping first.
4. **Stack until estimated wall-clock ≥ 2 hours.** Stretch goal is 4–6 hours.
5. **If estimated wall-clock > 8 hours:** split into two chains, second one queued for the next session. Don't author 12-hour chains; the failure surface is too large.
6. **Audit for halt-gate temptation.** Read the draft and find every "verify with Justin" or "halt for review" — most are framework violations. Replace with embedded decision trees. Only Tier 2/3 migration boundaries and genuinely novel findings survive as halts.
7. **Write pre-flight, post-flight, consolidated report spec.** These three are the difference between "Justin gets a chime" and "Justin gets a chime + a clean report."
8. **Read the prompt once as if you were CC.** If any step is ambiguous, fix it. CC will not ask a clarifying question; it will guess, and the guess might be wrong.

---

## Compatible-stacking examples (from the actual queue)

**Lead task: LongMemEval baseline benchmark.**
Compatible adjacent work (touches different files, shares verification harness in a productive way):
- Install synthesis cron units (different surface, verifies cron fires)
- Write VERBATIM-GUARANTEE.md (docs only, zero code conflict)
- Fix T11 contract test hollow-pass (different file, complementary correctness work)
- Fix analytics_events schema-qualifier bug (different file, kills log noise that would pollute LongMemEval logs)
- Fix 1–2 of the 19 `_db_execute + split` call sites (different files, mechanical, ships incremental hardening)

That's six stages, easily 3–4 hours wall-clock, all compatible.

**Lead task: Phase 4B SQL predicate push.**
Compatible adjacent work:
- Push to ≥10s clustering (the original goal, may take 2 attempts)
- Then immediately stack: install cron, T11 fix, analytics-schema fix, two `_db_execute` cleanups, VERBATIM-GUARANTEE.md
- Result: instead of 22 min → chime, 2.5–4 hours → chime with five backlog items closed alongside

Tonight's actual run was the wrong shape. This framework prevents that shape from being authored again.

---

## What changes for chat-Claude (me)

1. **No more single-task chain prompts.** If the lead task is < 2 hours, I stack. If I cannot stack (everything's blocked), I say so explicitly, name what's blocking, and propose the unblocker.
2. **No more pre-flight relay through Justin.** I write the pre-flight into the chain prompt and let CC self-verify. Justin runs pre-flight commands at the *start of a thread* once, to confirm the server context — never as a verification step inside an authoring session.
3. **No more halt gates that aren't Tier 2/3 migrations or novel findings.** Every "let me check with Justin" goes into the prompt as an embedded decision tree.
4. **Scope-doc authoring is the work.** A 6-hour CC run requires a tight, comprehensive prompt. I treat prompt authoring as the actual deliverable; CC execution is the side effect. If the prompt takes me 30 minutes to author, that's correct — it's buying 6 hours of Justin's untouched time.
5. **Consolidated report at the end, not progress pings.** CC produces one report. Justin reads it when he comes back. No mid-chain status updates, ever.

---

## What changes for Justin

1. **Pre-flight at thread start.** One paste, 30 seconds, confirms server state. After that, you don't paste anything until the chime.
2. **Read the chain prompt before launch.** Catch any halt-gate violations or stacking oversights I missed. Push back hard if a chain is < 2 hours of work.
3. **Trust the chime.** When it fires, read the consolidated report at `/tmp/chain-report-*.md`. That's the entire human-in-the-loop step.
4. **Tier 2/3 migrations are the legitimate halt point.** When CC writes a halt-report and fires the chime mid-chain because it hit a migration boundary, that's the protocol working correctly — not a framework failure.

---

## Standing template (paste-ready)

The next chain prompt I author will conform to the anatomy above. The standing template lives at `docs/CC-CHAIN-FRAMEWORK.md` once committed. Future authoring sessions reference it by path; CC reads it as part of its standing rules block.

Concrete commitment: every chain prompt I author from this point on opens with a one-line declaration:

> **This chain conforms to docs/CC-CHAIN-FRAMEWORK.md (vN). Estimated wall-clock: X hours. Stages: N. Tier: 0/1/2.**

If I author a prompt that doesn't open with that line, the prompt is invalid and Justin should reject it without reading further.
