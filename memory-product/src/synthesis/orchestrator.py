"""
CP8 Phase 2 Tasks 5+6 — Synthesis Orchestrator

Shared orchestration layer for manual trigger (T5) and cron (T6).

Cost-ceiling design:
- Pre-check: clusters_found==0 → status='skipped', no LLM calls
- Hard ceiling: max_clusters per invocation (default 5, max 10)
- Each synthesize_cluster call is independently rate-limited

Triggered-by tagging:
- 'cron': systemd timer-driven daily run
- 'manual_api': POST /synthesis/run
- 'manual_mcp': MCP memory_synthesize tool (Phase 4)

Partial-run semantics:
- If cluster 1 succeeds and cluster 2 hits rate limit, cluster 1's synthesis row persists
- job.result contains partial synthesis_ids list + rate_limited=True flag
- Next run will find different clusters (already-synthesized atoms filtered by recency)
"""

import time
import logging
from typing import Optional
from uuid import UUID

from src.synthesis.clustering import find_clusters
# Tier-aware dispatcher: routes to consensus on Enterprise, single-agent on Scale/Pro.
# Aliased to avoid name collision with the writer's same-named function.
from src.synthesis.tier_gates import synthesize_cluster as tier_gated_synthesize
from src.synthesis.jobs import (
    create_job,
    start_job,
    complete_job,
    fail_job,
)

# Performance profiling logger
perf_logger = logging.getLogger("synthesis.perf")



from dataclasses import dataclass
from typing import Optional, Any
from uuid import UUID


@dataclass
class _TierDispatchResult:
    """Adapter that gives tier_gates dispatcher results the same shape the
    orchestrator loop body expects (mimics writer.SynthesisResult fields).
    """
    success: bool
    synthesis_id: Optional[Any]   # uuid string or None
    cluster_size: int
    tokens_used: int
    rejected_reason: Optional[str]
    path: str                      # "consensus" | "single_agent" | "blocked"


def _adapt_dispatch_result(dispatch_result: dict, cluster_size: int) -> _TierDispatchResult:
    """Translate tier_gates.synthesize_cluster's dict return into the
    SynthesisResult-shaped object the orchestrator loop iterates over.

    Failure modes mapped to rejected_reason:
    - tier_blocked (Free tier): "tier_blocked"
    - consensus path with no synthesis_id: "consensus_failure"
    - single_agent path with no synthesis_id: derived from single_agent_result.rejected_reason
      if available, else "single_agent_failure"
    """
    path = dispatch_result.get("path", "unknown")
    if dispatch_result.get("tier_blocked"):
        return _TierDispatchResult(
            success=False,
            synthesis_id=None,
            cluster_size=cluster_size,
            tokens_used=0,
            rejected_reason="tier_blocked",
            path="blocked",
        )

    synthesis_id = dispatch_result.get("synthesis_id")
    if path == "consensus":
        consensus_result = dispatch_result.get("consensus_result") or {}
        tokens = int(consensus_result.get("total_tokens_used", 0))
        if synthesis_id is None:
            return _TierDispatchResult(
                success=False,
                synthesis_id=None,
                cluster_size=cluster_size,
                tokens_used=tokens,
                rejected_reason="consensus_failure",
                path=path,
            )
        return _TierDispatchResult(
            success=True,
            synthesis_id=synthesis_id,
            cluster_size=cluster_size,
            tokens_used=tokens,
            rejected_reason=None,
            path=path,
        )

    # single_agent path
    sa_result = dispatch_result.get("single_agent_result") or {}
    tokens = int(sa_result.get("tokens_used", 0))
    if synthesis_id is None:
        # Single-agent failure — extract rejected_reason if possible
        rejected = None
        if hasattr(sa_result, "rejected_reason"):
            rejected = sa_result.rejected_reason
        elif isinstance(sa_result, dict):
            rejected = sa_result.get("rejected_reason")
        return _TierDispatchResult(
            success=False,
            synthesis_id=None,
            cluster_size=cluster_size,
            tokens_used=tokens,
            rejected_reason=rejected or "single_agent_failure",
            path=path,
        )
    return _TierDispatchResult(
        success=True,
        synthesis_id=synthesis_id,
        cluster_size=cluster_size,
        tokens_used=tokens,
        rejected_reason=None,
        path=path,
    )


