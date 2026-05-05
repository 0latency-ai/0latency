
## 2026-05-05 — P4.2-PATCH SHIPPED (Gate D deferred)

- src/recall.py lines 786 + 1190: audit-emission key fix (memory_type rename, two sites — duplicate dict construction pattern; CC caught the second site I missed in scope authoring).
- p4-2-fix → master merged at edc8574.
- Prod cluster_id backfill applied: 42 rows backfilled, 1 correctly skipped.
- Verification gates A/B/C PASS with numeric evidence.
- p4-2-fix and p4-2-investigation branches deleted (local + origin).

Gate D (expand=cluster on /memories/{id}/source) DEFERRED — endpoint
parameter never implemented in P4.1 (P4.1 V5 only verified cluster_id
metadata population, not endpoint consumption). Scope doc V5 assumption
was incorrect; not a P4.1 ship defect.

Closes: P4.1 S02 verification gap, P4.1 S03 halt, P4.2 end-to-end
verification. Phase 4 functionally closed.

Carry-forward: expand=cluster query parameter on /memories/{id}/source
remains unimplemented. Useful for hierarchical descent ("show me
everything in the same theme" — CP8 v3 Phase 4 Task 4). Not blocking.
Candidate for focused 30-min chain after CP-SYNTHESIS-PERF.

Next chain: CP-SYNTHESIS-PERF.

## 2026-05-05 — CP-SYNTHESIS-PERF Stage 1 SHIPPED (profile)

Branch: cp-synthesis-perf-s1 (NOT YET MERGED — awaiting operator review of profile report).
Wall-clock total: 17457ms (cluster with 12 source memories, thomas tenant).
Dominant phase: embedding, 72.1% of total (12585ms).
Second phase: llm_call, 24.4% of total (4261ms).
Report: docs/profile/synthesis-writer-profile-2026-05-05.md

Key finding: Embedding generation (72%) dominates runtime, not LLM call (24%).
Hypothesis: sentence-transformer model loaded fresh per run.
Stage 2 scope to be authored from this report. Branch held until then.

## 2026-05-05 — CP-SYNTHESIS-PERF SHIPPED

Synthesis writer latency on user-justin validation cluster
6af31b14-900a-4c64-8031-6a7b5a1ea5b3 (12 members):
- Before: 17,457ms wall-clock (embedding 12,585ms = 72% cold model load).
- After: 5,899ms wall-clock (embedding 311ms after preload).
- Improvement: 3.0x faster.

Fix: FastAPI lifespan preload of SentenceTransformer model.
Cold-load cost moved from per-synthesis (paid every call) to
app-startup (paid once at boot, ~20s).

Stages: S1 (profile) → S2.A (diagnosis, no code) → S2.B (fix + verify + merge).
Branch cp-synthesis-perf-s1 merged to master and deleted.

LongMemEval and Show HN unblocked (writer now sub-6s steady state).
Next chain: Phase 5 (operational surface — redaction cascade,
webhooks, decision journals, calibration, audit access, tier polish).
