# HANDOFF — CP-SYNTHESIS-PERF closure → Phase 5 kickoff

**Date:** 2026-05-05
**Thread state at handoff:** CP-SYNTHESIS-PERF fully shipped. CP8 Phase 4 + perf chain both closed.
**Master HEAD at handoff:** post Stage 2.B merge + STATE-LOG entry (CC merged + cleaned up; SSH `git log master --oneline -5` will show exact SHA).

---

## What the next thread does first

Read this doc end-to-end. Then either:

**Path A (recommended) — author Phase 5 Stage 1 scope.** Phase 5 is the operational surface (redaction cascade, webhooks, decision journals, confidence calibration, audit access, tier-gating polish, pattern memory). It's a multi-stage chain — the next thread's first concrete task is to break it into autonomy-sized chunks and ship the first one.

**Path B — quick wins first.** A handful of small carry-forward items (listed below) could ship as a single ~30-min cleanup chain before Phase 5 starts, so the codebase is fully tidy when the bigger work begins. Operator's call. Default is Path A.

Either way: **do not start with implementation.** Start with reading STATE-LOG.md and the docs/profile/ folder so the new thread understands the writer's current performance characteristics before designing anything that runs on top of it.

---

## What just shipped this thread

### CP8 Phase 4 — FULLY CLOSED

| Sub-chain | Result | Headline |
|---|---|---|
| P4.1 | ✅ Merged 220d95a | Synthesis-aware recall, audit-aware reads, cluster_id staging-validated |
| P4.2 | ✅ Merged via edc8574 | Cross-agent synthesis in recall CTEs (synthesis bypasses agent_id filter) |
| P4.2-PATCH | ✅ Merged via edc8574 | Audit-emission key fix (src/recall.py:786 + :1190 — "type" → "memory_type") |
| P4.1 S03 prod backfill | ✅ Applied | 42 rows backfilled cluster_id (1 correctly skipped) |

Branches `p4-2-fix` and `p4-2-investigation` deleted local + origin.

### CP-SYNTHESIS-PERF — FULLY CLOSED

A focused performance chain that sat between Phase 4 and Phase 5. Three sequential CC chains, all on branch `cp-synthesis-perf-s1`:

| Stage | Wall-clock | Result |
|---|---|---|
| Stage 1 — Profile | ~15 min | Phase-boundary timing. Embedding identified as 72% of cost (12,585ms / 17,457ms total) |
| Stage 2.A — Diagnosis | ~5 min | Confirmed cold-load only; LLM/tier-gating cleared (Sonnet on Enterprise = spec) |
| Stage 2.B — Fix + merge | ~12 min | Preload via FastAPI lifespan + warmup; embedding 12,585ms → 311ms (40.5x); wall-clock 17,457ms → 5,899ms (3.0x) |

Branch `cp-synthesis-perf-s1` merged to master and deleted.

**Validation cluster:** `b28b7a99fd4791cb` on user-justin (21 members) — keep this cluster_id around for future regression-checks against the writer.

### Files that landed

- `src/synthesis/profiler.py` — phase-boundary timing harness (non-invasive log capture).
- `src/synthesis/writer.py`, `src/synthesis/clustering.py` — instrumented with timing markers.
- `src/storage_multitenant.py::_get_local_model()` — added warmup inference; SentenceTransformer is now preloaded with a `model.encode(["warmup"])` call at first instantiation.
- `api/main.py` — FastAPI startup event preloads the embedder. Cost: ~20s added to memory-api boot, paid once.
- `scripts/profile_synthesis.py` — driver script with `--cluster-id` flag.
- `docs/profile/synthesis-writer-profile-2026-05-05.{json,md}` — Stage 1 baseline.
- `docs/profile/CP-SYNTHESIS-PERF-S2A-DIAGNOSIS.md` — diagnosis note.
- `docs/profile/synthesis-writer-profile-2026-05-05-postfix.{json,md}` — post-fix profile with before/after table.

---

## Current performance state

After CP-SYNTHESIS-PERF, the writer's phase breakdown on validation cluster:

| Phase | Stage 1 (cold) | Stage 2.B (preloaded) |
|---|---|---|
| embedding | 12,585ms (72%) | 311ms (5%) |
| llm_call | 4,261ms (24%) | ~4,400ms (75%) |
| db_write | 416ms (2%) | ~400ms (7%) |
| tenant_load | 98ms (1%) | ~100ms (2%) |
| **wall_clock** | **17,457ms** | **5,899ms** |

