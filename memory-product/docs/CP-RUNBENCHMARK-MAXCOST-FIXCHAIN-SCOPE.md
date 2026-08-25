# CP-RUNBENCHMARK-MAXCOST-FIXCHAIN-SCOPE — Locked CC Scope

> **PHANTOM-COMMIT WARNING.** This document anchors to commit `f893c18`, the integration it replicates. It was discarded on
> 2026-05-22 by a `reset: moving to origin/master` on the workspace box: the commit
> was local-only, never pushed, and the reset moved HEAD onto `e50694d` from
> another machine. It is reachable by hash but contained by no branch, so the
> code this document describes was never in `master`.
> This document survived only because it was untracked, and `git reset` does not
> touch untracked files.
>
> **Therefore unverified:** the "ALREADY-PROVEN integration" it builds on is not in `master` — `f893c18` was
> discarded, and `benchmarks/longmemeval/cost_killswitch.py` does not exist in the tree.
> The chain's output commit `2e544f4` was discarded with it, so `run_benchmark.py` in
> `master` has no `--max-cost` flag and no runtime spend ceiling.
>
> The body below is preserved verbatim and has not been corrected. See
> `docs/RECENCY-WEIGHTING-ANALYSIS.md` §7 for the full reconstruction.

**Type:** Minimal integration fix chain. Replicate an ALREADY-PROVEN integration into a second runner. NOT a new build, NOT a redesign, NOT a port.
**Authored:** 2026-05-18 (lead engineer, pre-dispatch, adversarially self-reviewed)
**Mandate source:** Resolution of the n=25 pre-flight HALT (runner/scorer/`--max-cost` conflict). Banked-provenance investigation (git history: commit `600f7ee` lineage) established the banked 76%@20 was produced by `run_benchmark.py --scorer llm` (Sonnet judge). The cost brake (`--max-cost`) is non-negotiable (the $400+/$603 unbraked-spend incident). Both are simultaneously satisfiable ONLY if `run_benchmark.py` gains `--max-cost`. This chain does exactly that and nothing else.
**Estimate:** Low complexity. This is the SAME 2-hook integration that commit `f893c18` already performed on `run_q3_async.py`, applied to `run_benchmark.py`, reusing the existing `cost_killswitch.py` module unchanged. The pattern is proven and trip-tested once already; this is its second instance. Operator attention concentrates in the non-contamination proof and the trip-test, not in writing code. Stated as relative complexity, not wall-clock, per standing rule.

---

## WHY THIS CHAIN EXISTS — read before doing anything

The n=25 measurement run HALTed correctly at pre-flight on three conditions. Two are resolved (disk cleared; banked provenance = `run_benchmark.py --scorer llm` per git history). The third is structural: **the scope-mandated `--max-cost` brake and the bank-matched `--scorer llm` requirement cannot both be satisfied on the current code**, because:

