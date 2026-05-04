"""Test the persist=False path of synthesis writer.

These tests verify Phase 3 consensus enabler: persist flag behavior.
- persist=True (default): Phase 2 contract preserved (INSERT + synthesis_written audit)
- persist=False: Phase 3 consensus path (no INSERT + synthesis_candidate_prepared audit)

Tests marked as integration since they require real DB + real LLM calls.
Run with: pytest tests/test_writer_persist_flag.py -v -m integration
"""

import pytest
from uuid import uuid4, UUID
from src.synthesis.writer import synthesize_cluster
from src.storage_multitenant import _get_connection_pool, set_tenant_context


# Fixture: Justin's tenant UUID
TENANT_ID = "44c3080d-c196-407d-a606-4ea9f62ba0fc"


@pytest.fixture
def justin_cluster():
    """Load a real cluster from Justin's namespace for testing."""
    pool = _get_connection_pool()
    conn = pool.getconn()
    set_tenant_context(TENANT_ID)
    
    # Find a recent cluster with at least 3 memories
    query = """
        SELECT DISTINCT unnest(parent_memory_ids) as mem_id
        FROM memory_service.memories
        WHERE tenant_id = %s AND memory_type = 'synthesis'
        ORDER BY created_at DESC
        LIMIT 1;
    """
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT array_agg(id::text)
            FROM (
                SELECT id FROM memory_service.memories
                WHERE tenant_id = %s AND memory_type IN ('fact', 'task', 'decision')
                ORDER BY created_at DESC
                LIMIT 5
            ) sub
        """, (TENANT_ID,))
        result = cur.fetchone()
        if not result or not result[0]:
            pytest.skip("No memories available for test cluster")
        
        memory_ids = [UUID(id_str) for id_str in result[0]]
    
    pool.putconn(conn)
    
    from dataclasses import dataclass
    @dataclass
    class Cluster:
        memory_ids: list[UUID]
        cluster_id: str
    
    return Cluster(memory_ids=memory_ids, cluster_id=f"test-cluster-{uuid4()}")


def _count_synthesis_rows(tenant_id: str) -> int:
    """Count synthesis rows for a tenant."""
    pool = _get_connection_pool()
    conn = pool.getconn()
    set_tenant_context(tenant_id)
    
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM memory_service.memories WHERE tenant_id = %s AND memory_type = 'synthesis';",
            (tenant_id,)
        )
        count = cur.fetchone()[0]
    
    pool.putconn(conn)
    return count


def _audit_events_for_agent(agent_id: str) -> list[dict]:
    """Fetch audit events for a specific agent."""
    pool = _get_connection_pool()
    conn = pool.getconn()
    set_tenant_context(TENANT_ID)
    
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_type, event_payload, occurred_at
            FROM memory_service.synthesis_audit_events
            WHERE tenant_id = %s AND actor = %s
            ORDER BY occurred_at DESC
            LIMIT 10
            """,
            (TENANT_ID, agent_id)
        )
        events = [
            {"event_type": row[0], "payload": row[1], "occurred_at": row[2]}
            for row in cur.fetchall()
        ]
    
    pool.putconn(conn)
    return events


@pytest.mark.integration
def test_persist_false_does_not_insert(justin_cluster):
    """persist=False must not INSERT into memories."""
    count_before = _count_synthesis_rows(TENANT_ID)
    
    result = synthesize_cluster(
        cluster=justin_cluster,
        tenant_id=TENANT_ID,
        agent_id="test-agent-persist-false-a",
        role_tag="public",
        persist=False,
    )
    
    count_after = _count_synthesis_rows(TENANT_ID)
    
    assert count_after == count_before, "persist=False must not write a row"
    assert isinstance(result, dict), "persist=False must return a dict"
    assert "headline" in result, "Result must have headline"
    assert "context" in result, "Result must have context"
    assert "full_content" in result, "Result must have full_content"
    assert "source_memory_ids" in result, "Result must have source_memory_ids"
    assert "agent_id" in result, "Result must have agent_id"
    assert result["agent_id"] == "test-agent-persist-false-a"


@pytest.mark.integration
def test_persist_false_emits_candidate_audit(justin_cluster):
    """persist=False must emit synthesis_candidate_prepared audit, not synthesis_written."""
    agent_id = f"test-agent-persist-false-b-{uuid4()}"
    
    result = synthesize_cluster(
        cluster=justin_cluster,
        tenant_id=TENANT_ID,
        agent_id=agent_id,
        role_tag="public",
        persist=False,
    )
    
    events = _audit_events_for_agent(agent_id)
    event_types = {e["event_type"] for e in events}
    
    assert "synthesis_candidate_prepared" in event_types, "Must emit synthesis_candidate_prepared"
    assert "synthesis_written" not in event_types, "Must NOT emit synthesis_written"


@pytest.mark.integration
def test_persist_true_default_unchanged(justin_cluster):
    """Default persist=True path behavior preserved (Phase 2 contract)."""
    count_before = _count_synthesis_rows(TENANT_ID)
    agent_id = f"test-agent-persist-true-{uuid4()}"
    
    result = synthesize_cluster(
        cluster=justin_cluster,
        tenant_id=TENANT_ID,
        agent_id=agent_id,
        role_tag="public",
        # persist defaults to True — not passing it explicitly
    )
    
    count_after = _count_synthesis_rows(TENANT_ID)
    
    assert count_after == count_before + 1, "default persist=True must write exactly 1 row"
    # Result should be a SynthesisResult with synthesis_id
    assert hasattr(result, "synthesis_id") or isinstance(result, dict) and "synthesis_id" in result
    
    # Verify synthesis_written audit was emitted
    events = _audit_events_for_agent(agent_id)
    event_types = {e["event_type"] for e in events}
    assert "synthesis_written" in event_types, "Default path must emit synthesis_written"
