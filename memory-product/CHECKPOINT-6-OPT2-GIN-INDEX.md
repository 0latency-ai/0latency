# CHECKPOINT 6 — Optimization Part 2: Revert Parallelization + GIN Index

**Timestamp:** 2026-04-21T08:08:21Z  
**Git commits:**
- Revert: ded5a5b (cp6-opt1-revert)
- GIN index: 2124adb (cp6-opt2)

## Phase A: Revert Parallelization

Successfully reverted commit 576d3bc (parallelization) due to DB connection pool contention.
- Post-revert baseline confirmed: ~730ms post median (within ±50ms of Part 2's 705ms)
- s2: ~337ms, s3: ~398ms (matching Part 2)

## Phase B: GIN Index for Strategy 3

### Implementation

**Discovered existing infrastructure:**
- GIN index already exists:  on  column
-  is tsvector type, pre-populated for all 5268 memories

**Changes made:**
1. Replaced ILIKE pattern matching with full-text search
2. Uses 
3. Sanitizes keywords (removes special chars)
4. Query: 

**Column expression:** Existing  tsvector column (populated via trigger/function from headline + context)

### EXPLAIN ANALYZE (Execution Time: 35.7ms)



**✓ Index usage confirmed:** Bitmap Index Scan on idx_memories_search_text_gin

### Benchmark Results

| Query | s2_ms | s2_rows | s3_ms | s3_rows | post_total_ms | recall_total_ms |
|-------|-------|---------|-------|---------|---------------|-----------------|
| Q1    | 355   | 50      | 395   | 100     | 751           | 2258            |
| Q2    | 337   | 50      | 401   | 100     | 739           | 2613            |
| Q3    | 336   | 50      | 402   | 90      | 738           | 2639            |
| Q4    | 339   | 50      | 402   | 100     | 741           | 2441            |
| Q5    | 338   | 50      | 336   | 33      | 675           | 2378            |
| Q6    | 273   | 50      | 383   | 100     | 656           | 2346            |

**Medians:**
- s2: 337ms
- s3: 399ms
- post_total: 738ms
- recall_total: 2440ms

### Comparison with Part 2 Baseline

| Metric            | Part 2 (ILIKE) | Part 2 GIN | Delta   | % Change |
|-------------------|----------------|------------|---------|----------|
| s2 median         | 337.5ms        | 337ms      | -0.5ms  | 0%       |
| s3 median         | 367.5ms        | 399ms      | +31.5ms | +8.6%    |
| post_total        | 705ms          | 738ms      | +33ms   | +4.7%    |
| recall_total      | ~2300ms (est)  | 2440ms     | +140ms  | +6.1%    |

### Result Overlap Analysis

Test query: How should we approach model deployment for production infrastructure?

- Full-text search: 100 results
- ILIKE baseline: 100 results
- Overlap: **62 memories (62%)**
- FTS only: 38 memories
- ILIKE only: 38 memories

**Verdict:** Moderate overlap (62%) is expected. Full-text search uses stemming (e.g., deploy matches deployment, deployed), while ILIKE is literal pattern matching.

### Unexpected Finding: No Performance Improvement

**Expected:** ~327ms S3 speedup (367ms → ~40ms based on EXPLAIN ANALYZE)  
**Actual:** S3 slightly slower (367ms → 399ms)

**Possible explanations:**

1. **Query complexity overhead:**
   - EXPLAIN ANALYZE showed 35.7ms for a simple query
   - Actual queries have additional filters: , , etc.
   - These filters may dominate the query time, masking index benefit

2. **Row processing overhead:**
   - S3 returns 33-100 rows (avg ~87)
   - Row processing (parsing, dict creation) takes time regardless of index speed
   - If DB query is fast (35ms) but processing is slow, total S3 time won't improve

3. **Connection/transaction overhead:**
   - Direct psycopg2 connection with BEGIN/COMMIT adds latency
   - May offset index performance gains

4. **websearch_to_tsquery parsing:**
   - May be slower than expected for complex OR queries
   - plainto_tsquery might be faster but uses AND logic (not suitable)

5. **NOT IN (unnest(?)) anti-join:**
   - This subquery runs for each S3 execution
   - With ~16-20 UUIDs from S1, this may be expensive
   - Could benefit from rewrite to LEFT JOIN ... WHERE other.id IS NULL

### Recommendations

1. **Profile S3 breakdown:**
   - Add timing for: keyword extraction, query execution, row processing
   - Identify which component dominates the 399ms

2. **Optimize NOT IN anti-join:**
   - Current: 
   - Alternative: LEFT JOIN with IS NULL filter
   - Or: Skip exclusion entirely (dedup in Python - merge overhead is <1ms)

3. **Consider parallel execution after profiling:**
   - If S3 is truly I/O-bound (waiting on DB), parallelization may help
   - If S3 is CPU-bound (parsing, processing), parallelization won't help
   - Need connection pool size increase (pool_max=5 is too low)

4. **Alternative: Skip S3 entirely:**
   - S2 returns 50 high-importance memories (constant)
   - S1 returns ~20 semantic matches
   - Total: 70 candidates may be sufficient
   - S3 adds 33-100 more, but at 399ms cost
   - Consider making S3 optional or reducing its LIMIT

## Next Steps

**DO NOT re-attempt parallelization yet.** Instead:

1. Profile S3 to understand the 399ms breakdown
2. Fix the NOT IN anti-join overhead
3. Re-benchmark after fixes
4. Only then consider parallelization (with increased pool size)

---

**Files modified:** src/recall.py  
**Index used:** idx_memories_search_text_gin (existing)  
**Service status:** Healthy

**End of CP6 OPT2 Report**  
**Status:** COMPLETE — GIN index working but no performance gain observed
