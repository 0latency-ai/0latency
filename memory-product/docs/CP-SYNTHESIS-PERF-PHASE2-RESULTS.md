# CP-SYNTHESIS-PERF Phase 2 Results

## Objective

Profile sub-phases inside find_clusters() to identify the dominant bottleneck within the clustering phase identified in Phase 1.

## Methodology

- Added 8 instrumentation points inside find_clusters() in src/synthesis/clustering.py
- Used same timing pattern as Phase 1 (time.perf_counter(), synthesis.perf logger, structured JSON)
- Triggered synthesis run on tenant 44c3080d-c196-407d-a606-4ea9f62ba0fc, agent user-justin
- Captured logs via journalctl -u memory-api

## Results

### Run Metadata
- **Synthesis ID**: 5a379aff-1620-486a-aa12-8a237888fdf8 (first cluster)
- **Tenant ID**: 44c3080d-c196-407d-a606-4ea9f62ba0fc
- **Agent ID**: user-justin
- **Total wall clock**: 263,161 ms (263.2 seconds, 4.4 minutes)
- **Clustering total**: 229,102 ms (229.1 seconds)
- **Candidate memories**: 2,524
- **Similarity pairs found**: 2,020
- **Components after union-find**: 1,809
- **Valid clusters**: 119
- **Clusters synthesized**: 5 (max_clusters=5 default)

### Clustering Sub-Phase Breakdown

| Sub-Phase                          | Duration (ms) | % of Clustering | % of Total | Notes                                    |
|------------------------------------|---------------|-----------------|------------|------------------------------------------|
| clustering.pgvector_registration   | 0             | 0.00%           | 0.00%      | Lazy registration (cached after first)   |
| clustering.candidate_query         | 424           | 0.19%           | 0.16%      | SQL query for candidate atoms            |
| clustering.embedding_parsing       | 496           | 0.22%           | 0.19%      | Parse pgvector strings, build lookups    |
| **clustering.similarity_computation** | **228,258** | **99.61%**      | **86.73%** | **pgvector SQL self-join for pairwise similarities** |
| clustering.union_find_clustering   | 5             | 0.00%           | 0.00%      | DSU merge (2,020 edges, 2,524 nodes)     |
| clustering.cluster_filtering       | 0             | 0.00%           | 0.00%      | Size filtering (no oversized clusters)   |
| clustering.centroid_and_signature  | 76            | 0.03%           | 0.03%      | Centroid computation + headline join     |
| clustering.sorting                 | 0             | 0.00%           | 0.00%      | Sort by size (119 clusters)              |
| **TOTAL (sum of sub-phases)**      | **229,259**   | **100.00%**     | **87.11%** | (reported clustering total: 229,102ms)   |

### Full Synthesis Phase Breakdown (for context)

| Phase          | Duration (ms) | % of Total |
|----------------|---------------|------------|
| job_create     | 269           | 0.10%      |
| **clustering** | **229,102**   | **87.07%** |
| LLM calls (5×) | 28,992        | 11.02%     |
| embedding (5×) | 750           | 0.29%      |
| db_write (5×)  | 221           | 0.08%      |
| tenant_load (5×)| 464          | 0.18%      |
| total          | 263,161       | 100.00%    |

## Finding

**99.6% of clustering time (86.7% of total synthesis time) is spent in a single SQL query: the pgvector similarity computation.**

The query:


With:
- Candidate set: 2,524 atoms
- Theoretical worst-case comparisons: 2,524² = 6,370,576
- Actual comparisons returned: 2,020 (0.03% selectivity)
- Time: 228.3 seconds (~3.8 minutes)

## Dominant Bottleneck

**clustering.similarity_computation** (pgvector SQL self-join)

## Phase 3 Recommendation

**Investigate pgvector index performance.**

Likely root causes:
1. **Missing or suboptimal pgvector index** on memories.embedding column
   - Check:  for index on embedding column
   - Expected: HNSW or IVFFlat index with appropriate parameters
   - If missing: Add 

2. **Self-join cartesian product not leveraging index properly**
   - pgvector <=> operator should use index when filtering on similarity threshold
   - Verify with  on the similarity query
   - Check if index is being used or if it's falling back to sequential scan

3. **Large candidate set (2,524 atoms) forcing O(n²) comparisons**
   - Even with indexing, 2,524² comparisons is expensive
   - Consider: Pre-filter candidates using recency, memory_type, or other heuristics
   - Consider: Incremental clustering (only cluster new atoms against recent clusters)

4. **Database/network latency**
   - Check if database is remote (DigitalOcean managed DB per .env)
   - Large result set (2,020 rows × 3 columns) over network may add overhead
   - Consider: Move clustering computation to Python-side using numpy/faiss if DB query remains slow

**Next step**: Run  on the similarity query to confirm index usage and identify specific bottleneck (index missing vs. index parameters vs. query plan issue).

## Receipts

### Git Status Before Instrumentation


### Git Status After Instrumentation


### Services Status


### API Health


### Raw Profiling Data

Clustering sub-phases (synthesis run 5a379aff-1620-486a-aa12-8a237888fdf8):


## Conclusion

Phase 2 profiling successfully identified the exact bottleneck: **the pgvector similarity computation SQL query accounts for 99.6% of clustering time**.

This is a clear, actionable finding. The next phase should focus on optimizing this single query, starting with verifying pgvector index existence and quality.

Target: Reduce similarity_computation from 228s to <10s (matching Mem0's single-digit-second synthesis published benchmarks). A well-tuned pgvector HNSW index should enable this.
