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
import math
import re
import uuid
import json
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from collections import Counter, defaultdict

from .writer import synthesize_cluster, _write_audit_event
from src.storage_multitenant import _db_execute_rows, set_tenant_context

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

    # NEW: merge candidates and persist consensus row
    merge_result = merge_candidates(candidates)

    if not merge_result["merge_succeeded"]:
        _write_audit_event(
            tenant_id=tenant_id,
            target_memory_id=None,
            event_type="consensus_merge_failed",
            actor="system",
            event_payload={
                "cluster_id": cluster_id,
                "role_tag": role_tag,
                "reason": merge_result["reason"],
                "n_candidates": merge_result["n_candidates"],
                "rejected_claim_count": len(merge_result["rejected_claims"]),
            },
        )
        return {
            "consensus_eligible": True,
            "merge_succeeded": False,
            "candidates": candidates,
            "merge_result": merge_result,
            "fallback_reason": merge_result["reason"],
            "agents_attempted": selected,
            "agents_succeeded": [c.get("agent_id") for c in candidates],
            "cluster_id": cluster_id,
            "consensus_synthesis_id": None,
        }

    # Persist the merged consensus row
    consensus_id = persist_consensus_row(
        tenant_id=tenant_id,
        merge_result=merge_result,
        db_conn=db_conn,
        consensus_method="majority_vote",
        synthesis_prompt_version=candidates[0].get("synthesis_prompt_version") if candidates else None,
    )

    return {
        "consensus_eligible": True,
        "merge_succeeded": True,
        "candidates": candidates,
        "merge_result": merge_result,
        "consensus_synthesis_id": consensus_id,
        "fallback_reason": None,
        "agents_attempted": selected,
        "agents_succeeded": [c.get("agent_id") for c in candidates],
        "cluster_id": cluster_id,
    }


# ============================================================
# STAGE 04: Claim-level majority_vote merger
# ============================================================

# Claim normalization regex: collapse internal whitespace
_WS_RE = re.compile(r"\s+")
# Sentence boundary: . ! ? followed by space-or-end
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _normalize_claim(claim: str) -> str:
    """Lowercase, strip, collapse whitespace, drop trailing punctuation."""
    s = claim.strip().lower()
    s = _WS_RE.sub(" ", s)
    return s.rstrip(".!?,;:")


def _decompose_to_claims(full_content: str) -> List[str]:
    """Split full_content into sentence-level claims.

    v1 sentence-boundary split. Empty/whitespace claims dropped.
    Order is preserved within candidate (used for headline-from-candidate selection).
    """
    if not full_content:
        return []
    parts = _SENT_RE.split(full_content.strip())
    return [p.strip() for p in parts if p.strip()]


