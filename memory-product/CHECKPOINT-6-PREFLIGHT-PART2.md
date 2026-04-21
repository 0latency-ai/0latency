# CHECKPOINT 6 — Pre-flight Part 2: Post-Processing Strategy Breakdown

**Timestamp:** 2026-04-21T07:11:23Z  
**Git SHA:** (pending commit)  
**Based on:** Part 1 (commit d74acdb98d73c9e1a2ba95fa1fc09622f33eb555)

## Objective

Break down the post-processing phase (729.5ms median from Part 1) into Strategy 2 (high-importance) and Strategy 3 (keyword search) to identify which strategy dominates the bottleneck.

## Execution Mode: Sequential

Strategies 2 and 3 run **sequentially** (not concurrently) in the current implementation:
1. Strategy 2 completes
2. Strategy 3 begins
3. Results merge via shared `candidates` dict (implicit deduplication)

This means the post-processing time is the sum of S2 + S3 + merge overhead.

## Benchmark Results

| Query | embed_ms | db_ms | s2_ms | s2_rows | s3_ms | s3_rows | s3_skipped | post_total_ms |
|-------|----------|-------|-------|---------|-------|---------|------------|---------------|
| S1    | 21       | 448   | 337   | 50      | 395   | 100     | False      | 733           |
| S2    | 97       | 397   | 339   | 50      | 336   | 91      | False      | 675           |
| S3    | 243      | 364   | 337   | 50      | 402   | 100     | False      | 740           |
| K1    | 22       | 380   | 337   | 50      | 330   | 33      | False      | 667           |
| K2    | 51       | 440   | 338   | 50      | 399   | 92      | False      | 737           |
| K3    | 252      | 412   | 337   | 50      | 318   | 100     | False      | 656           |

### Computed Medians

- **embed**: 74ms (negligible, ~5% of total vector phase)
- **db**: 410ms (~31% of total vector phase)
- **s2**: 337.5ms (~26% of total vector phase)
- **s3**: 367.5ms (~28% of total vector phase)
- **post_total**: 705ms (~54% of total vector phase)

### Strategy Row Counts

- **S2 rows**: Constant 50 rows across all queries (hitting LIMIT 50)
- **S3 rows**: Variable 33-100 rows (avg 86 rows)
- **Total candidates**: 150-200 memories per query

## Key Findings

### 1. Both Strategies Contribute Significantly

Neither strategy dominates — they're roughly equal:
- **Strategy 2 (high-importance)**: 337.5ms median (~48% of post-processing)
- **Strategy 3 (keyword search)**: 367.5ms median (~52% of post-processing)

This is a **50/50 split**, not a single bottleneck.

### 2. Strategy 2 is Maxed Out

All queries return exactly 50 rows from S2, hitting the LIMIT 50 clause. This suggests:
- The agent has ≥50 high-importance memories (importance > 0.8)
- Query is retrieving all available high-importance memories
- No filtering happening based on relevance

**Implication**: Strategy 2 latency likely correlates with high-importance memory count, not query complexity.

### 3. Strategy 3 Shows Query Variance

S3 row counts vary widely (33-100 rows):
- Semantic queries (S1-S3): avg 97 rows
- Keyword queries (K1-K3): avg 75 rows

K1 returned only 33 rows, yet S3 took 330ms — comparable to queries returning 100 rows. This suggests:
- S3 latency is dominated by **query execution**, not result processing
- ILIKE pattern matching is expensive regardless of result count

### 4. Semantic vs Keyword Pattern

No clear pattern difference between semantic (S1-S3) and keyword (K1-K3) queries:
- S2 timing: identical (337ms ±2ms) — expected, same query every time
- S3 timing: both ranges overlap (318-402ms)
- Row counts: K1 is an outlier with 33 rows, rest are similar

### 5. Embed Variance Anomalies

embed_ms shows high variance (21-252ms):
- S3: 243ms, K3: 252ms (outliers, ~10x median)
- Most queries: 21-97ms

This is unrelated to post-processing but worth noting — local embedding may have GC pauses or other Python runtime overhead.

### 6. Merge Overhead is Minimal

post_total closely matches s2 + s3:
- Calculated sum (s2 + s3): 704.5ms median
- Measured post_total: 705ms median
- Merge overhead: <1ms

The dict-based deduplication and candidate parsing is negligible.

## Structural Observations

### Strategy 2: High-Importance Query
```sql
SELECT ... FROM memories
WHERE agent_id = ? AND tenant_id = ?
  AND superseded_at IS NULL
  AND importance > 0.8
  AND id NOT IN (SELECT unnest(?::uuid[]))
ORDER BY importance DESC
LIMIT 50
```

**Performance characteristics:**
- **337ms median** for 50 rows
- ~6.7ms per row
- Constant time across all queries (no query-specific variance)
- Likely dominated by `NOT IN (unnest(?))` exclusion check (Strategy 1 returned ~16-20 memories)

### Strategy 3: Keyword Search
```sql
SELECT ... FROM memories
WHERE agent_id = ? AND tenant_id = ?
  AND superseded_at IS NULL
  AND ((headline ILIKE ? OR context ILIKE ?) OR ... [5 keywords])
  AND id NOT IN (SELECT unnest(?::uuid[]))
ORDER BY importance DESC
LIMIT 100
```