**LLM call is now the dominant phase (75%).** This is expected and correct — Sonnet at 1413 output tokens runs ~4–5 seconds. Further cuts would require switching to Haiku for Scale-tier (already correct per spec — Sonnet is only for Enterprise), so no more low-hanging fruit on the writer hot path.

**5.9s steady-state writer is good enough for:**
- LongMemEval benchmark runs (was intractable at 3min/run; now hour-scale).
- Show HN demo where writer fires in real time without hanging the page.
- Customer "synthesis ready" notifications at acceptable lag.

**Future perf work (NOT this chain, but worth noting):**
- LLM call could be further cut by streaming the response or parallelizing source-quote validation. Both are Phase-5-or-later work.
- App-startup cost is now ~20s (was negligible before preload). Worth monitoring if cold restarts during deploy windows become a customer-visible issue. Currently fine.

---

## On the horizon — Phase 5

Per CHECKPOINT-8-SCOPE-v3.md Phase 5, the operational surface is:

1. **Redaction cascade.** When a source memory is deleted/redacted, every synthesis with that memory in `source_memory_ids` is marked `pending_resynthesis`. Re-synthesis runs, old version chained via `superseded_by`. Audit events for every step. GDPR-compliant via evidence-chain redaction.
2. **Diff webhooks.** When synthesis is replaced, emit webhook with diff payload. Standard hygiene: retry-with-backoff, dead-letter queue.
3. **Decision journals (data primitive only).** New `memory_type='decision'` write path — schema includes `decision_text`, `alternatives_considered`, `rationale`, `predicted_outcome`, `actual_outcome`. UI deferred.
4. **Confidence calibration.** Single-agent confidence from importance + LLM self-report + source-quote density. Multi-agent confidence from consensus agreement rate.
5. **Audit log read endpoint.** `GET /audit/events` for Enterprise tenants. Scale tier blocked.
6. **Tier-gating polish.** End-to-end regression: Free / Pro / Scale / Enterprise users each attempt all CP8 features; behavior matches matrix exactly.
7. **Pattern memory write path + pattern-aware recall.** Behavioral pattern extraction from `memory_feedback` events.
8. **Two weeks of dogfood.** Justin uses the new surface in real workflows, bugs triaged.

Phase 5 is the largest CP8 phase by surface area. It's correctly broken into multiple CC chains. The next thread's first authoring task is to sequence them by dependency:

- **Redaction cascade (1)** is foundational — webhooks, audit access, and decision journals all touch it. Author first.
- **Audit log read endpoint (5)** is small (one new endpoint, existing data). Could ship in parallel.
- **Diff webhooks (2)** depends on redaction cascade producing replaced syntheses. Comes after (1).
- **Decision journals (3)** is independent — its own data primitive, no dependencies on others.
- **Confidence calibration (4)** depends on having enough labeled data to calibrate against. Could be deferred until dogfood week 2 supplies the labels.
- **Pattern memory (7)** is its own subsystem. Independent.
- **Tier-gating regression (6)** is verification — runs after the surface lands.
- **Dogfood (8)** runs continuously alongside.

**Recommended Phase 5 sequencing for next thread:**

1. **P5.1 — Redaction cascade (large chain, multi-stage).** Foundational.
2. **P5.2 — Audit log read endpoint (small chain, single CC run).** Parallelizable, ship whenever convenient.
3. **P5.3 — Decision journal write path (medium chain).** Independent.
4. **P5.4 — Diff webhooks (medium chain).** Depends on P5.1.
5. **P5.5 — Pattern memory write path + recall (large chain, multi-stage).** Independent subsystem.
6. **P5.6 — Confidence calibration (medium, gated on dogfood data).**
7. **P5.7 — Tier-gating regression sweep (small, verification only).**
8. **Dogfood (continuous).**

Don't pre-author all of them. Author P5.1 next, run it, learn from it, then author P5.2 against that experience. Same posture as CP-SYNTHESIS-PERF — measure-then-scope, never pre-commit.

---

## Carry-list (NOT in Phase 5 — independent cleanup queue)

These are small standalone fixes that can ship as a single ~30-min cleanup chain before, after, or interleaved with Phase 5:

