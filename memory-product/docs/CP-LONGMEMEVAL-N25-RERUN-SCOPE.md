# CP-LONGMEMEVAL-N25-RERUN-SCOPE — Locked CC Scope

> **PHANTOM-COMMIT WARNING.** This document anchors to commits `243309e` (Q21) and `9333c04` (Q22). Both were discarded on
> 2026-05-22 by a `reset: moving to origin/master` on the workspace box: the commits
> were local-only, never pushed, and the reset moved HEAD onto `e50694d` from
> another machine. They are reachable by hash but contained by no branch, so the
> code this document describes was never in `master`.
> This document survived only because it was untracked, and `git reset` does not
> touch untracked files.
>
> **Therefore unverified:** its statement that Q21 and Q22 are "shipped, verified, live" is false — neither
> reached `master`. Its pre-flight instruction to confirm `git rev-parse HEAD` = `9333c04`
> cannot succeed on `master`. The banked 76%@20 / MRR 0.5366 / precision 0.9851 figures
> it cites are attributed to `0ceb578`, which IS in `master`, so those specific numbers
> are unaffected. Q22 was re-applied to `master` on 2026-08-25 as `8d8785c`.
>
> **Q21 (`243309e`) is CLOSED — do not recover it.** Its purpose was to let the
> LongMemEval harness anchor relative-date resolution to the story timeline instead of
> wall-clock now, via a `today_date` override threaded from the ingest request into
> extraction. `master` already does exactly that under a different name: `e50694d`
> introduced `session_timestamp`, which is exposed on the ingest request
> (`api/main.py`), threaded through `api/extraction_worker.py` into
> `extract_memories()`, and used to derive `conversation_date` (`src/extraction.py`).
> The harness already forwards it — `benchmarks/longmemeval/run_benchmark.py` sets
> `payload["session_timestamp"] = session_date`. Cherry-picking `243309e` would add a
> redundant second date-override path beside the working one. Assessed 2026-08-25.
>
> This also explains the future-dated `event_at` rows in the benchmark namespace: they
> were written 2026-05-21, one day before `e50694d` landed, so they predate the anchor
> rather than demonstrating its absence.
>
> The body below is preserved verbatim and has not been corrected. See
> `docs/RECENCY-WEIGHTING-ANALYSIS.md` §7 for the full reconstruction.

**Type:** Measurement run. NOT a fix chain. No code changes, no migrations, no ranker edits, no re-ingestion.
**Authored:** 2026-05-18 (lead engineer, pre-dispatch, adversarially self-reviewed)
**Mandate source:** `HANDOFF-2026-05-18-LONGMEMEVAL-PAUSED-Q21-Q22-CLOSED.md` RESUME POINT (lines 56–65) + `RUN-DISCIPLINE-BLOCK.md`.
**Gate cleared:** Verbatim Phase 0 verdict = **Shape C (capture-gap)**. There is NO Phase 1 ingestion rebuild. Storage/extraction path is correct and unchanged. The LongMemEval resume precondition ("confirm Phase 1 has landed / ingestion path settled") is satisfied: the path n=25 runs against was never the defect.
**Deliverable:** A written results report with the standard metric set, pasted real runner output (never summarized), and an explicit regression-tripwire pass/fail against the banked 76%@20.
**Estimate:** Low complexity. One n=25 stratified pass against the frozen corpus plus LLM-judge scoring of the ~25 stratified questions — no re-ingestion, no code changes, no fix work. Roughly the run-leg of a single prior n=25 thread minus all build/fix work. The run itself is short; operator attention concentrates in the pre-flight gate and the Step 4 cross-check, not the pass. Stated as relative complexity, not wall-clock, per standing rule.

---

## SCOPE LOCK — read before doing anything

This run produces the decision-driving number that feeds the investor narrative, the Luke/Stripe framing, and the go/no-go on CP9.3-and-beyond. The single largest documented process failure on this project was repeatedly trusting a flawed verification instrument (the key/sha saga: the thing doing the checking was broken, so every check lied, across multiple sessions). **The benchmark harness is an instrument. If it is misconfigured — wrong flag state, stale shell env, wrong tenant key, wrong corpus, scorer error — it will produce a plausible-but-wrong number that looks exactly like a real one.** Every rule below exists to make that specific failure impossible, not unlikely.

**Hard boundaries — violating any of these invalidates the run:**

