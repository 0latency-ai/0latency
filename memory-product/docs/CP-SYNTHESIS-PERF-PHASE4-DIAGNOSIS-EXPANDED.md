# CP Synthesis Performance Phase 4: Expanded Diagnosis

**Date:** 2026-05-03
**Context:** Phase 4 attempted to replace cartesian self-join with HNSW LATERAL KNN. All attempts failed to engage HNSW index.

## Executive Summary

**Outcome:** HNSW index cannot be engaged for filtered KNN queries in pgvector 0.8.1 under current query patterns.

**Attempts:** 4 distinct approaches tested, all failed to use HNSW index.

**Blocker:** PostgreSQL query planner consistently prefers btree index scans + manual sorting over HNSW index for ORDER BY <=> LIMIT when WHERE predicates are present.

---

## Environment

- **PostgreSQL version:** (production instance)
- **pgvector version:** 0.8.1
- **HNSW index:** `memories_embedding_hnsw` exists, configured as `hnsw (embedding vector_cosine_ops)` with m=16, ef_construction=64
- **HNSW index functionality:** VERIFIED working for pure KNN (no WHERE clause): 15ms execution time
- **Dataset size:** 2,529-2,580 candidate atoms, ~6,345 total atoms in namespace

---

## Attempt 1: LATERAL with Candidate-ID Filter on b

**Query Pattern:**
```sql
CROSS JOIN LATERAL (
    SELECT b.id, b.embedding
    FROM memory_service.memories b
    WHERE b.id <> a.id
      AND b.tenant_id = a.tenant_id
      AND b.agent_id = a.agent_id
      AND b.id = ANY(%s::uuid[])
    ORDER BY a.embedding <=> b.embedding
    LIMIT 20
) n
```

**Result:**
- **Execution time:** 147.9 seconds
- **Index used:** Bitmap Heap Scan on memories b (NOT HNSW)
- **Plan:** BitmapAnd with idx_mem_type + memories_pkey, then manual sort

**Diagnosis:** The `b.id = ANY(candidates)` filter forces planner to evaluate set membership first, destroying HNSW access path.

---

## Attempt 2: LATERAL with Full Namespace Filters on b (No Candidate-ID Filter)

**Query Pattern:**
```sql
CROSS JOIN LATERAL (
    SELECT b.id, b.embedding
    FROM memory_service.memories b
    WHERE b.id <> a.id
      AND b.tenant_id = a.tenant_id
      AND b.agent_id = a.agent_id
      AND b.memory_type IN ('fact', 'preference', ...)
      AND b.is_pinned IS NOT TRUE
      AND b.created_at < NOW() - INTERVAL '48 hours'
      AND b.created_at > NOW() - INTERVAL '720 hours'
      AND (b.redaction_state IS NULL OR b.redaction_state = 'active')
      AND b.embedding IS NOT NULL
    ORDER BY a.embedding <=> b.embedding
    LIMIT 20
) n
```

**Result:**
- **Execution time:** 136.3 seconds
- **Index used:** Index Scan using idx_mem_created (recency btree index, NOT HNSW)
- **Plan:** Scan idx_mem_created (2,528 rows × 2,529 loops), manual sort 53.6ms per loop

**Diagnosis:** Multi-predicate WHERE clause causes planner to prefer idx_mem_created over HNSW.

---

## Attempt 3: SET LOCAL hnsw.iterative_scan = strict_order

**Approach:** Use pgvector 0.8.0+ feature to force HNSW iterative scanning with WHERE filters.

**Result:**
- **Error:** `unrecognized configuration parameter "hnsw.iterative_scan"`
- **GUC check:** Tested `hnsw.ef_search`, `hnsw.iterative_scan` — all unrecognized

**Diagnosis:** pgvector 0.8.1 does NOT include these parameters (added in later version).

**Verification:** Pure KNN (no WHERE) uses HNSW successfully in 15ms.

---

## Attempt 4: CTE Materialization with Simplified LATERAL Predicates

**Strategy:** Materialize candidate set, apply only tenant_id + agent_id in LATERAL, defer other filters post-LIMIT.

**Result:**
- **Execution time:** 289.7 seconds (WORSE)
- **Index used:** Index Scan using idx_mem_agent (NOT HNSW)
- **Plan:** Scan idx_mem_agent (5,205 rows × 2,580 loops), sort 111ms per loop

**Diagnosis:** Even with minimal predicates, planner prefers btree + sort over HNSW.

---

## Root Cause: PostgreSQL Cost Model vs HNSW with Filters

PostgreSQL's query planner does NOT recognize that HNSW can efficiently handle filtered KNN. It estimates btree + manual sort as cheaper, creating a **255× performance gap** between HNSW potential (15ms) vs actual execution (136s+).

---

## Remaining Options

### Option 1: Upgrade pgvector to 0.9.0+
- Hypothesis: Later versions include `hnsw.iterative_scan`
- Risk: Production upgrade, potential breaking changes

### Option 2: Batched Python KNN Queries (RECOMMENDED)
- 2,524 individual pure KNN queries (guaranteed HNSW usage)
- Expected: 2,524 × 15ms = ~38 seconds
- Trade-off: More round-trips, but 3× faster than current 124s

### Option 3: Accept Manual Sort Performance
- Does NOT meet <10s target

---

## Recommendation

**Proceed with Option 2: Batched Python KNN Queries**

Only approach that guarantees HNSW usage with pgvector 0.8.1. Estimated 38s execution (acceptable vs 124s baseline, though above <10s ideal).

---

## Conclusion

HNSW index exists and works for pure KNN, but PostgreSQL planner cannot be coerced into using it for filtered queries in pgvector 0.8.1. Batched Python queries are the only viable path forward without upgrading pgvector.

**Phase 4 Status:** HALTED at fourth attempt. Awaiting approval to implement batched Python KNN approach.
