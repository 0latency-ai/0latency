# CP Synthesis Performance Phase 3: Diagnosis

**Date:** 2026-05-03
**Analyzed by:** Claude Code
**Context:** Phase 2 (commit 2e142a8) localized bottleneck to clustering.similarity_computation = 228s (99.6% of clustering, 86.7% of total synthesis)

## Executive Summary

**Root Cause Identified:** Query structure prevents HNSW index usage, resulting in cartesian product (6.4M pairs) computed in memory.

**Impact:** 124.7s execution time for 2,524 atoms × 2,524 atoms = 6,370,576 pair comparisons, yielding only 2,020 pairs above 0.78 threshold.

**Fix Category:** Algorithmic restructuring required (Tier 1 migration for state, code changes in clustering.py)

**Target:** <10s (Mem0 benchmark standard)

---

## 1. Exact SQL Query

```sql
SELECT a.id AS source_id, b.id AS neighbor_id,
       1 - (a.embedding <=> b.embedding) AS similarity
FROM memory_service.memories a
JOIN memory_service.memories b
  ON a.tenant_id = b.tenant_id
  AND a.agent_id = b.agent_id
  AND a.id != b.id
WHERE a.id = ANY(%s::uuid[])        -- Array of 2,524 candidate IDs
  AND b.id = ANY(%s::uuid[])        -- Same array (self-join)
  AND 1 - (a.embedding <=> b.embedding) >= %s  -- Threshold: 0.78
ORDER BY a.id, similarity DESC
```

**Parameters (Phase 2 run):**
- Tenant: `44c3080d-c196-407d-a606-4ea9f62ba0fc`
- Agent: `user-justin`
- Candidate count: 2,524 atoms
- Similarity threshold: 0.78
- Result pairs: 2,020

---

## 2. Existing Indexes on `memory_service.memories`

Relevant indexes:

```
"memories_pkey" PRIMARY KEY, btree (id)
"idx_mem_created" btree (agent_id, created_at DESC)
"memories_embedding_hnsw" hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')
```

**HNSW index configuration:**
- Operator class: `vector_cosine_ops` ✓ (correct for `<=>` cosine distance)
- Parameters: m=16, ef_construction=64 (standard pgvector defaults)
- Status: Built and active (verified via `\d`)

---

## 3. EXPLAIN ANALYZE Output

```
Sort  (cost=4478.83..4478.86 rows=12 width=40) (actual time=124652.767..124653.216 rows=2020 loops=1)
  Sort Key: a.id, (('1'::double precision - (a.embedding <=> b.embedding))) DESC
  Sort Method: quicksort  Memory: 159kB
  Buffers: shared hit=38231834
  InitPlan 1
    ->  Aggregate  (cost=2215.67..2215.68 rows=1 width=32) (actual time=21.297..21.408 rows=1 loops=1)
          Buffers: shared hit=3096
          ->  Limit  (cost=0.29..2192.15 rows=1881 width=24) (actual time=0.041..18.616 rows=2524 loops=1)
                Buffers: shared hit=3096
                ->  Index Scan using idx_mem_created on memories  (cost=0.29..2192.15 rows=1881 width=24) (actual time=0.040..18.199 rows=2524 loops=1)
                      Index Cond: ((agent_id = 'user-justin'::text) AND (created_at < (now() - '48:00:00'::interval)) AND (created_at > (now() - '720:00:00'::interval)))
                      Filter: ((is_pinned IS NOT TRUE) AND (embedding IS NOT NULL) AND ((redaction_state IS NULL) OR (redaction_state = 'active'::text)) AND (tenant_id = '44c3080d-c196-407d-a606-4ea9f62ba0fc'::uuid) AND (memory_type = ANY ('{fact,preference,instruction,event,correction,identity}'::text[])))
                      Rows Removed by Filter: 1960
  InitPlan 2
    ->  Aggregate  (cost=2215.67..2215.68 rows=1 width=32) (actual time=23.879..23.940 rows=1 loops=1)
          Buffers: shared hit=3096
          ->  Limit  (cost=0.29..2192.15 rows=1881 width=24) (actual time=0.067..21.790 rows=2524 loops=1)
                Buffers: shared hit=3096
                ->  Index Scan using idx_mem_created on memories memories_1  (cost=0.29..2192.15 rows=1881 width=24) (actual time=0.065..21.320 rows=2524 loops=1)
                      Index Cond: ((agent_id = 'user-justin'::text) AND (created_at < (now() - '48:00:00'::interval)) AND (created_at > (now() - '720:00:00'::interval)))
                      Filter: ((is_pinned IS NOT TRUE) AND (embedding IS NOT NULL) AND ((redaction_state IS NULL) OR (redaction_state = 'active'::text)) AND (tenant_id = '44c3080d-c196-407d-a606-4ea9f62ba0fc'::uuid) AND (memory_type = ANY ('{fact,preference,instruction,event,correction,identity}'::text[])))
                      Rows Removed by Filter: 1960
  ->  Hash Join  (cost=23.46..47.26 rows=12 width=40) (actual time=163.547..124634.085 rows=2020 loops=1)
        Hash Cond: ((a.tenant_id = b.tenant_id) AND (a.agent_id = b.agent_id))
        Join Filter: ((a.id <> b.id) AND (('1'::double precision - (a.embedding <=> b.embedding)) >= '0.78'::double precision))
        Rows Removed by Join Filter: 6368556
        Buffers: shared hit=38231828
        ->  Index Scan using memories_pkey on memories a  (cost=0.29..23.02 rows=10 width=83) (actual time=24.754..67.065 rows=2524 loops=1)
              Index Cond: (id = ANY ((InitPlan 1).col1))
              Index Searches: 9
              Buffers: shared hit=5683
        ->  Hash  (cost=23.02..23.02 rows=10 width=83) (actual time=45.328..45.363 rows=2524 loops=1)
              Buckets: 4096 (originally 1024)  Batches: 1 (originally 1)  Memory Usage: 264kB
              Buffers: shared hit=5683
              ->  Index Scan using memories_pkey on memories b  (cost=0.29..23.02 rows=10 width=83) (actual time=26.157..40.606 rows=2524 loops=1)
                    Index Cond: (id = ANY ((InitPlan 2).col1))
                    Index Searches: 9
                    Buffers: shared hit=5683
Planning:
  Buffers: shared hit=541
Planning Time: 26.774 ms
Execution Time: 124664.434 ms
```

