# CP-SYNTHESIS-PERF Phase 1 Results — Synthesis Latency Profiling

**Date:** 2026-05-04 01:26 UTC
**Status:** Phase 1 complete — clustering phase identified as dominant bottleneck
**Recommendation:** Phase 2 should target clustering algorithm optimization

---

## Synthesis Run Metadata

| Field | Value |
|-------|-------|
| **Synthesis ID** | `4adb6017-e7f4-4093-97bf-3be73e124b63` |
| **Tenant ID** | `44c3080d-c196-407d-a606-4ea9f62ba0fc` (user-justin) |
| **Agent ID** | `user-justin` |
| **Cluster Size** | 12 memories |
| **Clusters Found** | 119 total (processed 1 per max_clusters=1) |
| **Tokens Used** | 1389 (Haiku) |
| **Total Wall Clock** | 161,322 ms (161.3 seconds) |

---

## Phase Breakdown — Per-Cluster Synthesis Latency

| Phase | Duration (ms) | % of Total | Notes |
|-------|--------------|------------|-------|
| **clustering** | **154,198** | **95.6%** | **DOMINANT PHASE** — find_clusters() call |
| llm_call | 4,346 | 2.7% | Anthropic API call + parse + validation |
| embedding | 1,550 | 1.0% | sentence-transformers local embedding |
| job_create | 772 | 0.5% | synthesis_jobs row creation |
| tenant_load | 170 | 0.1% | Quota check + atom loading from DB |
| db_write | 156 | 0.1% | Insert synthesis + audit + rate-limit counters |
| **TOTAL** | **161,322** | **100%** | End-to-end orchestrator wall clock |

### Per-Cluster Sub-Total (cluster_synthesis phase)
- **tenant_load + llm_call + embedding + db_write:** 6,227 ms (3.9% of total)
- This represents the per-cluster synthesis work (LLM + storage)
- The other 96% is spent finding clusters (clustering phase)

---

## Key Findings

### 1. Clustering dominates end-to-end latency (95.6%)
The `find_clusters()` call in `src/synthesis/clustering.py` consumed **154.2 seconds** of the **161.3-second** total runtime. This is the clear optimization target for Phase 2.

**Hypothesis:** The clustering algorithm is likely performing expensive operations such as:
- Full table scans or unindexed queries on the memories table
- Expensive embedding similarity calculations across all candidate memories
- Inefficient filtering logic (e.g., checking synthesis recency, role tags, redaction state)
- Lack of caching for cluster candidates or intermediate results

**Phase 2 priority:** Profile and optimize `find_clusters()` internals before touching any other phase.

### 2. LLM call is NOT the bottleneck (2.7%)
Contrary to initial assumptions, the Anthropic API call (including prompt formatting, network round-trip, response parsing, and source-quote validation) only took **4.3 seconds** (2.7% of total). This is acceptable for a 1389-token Haiku call.

**No optimization needed** for this phase in Phase 2.

### 3. Embedding is acceptable (1.0%)
Local sentence-transformers embedding generation took **1.55 seconds** (1.0% of total). This is reasonable for a single synthesis output (~200-500 token output).

**No optimization needed** unless Phase 2 identifies batch embedding opportunities.

### 4. DB writes are negligible (0.1%)
Writing the synthesis memory row, audit event, and incrementing rate-limit counters took only **156 ms**. Database write performance is not a concern.

**No optimization needed** for this phase.

---

## Comparison to Expected Baseline

| Metric | Observed | Expected (Mem0 baseline) | Delta |
|--------|----------|-------------------------|-------|
| **Per-cluster latency** | 161.3s | <10s | **16x slower** |
| **Dominant phase** | clustering (95.6%) | LLM call (expected 60-80%) | **Unexpected** |
| **LLM call** | 4.3s | ~5-10s (Haiku) | ✅ **On target** |

The ~16x slowdown is entirely attributable to the clustering phase. If clustering can be reduced to <10 seconds (matching the Mem0 baseline assumption), end-to-end latency would drop to ~12 seconds, meeting the Phase 3 target.

---

## Phase 2 Recommendation: Optimize find_clusters()

### Top candidates for investigation (in priority order):

1. **Index audit:** Verify that queries in `find_clusters()` use indexed columns:
   - `WHERE tenant_id = ? AND agent_id = ? AND redaction_state = 'active'` should use an index
   - Filtering by `memory_type IN ('fact', 'preference', 'decision')` should be efficient
   - Check `EXPLAIN ANALYZE` output for full table scans

2. **Cluster candidate caching:** If clustering repeatedly considers the same memory set:
   - Cache eligible memory IDs per tenant/agent (TTL: 5 minutes)
   - Invalidate cache on new memory writes
   - Store pre-filtered candidates in Redis or in-memory

3. **Embedding similarity optimization:** If clustering uses vector similarity:
   - Use pgvector's IVFFlat or HNSW index for approximate nearest neighbor (ANN) search
   - Reduce candidate set size before computing similarities (e.g., filter by recency first)
   - Consider pre-computing cluster centroids

4. **Algorithmic swap:** If current clustering is O(n²):
   - Switch to a faster algorithm (e.g., MinHash LSH, DBSCAN with spatial indexing)
   - Or apply a two-phase approach: coarse clustering (fast) + fine refinement (slow, on smaller set)

