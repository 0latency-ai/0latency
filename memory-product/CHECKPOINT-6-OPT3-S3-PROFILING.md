# CHECKPOINT 6 — OPT3 Part 3: Strategy 3 Subphase Profiling

**Date:** 2026-04-21 08:24 UTC  
**Git SHA:** 68da74b (instrumentation + syntax fix)  
**Task:** Profile Strategy 3's internal phases to identify where the remaining ~330ms latency goes after GIN index optimization

## Context

Part 2 (git 2124adb) replaced Strategy 3's ILIKE pattern matching with GIN-indexed full-text search. EXPLAIN ANALYZE confirmed the index is being used (Bitmap Index Scan, 35.7ms query execution), but S3's wall-clock time remained ~367–399ms. This diagnostic profiles the non-SQL overhead.

## Instrumented Phases

Strategy 3 (_retrieve_candidates) was instrumented with 7 distinct timing phases:

1. **extract**: Regex keyword extraction from query text + stop word filtering
2. **sanitize**: Special character removal from extracted keywords
3. **build**: tsquery string construction (`' OR '.join()`) + SQL query string assembly
4. **conn**: Database connection pool acquisition + cursor creation + BEGIN + set_tenant_context
5. **exec**: The actual `cur.execute(query, params)` call
6. **fetch**: `cur.fetchall()` + row-by-row string parsing into dict format
7. **commit**: Transaction COMMIT

**Structural notes:**
- All phases are sequential, non-interleaved
- Phases 1–3 (extract/sanitize/build) all measured **0ms** in all runs (sub-millisecond, rounded down)
- No collapses or merges were needed

## Benchmark Results

6 queries measured (warmup discarded):

| Query | S3 Total | extract | sanitize | build | conn | exec | fetch | commit | rows_fetched |
|-------|----------|---------|----------|-------|------|------|-------|--------|--------------|
| Q1    | 350ms    | 0ms     | 0ms      | 0ms   | 134ms| 144ms| 3ms   | 67ms   | 100          |
| Q2    | 343ms    | 0ms     | 0ms      | 0ms   | 134ms| 139ms| 1ms   | 67ms   | 100          |
| Q3    | 342ms    | 0ms     | 0ms      | 0ms   | 135ms| 138ms| 1ms   | 67ms   | 100          |
| Q4    | 277ms    | 0ms     | 0ms      | 0ms   | 133ms| 76ms | 0ms   | 66ms   | 30           |
| Q5    | 346ms    | 0ms     | 0ms      | 0ms   | 136ms| 140ms| 2ms   | 67ms   | 87           |
| Q6    | 348ms    | 0ms     | 0ms      | 0ms   | 136ms| 141ms| 2ms   | 67ms   | 100          |

**Medians:**
- S3 Total: **345ms** (median of 342, 343, 346, 348, 350 = 344.5ms, Q4 is outlier low)
- extract: **0ms**
- sanitize: **0ms**
- build: **0ms**
- conn: **134.5ms** (median of 134, 134, 135, 136, 136)
- exec: **139.5ms** (median of 138, 139, 140, 141, 144)
- fetch: **1.5ms** (median of 1, 1, 2, 2, 3)
- commit: **67ms**
- rows_fetched: **93.5** (median of 30, 87, 100, 100, 100, 100 = 93.5)

**Sum of subphase medians:** 0 + 0 + 0 + 134.5 + 139.5 + 1.5 + 67 = **342.5ms**

## Reconciliation

- Reported S3 median: **345ms**
- Sum of subphase medians: **342.5ms**
- Gap: **2.5ms** (~0.7%)

The reconciliation is excellent — the instrumentation accounts for >99% of S3's measured time. The 2.5ms gap is well within measurement noise and Python overhead (perf_counter calls, variable assignment, etc.).

## Verdict Classification: **BIMODAL**

Two phases dominate S3's time:

1. **conn (connection setup):** 134.5ms median — **39.2%** of S3 total
2. **exec (DB execute):** 139.5ms median — **40.7%** of S3 total

Together: **274ms / 345ms = 79.4%** of S3 time.

### Breakdown by Phase Group:

- **Python preprocessing (extract + sanitize + build):** 0ms — **0%**
- **Database setup (conn):** 134.5ms — **39.2%**
- **Database query (exec):** 139.5ms — **40.7%**
- **Result processing (fetch):** 1.5ms — **0.4%**
- **Transaction cleanup (commit):** 67ms — **19.5%**

## Analysis

### Phase 1–3: Python Preprocessing (0ms)

The Python-side work (keyword extraction, sanitization, query building) is negligible — all phases round to 0ms. This is expected for simple string operations on short queries (typically 5–10 words → 3–5 keywords).

**Optimization potential:** None. Already effectively free.

### Phase 4: Connection Setup (134.5ms, 39.2%)

This phase includes:
- `pool.getconn()` — acquiring a connection from psycopg2 connection pool
- `cur = conn.cursor()` — creating a cursor
- `cur.execute("BEGIN")` — starting transaction
- `cur.execute("SELECT memory_service.set_tenant_context(%s)")` — setting RLS context

**134.5ms is suspiciously high** for connection pool operations. Typical psycopg2 `getconn()` on a warm pool is <1ms. The delay suggests:

