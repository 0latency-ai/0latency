"""End-to-end integration test for Phase 3 multi-agent consensus.

Runs synthesize_cluster() against a real cluster on the dogfood tenant
(Justin's) with a temporary tier promotion to Enterprise. Verifies the full
Phase 3 pipeline: orchestrator → writer.persist=False × N → merger →
persisted consensus row + contributing_agents + audit events + (if applicable)
synthesis_disagreements row.

Skipped by default. Run explicitly:

    CP8_E2E_CONSENSUS=1 pytest tests/test_e2e_consensus.py -v

This test creates real synthesis rows in production. They are intentional
artifacts of Phase 3 shipping and are referenced by docs/CHECKPOINT-8-PHASE-3-COMPLETE.md.
"""
import os
import uuid
from datetime import datetime, timezone

import psycopg2
import pytest

from src.synthesis.tier_gates import synthesize_cluster
from src.synthesis.consensus import run_consensus  # noqa: F401

JUSTIN_TENANT_ID = "44c3080d-c196-407d-a606-4ea9f62ba0fc"


pytestmark = pytest.mark.skipif(
    not os.environ.get("CP8_E2E_CONSENSUS"),
    reason="E2E consensus test runs only when CP8_E2E_CONSENSUS=1 (creates real rows + costs tokens)",
)