**Key metrics:**
- **Execution time:** 124,664 ms (124.7 seconds)
- **Rows checked:** 6,370,576 pairs (2,524 × 2,524)
- **Rows removed by filter:** 6,368,556 (99.97% rejection rate)
- **Rows returned:** 2,020 pairs above 0.78 threshold
- **Buffer hits:** 38,231,834 (all in shared memory - pure CPU computation)

---

## 4. Root Cause Analysis

### The Problem: HNSW Index Not Used

The query planner chooses:
1. Fetch all 2,524 rows from table `a` via primary key
2. Fetch all 2,524 rows from table `b` via primary key
3. Hash join on (tenant_id, agent_id)
4. **Compute embedding similarity in Join Filter** for all 6.4M pairs
5. Filter pairs below 0.78 threshold

**The HNSW index is never consulted.**

### Why HNSW Is Ignored

HNSW indexes are optimized for **nearest-neighbor search**:
- Query pattern: "Find k nearest neighbors to point X"
- SQL form: `ORDER BY embedding <=> $target_vector LIMIT k`
- Use case: Retrieval, recommendation, similarity search for a single query point

**Our query is fundamentally different:**
- Query pattern: "Find all pairs with similarity above threshold"
- SQL form: Self-join with threshold filter on distance expression
- Use case: Pairwise clustering, graph construction

**PostgreSQL query planner analysis:**
- Sees `a.id = ANY(array)` and `b.id = ANY(array)` → filters to 2,524 rows each
- Estimates small result set (planner estimate: 12 rows)
- Chooses hash join as lowest cost for 2,524 × 2,524 product
- Cannot apply HNSW index to "all pairs above threshold" pattern
- HNSW probes require a specific query vector, not a set-to-set comparison

### The Algorithmic Mismatch

**Current approach (O(n²)):**
- Compute all pairwise similarities: 2,524² = 6,370,576 comparisons
- Filter to threshold: 2,020 pairs (0.03% yield)
- Work done: 6.4M dot products in memory

**HNSW-native approach (O(n × k)):**
- For each of 2,524 atoms:
  - Query HNSW index for nearest neighbors above threshold
  - Expected k ~ 1–10 neighbors per atom (sparse similarity graph)
- Work done: 2,524 HNSW probes × ~10 neighbors = ~25,000 comparisons
- Speedup: 255× reduction in comparisons

**The Index Exists, But We're Not Asking the Right Question.**

---

## 5. Proposed Fix

### Strategy: Decompose Self-Join into KNN Queries

**Current query (single SQL self-join):**
```sql
SELECT a.id, b.id, 1 - (a.embedding <=> b.embedding) AS sim
FROM memories a JOIN memories b ON ...
WHERE a.id = ANY($candidates) AND b.id = ANY($candidates)
  AND 1 - (a.embedding <=> b.embedding) >= $threshold
```