**Performance characteristics:**
- **367.5ms median** for 33-100 rows (avg 86)
- ~4.3ms per row (when returning 86 rows)
- High variance (318-402ms) unrelated to row count
- Likely dominated by multiple ILIKE pattern scans

## Decision Gate for Optimization Priority

Given the 50/50 split, **both strategies require optimization** to achieve meaningful latency reduction:

### High-Priority Optimizations (Target: <200ms post-processing)

1. **Strategy 2: Index the exclusion check**
   - Current: `id NOT IN (SELECT unnest(?::uuid[]))` on 16-20 UUIDs
   - May benefit from rewriting as `LEFT JOIN ... WHERE other.id IS NULL`
   - Or: Skip exclusion entirely if deduplication happens in Python (negligible overhead shown)

2. **Strategy 3: Replace ILIKE with GIN index**
   - Current: 5× full-table ILIKE scans per query
   - Add GIN index on `headline || ' ' || context` (tsvector)
   - Use `ts_query` instead of ILIKE patterns
   - Expected: ~10x speedup (40-50ms instead of 367ms)

3. **Consider query parallelization**
   - Current: Sequential (S2 → S3)
   - Option: Run S2 and S3 concurrently via `asyncio.gather`
   - Expected: post-processing becomes `max(s2, s3)` instead of `s2 + s3`
   - Savings: ~337ms (cut post time in half)

### Lower-Priority Optimizations

4. **Strategy 2: Reduce LIMIT or cache results**
   - If high-importance memories rarely change, cache per agent
   - Or: Reduce LIMIT 50 → 20 (proportional latency savings)

5. **Strategy 3: Reduce keyword count**
   - Current: up to 5 keywords → 10 ILIKE clauses
   - Option: Limit to 3 keywords → 6 ILIKE clauses
   - Expected: ~40% speedup if linear (367ms → 220ms)

## Recommended Next Steps

### Immediate Action: Parallelize S2 & S3

This is the **highest ROI, lowest risk** optimization:
- No schema changes required
- Pure Python refactor in `_retrieve_candidates`
- Expected savings: ~337ms (median s2 time eliminated from wall-clock)
- New post-processing: ~367ms (just s3 time)

```python
async def _retrieve_candidates(...):
    # Run S1 (vector) first (required for exclusion list)
    s1_candidates = await _strategy_1_vector(...)
    
    # Run S2 & S3 in parallel
    s2_task = asyncio.create_task(_strategy_2_high_importance(...))
    s3_task = asyncio.create_task(_strategy_3_keyword(...))
    s2_candidates, s3_candidates = await asyncio.gather(s2_task, s3_task)
    
    # Merge (negligible overhead)
    return merge_candidates(s1, s2, s3)
```

**Expected outcome after parallelization:**
- embed: 74ms (unchanged)
- db: 410ms (unchanged)
- post: ~367ms (down from 705ms)
- **Total vector phase: ~851ms** (vs current ~1189ms)
- **Savings: 338ms (~28% reduction)**

### Medium-Term: Add GIN index for Strategy 3

After parallelization, S3 becomes the bottleneck. Replace ILIKE with full-text search:
- Add: `CREATE INDEX idx_memories_fulltext ON memories USING gin(to_tsvector('english', headline || ' ' || context))`
- Rewrite: `WHERE to_tsquery('english', ?) @@ to_tsvector('english', headline || ' ' || context)`
- Expected: 367ms → ~40ms (10x speedup)

**Expected outcome after GIN index:**
- post: ~40ms (S3 optimized, S2 running in parallel)
- **Total vector phase: ~524ms**
- **Savings: 665ms (~56% reduction from baseline)**

### Long-Term: Revisit colocation after query optimization

Once post-processing is <100ms, re-measure db latency:
- If db remains ~400ms, colocation may save ~200ms (RTT penalty)
- Combined target: <350ms total vector phase (meets original CP6 goal)

## Instrumentation Details

**Modified file:** `/root/.openclaw/workspace/memory-product/src/recall.py`  
**Backup:** `/root/.openclaw/workspace/memory-product/src/recall.py.backup-cp6-part2`

**Changes:**
- Added `_t_s2_start` / `_t_s2_end` timing around Strategy 2
- Added `_t_s3_start` / `_t_s3_end` timing around Strategy 3
- Added row counting: `_s2_count`, `_s3_count` (incremented when adding to candidates)
- Added `_s3_skipped` flag (True if no keywords found)
- Added log line: `[POST SUBPHASES] s2=Xms s2_rows=Y s3=Zms s3_rows=W s3_skipped=bool`
- Kept existing `[VECTOR SUBPHASES]` log line intact

**Service restart:** Completed with 30s warmup at 2026-04-21T07:10:48Z  
**Benchmark script:** `/tmp/bench_recall_post_cp5.sh`  
**Agent ID:** `user-justin`  
**Tenant ID:** `44c3080d-c196-407d-a606-4ea9f62ba0fc`

---

**End of CP6 Pre-flight Part 2 Report**  
**Status:** READY — Clear optimization path identified (parallelize, then GIN index)