def merge_candidates(
    candidates: List[Dict[str, Any]],
    majority_threshold: Optional[int] = None,
) -> Dict[str, Any]:
    """Merge N candidate syntheses by majority vote on claim-level.

    Args:
        candidates: list of candidate dicts from run_consensus
        majority_threshold: minimum support count for a claim to be retained.
                            Default: ceil(len(candidates) / 2). With 3 candidates → 2.

    Returns merge_result dict with merge_succeeded, merged_full_content, etc.
    """
    n = len(candidates)
    threshold = majority_threshold if majority_threshold is not None else math.ceil(n / 2)

    # Decompose each candidate to claims
    supporters_by_norm: Dict[str, List[str]] = defaultdict(list)
    original_by_norm: Dict[str, str] = {}
    claims_by_agent: Dict[str, List[str]] = {}

    for cand in candidates:
        agent_id = cand.get("agent_id", "<unknown>")
        decomposed = _decompose_to_claims(cand.get("full_content", "") or "")
        seen_in_this_candidate: set = set()
        norm_list_for_agent: List[str] = []
        for claim_orig in decomposed:
            norm = _normalize_claim(claim_orig)
            if not norm or norm in seen_in_this_candidate:
                continue
            seen_in_this_candidate.add(norm)
            supporters_by_norm[norm].append(agent_id)
            if norm not in original_by_norm:
                original_by_norm[norm] = claim_orig.strip()
            norm_list_for_agent.append(norm)
        claims_by_agent[agent_id] = norm_list_for_agent

    # Partition into retained / rejected
    retained: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for norm, supporters in supporters_by_norm.items():
        entry = {
            "claim": original_by_norm[norm],
            "claim_normalized": norm,
            "supporters": list(supporters),
            "support_count": len(supporters),
        }
        if len(supporters) >= threshold:
            retained.append(entry)
        else:
            rejected.append(entry)

    if not retained:
        return {
            "merge_succeeded": False,
            "merged_full_content": "",
            "merged_headline": "",
            "merged_context": "",
            "contributing_agents": [],
            "source_memory_ids": [],
            "parent_memory_ids": list(candidates[0].get("parent_memory_ids", [])) if candidates else [],
            "role_tag": candidates[0].get("role_tag") if candidates else None,
            "cluster_id": candidates[0].get("cluster_id") if candidates else None,
            "retained_claims": [],
            "rejected_claims": rejected,
            "n_candidates": n,
            "majority_threshold": threshold,
            "reason": "no_majority_claims",
        }

    # Determine highest-contributor candidate
    retained_norms = {r["claim_normalized"] for r in retained}
    contribution_counts: Counter = Counter()
    for cand in candidates:
        agent_id = cand.get("agent_id")
        contributed = sum(1 for n in claims_by_agent.get(agent_id, []) if n in retained_norms)
        contribution_counts[agent_id] = contributed

    def _rank_key(cand):
        a = cand.get("agent_id", "")
        return (-contribution_counts[a], -(cand.get("tokens_used", 0) or 0), a)

    ranked = sorted(candidates, key=_rank_key)
    top_candidate = ranked[0]

    # Reconstruct merged_full_content
    top_agent = top_candidate.get("agent_id")
    top_order = [n for n in claims_by_agent.get(top_agent, []) if n in retained_norms]
    seen = set(top_order)
    tail_order: List[str] = []
    for cand in ranked[1:]:
        for n in claims_by_agent.get(cand.get("agent_id"), []):
            if n in retained_norms and n not in seen:
                tail_order.append(n)
                seen.add(n)
    final_norm_order = top_order + tail_order

    merged_full_content = ". ".join(original_by_norm[n].rstrip(".!?,;:") for n in final_norm_order) + "."

    # contributing_agents
    contributing_agents = sorted({
        agent for r in retained for agent in r["supporters"]
    })

    # source_memory_ids
    contributing_set = set(contributing_agents)
    src_ids: List[str] = []
    seen_src = set()
    for cand in candidates:
        if cand.get("agent_id") not in contributing_set:
            continue
        for sid in (cand.get("source_memory_ids") or []):
            if sid not in seen_src:
                src_ids.append(sid)
                seen_src.add(sid)

    return {
        "merge_succeeded": True,
        "merged_full_content": merged_full_content,
        "merged_headline": top_candidate.get("headline", "") or "",
        "merged_context": top_candidate.get("context", "") or "",
        "contributing_agents": contributing_agents,
        "source_memory_ids": src_ids,
        "parent_memory_ids": list(top_candidate.get("parent_memory_ids", [])),
        "role_tag": top_candidate.get("role_tag"),
        "cluster_id": top_candidate.get("cluster_id"),
        "retained_claims": retained,
        "rejected_claims": rejected,
        "n_candidates": n,
        "majority_threshold": threshold,
        "reason": None,
    }


def persist_consensus_row(
    tenant_id: str,
    merge_result: Dict[str, Any],
    db_conn,
    consensus_method: str = "majority_vote",
    synthesis_prompt_version: Optional[str] = None,
) -> str:
    """INSERT the merged consensus row into memory_service.memories.

    Returns the inserted row's UUID as string.
    """
    if not merge_result.get("merge_succeeded"):
        raise ValueError(f"Cannot persist failed merge: {merge_result.get('reason')}")

    new_id = str(uuid.uuid4())
    
    metadata = {
        "parent_memory_ids": merge_result["parent_memory_ids"],
    }
    
    set_tenant_context(tenant_id)
    
    query = """
        INSERT INTO memory_service.memories (
            id, tenant_id, agent_id, memory_type,
            headline, context, full_content,
            source_memory_ids, role_tag, redaction_state,
            contributing_agents, consensus_method,
            synthesis_prompt_version, synthesis_version,
            is_pinned, metadata
        ) VALUES (
            %s, %s, %s, 'synthesis',
            %s, %s, %s,
            %s::uuid[], %s, 'active',
            %s::text[], %s,
            %s, 1,
            false, %s::jsonb
        )
    """
    
    params = (
        new_id,
        tenant_id,
        "system_consensus",
        (merge_result["merged_headline"] or "Consensus synthesis")[:200],
        merge_result["merged_context"] or merge_result["merged_full_content"][:200],
        merge_result["merged_full_content"],
        merge_result["source_memory_ids"],
        merge_result["role_tag"],
        merge_result["contributing_agents"],
        consensus_method,
        synthesis_prompt_version,
        json.dumps(metadata),
    )
    
    _db_execute_rows(query, params, tenant_id=tenant_id, fetch_results=False)

    # Emit synthesis_written audit event
    _write_audit_event(
        tenant_id=tenant_id,
        target_memory_id=UUID(new_id),
        event_type="synthesis_written",
        actor="system_consensus",
        event_payload={
            "cluster_id": merge_result["cluster_id"],
            "role_tag": merge_result["role_tag"],
            "consensus_method": consensus_method,
            "n_candidates": merge_result["n_candidates"],
            "majority_threshold": merge_result["majority_threshold"],
            "contributing_agents": merge_result["contributing_agents"],
            "retained_claim_count": len(merge_result["retained_claims"]),
            "rejected_claim_count": len(merge_result["rejected_claims"]),
            "synthesis_prompt_version": synthesis_prompt_version,
        },
    )

    return new_id
