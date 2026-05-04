"""Synthesis module exports."""

from .consensus import (
    run_consensus,
    gather_agent_ids_from_cluster,
    select_consensus_agents,
    merge_candidates,
    persist_consensus_row,
    CONSENSUS_AGENT_COUNT,
)
from .tier_gates import (
    synthesize_cluster,
    tier_supports_consensus,
    tier_blocked_from_synthesis,
)

__all__ = [
    "run_consensus",
    "gather_agent_ids_from_cluster",
    "select_consensus_agents",
    "merge_candidates",
    "persist_consensus_row",
    "CONSENSUS_AGENT_COUNT",
    "synthesize_cluster",
    "tier_supports_consensus",
    "tier_blocked_from_synthesis",
]