1. **No code changes. No fixes. No migrations. No ranker edits.** This is a measurement of the live code at `master` HEAD `9333c04` exactly as it is in production. If you find a bug mid-run, DO NOT fix it — record it and report it; fixing it inside a benchmark chain is the banned fix-stacking pattern and contaminates the number.
2. **No re-ingestion. The corpus is correct and frozen.** The handoff is explicit: "do NOT re-ingest without an explicit reason — the corpus is correct." Re-ingesting changes what's being measured. If the corpus appears wrong, that is a HALT-and-report condition, not a re-ingest condition.
3. **`RECENCY_CLAMP_ENABLED` flag ON (default true).** This is the production state. The run measures production. Echo the resolved flag value in pre-flight — do not assume the default; read it from the actual environment the API process sees.
4. **Key / .env / systemd permanently OUT of scope.** Do not rotate, regenerate, or modify the key, `.env`, or systemd units. You will READ the resolved tenant *name* the key maps to for the pre-flight gate (never print the key itself). Funded org key, $50 ceiling, single permanent key — all resolved history, do not relitigate.
5. **Standard metric set, never a lone ceiling number.** Report Recall@1 / @5 / @10 / @20 / @50 + MRR + precision. The handoff is emphatic (lines 62, 71): a single arbitrary ceiling number is non-defensible for field comparison vs Mem0/MemX/Memoria. The headline comparison point is Recall@20 vs the banked 76% and vs Mem0's published ~66%, but the full set must be reported or the number is not investor/field defensible.
6. **`--max-cost 3` is MANDATORY on the runner invocation. No run launches without it. Never raise it above 3.** This is the structural control that closed the single most expensive failure on this project (the unbraked-spend incident — $400+/$603 against a configured limit, auto-reload silently refilling with no brake). Every prior n=25 launch sequence carries this rule verbatim: a kill-switch-capped run is the *only* thing that makes an unattended benchmark run safe — not vigilance, not a watched terminal. The cap is a tested, hard-bounded code path: worst case is $3, physically impossible to exceed. If the runner does not support `--max-cost`, that is a HALT condition — do NOT launch an uncapped run "just this once." Echo the resolved `--max-cost` value in the pre-flight block alongside every other resolved precondition. An uncapped launch invalidates the run regardless of the number it produces, because an uncapped launch is the exact failure pattern the entire cost saga existed to make impossible.

---

## CONTEXT (what this run answers)

Q21 (harness date-anchoring, commit `243309e`) and Q22 (systemic ranker recency clamp, commit `9333c04`) are shipped, verified, live. These were the two open temporal-reasoning failures. The banked launch floor is **76%@20, MRR 0.5366, precision 0.9851** (`origin/master` HEAD `0ceb578`, untouched).

The question this run answers, and only this: **with Q21+Q22 live (flag ON), does a fresh n=25 stratified re-run beat, hold, or regress against the banked 76%@20 / 0.9851 precision?**

- Beats 76% clean → bank as new candidate headline.
- Flat / within noise → ship 76% as-is; Q21+Q22 are correctness improvements that don't move the headline. **The launch is never blocked — 76%@20 already beats Mem0's published ~66%.**
- Regresses below 76%@20 OR below 0.9851 precision → that is a tripwire breach: STOP, do not bank, write a ROOT-CAUSE block, surface immediately. A regression means Q21/Q22 perturbed the banked answers and the handoff's "76% is sacrosanct" rule is in force.

This run is the closest thing on the board to external, adversarial evidence that does not require a customer. It is treated with that weight.

---

## RUN DISCIPLINE — copy-verbatim block (per RUN-DISCIPLINE-BLOCK.md)

### 1. Retry ceiling: 2

If the run fails **twice for any reason** — same cause or different — do **not** attempt a third. Stop. Write a `ROOT-CAUSE` block and surface it before doing anything else. Symptom-patching (raising a timeout, draining a queue, restarting the service, swapping a key) does NOT reset the counter — a patched relaunch that fails is failure #3 and #3 is not allowed. "Different failure each time" means the problem is upstream of the launch (environment/preconditions/sequencing) — diagnose upstream, do not keep launching.

ROOT-CAUSE block format (write to chat AND to `LONGMEMEVAL-N25-ROOT-CAUSE.md` in workspace root):
```
ROOT-CAUSE — LONGMEMEVAL-N25
Attempts: N
Failure 1: <exact error/symptom>
Failure 2: <exact error/symptom>
Common upstream cause: <the one thing underneath both>
Structural fix: <what makes this class impossible, not just unlikely>
Patches already applied (and why insufficient): <list>
Recommended next action: <fix then ONE clean launch — or escalate>
```

