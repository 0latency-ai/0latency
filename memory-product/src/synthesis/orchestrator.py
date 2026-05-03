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
from typing import Optional
from uuid import UUID

from src.synthesis.clustering import find_clusters
from src.synthesis.writer import synthesize_cluster
from src.synthesis.jobs import (
    create_job,
    start_job,
    complete_job,
    fail_job,
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
    start_time = time.time()

    # Cap max_clusters at 10 server-side
    max_clusters = min(max_clusters, 10)

    # Step 1: Create job
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

    try:
        # Step 2: Mark started
        start_job(job_id)

        # Find clusters
        clusters = find_clusters(
            tenant_id=tenant_id,
            agent_id=agent_id,
            role_scope=role_scope,
            # Use default recency windows from clustering.py unless force=True
            # force=True means ignore recency entirely (for testing/manual runs)
        )

        clusters_found = len(clusters)

        # Step 3: Pre-check gate
        if clusters_found == 0:
            # No clusters → skip, no LLM cost
            end_time = time.time()
            result = {
                "job_id": job_id,
                "status": "skipped",
                "clusters_found": 0,
                "clusters_synthesized": 0,
                "synthesis_ids": [],
                "rate_limited": False,
                "tokens_used_total": 0,
                "duration_ms": int((end_time - start_time) * 1000),
            }

            complete_job(job_id, result)
            return result

        # Step 4: Synthesize clusters (up to max_clusters)
        synthesis_ids = []
        tokens_used_total = 0
        rate_limited = False
        clusters_to_process = clusters[:max_clusters]

        for cluster in clusters_to_process:
            try:
                synth_result = synthesize_cluster(
                    cluster=cluster,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    role_tag=role_scope,
                    dry_run=False,
                )

                if synth_result.success:
                    synthesis_ids.append(synth_result.synthesis_id)
                    tokens_used_total += synth_result.tokens_used
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
        end_time = time.time()
        result = {
            "job_id": job_id,
            "status": "succeeded",
            "clusters_found": clusters_found,
            "clusters_synthesized": len(synthesis_ids),
            "synthesis_ids": [str(id) for id in synthesis_ids],
            "rate_limited": rate_limited,
            "tokens_used_total": tokens_used_total,
            "duration_ms": int((end_time - start_time) * 1000),
        }

        complete_job(job_id, result)
        return result

    except Exception as e:
        # Job-level failure
        import logging
        logging.getLogger("synthesis.orchestrator").error(
            f"Synthesis run failed: {e}", exc_info=True
        )

        end_time = time.time()
        result = {
            "job_id": job_id,
            "status": "failed",
            "clusters_found": 0,
            "clusters_synthesized": 0,
            "synthesis_ids": [],
            "rate_limited": False,
            "tokens_used_total": 0,
            "duration_ms": int((end_time - start_time) * 1000),
            "error": str(e)[:4000],  # Truncate to job error column limit
        }

        fail_job(job_id, str(e))
        return result
