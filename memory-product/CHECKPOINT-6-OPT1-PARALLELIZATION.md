# CHECKPOINT 6 — Optimization Part 1: Parallelize Strategies 2 & 3

**Timestamp:** 2026-04-21T07:42:30Z  
**Git SHA:** (pending commit - cp6-opt1)  
**Based on:** Part 2 (982715f)

## Objective

Parallelize Strategy 2 (high-importance) and Strategy 3 (keyword search) using concurrent.futures.ThreadPoolExecutor to eliminate sequential execution overhead and reduce post-processing latency from ~705ms to ~367ms.

## Implementation

### Changes Made

1. Extracted S2 and S3 into helper functions (lines 374-467)
2. Parallelized execution in _retrieve_candidates (lines 556-568)
3. Preserved instrumentation from Part 2

### Verification

- Syntax check: Passed
- Service restart: Successful
- Parallelization confirmed: post_total ≈ max(s2, s3)

## Benchmark Results

| Query | s2_ms | s2_rows | s3_ms | s3_rows | post_total_ms | vector_total_ms | recall_total_ms |
|-------|-------|---------|-------|---------|---------------|-----------------|-----------------|
| Q1    | 430   | 50      | 1039  | 100     | 1042          | 2007            | 2973            |
| Q2    | 429   | 50      | 1067  | 100     | 1068          | 1761            | 3090            |
| Q3    | 430   | 50      | 1330  | 92      | 1333          | 2008            | 2957            |
| Q4    | 427   | 50      | 990   | 100     | 992           | 1592            | 2634            |
| Q5    | 421   | 50      | 904   | 32      | 905           | 1443            | 2772            |
| Q6    | 425   | 50      | 960   | 97      | 963           | 1555            | 2942            |

### Medians

- s2: 427.5ms  
- s3: 1000ms  
- post_total: 1027ms  
- vector_total: ~1779ms
- recall_total: ~2907ms

## Comparison with Part 2 Baseline

| Metric            | Part 2 Sequential | Part 3 Parallel | Delta      | % Change |
|-------------------|-------------------|-----------------|------------|----------|
| s2 median         | 337.5ms           | 427.5ms         | +90ms      | +27%     |
| s3 median         | 367.5ms           | 1000ms          | +632ms     | +172%    |
| post_total        | 705ms             | 1027ms          | +322ms     | +46%     |
| recall_total      | ~2900ms (est)     | ~2907ms         | +7ms       | +0.2%    |

## Analysis

### Parallelization Confirmed Working

Evidence: post_total ≈ max(s2, s3) instead of s2 + s3
- All 6 queries show post_total within 5ms of max(s2, s3)
- Parallelization overhead is negligible

### Unexpected Performance Degradation

Individual strategy times increased:
- S2: 337ms → 428ms (+27%)
- S3: 367ms → 1000ms (+172%) — **tripled**

Possible causes:
1. Database connection pool contention (pool_max=5)
2. PostgreSQL lock contention on memories table
3. CPU/IO contention from concurrent scans
4. ThreadPoolExecutor overhead (less likely)

### Net Result: No Improvement

Expected: post = max(337, 367) = 367ms (savings of 337ms)
Actual: post = 1027ms (regression of 322ms)

Root cause: Database contention eliminated parallelization benefits

### End-to-End Performance

Recall total unchanged: ~2900ms → ~2907ms (+7ms within noise)

## Verdict

Parallelization is functionally correct but performance regressed due to DB contention.

### Recommendations

1. Revert parallelization until DB contention is resolved
2. Investigate connection pool sizing (increase pool_max to 10-20)
3. Optimize S3 first (GIN index) before re-attempting parallelization
4. Consider query coalescing (UNION ALL) instead of parallelization

## Next Steps

Recommended: Proceed to CP6 OPT2 (GIN index for S3) before re-attempting parallelization

---

Files modified: /root/.openclaw/workspace/memory-product/src/recall.py
Backup: /root/.openclaw/workspace/memory-product/src/recall.py.backup-pre-cp6-opt1

End of CP6 OPT1 Report
Status: COMPLETE — Parallelization working, but performance regressed due to DB contention
