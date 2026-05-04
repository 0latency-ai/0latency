"""Multi-agent consensus orchestration for synthesis (CP8 Phase 3).

Calls writer.synthesize_cluster(persist=False) N times with distinct
agent contexts and returns N candidate synthesis dicts. Merging is in Stage 04;
persistence of the merged consensus row is also in Stage 04.

Tier-gating (Enterprise-only) is enforced upstream in tier_gates.py / the
caller — this orchestrator assumes consensus has already been deemed appropriate.

See CHECKPOINT-8-SCOPE-v3.md Phase 3 Tasks 1-3 for design context.

Actual audit function signature (from writer.py):
_write_audit_event(tenant_id, target_memory_id, event_type, actor, event_payload) -> UUID
Note: does not take db_conn parameter; uses internal connection pool.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from .writer import synthesize_cluster, _write_audit_event

logger = logging.getLogger("synthesis.consensus")

# Default consensus agent count for Enterprise tier.
# Locked at 3 per CHECKPOINT-8-SCOPE-v3.md Phase 3.
CONSENSUS_AGENT_COUNT: int = 3


def gather_agent_ids_from_cluster(
    cluster_memory_ids: List[str],
    db_conn,
) -> List[str]:
    """Return distinct agent_id values present in the cluster's source memories.

    Args:
        cluster_memory_ids: list of memory uuids that compose the cluster.
        db_conn: live psycopg2 connection.

    Returns:
        Sorted list of distinct, non-null agent_ids.
    """
    if not cluster_memory_ids:
        return []

    cur = db_conn.cursor()
    try:
        cur.execute(
            "SELECT DISTINCT agent_id "
            "FROM memory_service.memories "
            "WHERE id = ANY(%s::uuid[]) AND agent_id IS NOT NULL "
            "ORDER BY agent_id",
            (cluster_memory_ids,),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        cur.close()


def select_consensus_agents(
    available_agents: List[str],
    n_wanted: int = CONSENSUS_AGENT_COUNT,
) -> List[str]:
    """Deterministic selection: alphabetical, first N.

    Future variants may stratify by recency or contribution weight; for now,
    determinism is the priority — same cluster + same agent set → same selection.
    """
    return sorted(available_agents)[:n_wanted]


def run_consensus(
    tenant_id: str,
    cluster_id: str,
    cluster_memory_ids: List[str],
    role_tag: str,
    db_conn,
    n_agents: int = CONSENSUS_AGENT_COUNT,
) -> Dict[str, Any]:
    """Run N-agent consensus over a cluster.

    For each selected agent, calls writer.synthesize_cluster(persist=False)
    and collects the candidate dict. Per-candidate failures are caught and logged;
    the run continues with remaining agents.

    Returns:
        {
          "consensus_eligible": bool,
          "candidates": List[Dict] | None,        # populated when eligible
          "fallback_reason": str | None,           # populated when not eligible
          "agents_attempted": List[str],           # which agents we tried
          "agents_succeeded": List[str],           # which produced a candidate
          "cluster_id": str,
        }

    The caller (Stage 04 merger / Stage 05 tier-gating) decides what to do
    with the result — merge if eligible, fall back to single-agent if not.
    """
    from dataclasses import dataclass

    @dataclass
    class Cluster:
        memory_ids: List[UUID]
        cluster_id: str

    # Convert string IDs to UUIDs for writer.py
    memory_uuids = [UUID(mid) for mid in cluster_memory_ids]
    cluster_obj = Cluster(memory_ids=memory_uuids, cluster_id=cluster_id)

    available_agents = gather_agent_ids_from_cluster(cluster_memory_ids, db_conn)
    distinct_count = len(available_agents)

    # Edge case 1: <2 distinct agents → consensus is meaningless
    if distinct_count < 2:
        _write_audit_event(
            tenant_id=tenant_id,
            target_memory_id=None,
            event_type="consensus_skipped_insufficient_agents",
            actor="system",
            event_payload={
                "cluster_id": cluster_id,
                "role_tag": role_tag,
                "agents_found": distinct_count,
                "agents_required_min": 2,
            },
        )
        logger.info(
            "consensus.skipped cluster=%s agents=%d reason=insufficient_distinct_agents",
            cluster_id, distinct_count,
        )
        return {
            "consensus_eligible": False,
            "candidates": None,
            "fallback_reason": f"only_{distinct_count}_distinct_agents",
            "agents_attempted": [],
            "agents_succeeded": [],
            "cluster_id": cluster_id,
        }

    selected = select_consensus_agents(available_agents, n_wanted=n_agents)
    logger.info(
        "consensus.starting cluster=%s role=%s agents=%s",
        cluster_id, role_tag, selected,
    )

    _write_audit_event(
        tenant_id=tenant_id,
        target_memory_id=None,
        event_type="consensus_run_started",
        actor="system",
        event_payload={
            "cluster_id": cluster_id,
            "role_tag": role_tag,
            "agents_selected": selected,
            "n_agents_target": n_agents,
            "distinct_agents_available": distinct_count,
        },
    )

    candidates: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []

    for agent_id in selected:
        try:
            candidate = synthesize_cluster(
                cluster=cluster_obj,
                tenant_id=tenant_id,
                agent_id=agent_id,
                role_tag=role_tag,
                persist=False,  # Phase 3: candidates are NOT persisted directly
            )
            candidates.append(candidate)
            logger.info(
                "consensus.candidate_ok agent=%s cluster=%s tokens=%s",
                agent_id, cluster_id, candidate.get("tokens_used", "?"),
            )
        except Exception as exc:
            # Per-candidate failures don't kill the run.
            failures.append({"agent_id": agent_id, "error": repr(exc)})
            logger.warning(
                "consensus.candidate_failed agent=%s cluster=%s error=%r",
                agent_id, cluster_id, exc,
            )

    # Edge case 2: <2 candidates succeeded → merger has nothing meaningful to do
    if len(candidates) < 2:
        _write_audit_event(
            tenant_id=tenant_id,
            target_memory_id=None,
            event_type="consensus_failed_insufficient_candidates",
            actor="system",
            event_payload={
                "cluster_id": cluster_id,
                "role_tag": role_tag,
                "agents_attempted": selected,
                "candidates_succeeded": len(candidates),
                "failures": failures,
            },
        )
        logger.warning(
            "consensus.failed cluster=%s candidates_succeeded=%d failures=%d",
            cluster_id, len(candidates), len(failures),
        )
        return {
            "consensus_eligible": False,
            "candidates": candidates if candidates else None,
            "fallback_reason": f"only_{len(candidates)}_candidates_succeeded",
            "agents_attempted": selected,
            "agents_succeeded": [c.get("agent_id") for c in candidates],
            "cluster_id": cluster_id,
        }

    return {
        "consensus_eligible": True,
        "candidates": candidates,
        "fallback_reason": None,
        "agents_attempted": selected,
        "agents_succeeded": [c.get("agent_id") for c in candidates],
        "cluster_id": cluster_id,
    }
