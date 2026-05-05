# CP-SYNTHESIS-PERF — Strategic handoff brief

**Date authored:** 2026-05-05
**Master HEAD at authoring:** `a21f103` (Phase 4 closure)
**Next chain:** Stage 1 (profile), then Stage 2 (optimize, scope authored after Stage 1 ships)

---

## What this chain exists to fix

The synthesis writer takes ~3 minutes per cluster. Concrete number from the CP8 P2 Chain B smoke run on 2026-05-04: **173,958ms wall-clock for ONE cluster** on `user-justin` namespace, producing 1415 Haiku tokens output. Mem0 publishes single-digit seconds for the same kind of operation.

That gap — three minutes vs. seconds — is the wall between us and three things we can't do without closing it:

1. **LongMemEval benchmark** — running the benchmark against a writer that takes 3 minutes per cluster is intractable. The benchmark needs hundreds of writer invocations to produce credible coverage. At 3min/run, that's a multi-day execution. At 5sec/run, it's an hour.
2. **Show HN demo** — a public launch post needs to demonstrate the writer working at speed. Nobody clicks a demo that hangs for 3 minutes; the comments will be about the latency, not the differentiators.
3. **Customer-facing trust** — the writer runs server-side in async jobs, but tenants will see the lag indirectly through "synthesis ready" notifications. A 3-minute lag is acceptable for a one-time backfill; it is not acceptable as a steady-state per-cluster cost as namespaces grow.

This is also the structural blocker for moving into **Phase 5** (operational surface — redaction cascade, webhooks, decision journals, calibration, audit access). Every Phase 5 feature lands on top of the writer. Layering enterprise differentiators on top of a 3-minute write path is the wrong sequencing — it builds the storefront before the kitchen works.

The "what would Mem0 do at this stage" lens points the same direction: a well-funded competitor would close this latency gap before they ship redaction webhooks. We do the same.

---

## Why Phase 5 isn't next

The temptation is to keep building forward. Phase 5 has a clear scope, the schema is in place, and the work is real product surface. It would feel like progress.

But the build-quality bar (8–9 figure platform, never ship fast that breaks) cuts the other way here. Shipping Phase 5 on top of an unviable writer means:

- The Show HN post can't demo the new features — they all run on top of synthesis, and synthesis is too slow to demo.
- LongMemEval still doesn't run.
- Every Phase 5 fix that touches the synthesis path inherits the latency problem instead of being free of it.
- When we eventually do CP-SYNTHESIS-PERF, we have to re-test all of Phase 5 against the new performance profile.

Phase 5 after CP-SYNTHESIS-PERF is structurally cleaner. The writer is fast, the operational surface lands on top, the demo works, the benchmark runs, the launch post writes itself. That's the correct sequence.

---

## Why Stage 1 (profile) before Stage 2 (optimize)

I have hypotheses for what's slow:

- **Re-clustering on every call.** If the writer recomputes cluster membership every invocation instead of caching, that's pure waste.
- **Cold sentence-transformer model load.** If the embedding model loads from disk on every writer call rather than staying warm in process, that's seconds of overhead per run.
- **Sequential DB round-trips.** Synthesis writer touches multiple tables (`memories`, `synthesis_audit_events`, possibly `analytics_events`); if those writes happen serially when they could batch, that's recoverable latency.
- **Haiku call latency.** 1415 tokens at Haiku speed should be under 5 seconds. If the LLM call alone is dominating, the issue is upstream of clustering.

These are guesses. Shipping fixes against guesses produces band-aids — exactly the failure mode you flagged. If we parallelize DB writes and the actual bottleneck is a cold ST model loading on every call, we shipped a 5% improvement and called it a fix. Then six months later, when latency is "still bad," we go back through the same exercise with worse data.

**Stage 1 is instrument and measure.** ~20 minutes of wall clock, code-only, no schema. Output is a profile report — phase-by-phase breakdown of where the 173 seconds actually go. That report tells Stage 2 what to fix.

**Stage 2 is optimize, scoped against Stage 1's actual numbers.** Could be one fix, could be three. Could be 30 minutes of work, could be two hours. We don't pre-commit a Stage 2 scope because we don't have the data to write one yet. Authoring Stage 2 in advance against guesses is the same band-aid pattern at the meta level.

This is the same discipline we used in Phase 4: P4.2 was a focused 16-minute chain because we measured first (Stage 1 diagnosis on the recall-empty bug) before fixing. Stage 1 here is the same posture, applied to performance instead of correctness.

---

## What Stage 1 does mechanically

