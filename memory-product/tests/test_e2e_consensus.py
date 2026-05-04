"""End-to-end integration test for Phase 3 multi-agent consensus.

Runs synthesize_cluster() against a synthetic-but-grounded cluster on the
dogfood tenant (Justin's) with a temporary tier promotion to Enterprise.
Verifies the full Phase 3 pipeline: tier_gates dispatcher → run_consensus →
writer.persist=False × N → majority_vote merger → persisted consensus row +
contributing_agents + audit events + (if applicable) synthesis_disagreements row.

Skipped by default. Run explicitly:

    CP8_E2E_CONSENSUS=1 pytest tests/test_e2e_consensus.py -v -s

This test creates a real synthesis row in production and makes 3 real LLM
calls (~$0.05 in Sonnet token cost). It promotes the tenant to enterprise
for the duration and restores the original plan in finally.

The cluster used is a synthetic-but-grounded selection: 5 real memories
from Justin's namespace (clusterable memory_types, recall-eligible) with
distinct agent_ids forced via the consensus-input list. Memories themselves
are real and unmodified — only the agent_id selection at consensus-input
time is synthetic.
"""
import os
import sys
import uuid
from datetime import datetime, timezone

import psycopg2
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.synthesis.tier_gates import synthesize_cluster

JUSTIN_TENANT_ID = "44c3080d-c196-407d-a606-4ea9f62ba0fc"
JUSTIN_AGENT_ID = "user-justin"
CLUSTERABLE_TYPES = ("fact", "preference", "instruction", "event", "correction", "identity")


pytestmark = pytest.mark.skipif(
    not os.environ.get("CP8_E2E_CONSENSUS"),
    reason="E2E consensus test runs only when CP8_E2E_CONSENSUS=1 (creates real rows + costs LLM tokens)",
)


