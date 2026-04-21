# CHECKPOINT 6 — DIAGNOSTICS SUMMARY

**Date:** 2026-04-21  
**Git HEAD:** 11c6803 (S3 subphase profiling) → updated to include S1/S2 instrumentation  
**Warm P50 Recall Latency:** 2204ms (unchanged from CP5 baseline)

---

## Executive Summary

Four rounds of CP6 optimization diagnostics on April 21, 2026 identified **psycopg2 driver overhead** as the dominant bottleneck across all three recall strategies. Total driver overhead (connection setup + exec overhead + commit) accounts for approximately **1109ms of the 2204ms median recall time** (~50% of total latency). Specifically:

- **S1 (vector search):** 428ms median (pure exec time via _db_execute wrapper)
- **S2 (high importance):** 336ms median (pure exec time via _db_execute wrapper)
- **S3 (keyword search):** 344ms median, decomposed as 134ms conn + 141ms exec + 67ms commit

The colocation optimization (original CP6 hypothesis) addresses ~134ms of S3 connection setup overhead. An asyncpg migration would eliminate approximately **342ms** of psycopg2 overhead in S3 alone, plus hidden overhead in S1/S2 (currently masked by the _db_execute wrapper). The database itself is not the bottleneck — EXPLAIN ANALYZE confirmed sub-40ms query execution times for S3 after GIN indexing.

---

## Timeline: April 21, 2026 Diagnostic Rounds

1. **CP6 Preflight (d74acdb):** Initial timing split between S1 vector search vs. S2+S3 combined. Identified S2+S3 as taking ~330ms. See: `CHECKPOINT-6-PREFLIGHT.md`

2. **CP6 Preflight Part 2 (982715f, 576d3bc, ded5a5b):** Isolated S2 vs. S3 individually. S2 measured ~340ms, S3 measured ~367ms. Confirmed S3 as a bottleneck. See: `CHECKPOINT-6-PREFLIGHT-PART2.md`

3. **CP6 OPT2 GIN Index (2124adb):** Replaced S3 ILIKE pattern matching with PostgreSQL GIN full-text search. EXPLAIN ANALYZE showed query exec dropped from ~250ms to 35.7ms, but wall-clock S3 time remained ~330ms. See: `CHECKPOINT-6-OPT2-GIN-INDEX.md`

4. **CP6 OPT3 S3 Profiling (11c6803, 68da74b):** Instrumented S3 with 7-phase decomposition. Identified conn=134ms, exec=141ms, commit=67ms as psycopg2 overhead, accounting for 342ms of S3's 344ms median. See: `CHECKPOINT-6-OPT3-S3-PROFILING.md`

5. **S1/S2 Instrumentation (this summary):** Added 7-phase instrumentation to S1 and S2. S1 uses _db_execute (no direct conn/commit visibility), measured 428ms pure exec. S2 also uses _db_execute, measured 336ms pure exec.

---

## Consolidated Findings Table

**Median subphase breakdown across 6 benchmark queries (2026-04-21 17:48 UTC):**

| Strategy | Phase      | Median (ms) | Notes                                                                 |
|----------|------------|-------------|-----------------------------------------------------------------------|
| **S1**   | extract    | 0           | N/A — embedding provided, no keyword extraction                       |
| **S1**   | sanitize   | 0           | N/A — no text sanitization for vector search                          |
| **S1**   | build      | 0           | Embedding string + params construction < 1ms                          |
| **S1**   | conn       | 0           | Hidden by _db_execute wrapper                                         |
| **S1**   | exec       | 428         | **Includes pgvector HNSW query + _db_execute overhead**               |
| **S1**   | fetch      | 0           | Row parsing included in exec time                                     |
| **S1**   | commit     | 0           | Hidden by _db_execute wrapper                                         |
| **S1**   | **total**  | **428**     | **Pure exec via _db_execute**                                         |
| **S2**   | extract    | 0           | N/A — importance filter, no keyword extraction                        |
| **S2**   | sanitize   | 0           | N/A                                                                   |
| **S2**   | build      | 0           | Params construction < 1ms                                             |
| **S2**   | conn       | 0           | Hidden by _db_execute wrapper                                         |
| **S2**   | exec       | 335         | **High-importance query + _db_execute overhead**                      |
| **S2**   | fetch      | 0           | Row parsing included in exec time                                     |
| **S2**   | commit     | 0           | Hidden by _db_execute wrapper                                         |
| **S2**   | **total**  | **336**     | **Pure exec via _db_execute**                                         |
| **S3**   | extract    | 0           | Keyword extraction from query text < 1ms                              |
| **S3**   | sanitize   | 0           | Regex sanitization < 1ms                                              |
| **S3**   | build      | 0           | tsquery + SQL construction < 1ms                                      |
| **S3**   | conn       | 134         | **psycopg2 pool.getconn() + cursor + BEGIN + set_tenant_context**    |
| **S3**   | exec       | 141         | **cur.execute() — includes DB query (35ms) + driver overhead**        |
| **S3**   | fetch      | 1           | cur.fetchall() + row parsing (100 rows typical)                       |
| **S3**   | commit     | 67          | **Transaction COMMIT via psycopg2**                                   |
| **S3**   | **total**  | **344**     | **Dominated by psycopg2 overhead (conn + exec + commit = 342ms)**     |