- `run_benchmark.py` HAS `--scorer llm` (the bank's scorer) but NO `--max-cost`.
- `run_q3_async.py` HAS `--max-cost` (via the `f893c18` kill-switch integration) but NO LLM judge.

Running n=25 on `run_q3_async.py` with fuzzy scoring would produce a number measured by a different ruler than the banked 76%@20 — the exact scorer-mismatch trap the n=25 scope was built to prevent. That path is dead. The only non-self-defeating path is to give `run_benchmark.py` the `--max-cost` brake, so the n=25 runs on the bank-matched scorer WITH the cost control intact.

**The control already exists and is proven.** `cost_killswitch.py` is a clean, standalone, runner-agnostic module (`preflight_estimate(...)` + thread-safe `CostAccumulator`). Commit `f893c18` already integrated it into `run_q3_async.py` with a documented, trip-tested 2-hook pattern that is bit-identical to `0ceb578` when the switch does not trip. **This chain replicates that exact integration into `run_benchmark.py`.** It does not invent a new control. It does not modify the proven module. It applies a known-good pattern a second time.

---

## SCOPE LOCK — hard boundaries, violating any invalidates the chain

1. **`cost_killswitch.py` is NOT modified.** It is imported and used exactly as `run_q3_async.py` uses it. If you believe the module needs a change to integrate into `run_benchmark.py`, that is a HALT-and-report — do not modify the proven safety module inside this chain. The module is runner-agnostic by design; if it isn't, that is a finding, not a fix.
2. **ONLY `run_benchmark.py` is modified.** No ranker, no extraction code, no prompt content, no scoring/judge logic, no payload construction, no recall path, no corpus, no migration, no `.env`, no systemd. The diff is `run_benchmark.py` plus (if argparse requires) nothing else. A diff that touches any scoring/recall/prompt/extraction file is an automatic invalidation.
3. **2-hook pattern, mirrored from `f893c18`, no more.** Hook A: pre-flight cost gate after dataset load, before any API call (`preflight_estimate`, hard exit if projected > `--max-cost`). Hook B: accumulate + breach-check at the submission chokepoint. `run_benchmark.py`'s chokepoint is `submit_extraction_job` (line ~149) for extraction tokens; the LLM judge call (line ~367) is a SECOND cost-bearing path that `run_q3_async.py` does not have. Account for BOTH token streams in the accumulator (extraction + judge) — under-counting the judge path is a cost-control hole of the exact class the $603 incident exposed. If non-bypassable coverage genuinely requires more than these hook points because of the judge path, add the MINIMUM extra and justify each in the log. Document every hook and why the set is non-bypassable (no API path that skips an accumulator update).
4. **Non-contamination is mandatory and must be PROVEN, not asserted.** When `--max-cost` is not breached, `run_benchmark.py` behavior must be bit-identical to its pre-change behavior (and therefore to the `0ceb578` banked-scorer path). Static diff review + explicit written argument for why scoring/recall/prompt/judge output is unchanged when the switch does not trip. This is the single highest-risk property: a cost hook that perturbs the judged result silently corrupts the sacred number. Treat it with that weight.
5. **`--max-cost` default and ceiling.** Add `--max-cost` to argparse. The n=25 will pass `--max-cost 3`. Do not hardcode 3; make it the passed argument exactly as `run_q3_async.py` does. Default may match `run_q3_async.py`'s default for consistency. Never wire it so a higher value bypasses the accumulator.
6. **Attributed commit, no banked-branch contamination.** Commit to `master` only, attributed, message referencing the n=25 HALT resolution and `f893c18` as the pattern source. `origin/master` `0ceb578` (banked 76%@20) is NEVER touched. No `--max-cost` value, no run, no n=25 inside this chain — this chain ends at a committed, trip-tested integration. The measurement is a separate dedicated session.
7. **Trip-test REQUIRED before declaring done.** Mirror the `f893c18` test plan. Must demonstrate BOTH, with pasted output: (a) pre-flight refusal — projected > `--max-cost` → hard exit, zero API calls made; (b) runtime abort — cumulative cost crosses `--max-cost` mid-run → clean shutdown, no orphaned workers, queue clean. Use the smallest real-or-mocked run that proves firing; if a real call is needed, cap `--max-cost` low enough that total spend is under $0.50 and confirm actual spend after. A kill-switch that has not been observed to fire is indistinguishable from no kill-switch — the documented failure pattern of accepting an unverified "it works" under pressure is in force here specifically.

---

## METHOD (locked sequence)

### Step 1 — Orient (read-only)
- Server `root@164.90.156.169`, workspace `/root/.openclaw/workspace/memory-product`. Branch `master`.
- Read `cost_killswitch.py` in full (the module — unchanged, ~6KB, public surface: `preflight_estimate`, `CostAccumulator`).
- Read `run_q3_async.py`'s `f893c18` integration (the 61-line, 2-hook diff: `git show f893c18 -- benchmarks/longmemeval/run_q3_async.py`). This is the EXACT pattern to mirror. Study how it wires preflight + accumulator + abort.
- Read `run_benchmark.py`: argparse block (~555–567), `submit_extraction_job` (~149), `extract_single_session` token accrual (~237), `llm_judge` token accrual (~367), the cost-projection block (~384–403). Identify the extraction chokepoint AND the judge chokepoint. Both bear cost; both must feed the accumulator.
- Echo the resolved chokepoint line numbers and the planned hook set BEFORE writing any code.

### Step 2 — Replicate the 2-hook integration
- Import `cost_killswitch` into `run_benchmark.py` exactly as `run_q3_async.py` does.
- Add `--max-cost` to argparse (mirror `run_q3_async.py`'s arg definition).
- Hook A: `preflight_estimate(...)` after dataset load, before first API call. Hard exit on projected > `--max-cost`.
- Hook B: instantiate `CostAccumulator(max_cost, model)`; call `.add(input_tokens, output_tokens)` at the extraction submission chokepoint AND at the judge call return (both token streams). Clean abort the moment `.add` signals breach. No orphaned workers on abort.
- Match `run_q3_async.py`'s abort semantics (clean shutdown, worker drain, exit code).

### Step 3 — Non-contamination proof
- Static diff: `git diff` the full change. Confirm zero edits to scoring/recall/prompt/judge-logic/extraction/payload.
- Written argument: explicitly why, when `--max-cost` is NOT breached, every judged result and recall is bit-identical to pre-change. The accumulator observes tokens; it must not alter prompt, payload, scoring threshold, or judge decision.
- This is the gate. If non-contamination cannot be cleanly argued, HALT — do not commit a cost hook that might move the number.

### Step 4 — Trip-test (prove it fires)
- (a) Pre-flight refusal test: set `--max-cost` below projected → must hard-exit with zero API calls. Paste output.
- (b) Runtime abort test: set `--max-cost` low enough to trip mid-run on a tiny run (real spend < $0.50, or mocked) → must clean-abort, no orphaned workers, queue == 0. Paste output + confirmed actual spend.
- Confirm post-test: `pgrep` shows no orphaned workers, `rq:queue:extraction == 0`, no systemd unit auto-started.

### Step 5 — Commit
- Commit to `master`, attributed, message references the n=25 HALT resolution and `f893c18` as pattern source. Do NOT commit `.env`. Echo the commit hash. Do NOT run n=25. Do NOT launch any benchmark.

### Step 6 — Resolve the two open provenance items (read-only, for the n=25 that follows)
These are not fixes; they are confirmations the next n=25 needs and currently lacks. Read-only, report values:
- **Banked extraction model.** From the banked-run artifacts / result reports for `0ceb578` (search `docs/`, results files, prior result reports), confirm the banked 76%@20 was produced with extraction model = `claude-haiku-4-5-20251001`. The May-17 thread flagged this as never-closed and "non-negotiable before we trust the number." If artifacts confirm Haiku → the n=25 compares like-for-like. If artifacts confirm Sonnet, or cannot confirm → REPORT that explicitly; the n=25 then re-establishes the floor rather than comparing to it. Do not assume.
- **Banked corpus row count.** From the banked-run artifacts, find the recorded corpus/tenant row count at `0ceb578`. The benchmark tenant currently has ~16,500 rows. Report the banked baseline if recorded; if not recorded anywhere, report that it is unrecorded (a known limitation the n=25 pre-flight must treat as a confirmation gap, not a silent pass).

### Step 7 — Deliverable
Single file on-server: `/root/.openclaw/workspace/memory-product/docs/RUNBENCHMARK-MAXCOST-FIXCHAIN-RESULTS.md`, AND `cat` it back into the CC session. Sections:
1. Resolved chokepoint line numbers + the hook set + why non-bypassable (both token streams covered).
2. Full `git diff` of the change, pasted verbatim.
3. Non-contamination proof — static-diff confirmation + the written bit-identical argument.
4. Trip-test results — both modes, pasted output, confirmed actual spend on the runtime test.
5. Post-test clean-state confirmation (pgrep / queue / systemd).
6. Commit hash + attributed message.
7. Provenance findings — banked extraction model (Haiku/Sonnet/unconfirmed, with the artifact cited) and banked corpus row count (value or unrecorded).
8. Any bugs observed but NOT fixed — explicitly logged, not actioned. The 31 python3 coredumps cleared from `/var/lib/coredumps/` (May 16–18, most recent ~hours before this chain) indicate a recent python3 crash-loop on this box; log it as an open diagnostic item for a separate chain. Fix-stacking ban in force.

---

## RUN DISCIPLINE

- **Retry ceiling: 2.** Two failures for any reason → STOP, write `RUNBENCHMARK-MAXCOST-ROOT-CAUSE.md` + post it, do not attempt a third. Symptom-patching does not reset the counter.
- **Non-contamination is the tripwire.** If the static diff or the written argument cannot cleanly establish bit-identical-when-not-tripped, HALT and surface — do not commit on "probably fine."
- **Trip-test is non-optional.** No "the switch is built" without both fire-modes observed in pasted output. Agent self-report is not the verdict; the pasted trip-test output is.
- **Time-box:** this mirrors a 61-line proven diff. If heads-down materially past "mirror a known 2-hook integration + prove non-contamination + trip-test," post a status report rather than going silent. "I don't know why this is slow" is a valid report.
- **Receipts standard:** the integration is valid only backed by pasted `git diff` + pasted trip-test output (both modes) + pasted clean-state. No narrative self-report accepted.

## OPERATIONAL CONSTRAINTS CARRIED INTO CC
- `python3` not `python`; `_db_execute_rows` not legacy stringify+split.
- Never print the API key, `.env`, or any credential. Tenant *name* only if needed.
- Do not touch systemd, workers' env, or `.env`.
- Branch `master`. One attributed commit (the integration). `origin/master 0ceb578` untouched. No n=25, no benchmark run, no `--max-cost` execution beyond the sub-$0.50 trip-test.
- Single CC session, cost-braked. Dedicated chain — no other work interleaved.