5. **Parallelization:** If clustering is CPU-bound:
   - Parallelize candidate selection across multiple workers (e.g., asyncio, threading, or multiprocessing)
   - Batch-process embedding similarity calculations

---

## Raw Log Excerpt (First 8 synthesis_perf Entries)

```
May 04 01:23:33 thomas-server python3[346280]: {"time":"2026-05-04T01:23:33","level":"INFO","msg":"{"metric": "synthesis_perf", "phase": "job_create", "duration_ms": 772, "tenant_id": "44c3080d-c196-407d-a606-4ea9f62ba0fc", "synthesis_id": null}"}

May 04 01:26:07 thomas-server python3[346280]: {"time":"2026-05-04T01:26:07","level":"INFO","msg":"{"metric": "synthesis_perf", "phase": "clustering", "duration_ms": 154198, "tenant_id": "44c3080d-c196-407d-a606-4ea9f62ba0fc", "synthesis_id": null, "clusters_found": 119}"}

May 04 01:26:07 thomas-server python3[346280]: {"time":"2026-05-04T01:26:07","level":"INFO","msg":"{"metric": "synthesis_perf", "phase": "tenant_load", "duration_ms": 170, "tenant_id": "44c3080d-c196-407d-a606-4ea9f62ba0fc", "synthesis_id": null, "cluster_size": 12}"}

May 04 01:26:12 thomas-server python3[346280]: {"time":"2026-05-04T01:26:12","level":"INFO","msg":"{"metric": "synthesis_perf", "phase": "llm_call", "duration_ms": 4346, "tenant_id": "44c3080d-c196-407d-a606-4ea9f62ba0fc", "synthesis_id": null, "tokens_used": 1389}"}

May 04 01:26:13 thomas-server python3[346280]: {"time":"2026-05-04T01:26:13","level":"INFO","msg":"{"metric": "synthesis_perf", "phase": "embedding", "duration_ms": 1550, "tenant_id": "44c3080d-c196-407d-a606-4ea9f62ba0fc", "synthesis_id": null}"}

May 04 01:26:13 thomas-server python3[346280]: {"time":"2026-05-04T01:26:13","level":"INFO","msg":"{"metric": "synthesis_perf", "phase": "db_write", "duration_ms": 156, "tenant_id": "44c3080d-c196-407d-a606-4ea9f62ba0fc", "synthesis_id": "4adb6017-e7f4-4093-97bf-3be73e124b63"}"}

May 04 01:26:13 thomas-server python3[346280]: {"time":"2026-05-04T01:26:13","level":"INFO","msg":"{"metric": "synthesis_perf", "phase": "cluster_synthesis", "duration_ms": 6227, "tenant_id": "44c3080d-c196-407d-a606-4ea9f62ba0fc", "synthesis_id": "4adb6017-e7f4-4093-97bf-3be73e124b63", "cluster_idx": 0, "cluster_size": 12}"}

May 04 01:26:13 thomas-server python3[346280]: {"time":"2026-05-04T01:26:13","level":"INFO","msg":"{"metric": "synthesis_perf", "phase": "total", "duration_ms": 161322, "tenant_id": "44c3080d-c196-407d-a606-4ea9f62ba0fc", "synthesis_id": "4adb6017-e7f4-4093-97bf-3be73e124b63"}"}
```

---

## Instrumentation Artifacts

**Files modified:**
- `src/synthesis/orchestrator.py` (Phase boundaries: job_create, clustering, cluster_synthesis, total)
- `src/synthesis/writer.py` (Phase boundaries: tenant_load, llm_call, embedding, db_write)

**Instrumentation approach:**
- Used `time.perf_counter()` for monotonic timing (immune to clock drift)
- Logged structured JSON to `synthesis.perf` logger for grep-able extraction
- Each phase logged as `{"metric": "synthesis_perf", "phase": "<name>", "duration_ms": <int>, ...}`

**Verification:**
- All phase boundaries executed successfully (8 log entries captured)
- Total phase duration (161,322 ms) matches end-to-end wall clock
- No exceptions or errors during instrumented run

---

## Phase 1 Acceptance Criteria: ✅ PASSED

- ✅ Instrumentation added to orchestrator and writer (no behavior changes)
- ✅ Synthesis run completed successfully (1 cluster synthesized)
- ✅ Phase-boundary logs extracted from journald
- ✅ Dominant phase identified: **clustering (95.6%)**
- ✅ Total wall clock >30 seconds (161.3s — exercised the slow path)
- ✅ Report written with phase breakdown and Phase 2 recommendations

---

## Next Steps (Phase 2 Handoff)

1. **Profile clustering internals:** Add timing boundaries inside `src/synthesis/clustering.py` to identify which sub-phase dominates:
   - Candidate memory query (DB fetch)
   - Embedding similarity calculation (pgvector or numpy)
   - Cluster formation algorithm (grouping logic)
   - Filtering/post-processing (recency check, deduplication)

2. **Optimize the dominant clustering sub-phase** based on profiling data (likely candidate query or similarity calculation)

3. **Re-benchmark:** Run synthesis again and verify clustering phase drops below 10 seconds

4. **Phase 3 gate:** Total per-cluster latency <10 seconds (currently 161s)

---

**End of Phase 1 Report**
