# Synthesis Writer Profile Report

**Date:** 2026-05-05 05:55:16
**Cluster ID:** 6af31b14-900a-4c64-8031-6a7b5a1ea5b3
**Cluster Size:** 12 memories
**Synthesis ID:** 51465483-9801-4f91-a1de-7150eacc47c9
**Model:** claude-sonnet-4-6
**Tokens Used:** 1413

## Summary

- **Total wall-clock:** 17457ms (17.5s)
- **Total accounted:** 17360ms (99.4% coverage)
- **Phases recorded:** 4

## Phase Breakdown

| Phase | Duration (ms) | % of Total | Metadata |
|-------|--------------|-----------|----------|
| embedding | 12585 | 72.1% | synthesis_id=None |
| llm_call | 4261 | 24.4% | synthesis_id=None, tokens_used=1413 |
| db_write | 416 | 2.4% | synthesis_id=51465483-9801-4f91-a1de-7150eacc47c9 |
| tenant_load | 98 | 0.6% | synthesis_id=None, cluster_size=12 |

## Interpretation

The dominant cost is **embedding generation** (12,585ms, 72.1% of total), dwarfing the **LLM call** (4,261ms, 24.4%). The 17.5-second end-to-end runtime is dominated by embedding, not the LLM. Stage 2 should prioritize embedding optimization over LLM optimization.

Candidate hypotheses for Stage 2:

1. **Model loading overhead**: The sentence-transformer model (all-MiniLM-L6-v2) appears to be loaded fresh on each synthesis run (logs show HuggingFace cache HEAD requests). Preloading the model at server startup or caching it across runs could eliminate 12+ seconds of the embedding phase.

2. **Synchronous in-process embedding**: The embedding is computed inline during the synthesis writer's critical path. Moving embedding to an async queue, dedicated service, or pre-computed cache would remove it from the user-visible latency.

3. **Redundant embedding computation**: If synthesis text is deterministic or rarely changes, embeddings could be cached or computed once and reused. However, synthesis is inherently non-deterministic, so this may not apply.

Stage 2 should investigate hypothesis #1 first (model preloading) as it's the simplest fix with the largest potential impact.
