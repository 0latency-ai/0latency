"""
Synthesis Clustering Engine — CP8 Phase 2 Task 1

Finds clusters of semantically-related atom memories suitable for synthesis.
Read-only foundation; no LLM calls, no DB writes, no external dependencies beyond pgvector.

Algorithm:
- pgvector cosine distance for pairwise similarity (computed in SQL)
- Union-find (Disjoint Set Union / DSU) for connected-component merging
- Hard clustering only (each atom in exactly one cluster)
- Soft clustering (atom in multiple clusters) deferred to Phase 2.5

Filters applied:
- Pinned atoms excluded (is_pinned IS NOT TRUE)
- Redacted/modified/pending atoms excluded (redaction_state IS NULL OR = 'active')
- Recency window: 48hr–30d by default (configurable)
- Embedding required (embedding IS NOT NULL)
- Memory types: fact, preference, instruction, event, correction, identity

Embedding dimension assumption: 384 (all-MiniLM-L6-v2 from CP6).
If mixed dimensions detected, this will raise an error.

Why filters are applied here and not at recall:
- Recall serves user queries (pinned atoms are DESIRED in recall context)
- Synthesis looks for consolidation candidates (pinned atoms are user-curated, should not be auto-merged)
- Redaction state filtering ensures we don't synthesize over tombstones or pending-review rows
"""

import uuid
import time
import json
import logging
import datetime
from dataclasses import dataclass
from typing import Optional

from src.storage_multitenant import _db_execute_rows, set_tenant_context, _get_connection_pool

# Performance profiling logger
perf_logger = logging.getLogger("synthesis.perf")


@dataclass
class Cluster:
    """A cluster of related atom memories.
    
    Attributes:
        memory_ids: List of memory UUIDs in this cluster
        centroid_embedding: Mean of member embeddings (normalized), for downstream use
        cluster_signature: Human-readable summary (top 3 headlines, most recent first)
    """
    memory_ids: list[uuid.UUID]
    centroid_embedding: list[float]
    cluster_signature: str