- **`expand=cluster` query parameter on `/memories/{id}/source`** — never implemented in P4.1. P4.1 V5 only verified cluster_id metadata population, not endpoint consumption. 30-min focused chain. Useful for hierarchical descent ("show me everything in the same theme").
- **`error_logs` schema bug** — 1 occurrence/hour in journal. Same fix class as `analytics_events` from B-5. Schema-qualify or create table. Trivial.
- **6 remaining `_db_execute + split` sites** in `src/recall.py` — rolling cleanup, 1–2 per chain.
- **MCP server `memory_synthesize` tool** — not yet shipped to npm. Now that the writer is sub-6s, exposing this to MCP clients is reasonable. Lands when Phase 5 work surfaces a natural moment.
- **mcp.0latency.ai/authorize page UI polish** — not blocking.
- **VERBATIM-GUARANTEE.md verification** — confirm still accurate post-Phase-4.
- **`analytics_events` schema fix verification** — memory #14 mentions this; verify whether B-5 fix already addressed it or whether it's still leaking retry storms.

None blocks Phase 5. None blocks anything customer-visible.

---

## Standing rules (carry forward verbatim)

All 12 standing rules carry forward unchanged:

1. Branch isolation; operator merges manually after CC chain.
2. Stage cap appropriate to chain size.
3. Category discipline.
4. No questionnaires.
5. Outcome categories: SHIPPED | SKIPPED-PREEXISTING | SKIPPED-OUT-OF-SCOPE | BLOCKED-NEEDS-HUMAN | FAILED.
6. Halt-at-boundary, continue chain.
7. Per-stage evidence files + STATE-LOG.md.
8. No multi-line python heredocs.
9. No `&&` chains past verification gates.
10. Forbidden-exit regex enforced.
11. Audio chime: every CC launch prompt ends with `; afplay /System/Library/Sounds/Glass.aiff`.
12. Production write boundary per AUTONOMY-PROTOCOL.

**Lessons reinforced this thread:**

- **Profile first, optimize second.** Stage 1 + 2.A took ~20 min combined and produced a Stage 2.B that took ~12 min and shipped a 40x improvement on the bottleneck. If we'd skipped to optimization, we'd have likely targeted the LLM call (the obvious-but-wrong assumption) and wasted a chain. Apply the same posture to Phase 5: every hypothesis-driven chain should have a quick measurement step before the fix step.
- **Diagnosis-only chains are real chains.** Stage 2.A wrote zero code and was the most leveraged ~5 minutes of the day. If a question is "what's actually slow" or "what's actually wrong," authoring a diagnosis-only scope doc is correct — not a delay tactic.
- **Independent verification still matters.** CC's self-reports were accurate this thread, but independent verification (paste outputs, read JSON profiles) caught the Sonnet-vs-Haiku question early enough to resolve cleanly.
- **Scope-doc authoring errors are real.** P4.2-PATCH Gate D was based on a faulty read of P4.1's V5. CC correctly halted. Lesson: when a verification gate references a prior phase's deliverable, grep the codebase to confirm it exists before writing the gate.

---

## Resumption prompt for next thread

```
Picking up 0Latency. CP8 Phase 4 closed. CP-SYNTHESIS-PERF closed.
Writer is now 5.9s steady state on user-justin 21-member cluster
(was 17.5s; embedding 311ms after preload, was 12,585ms — 40.5x faster
on that phase, 3.0x overall). Master clean.

Read /root/.openclaw/workspace/memory-product/STATE-LOG.md and
docs/profile/synthesis-writer-profile-2026-05-05-postfix.md before
designing anything new.

Next chain: Phase 5 — operational surface. Largest CP8 phase by
surface area. Sequence per handoff doc:
  P5.1 redaction cascade (foundational, large)
  P5.2 audit log read endpoint (small, parallelizable)
  P5.3 decision journal write path (independent, medium)
  P5.4 diff webhooks (depends on P5.1)
  P5.5 pattern memory (independent subsystem, large)
  P5.6 confidence calibration (gated on dogfood data)
  P5.7 tier-gating regression sweep (small, verification)

Author P5.1 first. Don't pre-author the rest. Measure-then-scope
applies as it did for CP-SYNTHESIS-PERF.

Carry-list (independent cleanup, not blocking):
  expand=cluster endpoint, error_logs schema bug, 6× _db_execute+split
  sites, MCP memory_synthesize tool, authorize page polish.

Standing rules (12) carry forward verbatim. Forbidden-exit regex
enforced. Audio chime mandatory on CC launches.

DESK-MODE on. Mac/SSH/CC all open.
```