Single-task autonomy chain on a new branch `cp-synthesis-perf-s1` off `master` at `a21f103`.

1. Read the synthesis writer call graph end-to-end to identify natural phase boundaries (typically: cluster member fetch, embedding lookup, prompt assembly, LLM call, source-quote validation, DB writes).
2. Add lightweight phase-boundary timing instrumentation — non-invasive, structured records, one INFO log line per phase. No behavior change.
3. Write a driver script `scripts/profile_synthesis.py` that runs ONE writer pass against ONE existing user-justin cluster and emits two artifacts: a JSON profile and a Markdown report.
4. Run the profile, verify ≥70% of wall-clock is accounted for in named phases (catches un-instrumented hotspots).
5. CC writes a 3–6 sentence interpretation paragraph at the bottom of the MD report — names the dominant phase, names the runner-up, lists 2–3 hypotheses for Stage 2 to test.
6. Commit on branch, push, **do NOT merge.** Stage 2 builds on this branch.

Estimated wall clock: 15–25 min. No schema changes. No optimization. Pure measurement.

---

## What success looks like

After Stage 1 ships, we have:

- A repeatable profile harness — anyone can run `python3 scripts/profile_synthesis.py` and get a fresh report. Stage 2 uses this as its before/after diff. Future regressions can be caught the same way.
- A concrete, numeric understanding of where the 3 minutes go. Not "I think it's clustering" — "clustering is 47% of total, LLM call is 31%, DB writes are 18%, everything else is 4%." (Numbers fictional; actuals come from the report.)
- A short list of falsifiable hypotheses for Stage 2 to act on.
- Phase 5 is unblocked-pending-Stage-2. The scope of Stage 2 is now writable.

After Stage 2 ships, we have:

- Single-digit-second writer latency, or close enough that LongMemEval and Show HN are viable.
- Performance regression test in the test suite (the profile run, gated to flag if any phase exceeds a baseline by >2x).
- Phase 5 starts on solid ground.

---

## What Stage 1 explicitly does NOT do

- No optimization. If CC sees an obvious fix (a missing cache, a redundant call), it documents it in the report and does NOT apply it. Stage 2 is where fixes land — under their own scope, with measurement before and after.
- No schema changes. Pure code instrumentation.
- No changes to the writer's external contract. Same inputs, same outputs, same error behavior. Just observable from the inside.
- No changes to recall, the API surface, or the MCP server. Synthesis writer subsystem only.
- No merge to master in Stage 1. The branch is held until Stage 2 lands so the optimization work has a clean diff target.

---

## Carry-list state (what's NOT in this chain)

For reference — these are tracked but not addressed in CP-SYNTHESIS-PERF:

- **`expand=cluster` endpoint on `/memories/{id}/source`** — never implemented in P4.1. 30-min focused chain candidate, post-Phase-5.
- **`error_logs` schema bug** — 1 occurrence/hour, not blocking. Same fix class as `analytics_events` from B-5.
- **6 remaining `_db_execute + split` sites** in `src/recall.py` — rolling cleanup, 1–2 per chain.
- **MCP server `memory_synthesize` tool** — not yet shipped to npm. Lands when synthesis writer is fast enough to expose to MCP clients (i.e., post-CP-SYNTHESIS-PERF).
- **mcp.0latency.ai/authorize page UI polish** — not blocking.
- **VERBATIM-GUARANTEE.md verification** — confirm still accurate post-Phase-4.

None of these are blocking CP-SYNTHESIS-PERF or Phase 5. They're the rolling cleanup queue.

---

## Resumption prompt for next thread

```
Picking up 0Latency. Master at a21f103 (Phase 4 closed). Next chain is
CP-SYNTHESIS-PERF Stage 1 — profile the synthesis writer (currently
~3min/cluster, blocking LongMemEval + Show HN + Phase 5).

Stage 1 is profile-only: instrument writer + clustering with phase-
boundary timing, write a driver script that runs ONE writer pass on a
real user-justin cluster, emit a JSON+MD profile report. No optimization
in Stage 1. Stage 2 authored after Stage 1 ships.

Scope doc lives at /root/.openclaw/workspace/memory-product/docs/
CP-SYNTHESIS-PERF-S1-AUTONOMY-SCOPE.md (or in /mnt/user-data/outputs/
locally before SCP).

Branch: cp-synthesis-perf-s1 off master. DO NOT MERGE in Stage 1 —
branch held until Stage 2 lands.

Standing rules carry forward verbatim. Target 15-25 min wall clock.
Single CC chain.
```
