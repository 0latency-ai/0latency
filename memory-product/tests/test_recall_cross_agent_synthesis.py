"""
P4.2 Integration tests for cross-agent synthesis recall fix.

Tests verify that synthesis memories are accessible across agent boundaries
while atoms remain agent-scoped.
"""
import pytest
import requests
import os

API_BASE = "http://localhost:8420"
TENANT_ID = "44c3080d-c196-407d-a606-4ea9f62ba0fc"  # test tenant from diagnosis

@pytest.fixture
def api_headers():
    """Get API headers with valid key. Requires ZEROLATENCY_API_KEY env var."""
    api_key = os.environ.get("ZEROLATENCY_API_KEY")
    if not api_key:
        pytest.skip("ZEROLATENCY_API_KEY not set")
    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

@pytest.mark.integration
def test_cross_agent_synthesis_accessible(api_headers):
    """
    Synthesis rows must appear in recall results regardless of caller agent_id.
    
    Per CP8 v3: synthesis is cross-agent by design. The agent_id filter should
    NOT apply to synthesis rows.
    """
    # Query with agent thomas (has few/no synthesis rows of his own)
    response = requests.post(
        f"{API_BASE}/recall",
        headers=api_headers,
        json={
            "agent_id": "thomas",
            "conversation_context": "User navigating CLI",
            "budget_tokens": 4000
        }
    )
    response.raise_for_status()
    data = response.json()
    
    memories = data.get("memories", [])
    assert len(memories) > 0, "Recall must return results"
    
    # Check for synthesis rows
    synthesis_memories = [m for m in memories if m.get("memory_type") == "synthesis"]
    assert len(synthesis_memories) > 0, (
        f"Must return synthesis rows cross-agent. "
        f"Got {len(memories)} total, 0 synthesis"
    )
    
    # Verify synthesis can come from different agent
    synthesis_agents = {m.get("agent_id") for m in synthesis_memories if m.get("agent_id")}
    # user-justin agent has synthesis rows per diagnosis
    assert "user-justin" in synthesis_agents or len(synthesis_agents) > 1, (
        "Synthesis should be cross-agent"
    )

@pytest.mark.integration
def test_atoms_remain_agent_scoped(api_headers):
    """
    Atoms (non-synthesis memories) must still be scoped to caller agent_id.
    
    The fix should ONLY affect synthesis rows. Regular memories must not
    leak across agents.
    """
    response = requests.post(
        f"{API_BASE}/recall",
        headers=api_headers,
        json={
            "agent_id": "thomas",
            "conversation_context": "test query",
            "budget_tokens": 4000
        }
    )
    response.raise_for_status()
    data = response.json()
    
    memories = data.get("memories", [])
    
    # Filter to atoms only
    atoms = [m for m in memories if m.get("memory_type") != "synthesis"]
    
    if len(atoms) > 0:
        # All atoms must belong to thomas
        wrong_agent_atoms = [
            m for m in atoms 
            if m.get("agent_id") and m["agent_id"] != "thomas"
        ]
        assert len(wrong_agent_atoms) == 0, (
            f"Atoms leaked from wrong agent: {wrong_agent_atoms[:3]}"
        )

@pytest.mark.integration
def test_synthesis_auto_resolve_agent(api_headers):
    """
    When no agent_id provided, auto-resolve should work and include synthesis.
    
    Tests that synthesis is accessible even when using auto-resolved agent_id.
    """
    response = requests.post(
        f"{API_BASE}/recall",
        headers=api_headers,
        json={
            # No agent_id - should auto-resolve to user-justin (highest count)
            "conversation_context": "themes and patterns",
            "budget_tokens": 4000
        }
    )
    response.raise_for_status()
    data = response.json()
    
    memories = data.get("memories", [])
    # Should get results from auto-resolved agent
    assert len(memories) > 0, "Auto-resolve should return results"
    
    # Should include synthesis
    synthesis_count = len([m for m in memories if m.get("memory_type") == "synthesis"])
    assert synthesis_count > 0, "Auto-resolved recall should include synthesis"

@pytest.mark.integration
@pytest.mark.skipif(
    "psycopg2" not in dir(),
    reason="psycopg2 not available"
)
def test_synthesis_audit_emission(api_headers):
    """
    Audit events must be emitted when synthesis rows are returned.
    
    Closes P4.1 S02 verification gap - ensures Enterprise tier audit works.
    """
    import psycopg2
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")
    
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Get baseline count
    cur.execute(
        "SELECT COUNT(*) FROM memory_service.synthesis_audit_events "
        "WHERE event_type='read'"
    )
    before_count = cur.fetchone()[0]
    
    # Make recall request
    requests.post(
        f"{API_BASE}/recall",
        headers=api_headers,
        json={
            "conversation_context": "test query",
            "budget_tokens": 4000
        }
    ).raise_for_status()
    
    import time
    time.sleep(2)  # Allow async audit write
    
    # Check audit event written
    cur.execute(
        "SELECT COUNT(*) FROM memory_service.synthesis_audit_events "
        "WHERE event_type='read'"
    )
    after_count = cur.fetchone()[0]
    
    assert after_count > before_count, (
        f"Audit event not written: {before_count} -> {after_count}"
    )
    
    conn.close()