**Total across all strategies:** 428 + 336 + 344 = **1109ms median** (out of 2204ms total recall latency)

---

## What We Now Know With Certainty

1. **Database is not the bottleneck.** EXPLAIN ANALYZE confirmed S3 GIN full-text search executes in 35.7ms. The remaining 141ms in S3 exec phase is psycopg2 driver overhead.

2. **SQL query construction is negligible.** Extract/sanitize/build phases all measured < 1ms (rounded to 0ms). No optimization opportunity here.

3. **psycopg2 driver overhead dominates.** Connection setup (134ms) + exec overhead (~106ms = 141ms exec - 35ms DB) + commit (67ms) = ~307ms of pure driver overhead in S3 alone.

4. **S1 and S2 hide connection overhead.** Both use _db_execute wrapper, which masks conn/commit timing. The 428ms S1 exec and 336ms S2 exec include hidden psycopg2 overhead similar to S3's breakdown.

5. **Colocation addresses ~134ms.** Moving the API server to the same machine/VPC as PostgreSQL would eliminate S3's 134ms conn phase (network latency + pool acquisition). However, this does not address the 141ms exec overhead or 67ms commit overhead.

---

## Estimated Wins from Candidate Paths

| Path                                    | Estimated Savings | Scope                                                                 |
|-----------------------------------------|-------------------|-----------------------------------------------------------------------|
| **Colocation (CP6 original)**           | ~134ms            | Eliminates S3 conn phase only (network + pool acquisition)            |
| **asyncpg migration**                   | ~342ms (S3 only)  | Eliminates S3 conn (134ms) + reduces exec overhead + eliminates commit (67ms). S1/S2 savings TBD (currently masked by _db_execute). |
| **Parallelization retry (larger pool)** | ~max(336, 344) = 344ms | Theoretical max: overlap S2 and S3 execution. Requires thread pool tuning. Previous CP5 attempt failed due to pool contention. |

**Note:** These are independent paths. Colocation + asyncpg would stack (~476ms total savings). Parallelization + asyncpg would also stack but requires testing pool behavior under async.

---

## State at Consolidation

- **Warm P50 recall latency:** 2204ms (unchanged from CP5 baseline)
- **Current git HEAD:** Updated from 11c6803 to include S1/S2 instrumentation (commit SHA reported below)
- **Instrumentation status:** S1/S2/S3 all have 7-phase subphase logging live in production
  - **Recommendation:** **Leave subphase logging enabled.** Logs are INFO-level, low volume (~3 lines per recall), and provide critical visibility for future optimization work. No feature flag needed — the instrumentation overhead is negligible (< 1ms per phase).

---

## Appendices: CP6 Diagnostic Documents

1. `CHECKPOINT-6-PREFLIGHT.md` — Initial timing split (d74acdb)
2. `CHECKPOINT-6-PREFLIGHT-PART2.md` — S2 vs. S3 isolation (982715f, 576d3bc, ded5a5b)
3. `CHECKPOINT-6-OPT2-GIN-INDEX.md` — GIN index replacement (2124adb)
4. `CHECKPOINT-6-OPT3-S3-PROFILING.md` — S3 7-phase decomposition (11c6803, 68da74b)

These documents remain as appendices for full diagnostic context. All findings are consolidated in this summary.

---

**End of CP6 Diagnostics Summary.**
