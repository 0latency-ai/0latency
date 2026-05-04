"""Tier-gating and dispatcher for synthesis (CP8 Phase 3 Task 5).

Determines which synthesis path (multi-agent consensus vs single-agent) to use
based on tenant plan tier. Called by manual-trigger endpoint and cron.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("synthesis.tier_gates")

# Tier sets (based on actual tenant plan values in DB)
CONSENSUS_TIERS = {"enterprise"}
SINGLE_AGENT_TIERS = {"scale", "pro"}
BLOCKED_TIERS = {"free"}


def tier_supports_consensus(plan: Optional[str]) -> bool:
    """Return True iff the plan grants multi-agent consensus access."""
    return (plan or "").lower() in CONSENSUS_TIERS


def tier_blocked_from_synthesis(plan: Optional[str]) -> bool:
    """Return True iff the plan has zero synthesis access (Free tier)."""
    p = (plan or "").lower()
    return (not p) or p in BLOCKED_TIERS


def synthesize_cluster(
    tenant_id: str,
    cluster_id: str,
    cluster_memory_ids: List[str],
    role_tag: str,
    db_conn,
    plan: Optional[str] = None,
) -> Dict[str, Any]:
    """Tier-aware dispatcher.

    - Enterprise: run multi-agent consensus (calls run_consensus → merger → persist).
    - Scale/Pro: single-agent path (calls writer.write_synthesis_for_cluster persist=True).
    - Free / unknown: block.

    If `plan` not provided, looks it up from memory_service.tenants.

    Returns a dispatcher result dict with at least:
        {
          "tier_blocked": bool,
          "path": "consensus" | "single_agent" | "blocked",
          "synthesis_id": str | None,             # populated for both consensus and single_agent
          "consensus_result": dict | None,         # the run_consensus return on consensus path
          "single_agent_result": dict | None,      # the writer return on single_agent path
        }
    """
    # Resolve plan if not provided
    if plan is None:
        cur = db_conn.cursor()
        try:
            cur.execute(
                "SELECT plan FROM memory_service.tenants WHERE id = %s",
                (tenant_id,),
            )
            row = cur.fetchone()
            plan = row[0] if row else None
        finally:
            cur.close()

    if tier_blocked_from_synthesis(plan):
        return {
            "tier_blocked": True,
            "path": "blocked",
            "synthesis_id": None,
            "consensus_result": None,
            "single_agent_result": None,
            "plan": plan,
        }

    if tier_supports_consensus(plan):
        # Lazy import to avoid circular: tier_gates → consensus → writer
        from .consensus import run_consensus
        consensus_result = run_consensus(
            tenant_id=tenant_id,
            cluster_id=cluster_id,
            cluster_memory_ids=cluster_memory_ids,
            role_tag=role_tag,
            db_conn=db_conn,
        )
        return {
            "tier_blocked": False,
            "path": "consensus",
            "synthesis_id": consensus_result.get("consensus_synthesis_id"),
            "consensus_result": consensus_result,
            "single_agent_result": None,
            "plan": plan,
        }

    # Scale / Pro → single-agent
    from .writer import synthesize_cluster as writer_synthesize
    from .consensus import gather_agent_ids_from_cluster
    from dataclasses import dataclass
    from uuid import UUID

    @dataclass
    class Cluster:
        memory_ids: List[UUID]
        cluster_id: str

    # Pick agent from cluster (same logic as consensus orchestrator)
    agents = gather_agent_ids_from_cluster(cluster_memory_ids, db_conn)
    chosen_agent = agents[0] if agents else "system_single_agent"

    # Convert to UUID format for writer
    memory_uuids = [UUID(mid) for mid in cluster_memory_ids]
    cluster_obj = Cluster(memory_ids=memory_uuids, cluster_id=cluster_id)

    single_result = writer_synthesize(
        cluster=cluster_obj,
        tenant_id=tenant_id,
        agent_id=chosen_agent,
        role_tag=role_tag,
        persist=True,   # single-agent path persists directly per Phase 2
    )
    return {
        "tier_blocked": False,
        "path": "single_agent",
        "synthesis_id": single_result.get("id") or single_result.get("inserted_id"),
        "consensus_result": None,
        "single_agent_result": single_result,
        "plan": plan,
    }