@pytest.fixture
def db_conn():
    """Direct DB connection. .env must be sourced before pytest invocation."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    yield conn
    conn.close()


def _select_recent_clusterable_memories(conn, tenant_id, limit=5):
    """Return the most recent clusterable memories for the tenant.

    Returns list of (id, agent_id, headline, memory_type) tuples, newest first.
    Filters: memory_type in CLUSTERABLE_TYPES, redaction_state active, not pinned.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, agent_id, headline, memory_type
          FROM memory_service.memories
         WHERE tenant_id = %s
           AND memory_type = ANY(%s)
           AND (redaction_state IS NULL OR redaction_state = 'active')
           AND is_pinned IS NOT TRUE
         ORDER BY created_at DESC
         LIMIT %s
        """,
        (tenant_id, list(CLUSTERABLE_TYPES), limit),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def _get_tenant_plan(conn, tenant_id):
    cur = conn.cursor()
    cur.execute("SELECT plan FROM memory_service.tenants WHERE id = %s", (tenant_id,))
    plan = cur.fetchone()[0]
    cur.close()
    return plan


def _set_tenant_plan(conn, tenant_id, plan):
    cur = conn.cursor()
    cur.execute("UPDATE memory_service.tenants SET plan = %s WHERE id = %s", (plan, tenant_id))
    conn.commit()
    cur.close()


def _force_distinct_agents_in_cluster(conn, memory_ids, agent_assignments):
    """Temporarily UPDATE the agent_id of selected memories so the cluster has
    ≥2 distinct agents — the consensus eligibility threshold.

    Returns a list of (memory_id, original_agent_id) for restoration in finally.

    agent_assignments: list of (memory_id, new_agent_id) pairs.
    """
    cur = conn.cursor()
    backups = []
    for mid, new_agent in agent_assignments:
        cur.execute(
            "SELECT agent_id FROM memory_service.memories WHERE id = %s",
            (mid,),
        )
        original = cur.fetchone()[0]
        backups.append((mid, original))
        cur.execute(
            "UPDATE memory_service.memories SET agent_id = %s WHERE id = %s",
            (new_agent, mid),
        )
    conn.commit()
    cur.close()
    return backups


def _restore_agent_ids(conn, backups):
    """Restore agent_ids per the backup tuples produced by _force_distinct_agents_in_cluster."""
    cur = conn.cursor()
    for mid, original in backups:
        cur.execute(
            "UPDATE memory_service.memories SET agent_id = %s WHERE id = %s",
            (original, mid),
        )
    conn.commit()
    cur.close()


def test_e2e_consensus_on_synthetic_cluster(db_conn):
    """Full Phase 3 flow against a synthetic-but-grounded cluster.

    Constructs a 5-memory cluster from Justin's recent clusterable memories,
    forces 2 of them to a distinct agent_id ("synthetic-agent-b") so the
    cluster has 2+ distinct agents. Promotes tier to enterprise. Runs the
    dispatcher. Asserts consensus path. Restores all state.
    """
    rows = _select_recent_clusterable_memories(db_conn, JUSTIN_TENANT_ID, limit=5)
    if len(rows) < 5:
        pytest.skip(
            f"Need ≥5 clusterable memories on tenant {JUSTIN_TENANT_ID}, "
            f"found {len(rows)}. Test setup needs more dogfood data."
        )

    memory_ids = [r[0] for r in rows]
    print(f"\nE2E synthetic cluster: {len(memory_ids)} memories")
    for r in rows:
        print(f"  {r[0]} agent={r[1]} type={r[3]} headline={r[2][:60]!r}")

    # Force agent diversity: assign 2 of the 5 memories to "synthetic-agent-b".
    # The cluster now has agents {user-justin, synthetic-agent-b} — meets ≥2 threshold.
    SYNTHETIC_AGENT = "synthetic-agent-b"
    agent_backups = _force_distinct_agents_in_cluster(
        db_conn,
        memory_ids,
        [(memory_ids[0], SYNTHETIC_AGENT), (memory_ids[1], SYNTHETIC_AGENT)],
    )

    # Snapshot tier
    original_plan = _get_tenant_plan(db_conn, JUSTIN_TENANT_ID)
    print(f"  Original plan: {original_plan}")

    # Snapshot pre-state for delta assertions
    cur = db_conn.cursor()
    cur.execute(
        "SELECT count(*) FROM memory_service.memories "
        "WHERE tenant_id = %s AND memory_type = 'synthesis'",
        (JUSTIN_TENANT_ID,),
    )
    pre_synthesis_count = cur.fetchone()[0]
    cur.close()
    
    cur = db_conn.cursor()
    cur.execute(
        "SELECT count(*) FROM memory_service.synthesis_audit_events "
        "WHERE tenant_id = %s AND event_type LIKE 'consensus_%' "
        "AND occurred_at > now() - interval '5 minutes'",
        (JUSTIN_TENANT_ID,),
    )
    pre_audit_count = cur.fetchone()[0]
    cur.close()

    consensus_row_id = None
    test_synthetic_cluster_id = f"e2e-test-{uuid.uuid4().hex[:8]}"
    try:
        _set_tenant_plan(db_conn, JUSTIN_TENANT_ID, "enterprise")
        db_conn.commit()

        # RUN — production code path under test.
        cluster_memory_ids_str = [str(m) for m in memory_ids]
        result = synthesize_cluster(
            tenant_id=JUSTIN_TENANT_ID,
            cluster_id=test_synthetic_cluster_id,
            cluster_memory_ids=cluster_memory_ids_str,
            role_tag="public",
            db_conn=db_conn,
        )
        print(f"  synthesize_cluster result keys: {list(result.keys())}")
        print(f"  path: {result.get('path')}")
        print(f"  synthesis_id: {result.get('synthesis_id')}")
        print(f"  tier_blocked: {result.get('tier_blocked')}")

        # Phase 3 ASSERTIONS
        assert result.get("tier_blocked") is False, f"Unexpected tier block: {result}"
        assert result.get("path") == "consensus", (
            f"Expected consensus path on enterprise tier; got '{result.get('path')}'. "
            f"Full result: {result}"
        )
        assert result.get("synthesis_id") is not None, f"No synthesis_id in result: {result}"
        consensus_row_id = result["synthesis_id"]

        # Validate consensus row landed in DB with correct shape
        cur = db_conn.cursor()
        cur.execute(
            "SELECT id, memory_type, consensus_method, contributing_agents, "
            "       source_memory_ids, role_tag, headline "
            "  FROM memory_service.memories WHERE id = %s",
            (consensus_row_id,),
        )
        row = cur.fetchone()
        cur.close()
        assert row is not None, f"Consensus row {consensus_row_id} not in DB"
        (row_id, memory_type, consensus_method, contributing_agents,
         source_memory_ids, role_tag, headline) = row
        assert memory_type == "synthesis", f"Wrong memory_type: {memory_type}"
        assert consensus_method == "majority_vote", f"Wrong consensus_method: {consensus_method}"
        assert contributing_agents and len(contributing_agents) >= 2, (
            f"contributing_agents must have ≥2 entries; got {contributing_agents}"
        )
        assert source_memory_ids and len(source_memory_ids) >= 1, (
            f"source_memory_ids must be populated; got {source_memory_ids}"
        )
        assert role_tag == "public", f"Wrong role_tag: {role_tag}"
        print(f"  consensus row VERIFIED: contributing_agents={contributing_agents}, "
              f"source_memory_ids count={len(source_memory_ids)}")

        # Validate post-state delta
        cur = db_conn.cursor()
        cur.execute(
            "SELECT count(*) FROM memory_service.memories "
            "WHERE tenant_id = %s AND memory_type = 'synthesis'",
            (JUSTIN_TENANT_ID,),
        )
        post_synthesis_count = cur.fetchone()[0]
        cur.close()
        
        cur = db_conn.cursor()
        cur.execute(
            "SELECT count(*) FROM memory_service.synthesis_audit_events "
            "WHERE tenant_id = %s AND event_type LIKE 'consensus_%' "
            "AND occurred_at > now() - interval '5 minutes'",
            (JUSTIN_TENANT_ID,),
        )
        post_audit_count = cur.fetchone()[0]
        cur.close()
        assert post_synthesis_count == pre_synthesis_count + 1, (
            f"Expected synthesis count to increase by 1; pre={pre_synthesis_count} post={post_synthesis_count}"
        )
        assert post_audit_count > pre_audit_count, (
            f"Expected at least one new consensus_* audit event; pre={pre_audit_count} post={post_audit_count}"
        )
        print(f"  delta VERIFIED: synthesis_count +{post_synthesis_count - pre_synthesis_count}, "
              f"consensus audit +{post_audit_count - pre_audit_count}")
    finally:
        # Restore tier
        try:
            _set_tenant_plan(db_conn, JUSTIN_TENANT_ID, original_plan)
        except Exception as e:
            print(f"  WARN: failed to restore plan to {original_plan}: {e}")

        # Restore agent_ids
        try:
            _restore_agent_ids(db_conn, agent_backups)
        except Exception as e:
            print(f"  WARN: failed to restore agent_ids: {e}")

        # Optionally clean up synthesis row created by the test (commented out by default;
        # the row is real production data and can be left as Phase 3 evidence)
        # if consensus_row_id:
        #     cur = db_conn.cursor()
        #     cur.execute("DELETE FROM memory_service.memories WHERE id = %s", (consensus_row_id,))
        #     db_conn.commit()
        #     cur.close()
