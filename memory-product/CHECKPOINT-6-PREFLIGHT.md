# CHECKPOINT 6 — Pre-flight Vector Phase Subinstrumentation

**Timestamp:** 2026-04-21T06:38:51Z  
**Git SHA:** fdf7f46ad4b09c906365b0268af5bf0f86a1d1a8  
Instrumentation commit: 705a49326c6519579e16b1201f6f1ff2981e04d7

## Objective

Validate whether the ~2000ms vector phase in warm recall is dominated by cross-region DB RTT (Supabase us-east-1 ← DO server NYC3) before committing to a colocation migration.

## Method

Added three timing boundaries inside the vector recall path:
- **embed**: Local embedding generation (embed_text_local call in recall_fixed)
- **db**: Remote pgvector HNSW query (Strategy 1 semantic search in retrieve_candidates)
- **post**: In-process post-processing (Strategies 2 & 3: high-importance + keyword search)

## Benchmark Results

| Query | embed_ms | db_ms | post_ms | total_vector_ms |
|-------|----------|-------|---------|-----------------|
| S1    | 16       | 679   | 747     | 1,442           |
| S2    | 197      | 551   | 681     | 1,429           |
| S3    | 19       | 439   | 739     | 1,197           |
| K1    | 26       | 401   | 671     | 1,098           |
| K2    | 17       | 489   | 731     | 1,237           |
| K3    | 176      | 428   | 728     | 1,332           |

### Computed Medians

- **embed**: 22.5ms (negligible)
- **db**: 464ms (~36% of vector phase)
- **post**: 729.5ms (~57% of vector phase)
- **total vector**: 1,284.5ms

## Decision Gate Analysis

**Gate criteria:**
- db >= 1500ms → colocation hypothesis VALIDATED, proceed with CP6
- db <= 800ms → colocation hypothesis WEAK, CP6 needs reframing
- db 800–1500ms → proceed with CP6 but revise public latency target from ~300ms to ~800ms

**Measured median db latency:** 464ms

## Verdict

**COLOCATION HYPOTHESIS WEAK — CP6 NEEDS REFRAMING**

### Key Findings

1. **DB query is NOT the dominant factor** — median 464ms represents only ~36% of total vector phase time
2. **Post-processing dominates** — median 729.5ms (~57%) spent in Strategies 2 & 3 (high-importance + keyword search)
3. **Cross-region RTT impact is moderate** — ~464ms is plausible for us-east-1 DB queries but not the 1500-2000ms bottleneck originally hypothesized

### Implications

- **Colocation alone will NOT deliver the expected ~1500ms reduction** to reach 300-500ms total latency
- Post-processing (especially keyword search with complex ILIKE queries) requires optimization independent of infrastructure location
- The 464ms DB latency suggests ~250-300ms RTT penalty for cross-region, leaving ~200ms for actual query execution

### Recommended Next Steps

1. **HOLD on CP6 infrastructure migration** until post-processing is optimized
2. **Profile post-processing subphases**:
   - Strategy 2: High-importance query time
   - Strategy 3: Keyword search ILIKE query time
   - Python-side candidate merging and deduplication overhead
3. **Consider alternative optimizations**:
   - Reduce keyword search complexity (limit ILIKE patterns, use GIN indexes)
   - Parallelize Strategy 2 & 3 queries if not already doing so
   - Cache high-importance memories per agent (minimal changes between queries)
4. **Re-run CP6 decision** after post-processing optimization demonstrates <200ms post time

## Instrumentation Details

**Modified file:** /root/.openclaw/workspace/memory-product/src/recall.py  
**Backup:** /root/.openclaw/workspace/memory-product/src/recall.py.backup-cp6-preflight

**Changes:**
- Added t_db_start / t_db_end timing around Strategy 1 vector query
- Added t_post_start / t_post_end timing around Strategies 2 & 3
- Added log line: [VECTOR SUBPHASES] embed=Xms db=Yms post=Zms
- Modified retrieve_candidates to return timing dict with db_ms and post_ms

**Service restart:** Completed with 30s warmup at 2026-04-21T06:38:01Z  
**Benchmark script:** /tmp/bench_recall_post_cp5.sh  
**Agent ID:** user-justin  
**Tenant ID:** 44c3080d-c196-407d-a606-4ea9f62ba0fc

---

**End of CP6 Pre-flight Report**  
**Status:** HOLD — Infrastructure migration blocked pending query optimization