def run_synthesis_for_tenant(
    tenant_id: str,
    agent_id: str,
    role_scope: str = "public",
    force: bool = False,
    max_clusters: int = 5,
    triggered_by: str = "cron",
) -> dict:
    """
    Orchestrate one synthesis run for a tenant.

    Steps:
    1. Create synthesis_jobs row (status='queued')
    2. Mark started; find_clusters
    3. Pre-check: if clusters_found==0, skip (no LLM cost)
    4. For each cluster (up to max_clusters): synthesize_cluster
    5. Mark job succeeded/failed; return summary

    Args:
        tenant_id: Tenant UUID
        agent_id: Agent identifier
        role_scope: Role visibility filter (default: "public")
        force: Bypass recency pre-check if True (default: False)
        max_clusters: Max clusters to synthesize per run (default: 5, capped at 10)
        triggered_by: Source of trigger ('cron' | 'manual_api' | 'manual_mcp')

    Returns:
        Summary dict with job_id, status, counts, synthesis_ids, etc.
    """
    start_time = time.perf_counter()
    start_time_wall = time.time()
    synthesis_id_for_logging = None  # Will be set after first successful cluster

    # Cap max_clusters at 10 server-side
    max_clusters = min(max_clusters, 10)

    # Step 1: Create job
    phase_start = time.perf_counter()
    job_id = create_job(
        tenant_id=tenant_id,
        agent_id=agent_id,
        job_type="synthesis_run",
        payload={
            "role_scope": role_scope,
            "max_clusters": max_clusters,
            "triggered_by": triggered_by,
        }
    )
    phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
    import json
    perf_logger.info(json.dumps({
        "metric": "synthesis_perf",
        "phase": "job_create",
        "duration_ms": phase_duration_ms,
        "tenant_id": tenant_id,
        "synthesis_id": None,
    }))

    try:
        # Step 2: Mark started
        start_job(job_id)

        # Find clusters
        phase_start = time.perf_counter()
        clusters = find_clusters(
            tenant_id=tenant_id,
            agent_id=agent_id,
            role_scope=role_scope,
            # Use default recency windows from clustering.py unless force=True
            # force=True means ignore recency entirely (for testing/manual runs)
        )
        phase_duration_ms = int((time.perf_counter() - phase_start) * 1000)
        perf_logger.info(json.dumps({
            "metric": "synthesis_perf",
            "phase": "clustering",
            "duration_ms": phase_duration_ms,
            "tenant_id": tenant_id,
            "synthesis_id": None,
            "clusters_found": len(clusters),
        }))

        clusters_found = len(clusters)

        # Step 3: Pre-check gate
        if clusters_found == 0:
            # No clusters → skip, no LLM cost
            end_time = time.perf_counter()
            total_duration_ms = int((end_time - start_time) * 1000)

            perf_logger.info(json.dumps({
                "metric": "synthesis_perf",
                "phase": "total",
                "duration_ms": total_duration_ms,
                "tenant_id": tenant_id,
                "synthesis_id": None,
            }))

            result = {
                "job_id": job_id,
                "status": "skipped",
                "clusters_found": 0,
                "clusters_synthesized": 0,
                "synthesis_ids": [],
                "rate_limited": False,
                "tokens_used_total": 0,
                "duration_ms": int((time.perf_counter() - start_time_wall) * 1000),
            }

            complete_job(job_id, result)
            return result

        # Step 4: Synthesize clusters (up to max_clusters)
        synthesis_ids = []
        tokens_used_total = 0
        rate_limited = False
        clusters_to_process = clusters[:max_clusters]

        for idx, cluster in enumerate(clusters_to_process):
            try:
                cluster_phase_start = time.perf_counter()
                # Route via tier-aware dispatcher:
                # - Enterprise → consensus (N agents, majority_vote merger, persist)
                # - Scale/Pro → single-agent (writer.synthesize_cluster, persist=True)
                # - Free → blocked (returns tier_blocked=True)
                from storage_multitenant import _get_connection_pool
                pool = _get_connection_pool()
                conn = pool.getconn()
                try:
                    cluster_memory_ids_str = [str(mid) for mid in cluster.memory_ids]
                    dispatch_result = tier_gated_synthesize(
                        tenant_id=tenant_id,
                        cluster_id=cluster.cluster_id,
                        cluster_memory_ids=cluster_memory_ids_str,
                        role_tag=role_scope,
                        db_conn=conn,
                    )
                finally:
                    pool.putconn(conn)
                synth_result = _adapt_dispatch_result(dispatch_result, cluster_size=len(cluster.memory_ids))
                cluster_phase_duration_ms = int((time.perf_counter() - cluster_phase_start) * 1000)

                if synth_result.success:
                    synthesis_ids.append(synth_result.synthesis_id)
                    tokens_used_total += synth_result.tokens_used
                    if synthesis_id_for_logging is None:
                        synthesis_id_for_logging = str(synth_result.synthesis_id)

                    perf_logger.info(json.dumps({
                        "metric": "synthesis_perf",
                        "phase": "cluster_synthesis",
                        "duration_ms": cluster_phase_duration_ms,
                        "tenant_id": tenant_id,
                        "synthesis_id": str(synth_result.synthesis_id),
                        "cluster_idx": idx,
                        "cluster_size": synth_result.cluster_size,
                    }))
                elif synth_result.rejected_reason == "rate_limited":
                    # Hit quota mid-run - mark flag and stop processing
                    rate_limited = True
                    break
                # Other failures (validation_failed, llm_error) are logged but don't stop the run

            except Exception as e:
                # Log error but continue to next cluster
                import logging
                logging.getLogger("synthesis.orchestrator").error(
                    f"Cluster synthesis failed: {e}", exc_info=True
                )
                continue

        # Step 5: Mark job succeeded
        end_time = time.perf_counter()
        total_duration_ms = int((end_time - start_time) * 1000)

        perf_logger.info(json.dumps({
            "metric": "synthesis_perf",
            "phase": "total",
            "duration_ms": total_duration_ms,
            "tenant_id": tenant_id,
            "synthesis_id": synthesis_id_for_logging,
        }))

        result = {
            "job_id": job_id,
            "status": "succeeded",
            "clusters_found": clusters_found,
            "clusters_synthesized": len(synthesis_ids),
            "synthesis_ids": [str(id) for id in synthesis_ids],
            "rate_limited": rate_limited,
            "tokens_used_total": tokens_used_total,
            "duration_ms": int((time.perf_counter() - start_time_wall) * 1000),
        }

        complete_job(job_id, result)
        return result

    except Exception as e:
        # Job-level failure
        import logging
        logging.getLogger("synthesis.orchestrator").error(
            f"Synthesis run failed: {e}", exc_info=True
        )

        end_time = time.perf_counter()
        total_duration_ms = int((end_time - start_time) * 1000)

        perf_logger.info(json.dumps({
            "metric": "synthesis_perf",
            "phase": "total",
            "duration_ms": total_duration_ms,
            "tenant_id": tenant_id,
            "synthesis_id": None,
            "error": True,
        }))

        result = {
            "job_id": job_id,
            "status": "failed",
            "clusters_found": 0,
            "clusters_synthesized": 0,
            "synthesis_ids": [],
            "rate_limited": False,
            "tokens_used_total": 0,
            "duration_ms": int((time.perf_counter() - start_time_wall) * 1000),
            "error": str(e)[:4000],  # Truncate to job error column limit
        }

        fail_job(job_id, str(e))
        return result