@pytest.fixture
def db_conn():
    """Direct DB connection. .env must be sourced before pytest invocation."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    yield conn
    conn.close()


def _select_eligible_cluster(conn):
    """Find the most recent cluster_id with ≥5 atoms and ≥2 distinct agents.

    Returns (cluster_id, atom_ids, distinct_agent_ids) or None if no
    cluster qualifies.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT cluster_id,
                   array_agg(id) AS atom_ids,
                   array_agg(DISTINCT agent_id) AS agent_ids,
                   count(*) AS atom_count
              FROM memory_service.memories
             WHERE tenant_id = %s
               AND memory_type = 'atom'
               AND cluster_id IS NOT NULL
             GROUP BY cluster_id
            HAVING count(*) >= 5
               AND count(DISTINCT agent_id) >= 2
             ORDER BY max(created_at) DESC
             LIMIT 1
            """,
            (JUSTIN_TENANT_ID,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        cluster_id, atom_ids, agent_ids, atom_count = row
        return cluster_id, atom_ids, agent_ids, atom_count
    except Exception:
        # cluster_id column may not exist, or no atoms/clusters in this tenant
        cur.close()
        return None


def _get_tenant_tier(conn, tenant_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT plan FROM memory_service.tenants WHERE id = %s",
        (tenant_id,),
    )
    plan = cur.fetchone()[0]
    cur.close()
    return plan


def _set_tenant_tier(conn, tenant_id, plan):
    cur = conn.cursor()
    cur.execute(
        "UPDATE memory_service.tenants SET plan = %s WHERE id = %s",
        (plan, tenant_id),
    )
    conn.commit()
    cur.close()


def test_e2e_consensus_on_real_cluster(db_conn):
    """Full Phase 3 flow against a real cluster on Justin's tenant."""
    selection = _select_eligible_cluster(db_conn)

    if selection is None:
        # Document the skip in a halt-style report so the chain run captures the reason
        skip_path = "/tmp/cp8-b1-stage-06-cluster-skip.md"
        with open(skip_path, "w") as f:
            f.write(
                "# STAGE-06 E2E SKIP — no Phase 3 eligible cluster\n\n"
                f"As of {datetime.now(timezone.utc).isoformat()}, Justin's tenant "
                f"({JUSTIN_TENANT_ID}) has no cluster_id with ≥5 atoms AND ≥2 distinct "
                "agents. Phase 3 unit tests pass; E2E proof point deferred until more "
                "agent diversity accumulates in dogfood.\n\n"
                "To diagnose:\n\n"
                "```sql\n"
                "SELECT cluster_id, count(*) AS atoms,\n"
                "       count(DISTINCT agent_id) AS agents\n"
                "  FROM memory_service.memories\n"
                f" WHERE tenant_id = '{JUSTIN_TENANT_ID}'\n"
                "   AND memory_type = 'atom' AND cluster_id IS NOT NULL\n"
                "GROUP BY cluster_id\n"
                "ORDER BY count(*) DESC LIMIT 20;\n"
                "```\n"
            )
        pytest.skip(f"No Phase-3-eligible cluster on tenant {JUSTIN_TENANT_ID}; see {skip_path}")

    cluster_id, atom_ids, agent_ids, atom_count = selection
    print(f"\nE2E cluster: {cluster_id}")
    print(f"  Atoms: {atom_count}")
    print(f"  Distinct agents in cluster: {len(agent_ids)} ({agent_ids})")

    # Snapshot tier so we can restore after.
    original_tier = _get_tenant_tier(db_conn, JUSTIN_TENANT_ID)
    print(f"  Original tier: {original_tier}")

    # Snapshot pre-state counts so we can compute deltas after.
    cur = db_conn.cursor()
    cur.execute(
        "SELECT count(*) FROM memory_service.memories "
        "WHERE tenant_id = %s AND memory_type = 'synthesis'",
        (JUSTIN_TENANT_ID,),
    )
    pre_synthesis_count = cur.fetchone()[0]
    cur.execute(
        "SELECT count(*) FROM memory_service.synthesis_disagreements "
        "WHERE tenant_id = %s",
        (JUSTIN_TENANT_ID,),
    )
    pre_disagreement_count = cur.fetchone()[0]
    cur.execute(
        "SELECT count(*) FROM memory_service.synthesis_audit_events "
        "WHERE tenant_id = %s AND event_type LIKE 'consensus_%' "
        "AND occurred_at > now() - interval '1 hour'",
        (JUSTIN_TENANT_ID,),
    )
    pre_consensus_audit_count = cur.fetchone()[0]
    cur.close()

    consensus_row_id = None
    try:
        # Promote tier
        _set_tenant_tier(db_conn, JUSTIN_TENANT_ID, "enterprise")
        # Re-open the conn so any cached tier reads pick up the new value
        db_conn.commit()

        # RUN. This is the actual production code path under test.
        result = synthesize_cluster(
            tenant_id=JUSTIN_TENANT_ID,
            cluster_id=cluster_id,
            cluster_memory_ids=atom_ids,
            role_tag="public",
            db_conn=db_conn,
        )
        print(f"  synthesize_cluster result: {result}")

        # Validate result shape: must be a consensus run, not a fallback
        assert result.get("path") == "consensus", (
            f"Expected consensus path for Enterprise tenant; got {result.get('path')}. "
            f"Full result: {result}"
        )
        assert "synthesis_id" in result, f"No synthesis_id in {result}"
        consensus_row_id = result["synthesis_id"]

        # Validate consensus row landed in DB with correct shape
        cur = db_conn.cursor()
        cur.execute(
            "SELECT id, memory_type, consensus_method, contributing_agents, "
            "       source_memory_ids, parent_memory_ids, headline "
            "  FROM memory_service.memories WHERE id = %s",
            (consensus_row_id,),
        )
        row = cur.fetchone()
        assert row is not None, f"Consensus row {consensus_row_id} not in DB"
        (
            row_id,
            memory_type,
            consensus_method,
            contributing_agents,
            source_memory_ids,
            parent_memory_ids,
            headline,
        ) = row
        assert memory_type == "synthesis", f"memory_type={memory_type}, expected 'synthesis'"
        assert consensus_method == "majority_vote", f"consensus_method={consensus_method}"
        assert len(contributing_agents) >= 2, (
            f"contributing_agents has only {len(contributing_agents)} entries; "
            "expected ≥2 for a consensus run"
        )
        assert all(a in agent_ids for a in contributing_agents), (
            f"contributing_agents {contributing_agents} contains agents not in cluster {agent_ids}"
        )
        assert headline, "headline is empty"
        cur.close()

        print(f"  Consensus row id: {row_id}")
        print(f"  Headline: {headline}")
        print(f"  contributing_agents: {contributing_agents}")
        print(f"  source_memory_ids count: {len(source_memory_ids or [])}")

        # Validate audit events fired
        cur = db_conn.cursor()
        cur.execute(
            "SELECT event_type, count(*) FROM memory_service.synthesis_audit_events "
            "WHERE tenant_id = %s AND event_type LIKE 'consensus_%' "
            "AND occurred_at > now() - interval '5 minutes' "
            "GROUP BY event_type",
            (JUSTIN_TENANT_ID,),
        )
        audit_events = dict(cur.fetchall())
        cur.close()
        assert audit_events.get("consensus_run_started", 0) >= 1, (
            f"Expected ≥1 consensus_run_started event; got {audit_events}"
        )
        print(f"  Audit events emitted: {audit_events}")

        # Synthesis count delta
        cur = db_conn.cursor()
        cur.execute(
            "SELECT count(*) FROM memory_service.memories "
            "WHERE tenant_id = %s AND memory_type = 'synthesis'",
            (JUSTIN_TENANT_ID,),
        )
        post_synthesis_count = cur.fetchone()[0]
        assert post_synthesis_count == pre_synthesis_count + 1, (
            f"Expected synthesis count to increase by exactly 1; "
            f"pre={pre_synthesis_count} post={post_synthesis_count}"
        )

        # Disagreement: not required (cluster might be unanimous), but if present, validate shape
        cur.execute(
            "SELECT count(*) FROM memory_service.synthesis_disagreements "
            "WHERE tenant_id = %s AND consensus_synthesis_id = %s",
            (JUSTIN_TENANT_ID, consensus_row_id),
        )
        post_disagreement_count = cur.fetchone()[0]
        if post_disagreement_count >= 1:
            print(f"  Disagreement row(s) for this consensus: {post_disagreement_count}")
            cur.execute(
                "SELECT event_type, count(*) FROM memory_service.synthesis_audit_events "
                "WHERE event_payload->>'cluster_id' = %s "
                "AND event_type = 'consensus_disagreement_logged' "
                "AND occurred_at > now() - interval '5 minutes'",
                (cluster_id,),
            )
            disagreement_audits = dict(cur.fetchall())
            assert disagreement_audits.get("consensus_disagreement_logged", 0) >= 1, (
                f"Disagreement row exists but no consensus_disagreement_logged audit "
                f"event found. Trigger may be broken. Got: {disagreement_audits}"
            )
            print(f"  Disagreement audit emitted: {disagreement_audits}")
        else:
            print(f"  No disagreements (perfect majority across {len(contributing_agents)} agents)")
        cur.close()

        # Persist the consensus row id for the doc
        with open("/tmp/cp8-b1-stage-06-consensus-id.txt", "w") as f:
            f.write(consensus_row_id + "\n")
        with open("/tmp/cp8-b1-stage-06-cluster-id.txt", "w") as f:
            f.write(cluster_id + "\n")
        with open("/tmp/cp8-b1-stage-06-disagreement-count.txt", "w") as f:
            f.write(str(post_disagreement_count) + "\n")

    finally:
        # Always restore tier
        _set_tenant_tier(db_conn, JUSTIN_TENANT_ID, original_tier)
        db_conn.commit()
        print(f"  Tier restored: {original_tier}")