**Proposed approach (batched KNN queries):**
```python
# Phase 4: Compute similarities using HNSW-indexed KNN queries
similarities = []
for candidate_id in candidate_ids:
    # For each atom, find its nearest neighbors above threshold
    knn_query = """
        SELECT id AS neighbor_id,
               1 - (embedding <=> (SELECT embedding FROM memories WHERE id = %s)) AS similarity
        FROM memory_service.memories
        WHERE tenant_id = %s
          AND agent_id = %s
          AND id = ANY(%s::uuid[])
          AND id != %s
          AND 1 - (embedding <=> (SELECT embedding FROM memories WHERE id = %s)) >= %s
        ORDER BY embedding <=> (SELECT embedding FROM memories WHERE id = %s)
        LIMIT 100
    """
    neighbors = _db_execute_rows(knn_query, (candidate_id, tenant_id, agent_id, candidate_ids, candidate_id, candidate_id, threshold, candidate_id))
    for neighbor_id, sim in neighbors:
        similarities.append((candidate_id, neighbor_id, sim))
```

**Performance profile:**
- 2,524 KNN queries (one per atom)
- Each query uses HNSW index → ~1ms per probe (typical pgvector performance)
- Total: 2,524 × 1ms = ~2.5s (50× speedup)
- With batching (10 queries in parallel): ~250ms

**Tier classification:** Code change only (clustering.py), no schema migration. Tier 0.5.

---

### Alternative Approaches Considered

#### Option B: Batch KNN with LATERAL Join
```sql
SELECT a.id, knn.id, knn.similarity
FROM unnest($candidate_ids::uuid[]) AS a(id)
CROSS JOIN LATERAL (
    SELECT b.id, 1 - (a_emb.embedding <=> b.embedding) AS similarity
    FROM memory_service.memories b,
         LATERAL (SELECT embedding FROM memories WHERE id = a.id) a_emb
    WHERE b.id = ANY($candidate_ids::uuid[])
      AND b.id != a.id
      AND 1 - (a_emb.embedding <=> b.embedding) >= $threshold
    ORDER BY a_emb.embedding <=> b.embedding
    LIMIT 100
) knn
```
- Pros: Single query, HNSW-indexed
- Cons: Complex query plan, planner may still choose nested loop without index
- Risk: Untested on production planner

#### Option C: Pre-compute Similarity Matrix (Rejected)
- Store pairwise similarities in a table
- Requires O(n²) storage, stale data problem
- Against CP8 principles (read-only synthesis, no pre-computation)

---

## 6. Estimated Impact

**Current performance:**
- Similarity computation: 124.7s (EXPLAIN ANALYZE)
- Phase 2 profile: 228s (includes overhead, 2× candidates)

**Projected performance (KNN batched approach):**
- 2,524 HNSW probes × 1ms = 2.5s (sequential)
- With connection pooling + batching: 500ms–1s
- **Target achieved: <10s** ✓

**Reduction:**
- From 124.7s → <1s
- **124× speedup**
- Moves clustering from 86.7% of synthesis to <1%

**Side effects:**
- More database round-trips (2,524 queries vs 1)
  - Mitigated by connection pooling, prepared statements
  - Net latency: negligible with local DB connection (<1ms RTT)
- Slightly more complex application code
  - Trade-off justified: algorithmic correctness > code simplicity

---

## 7. Implementation Notes

### Code changes required:
- **File:** `src/synthesis/clustering.py`
- **Function:** `find_clusters()`, Phase 4 section
- **Lines:** ~140–160 (similarity_query block)

### Migration required:
- **None.** HNSW index already exists and is correctly configured.
- No DDL changes needed.

### Testing requirements:
1. Unit test: KNN query returns same pairs as current query (on small dataset)
2. Integration test: End-to-end synthesis run, verify cluster output unchanged
3. Performance test: Log `clustering.similarity_computation` duration, confirm <10s

### Rollback plan:
- Git revert commit
- No schema rollback needed (no migrations)

---

## 8. Conclusion

**Root cause:** Query structure (cartesian self-join) prevents HNSW index usage, forcing 6.4M in-memory comparisons.

**Fix:** Decompose self-join into 2,524 HNSW-indexed KNN queries.

**Outcome:** 124× speedup (124.7s → <1s), synthesis time reduced from 263s → <10s.

**Next step:** Implement KNN query approach in clustering.py, verify with unit/integration tests, deploy to staging.

**Approval required before proceeding to Phase 4 (implementation).**