1. **Pool exhaustion:** All connections busy, waiting for one to become available
2. **set_tenant_context overhead:** The RLS context function may be slow (locks, schema lookups, etc.)
3. **Network latency:** If the pool is creating new connections (cold pool), DNS + TCP handshake

**Key insight:** This is the same connection setup overhead that affects S2 (high-importance search). Both S2 and S3 use psycopg2 directly (bypassing the asyncpg-based `_db_execute` used by S1 vector search).

### Phase 5: DB Execute (139.5ms, 40.7%)

The actual `cur.execute(query, params)` call takes 139.5ms median. From CP5 Part 2, we know the **query execution itself** (server-side EXPLAIN ANALYZE) is only ~35–45ms.

**139.5ms exec time breakdown (inferred):**
- Query execution (server-side): ~35–45ms
- Network round-trip: ~10–20ms (localhost, but still TCP)
- Client-side query preparation (psycopg2 parameter binding, protocol overhead): ~85–95ms

The gap suggests **psycopg2 driver overhead** — the Python client spends significant time preparing the parameterized query before sending it to Postgres.

### Phase 6: Fetch + Materialize (1.5ms, 0.4%)

`cur.fetchall()` + row parsing is extremely fast — 1.5ms median even for 100 rows. The string-join-and-split materialization strategy is efficient.

**Optimization potential:** None. Already negligible.

### Phase 7: Commit (67ms, 19.5%)

Transaction commit is consistently 66–67ms across all runs. This is **unusually slow** for a read-only transaction with no writes.

Likely causes:
1. **fsync/WAL overhead:** Even read-only transactions may trigger commit logging if there were prior writes in the session
2. **Lock release overhead:** RLS context cleanup or other session-local state
3. **Connection pool return overhead:** If `pool.putconn(conn)` is slow (though this is in the `finally` block, not timed here)

**Note:** The COMMIT time is very consistent (66–67ms), suggesting it's not network latency (which would vary more).

## Optimization Targets (Ranked)

### Target 1: DB Execute Overhead (139.5ms, 40.7%)

**Root cause:** psycopg2 client-side query preparation overhead (~85–95ms inferred).

**Potential optimizations:**
1. **Switch to asyncpg:** The asyncpg driver used by S1 (vector search) is significantly faster than psycopg2. Migrate S3 to use the shared `_db_execute` function.
2. **Prepared statements:** If psycopg2 is retained, use server-side prepared statements to amortize query planning across multiple calls.
3. **Query simplification:** The `NOT IN (SELECT unnest(%s::uuid[]))` anti-join may be slow. Consider using a temporary table or lateral join.

**Expected win:** 50–80ms (reducing exec from ~140ms to ~60–90ms).

### Target 2: Connection Setup Overhead (134.5ms, 39.2%)

**Root cause:** Either pool exhaustion or slow `set_tenant_context` RLS function.

**Potential optimizations:**
1. **Increase connection pool size:** If the pool is exhausted, increase `pool_max` in the connection pool config.
2. **Profile set_tenant_context:** Add timing around the RLS context call specifically. If it's slow, optimize the Postgres function (cache schema lookups, reduce locks).
3. **Reuse connections:** If S2 and S3 are called sequentially (which they are), reuse the same connection/transaction instead of getting a new one.

**Expected win:** 80–120ms (reducing conn from ~135ms to ~15–55ms).

### Target 3: Commit Overhead (67ms, 19.5%)

**Root cause:** Unclear — read-only transactions shouldn't be this slow to commit.

**Potential optimizations:**
1. **Eliminate transaction:** If S3 is a pure read, it doesn't need an explicit BEGIN/COMMIT. Use autocommit mode.
2. **Combine with S2:** Run S2 and S3 in the same transaction to amortize the commit cost.

**Expected win:** 30–50ms (reducing commit from ~67ms to ~15–20ms, or eliminating it entirely).

## Verdict

**Classification: BIMODAL**

Strategy 3's latency is concentrated in two phases:
1. **DB execute (40.7%)**: Likely psycopg2 driver overhead, not the query itself
2. **Connection setup (39.2%)**: Likely pool exhaustion or slow RLS context setting

Together these account for **80% of S3's time**. The remaining 20% is split between commit (19.5%) and result processing (0.4%).

**Recommendation for future work (not implemented in this checkpoint):**

1. **Immediate win (Part 4):** Profile connection setup specifically — split `conn` into `pool_get`, `cursor_create`, `begin`, and `set_context` to identify the bottleneck.
2. **Medium-term (Part 5):** Migrate S3 to asyncpg (use `_db_execute` instead of raw psycopg2) to eliminate driver overhead.
3. **Long-term (Part 6):** Combine S2 + S3 into a single transaction to amortize connection + commit overhead.

**Current status:** Instrumentation complete. No optimizations applied. Next step is to decide whether to pursue Part 4 (profile connection setup) or move to Part 5 (migrate to asyncpg).

---

**Git log:**
```
68da74b cp6-opt3: fix missing outer exception handler in S3 instrumentation
8331bd7 cp6-opt3: instrument strategy 3 subphases for profiling
```
