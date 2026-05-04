"""Tier-gating dispatcher tests for synthesize_cluster (Stage 05)."""
from unittest.mock import MagicMock, patch
import pytest
from src.synthesis.tier_gates import (
    synthesize_cluster,
    tier_supports_consensus,
    tier_blocked_from_synthesis,
)


def test_tier_supports_consensus_enterprise():
    assert tier_supports_consensus("enterprise") is True
    assert tier_supports_consensus("Enterprise") is True
    assert tier_supports_consensus("ENTERPRISE") is True


def test_tier_supports_consensus_others():
    for plan in ["scale", "pro", "free", None, "", "unknown"]:
        assert tier_supports_consensus(plan) is False, f"plan={plan!r}"


def test_tier_blocked_free():
    assert tier_blocked_from_synthesis("free") is True
    assert tier_blocked_from_synthesis(None) is True
    assert tier_blocked_from_synthesis("") is True


def test_tier_not_blocked_paid():
    for plan in ["pro", "scale", "enterprise"]:
        assert tier_blocked_from_synthesis(plan) is False


def test_dispatch_enterprise_calls_consensus():
    fake_db = MagicMock()
    # Patch the lazy import target
    with patch("src.synthesis.consensus.run_consensus") as mock_consensus:
        mock_consensus.return_value = {
            "consensus_eligible": True, "merge_succeeded": True,
            "consensus_synthesis_id": "00000000-0000-0000-0000-deadbeef0001",
            "candidates": [], "merge_result": {}, "fallback_reason": None,
            "agents_attempted": [], "agents_succeeded": [], "cluster_id": "c1",
        }
        result = synthesize_cluster(
            tenant_id="00000000-0000-0000-0000-000000000001",
            cluster_id="c1",
            cluster_memory_ids=["00000000-0000-0000-0000-000000000abc"],
            role_tag="public",
            db_conn=fake_db,
            plan="enterprise",
        )
        mock_consensus.assert_called_once()
        assert result["path"] == "consensus"
        assert result["tier_blocked"] is False
        assert result["synthesis_id"] == "00000000-0000-0000-0000-deadbeef0001"


def test_dispatch_scale_calls_single_agent():
    fake_db = MagicMock()
    fake_cur = MagicMock()
    fake_db.cursor.return_value = fake_cur
    fake_cur.fetchall.return_value = [("agent-only",)]

    with patch("src.synthesis.writer.synthesize_cluster") as mock_writer:
        mock_writer.return_value = {"id": "00000000-0000-0000-0000-feedface0001"}
        result = synthesize_cluster(
            tenant_id="00000000-0000-0000-0000-000000000001",
            cluster_id="c2",
            cluster_memory_ids=["00000000-0000-0000-0000-000000000abc"],
            role_tag="public",
            db_conn=fake_db,
            plan="scale",
        )
        mock_writer.assert_called_once()
        kwargs = mock_writer.call_args.kwargs
        assert kwargs.get("persist") is True   # single-agent path persists directly
        assert result["path"] == "single_agent"
        assert result["tier_blocked"] is False


def test_dispatch_free_blocks():
    fake_db = MagicMock()
    result = synthesize_cluster(
        tenant_id="00000000-0000-0000-0000-000000000001",
        cluster_id="c3",
        cluster_memory_ids=["00000000-0000-0000-0000-000000000abc"],
        role_tag="public",
        db_conn=fake_db,
        plan="free",
    )
    assert result["tier_blocked"] is True
    assert result["path"] == "blocked"
    assert result["synthesis_id"] is None


def test_dispatch_resolves_plan_from_db_when_not_provided():
    fake_db = MagicMock()
    fake_cur = MagicMock()
    fake_db.cursor.return_value = fake_cur
    fake_cur.fetchone.return_value = ("free",)
    result = synthesize_cluster(
        tenant_id="00000000-0000-0000-0000-000000000001",
        cluster_id="c4",
        cluster_memory_ids=["00000000-0000-0000-0000-000000000abc"],
        role_tag="public",
        db_conn=fake_db,
        plan=None,
    )
    fake_cur.execute.assert_called_once()
    assert result["tier_blocked"] is True
    assert result["plan"] == "free"