### 2. Time-box: report at 1.5x estimate

This run's estimate: **low complexity — one n=25 stratified pass + LLM-judge scoring of ~25 questions, no re-ingestion, no fix work**. If still running materially past one clean pass + scoring (the 1.5x equivalent for this shape — i.e. heads-down with the pass not converging or the scorer not completing), STOP and post a status report (where it is, what it's waiting on, what looks wrong, honest revised estimate) before continuing. Do not go heads-down past 1.5x. "I don't know why this is slow" is itself a valid report — say it.

### 3. Pre-flight gate: verify and echo every precondition before launch

Before launch, verify EACH precondition and echo the RESOLVED VALUE (the actual value, not "looks fine"). Any check fails → halt and report. Do not launch on assumption. Echo all of these in one pre-flight summary block, then launch:

- **Correct service is live.** Service name + PID + uptime of whatever is bound to port 8420. Must be the intended `zerolatency-api`, single process, no orphan/duplicate unit (the handoff State Block asserts this — prove it still holds).
- **Code is at expected HEAD.** Echo `git rev-parse HEAD` in the workspace = `9333c04`. Echo the start-time/commit the running API process is actually serving (not just the git checkout — the loaded process). Stale process serving old code = HALT.
- **Flag state resolved.** Echo the value of `RECENCY_CLAMP_ENABLED` as the running API process sees it. Must be ON/true. Not "default is true" — the resolved value.
- **Key resolves to EXPECTED tenant by name.** Echo the resolved tenant *name* the live key maps to (never the key). Must match the benchmark's intended tenant. Wrong tenant = the entire run is meaningless (this is a direct key/sha-saga-class trap).
- **Queue empty.** Echo WIP / failed / deferred counts. Non-zero = investigate before launch, do NOT blind-drain (draining orphans in-flight jobs).
- **Disk healthy.** Echo `df -h` for the workspace mount. >80% = halt.
- **Corpus / target data state.** Echo the row count on the target tenant/table for the benchmark corpus. It MUST match the expected base from the prior banked run. A changed corpus = measuring a different thing = HALT. This is the "corpus is correct, do not re-ingest" rule made into a pre-flight check.
- **Shell env freshness (key/sha-saga-specific).** Immediately before invoking the runner, in the SAME shell: `set -a && source .env && set +a` (per handoff line 73). Echo that this was done in the same shell as the runner invocation. A stale shell env reading an old key/tenant is the exact multi-thread saga failure — this check exists specifically to kill it.
- **Cost cap present and resolved (cost-saga-specific).** Echo the literal `--max-cost` value that will be on the runner invocation. It MUST be present and MUST be `3` (never higher). Echo the runner's own help/flag output proving `--max-cost` is a supported flag the runner actually honors — not assumed. If `--max-cost` is absent from the invocation OR the runner does not support it, that is a HALT, not a launch-anyway. This is the single control that closed the most expensive failure on this project; an uncapped launch is the exact failure pattern the cost saga existed to make impossible.
- **Extraction / scorer model resolved and bank-matched (scorer-mismatch class).** Echo the resolved extraction model the running API process uses (`.env` carries `EXTRACTION_MODEL` — read the resolved value, do not assume) AND the scorer model the runner will use. BOTH must match what the banked `0ceb578` 76%@20 run used. A different extraction or scorer model makes the number non-comparable to the bank — same HALT class as the corpus-drift and scorer-mismatch traps. If the banked run's models cannot be confirmed from the banked-run artifacts, that is a HALT-and-report, not a launch-on-assumption.

---

## METHOD (locked sequence)

### Step 1 — Orient (read-only)

- Server `root@164.90.156.169`, workspace `/root/.openclaw/workspace/memory-product`.
- Identify the n=25 stratified runner: the exact script/command, the stratified-25 question set definition, the scorer (the handoff references an LLM judge `--scorer llm` using Sonnet — confirm which scorer the banked 76% used and use the SAME one; a different scorer makes the number non-comparable to the bank).
- Locate the banked-run artifacts for comparison: `origin/master` `0ceb578` banked 76%@20 / MRR 0.5366 / precision 0.9851, and the prior result report(s). The new run is compared against these exact numbers.
- Echo the resolved runner command and scorer choice in the deliverable BEFORE running. Scorer mismatch vs the bank is a HALT condition.

### Step 2 — Pre-flight gate

Execute the full pre-flight block above. One summary block, every value resolved and echoed. Any failure → halt + report, do not launch.

### Step 3 — ONE clean n=25 run