class _UnionFind:
    """Disjoint Set Union (DSU) for connected-component clustering."""
    
    def __init__(self, elements):
        self.parent = {e: e for e in elements}
        self.rank = {e: 0 for e in elements}
    
    def find(self, x):
        """Find root with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x, y):
        """Union by rank."""
        root_x = self.find(x)
        root_y = self.find(y)
        
        if root_x == root_y:
            return
        
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1
    
    def get_components(self):
        """Return list of clusters (each cluster is a list of elements)."""
        components = {}
        for e in self.parent:
            root = self.find(e)
            if root not in components:
                components[root] = []
            components[root].append(e)
        return list(components.values())


def _parse_pgvector_string(vec_str: str) -> list[float]:
    """Parse pgvector string representation into list of floats.
    
    Format: "[0.1,0.2,0.3,...] "
    """
    if isinstance(vec_str, list):
        return vec_str  # Already a list
    if isinstance(vec_str, str):
        # Strip brackets and split on comma
        vec_str = vec_str.strip()
        if vec_str.startswith('[') and vec_str.endswith(']'):
            vec_str = vec_str[1:-1]
        return [float(x.strip()) for x in vec_str.split(',') if x.strip()]
    raise TypeError(f"Cannot parse embedding of type {type(vec_str)}")



# Global flag to track if pgvector is registered
_pgvector_registered = False

def _ensure_pgvector_registered():
    """Lazy registration of pgvector type. Called on first use."""
    global _pgvector_registered
    if not _pgvector_registered:
        try:
            from pgvector.psycopg2 import register_vector
            pool = _get_connection_pool()
            conn = pool.getconn()
            try:
                register_vector(conn)
                _pgvector_registered = True
            finally:
                pool.putconn(conn)
        except ImportError:
            # pgvector not installed, will use fallback parsing
            _pgvector_registered = True  # Mark as "handled" to avoid retry

def find_clusters(
    tenant_id: str,
    agent_id: str,
    role_scope: str = "public",
    recency_window_hours_min: int = 48,
    recency_window_hours_max: int = 720,  # 30 days default
    similarity_threshold: float = 0.78,
    min_cluster_size: int = 3,
    max_cluster_size: int = 25,
) -> list[Cluster]:
    """
    Find clusters of related atom memories suitable for synthesis.
    
    Args:
        tenant_id: Tenant UUID
        agent_id: Agent identifier within tenant
        role_scope: Role visibility scope (currently unused; reserved for Phase 2.5)
        recency_window_hours_min: Minimum age in hours (default 48)
        recency_window_hours_max: Maximum age in hours (default 720 = 30 days)
        similarity_threshold: Cosine similarity threshold (default 0.78)
        min_cluster_size: Minimum atoms per cluster (default 3)
        max_cluster_size: Maximum atoms per cluster (default 25)
    
    Returns:
        List of Cluster objects, sorted by cluster size descending.
        Returns empty list if no clusters meet criteria.
    
    Raises:
        RuntimeError: If embedding dimension mismatch detected or DB error occurs
    """
    # Phase 1: pgvector registration
    phase_start = time.perf_counter()
    _ensure_pgvector_registered()
    set_tenant_context(tenant_id)
    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "clustering.pgvector_registration",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
    }))
    
    # Phase 2: Query candidate atoms
    phase_start = time.perf_counter()
    candidate_query = f"""
        SELECT id, embedding, headline, full_content, created_at
        FROM memory_service.memories
        WHERE tenant_id = %s
          AND agent_id = %s
          AND memory_type IN ('fact', 'preference', 'instruction', 'event', 'correction', 'identity')
          AND is_pinned IS NOT TRUE
          AND created_at < NOW() - INTERVAL '{recency_window_hours_min} hours'
          AND created_at > NOW() - INTERVAL '{recency_window_hours_max} hours'
          AND (redaction_state IS NULL OR redaction_state = 'active')
          AND embedding IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 5000
    """
    
    candidates = _db_execute_rows(
        candidate_query,
        (tenant_id, agent_id),
        tenant_id=tenant_id
    )
    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "clustering.candidate_query",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
        "candidate_count": len(candidates),
    }))
    
    if len(candidates) < min_cluster_size:
        return []
    
    # Phase 3: Parse embeddings and build lookup maps
    phase_start = time.perf_counter()
    candidate_ids = [row[0] for row in candidates]
    id_to_embedding = {}
    for row in candidates:
        emb = row[1]
        # Handle both list and string representations
        if isinstance(emb, str):
            emb = _parse_pgvector_string(emb)
        id_to_embedding[row[0]] = emb
    
    id_to_headline = {row[0]: row[2] for row in candidates}
    id_to_created_at = {row[0]: row[4] for row in candidates}
    
    # Verify embedding dimensions
    embedding_dims = set()
    for emb in id_to_embedding.values():
        if emb is not None:
            embedding_dims.add(len(emb))
    
    if len(embedding_dims) > 1:
        raise RuntimeError(
            f"Embedding dimension mismatch detected: {embedding_dims}. "
            f"Expected all embeddings to be 384-dimensional. "
            f"Mixed dimensions require migration."
        )
    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "clustering.embedding_parsing",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
    }))
    
    # Phase 4: Compute pairwise similarities using batched HNSW KNN queries
    # PLATFORM CONSTRAINT: pgvector 0.8.1 on DO Managed PG cannot route filtered KNN
    # through HNSW index (planner cost-misestimation). Batched pure KNN queries guarantee
    # HNSW usage (~1.6ms each). Post-filter in Python.
    # TODO: When DO offers pgvector >=0.9.0, revert to single-query LATERAL + SET LOCAL
    # hnsw.iterative_scan pattern. See docs/CP-SYNTHESIS-PERF-PHASE4-RESULTS.md.
    phase_start = time.perf_counter()

    # Acquire single connection for all queries (reusing connection pool)
    from src.storage_multitenant import _get_connection_pool
    pool = _get_connection_pool()
    conn = pool.getconn()

    try:
        cursor = conn.cursor()
        set_tenant_context(tenant_id)  # Already set, but ensure it's active

        # Pure KNN query: minimal WHERE predicates → HNSW index used
        knn_query = """
            SELECT id, embedding, created_at, memory_type, is_pinned, redaction_state,
                   1 - (embedding <=> %s) AS similarity
            FROM memory_service.memories
            WHERE tenant_id = %s
              AND agent_id = %s
              AND id != %s
              AND embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT 50
        """

        similarities = []
        failed_atoms = []
        knn_batch_start = time.perf_counter()

        # Convert to set for O(1) membership checks in post-filter
        candidate_ids_set = set(candidate_ids)

        for idx, candidate_id in enumerate(candidate_ids):
            candidate_emb = id_to_embedding[candidate_id]

            # Log progress every 500 atoms
            if idx > 0 and idx % 500 == 0:
                elapsed_ms = int((time.perf_counter() - knn_batch_start) * 1000)
                perf_logger.info(json.dumps({
                    "metric": "synthesis_perf",
                    "phase": "clustering.knn_batch_progress",
                    "atoms_processed": idx,
                    "total_atoms": len(candidate_ids),
                    "elapsed_ms": elapsed_ms,
                    "tenant_id": tenant_id,
                }))

            try:
                # Execute KNN query for this candidate
                cursor.execute(
                    knn_query,
                    (candidate_emb, tenant_id, agent_id, candidate_id, candidate_emb)
                )
                neighbors = cursor.fetchall()

                # Post-filter in Python: recency, type, status, pinned, redaction
                # Compute recency window bounds once per batch (not per neighbor)
                now = datetime.datetime.now(datetime.timezone.utc)
                min_age = datetime.timedelta(hours=recency_window_hours_min)
                max_age = datetime.timedelta(hours=recency_window_hours_max)

                for neighbor_row in neighbors:
                    neighbor_id, neighbor_emb, neighbor_created_at, neighbor_type, \
                        neighbor_pinned, neighbor_redaction, similarity = neighbor_row

                    # Apply same filters as candidate query
                    # Recency window check

                    if not (neighbor_created_at < (now - min_age) and
                            neighbor_created_at > (now - max_age)):
                        continue

                    # Memory type check
                    if neighbor_type not in ('fact', 'preference', 'instruction',
                                            'event', 'correction', 'identity'):
                        continue

                    # Pinned check
                    if neighbor_pinned is True:
                        continue

                    # Redaction state check
                    if neighbor_redaction is not None and neighbor_redaction != 'active':
                        continue

                    # Similarity threshold check
                    if similarity < similarity_threshold:
                        continue

                    # Candidate set membership: neighbor must also be a candidate
                    # (original query had b.id = ANY(candidates))
                    if neighbor_id not in candidate_ids_set:
                        continue

                    # Symmetry dedup: only keep pairs where candidate_id < neighbor_id
                    if candidate_id < neighbor_id:
                        similarities.append((candidate_id, neighbor_id, similarity))

            except Exception as e:
                failed_atoms.append((candidate_id, str(e)))
                perf_logger.warning(json.dumps({
                    "metric": "synthesis_perf",
                    "phase": "clustering.knn_query_failed",
                    "candidate_id": str(candidate_id),
                    "error": str(e),
                    "tenant_id": tenant_id,
                }))

                # Abort if >5% of atoms failed
                if len(failed_atoms) > len(candidate_ids) * 0.05:
                    raise RuntimeError(
                        f"KNN batch failed for {len(failed_atoms)} atoms "
                        f"(>{len(candidate_ids) * 0.05:.0f}, exceeds 5% threshold). "
                        f"First error: {failed_atoms[0]}"
                    )

        knn_batch_duration_ms = int((time.perf_counter() - knn_batch_start) * 1000)

        # Log final batch stats
        perf_logger.info(json.dumps({
            "metric": "synthesis_perf",
            "phase": "clustering.knn_batch_total",
            "duration_ms": knn_batch_duration_ms,
            "atoms_processed": len(candidate_ids),
            "failed_atoms": len(failed_atoms),
            "pairs_found": len(similarities),
            "tenant_id": tenant_id,
        }))

        cursor.close()

    finally:
        # Return connection to pool
        pool.putconn(conn)

    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "clustering.similarity_computation",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
        "similarity_pair_count": len(similarities),
    }))
    
    # Phase 5: Build neighbor graph and cluster with union-find
    phase_start = time.perf_counter()
    dsu = _UnionFind(candidate_ids)
    
    for source_id, neighbor_id, sim in similarities:
        dsu.union(source_id, neighbor_id)
    
    components = dsu.get_components()
    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "clustering.union_find_clustering",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
        "component_count": len(components),
    }))
    
    # Phase 6: Filter clusters by size
    phase_start = time.perf_counter()
    valid_clusters = [
        comp for comp in components
        if min_cluster_size <= len(comp) <= max_cluster_size
    ]
    
    # Handle over-size clusters (split with k-means if needed)
    final_clusters = []
    for comp in valid_clusters:
        if len(comp) > max_cluster_size:
            # Split large cluster
            final_clusters.extend(_split_cluster(comp, id_to_embedding, max_cluster_size))
        else:
            final_clusters.append(comp)
    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "clustering.cluster_filtering",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
        "valid_cluster_count": len(valid_clusters),
        "final_cluster_count": len(final_clusters),
    }))
    
    # Phase 7: Compute centroid and signature for each cluster
    phase_start = time.perf_counter()
    result_clusters = []
    for cluster_ids in final_clusters:
        # Compute centroid embedding
        embeddings = [id_to_embedding[cid] for cid in cluster_ids]
        centroid = _compute_centroid(embeddings)
        
        # Compute cluster signature (top 3 most recent headlines)
        sorted_by_recency = sorted(
            cluster_ids,
            key=lambda cid: id_to_created_at[cid],
            reverse=True
        )
        top_headlines = [id_to_headline[cid] for cid in sorted_by_recency[:3]]
        signature = "; ".join(top_headlines)
        
        result_clusters.append(Cluster(
            memory_ids=cluster_ids,
            centroid_embedding=centroid,
            cluster_signature=signature
        ))
    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "clustering.centroid_and_signature",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
    }))
    
    # Phase 8: Sort by cluster size descending
    phase_start = time.perf_counter()
    result_clusters.sort(key=lambda c: len(c.memory_ids), reverse=True)
    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "clustering.sorting",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
    }))
    
    return result_clusters


def _compute_centroid(embeddings: list[list[float]]) -> list[float]:
    """Compute mean of embeddings and normalize."""
    if not embeddings:
        return []
    
    dim = len(embeddings[0])
    centroid = [0.0] * dim
    
    for emb in embeddings:
        for i in range(dim):
            centroid[i] += emb[i]
    
    # Mean
    for i in range(dim):
        centroid[i] /= len(embeddings)
    
    # Normalize
    magnitude = sum(x * x for x in centroid) ** 0.5
    if magnitude > 0:
        centroid = [x / magnitude for x in centroid]
    
    return centroid


def _split_cluster(
    cluster_ids: list[uuid.UUID],
    id_to_embedding: dict[uuid.UUID, list[float]],
    max_cluster_size: int
) -> list[list[uuid.UUID]]:
    """Split over-size cluster using k-means.
    
    Uses scipy.cluster.vq.kmeans if available, otherwise halts.
    """
    import math
    
    try:
        import numpy as np
        from scipy.cluster.vq import kmeans, vq
    except ImportError:
        raise RuntimeError(
            f"Cluster size {len(cluster_ids)} exceeds max_cluster_size {max_cluster_size}. "
            f"scipy is required for k-means splitting but is not installed. "
            f"This is a HALT condition per scope. Install scipy or adjust max_cluster_size."
        )
    
    k = math.ceil(len(cluster_ids) / max_cluster_size)
    
    # Prepare embeddings matrix
    embeddings_matrix = np.array([id_to_embedding[cid] for cid in cluster_ids])
    
    # Run k-means
    centroids, _ = kmeans(embeddings_matrix, k)
    labels, _ = vq(embeddings_matrix, centroids)
    
    # Group by label
    split_clusters = [[] for _ in range(k)]
    for idx, label in enumerate(labels):
        split_clusters[label].append(cluster_ids[idx])
    
    # Filter out empty clusters
    return [sc for sc in split_clusters if len(sc) > 0]
