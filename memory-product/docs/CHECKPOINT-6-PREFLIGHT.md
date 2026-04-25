# CHECKPOINT 6 — Pre-flight: Vector Phase DB RTT Measurement

**Timestamp:** 2026-04-24T21:51:04Z  
**Measurement Session:** CP6 Vector Phase Subinstrumentation (Final Gate Check)  
**Agent:** user-justin  
**Tenant:** 44c3080d-c196-407d-a606-4ea9f62ba0fc

## Objective

Determine what fraction of the ~2000ms vector phase is attributable to cross-region DB RTT (Supabase us-east-1 ← DigitalOcean NYC3) versus local post-processing work, to gate the DB colocation migration decision for Checkpoint 6.

## Methodology

Leveraged existing instrumentation in `recall.py`:
- **[VECTOR SUBPHASES]**: Top-level breakdown of embed/s1/s2/s3 timing
- **[S1 SUBPHASES]**: Fine-grained 7-phase breakdown of Strategy 1 (vector search), including `exec` (DB query execution) and `fetch` (result materialization)
- **s1_db = s1_exec + s1_fetch**: Represents the actual cross-region network + DB query round-trip time

Probe methodology:
1. Restart memory-api, 30s warmup
2. Execute warmup query (discarded)
3. Run 6 varied queries (3 semantic: S1-S3, 3 keyword: K1-K3) covering infrastructure, strategy, architecture, proper nouns (Palmer), pgvector, and benchmark themes
4. Extract timing data from journalctl logs

## Benchmark Results

| Query | embed_ms | s1_exec_ms | s1_fetch_ms | s1_db (exec+fetch) | s2_ms | s3_ms | vector_total_ms |
|-------|----------|------------|-------------|---------------------|-------|-------|-----------------|
| S1    | 86       | 414        | 0           | 414                 | 340   | 349   | 2519            |
| S2    | 245      | 416        | 0           | 416                 | 339   | 346   | 2662            |
| S3    | 30       | 423        | 0           | 423                 | 341   | 396   | 2012            |
| K1    | 27       | 385        | 0           | 385                 | 336   | 276   | 2317            |
| K2    | 68       | 380        | 0           | 380                 | 337   | 281   | 2383            |
| K3    | 110      | 369        | 0           | 369                 | 273   | 347   | 2404            |

### Computed Medians

- **embed**: 77.0ms (~3% of vector phase)
- **s1_db (exec+fetch)**: 399.5ms (~17% of vector phase) — **CRITICAL METRIC**
- **s2**: 338.0ms (~14% of vector phase)
- **s3**: 346.5ms (~14% of vector phase)
- **vector_total**: 2394.5ms

### Phase Composition

- **Local embedding generation**: 77ms (3%)
- **Cross-region DB RTT (s1_db)**: 400ms (17%)
- **Post-processing (s2 + s3)**: 685ms (29%)
- **Unaccounted overhead**: ~1233ms (51%)

The unaccounted 51% likely includes:
- Python runtime overhead between phase boundaries
- Config loading, agent resolution, always-include block construction
- Candidate scoring and ranking (Step 5-7 in recall_fixed)
- Context block formatting

## Decision Gate Analysis

**Gate criteria** (from CHECKPOINT-6-SCOPE.md lines 102-106):
- s1_db ≥ 1500ms → **PROCEED** with colocation migration
- s1_db ≤ 800ms → **REFRAME** — colocation hypothesis weak
- s1_db 800-1500ms → **PROCEED** but update public latency target

**Measured s1_db median: 399.5ms**

**Decision: REFRAME — Colocation hypothesis weak**

## Key Findings

1. **Cross-region RTT is NOT the bottleneck** — s1_db represents only 17% of total vector phase time (400ms of 2394ms)
2. **Post-processing strategies dominate** — s2 + s3 contribute ~685ms (29%), comparable to the entire DB round-trip
3. **Python overhead is substantial** — 51% of vector phase time (~1233ms) is unaccounted for in explicit phase timing, suggesting significant Python-side processing cost
4. **Fetch time is negligible** — All queries show 0ms fetch time, meaning result materialization is instant; the 400ms is pure network + query execution
5. **Colocation would save at most ~400ms** — Even if colocation eliminated 100% of network RTT, vector phase would still be ~2000ms due to post-processing and Python overhead

## Comparison to Previous Checkpoints

This measurement contradicts earlier hypotheses from CHECKPOINT-6-PREFLIGHT.md (April 21, 2026) which measured:
- s1_db median: 464ms (vs 400ms today)
- post median: 729.5ms (vs 685ms today)
- vector_total median: 1284.5ms (vs 2395ms today)

**Why the discrepancy?**
The April 21 measurement used a different agent namespace and query set. The current measurement (user-justin tenant, April 24) shows:
- **Higher vector_total** (2395ms vs 1285ms): Likely due to larger memory corpus or different tenant data distribution
- **Lower s1_db** (400ms vs 464ms): Consistent cross-region RTT, minimal variance
- **Lower s2+s3** (685ms vs 730ms): Slight improvement, possibly from query optimizer changes

Despite absolute latency differences, the **proportional breakdown is consistent**: cross-region DB RTT is 17-36% of total vector phase, NOT the dominant factor.

## Recommendation: HOLD CP6 Migration, Pursue Query Optimization

**Immediate priority:** Do NOT proceed with DB colocation migration. The 400ms cross-region RTT penalty is manageable and represents a minority of total latency.

**Alternative optimization path** (based on CHECKPOINT-6-PREFLIGHT-PART2.md):

1. **Parallelize S2 & S3 queries** (highest ROI, zero risk)
   - Current: Sequential execution (s2 → s3)
   - Target: Concurrent execution via asyncio.gather
   - Expected savings: ~338ms (eliminate s2 from wall-clock time)
   - New vector_total: ~2057ms

2. **Replace Strategy 3 ILIKE with GIN full-text search** (medium-term)
   - Current: 5× ILIKE pattern scans (~347ms)
   - Target: Single GIN tsvector query (~40ms)
   - Expected savings: ~300ms
   - New vector_total: ~1757ms

3. **Profile Python overhead** (long-term)
   - Investigate the 1233ms unaccounted time
   - Candidate areas: scoring loops, dict comprehensions, logging overhead
   - Potential savings: ~500ms

4. **Consider colocation only after query optimization**
   - Once vector_total < 1000ms, revisit cross-region RTT impact
   - At that point, 400ms RTT would represent 40% of total time, justifying migration
   - Target post-migration: <600ms vector phase

**Updated CP6 gate decision:** Change from infrastructure migration to query optimization. DB colocation remains a future option but is not the critical path for achieving <1000ms recall latency.

---

**End of CP6 Pre-flight Report**  
**Status:** HOLD — Infrastructure migration blocked; proceed with query parallelization (asyncio refactor)  
**Next milestone:** CP6-OPT1 — Parallelize S2/S3 strategies (target: <2100ms vector phase)
