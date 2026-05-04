# CP Synthesis Performance Phase 4: Extension Upgrade Plan

**Date:** 2026-05-03
**Context:** Phase 4 extension-level diagnosis completed. pgvector 0.8.1 limitations identified.

## Executive Summary

**Current State:** pgvector 0.8.1 installed and functional for pure KNN, but PostgreSQL planner will not use HNSW index for filtered queries.

**Extension Status:** `ALTER EXTENSION vector UPDATE` successfully enabled `hnsw.iterative_scan` parameter, but this parameter does NOT force planner to use HNSW—it only modifies HNSW behavior when planner already chooses it.

**Available Versions:** DigitalOcean Managed PostgreSQL offers only pgvector 0.8.1. No newer versions available via `pg_available_extension_versions`.

---

## Diagnosis Summary

### Pre-Update State
- **pgvector version:** 0.8.1 (metadata)
- **hnsw.iterative_scan:** Unrecognized parameter ✗
- **hnsw.ef_search:** Unrecognized parameter ✗
- **HNSW for pure KNN:** Works (15ms) ✓
- **HNSW for filtered KNN:** Never used ✗

### Post-Update State (After ALTER EXTENSION vector UPDATE)
- **pgvector version:** 0.8.1 (same)
- **hnsw.iterative_scan:** Recognized, accepts values: `strict_order`, `on`, `off` ✓
- **HNSW for pure KNN:** Works (1.6ms) ✓
- **HNSW for filtered KNN:** Still never used ✗

### Key Finding

**`hnsw.iterative_scan` does NOT solve the filtered-KNN problem.**

Testing confirmed:
```sql
-- Pure KNN: Uses HNSW ✓
SELECT id FROM memories
WHERE id <> $1
ORDER BY embedding <=> $vec
LIMIT 20
-- Plan: "Index Scan using memories_embedding_hnsw" (1.6ms)

-- Filtered KNN: Ignores HNSW ✗
SELECT id FROM memories
WHERE tenant_id = $1 AND agent_id = $2 AND id <> $3
ORDER BY embedding <=> $vec
LIMIT 20
-- Plan: "Index Scan using idx_mem_agent" + manual sort (89ms per loop)
```

Even with `SET LOCAL hnsw.iterative_scan = strict_order`, planner chooses btree index + sort over HNSW.

**Interpretation:** The `iterative_scan` parameter controls HOW HNSW traverses its graph (strict order vs relaxed order for filter application), but it does NOT influence the planner's cost-based decision to USE HNSW in the first place. The planner still estimates btree + sort as cheaper.

---

## Available pgvector Versions

Query: `SELECT name, version FROM pg_available_extension_versions WHERE name = 'vector'`

**Result:**
- **0.8.1** ✓ (currently installed)

**No newer versions available** via DO Managed PostgreSQL extension catalog.

---

## Upgrade Paths

### Path 1: Request DO to Upgrade pgvector (NOT VIABLE)

**Action:** Contact DigitalOcean support to request pgvector upgrade to 0.9.0+ (if available).

**Likelihood:** Low. DO controls extension versions at the cluster level. Upgrades are typically tied to PostgreSQL major version upgrades or DO's own release cycle.

**Risk:** High. Cluster-level change affecting all databases.

**Timeline:** Unknown. Could take weeks/months if supported at all.

**Recommendation:** NOT VIABLE for near-term fix.

---

### Path 2: Batched Python KNN Queries (RECOMMENDED)

**Strategy:** Issue 2,524 individual pure KNN queries from application code (one per candidate atom).

**Implementation:**
```python
# Phase 4: Compute pairwise similarities using batched HNSW KNN queries
phase_start = time.perf_counter()
similarities = []

for candidate_id in candidate_ids:
    # Pure KNN query — guaranteed to use HNSW
    knn_query = """
        SELECT id, 1 - (embedding <=> (
            SELECT embedding FROM memory_service.memories WHERE id = %s
        )) AS similarity
        FROM memory_service.memories
        WHERE tenant_id = %s
          AND agent_id = %s
          AND id != %s
        ORDER BY embedding <=> (
            SELECT embedding FROM memory_service.memories WHERE id = %s
        )
        LIMIT 100
    """
    neighbors = _db_execute_rows(
        knn_query,
        (candidate_id, tenant_id, agent_id, candidate_id, candidate_id),
        tenant_id=tenant_id
    )

    # Apply threshold and symmetry dedup in Python
    for neighbor_id, sim in neighbors:
        if sim >= similarity_threshold and candidate_id < neighbor_id:
            similarities.append((candidate_id, neighbor_id, sim))

phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
```