- Single n=25 stratified run, flag ON, same harness, same corpus, same scorer as the bank.
- **`--max-cost 3` on the invocation, verbatim. The pre-flight cost-cap echo and this launch flag must be the same value. If the runner aborts on the cost cap, that is a correct safe stop — report it as a cost-cap halt with the spend at abort, do NOT relaunch with a higher cap (raising the cap is the banned cost-saga failure pattern; a cap-triggered abort is a finding, not a retry trigger).**
- No fixes, no re-ingestion, no parameter changes between pre-flight and launch.
- Capture the FULL runner output (stdout/results file) — this is pasted into the deliverable verbatim, not summarized.

### Step 4 — Cross-check the number (instrument-can-be-the-bug rule)

The handoff (line 73): "re-run once if a number looks suspiciously identical or off." Apply it:
- If the new Recall@20 is **bit-identical** to the banked 19/25, that is plausible (Q22 shipped *because* it held bit-identical on the banked-25 — see handoff line 24) BUT verify it's identical for the right reason: spot-check 3 individual question results against the banked per-question ranks, not just the aggregate. Identical aggregate with different per-question ranks = a masking bug, not a clean hold.
- If the number is materially different (better OR worse) than expected, do ONE confirmatory re-run before trusting it. A single surprising number from a known-fragile instrument is a hypothesis, not a result.
- Document the cross-check explicitly: what was expected, what was got, whether a confirmatory re-run was done, and the per-question spot-check.

### Step 5 — Tripwire evaluation

- Recall@20 ≥ 76% AND precision ≥ 0.9851 → PASS. Report the full metric set, state whether it beats/holds the bank, recommend bank-as-new-candidate (if clean beat) or ship-76%-as-is (if flat/within noise).
- Recall@20 < 76% OR precision < 0.9851 → TRIPWIRE BREACH. Do NOT bank. Write the ROOT-CAUSE block. The handoff's "76% is sacrosanct, perturbation = revert + handoff" rule is in force — surface for human decision, do not attempt remediation inside this chain.

---

## DELIVERABLE

Single file on-server: `/root/.openclaw/workspace/memory-product/docs/LONGMEMEVAL-N25-RERUN-RESULTS.md`, AND `cat` the full contents back into the CC session. Sections:

1. **Pre-flight summary block** — every precondition with its resolved value, as echoed before launch.
2. **Runner invocation** — exact command + scorer, with the scorer-matches-bank confirmation.
3. **Raw runner output** — pasted verbatim (the results file / stdout), not summarized. This is the receipt.
4. **Standard metric set** — Recall@1/@5/@10/@20/@50 + MRR + precision, in a table, next to the banked baseline (76%@20 / MRR 0.5366 / precision 0.9851) for direct comparison.
5. **Cross-check** — expected vs got, per-question spot-check (3 questions vs banked ranks), whether a confirmatory re-run was done and its result.
6. **Tripwire verdict** — PASS or BREACH, one bolded sentence, then the evidence.
7. **Recommendation** — one paragraph: bank-as-new-candidate / ship-76%-as-is / tripwire-breach-escalate. No next-phase scoping in this doc — that is downstream.
8. **Any bugs observed but NOT fixed** — logged for backlog, explicitly not actioned (fix-stacking ban).

**Receipts standard:** the number is only valid backed by pasted raw runner output. "The run scored X" in prose is not a receipt. Per-question results pasted, scorer named, flag/tenant/corpus/HEAD all echoed-resolved in pre-flight. No agent self-report ("the run passed") accepted as the verdict — the verdict is the pasted output and the tripwire arithmetic on it. If any step cannot complete, say so and state the impact on number confidence — a partial honest result beats a confident wrong number.

---

## OPERATIONAL CONSTRAINTS CARRIED INTO CC

- `python3` not `python`; `_db_execute_rows` not legacy stringify+split.
- Read-only DB except none — this run does not write to the DB at all (no ingestion). Runner may write its own results artifacts; that is expected.
- Never print the API key, `.env`, or any credential. Tenant *name* only, for the pre-flight tenant check.
- Do not touch systemd, workers' env, or `.env` contents. Pre-flight echoes resolved values; it does not modify them.
- Branch `master` HEAD `9333c04`. No commits — this run produces a results doc, not a code change. The results doc may be added; no source/migration/ranker changes of any kind.
- Single CC session, cost-braked per chain. This is a dedicated benchmark session — no other work interleaved (handoff line 75: "no n=25/n=500 inside a fix chain; full benchmark runs are their own dedicated, cost-braked sessions").