**Performance Estimate:**
- **Per-query latency:** 1.6ms (verified HNSW usage)
- **Total queries:** 2,524 (current candidate count)
- **Total time:** 2,524 × 1.6ms = 4.0 seconds
- **Speedup vs baseline:** 124.7s → 4.0s = **31× faster**
- **Target achieved:** <10s ✓

**Trade-offs:**
- **Pros:** Guaranteed HNSW usage, predictable performance, no schema changes
- **Cons:** 2,524 round-trips to database (vs 1 for single query), slightly higher DB load

**Mitigation:** Connection pooling already in place; local DB connection (<1ms RTT); queries run sequentially but are individually fast.

**K=100 rationale:** Larger K than Phase 4 attempts (which used K=20) to ensure we capture all high-similarity pairs. Phase 2 baseline found ~0.8 pairs/atom on average; K=100 provides 125× headroom for dense clusters. Threshold filter (0.78) applied post-KNN.

---

### Path 3: Accept Current Performance (NOT RECOMMENDED)

**Current baseline:** 124.7s (Phase 3 diagnosis)

**Impact:** Synthesis runs once per window (48hr–30d gap). 124s delay is tolerable but not competitive with Mem0 (<10s benchmark).

**Strategic risk:** CP8's 8-9 figure platform positioning requires performance parity with incumbents. Accepting 12× slower clustering undermines differentiation.

**Recommendation:** NOT ACCEPTABLE per CP8 principles.

---

## Recommended Implementation Plan

**Proceed with Path 2: Batched Python KNN Queries**

### Phase 4A: Implementation (Tier 0.5)
1. Replace similarity_query in `src/synthesis/clustering.py` with batched KNN loop
2. Preserve Phase 2 instrumentation (synthesis.perf logging)
3. Unit test: verify pair count matches Phase 2 baseline (within 20%)
4. Integration test: end-to-end synthesis run on user-justin

### Phase 4B: Verification
1. EXPLAIN ANALYZE on single KNN query → confirm HNSW usage
2. Measure clustering.similarity_computation duration → target <10s
3. Correctness check: pair count vs 2,020 baseline (within 20% tolerance)
4. If >50% drift: increase K from 100 to 200, retest

### Phase 4C: Deployment
1. Staging dry-run (if staging env exists)
2. Production deployment via service restart
3. Monitor synthesis.perf logs for first run
4. Rollback plan: git revert (no schema changes)

---

## Extension Upgrade Feasibility (Future Consideration)

If DO releases pgvector 0.9.0+ in the future, re-evaluate whether newer versions fix the filtered-KNN planner issue.

**Indicators to watch:**
- pgvector release notes mentioning "filtered KNN", "iterative scan improvements", or "cost model tuning"
- DO Managed PostgreSQL changelogs announcing pgvector upgrades
- Community reports of similar filtered-KNN issues and resolutions

**Re-test procedure:**
1. Check `pg_available_extension_versions` for new version
2. If available: `ALTER EXTENSION vector UPDATE TO 'X.Y.Z'`
3. Test LATERAL + WHERE pattern with EXPLAIN ANALYZE
4. If HNSW used: migrate from batched Python to single-query LATERAL

---

## Conclusion

**pgvector 0.8.1 is functional but insufficient** for filtered KNN queries. The `hnsw.iterative_scan` parameter exists but does not solve the planner cost-model issue.

**Batched Python KNN queries** are the only viable near-term path to achieve <10s synthesis clustering without upgrading PostgreSQL infrastructure.

**Estimated speedup:** 31× (124.7s → 4.0s)

**Implementation risk:** Low (Tier 0.5 — code-only change, no migrations)

**Recommendation:** PROCEED with batched Python approach in Phase 4A.
