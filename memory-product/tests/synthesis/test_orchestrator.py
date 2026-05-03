"""
CP8 Phase 2 T5+T6 — Orchestrator Tests

Six integration tests covering run_synthesis_for_tenant.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from uuid import uuid4

from src.synthesis.orchestrator import run_synthesis_for_tenant
from src.storage_multitenant import _get_connection_pool, set_tenant_context, _db_execute_rows
from pgvector.psycopg2 import register_vector


@pytest.fixture
def db_conn():
    pool = _get_connection_pool()
    conn = pool.getconn()
    register_vector(conn)
    try:
        yield conn
    finally:
        pool.putconn(conn)


@pytest.fixture
def test_tenant_id():
    return "44c3080d-c196-407d-a606-4ea9f62ba0fc"


@pytest.fixture
def test_agent_id():
    return "user-justin"


@pytest.mark.integration
def test_zero_clusters_returns_skipped(test_tenant_id):
    """Test 1: Zero clusters found → status='skipped', no LLM calls."""
    # Use a fresh agent with no memories
    result = run_synthesis_for_tenant(
        tenant_id=test_tenant_id,
        agent_id="test-empty-agent-" + str(uuid4())[:8],
        max_clusters=5,
    )
    
    assert result["status"] == "skipped"
    assert result["clusters_found"] == 0
    assert result["clusters_synthesized"] == 0
    assert len(result["synthesis_ids"]) == 0
    assert result["tokens_used_total"] == 0


@pytest.mark.integration
def test_normal_run_creates_job_and_synthesis(db_conn, test_tenant_id, test_agent_id):
    """Test 2: Normal run creates job + synthesis rows."""
    result = run_synthesis_for_tenant(
        tenant_id=test_tenant_id,
        agent_id=test_agent_id,
        max_clusters=1,  # Just one to keep test fast
    )
    
    assert result["status"] in ("succeeded", "skipped")
    assert "job_id" in result
    
    if result["status"] == "succeeded":
        assert result["clusters_synthesized"] > 0
        assert len(result["synthesis_ids"]) > 0
        
        # Verify job exists
        set_tenant_context(test_tenant_id)
        job_rows = _db_execute_rows(
            "SELECT status FROM memory_service.synthesis_jobs WHERE id = %s",
            (result["job_id"],),
            tenant_id=test_tenant_id,
        )
        assert len(job_rows) == 1
        assert job_rows[0][0] == "succeeded"


@pytest.mark.integration
def test_max_clusters_caps_run(db_conn, test_tenant_id, test_agent_id):
    """Test 3: max_clusters parameter caps synthesis count."""
    result = run_synthesis_for_tenant(
        tenant_id=test_tenant_id,
        agent_id=test_agent_id,
        max_clusters=2,
    )
    
    if result["status"] == "succeeded":
        assert result["clusters_synthesized"] <= 2


@pytest.mark.integration  
def test_triggered_by_propagates(db_conn, test_tenant_id, test_agent_id):
    """Test 4: triggered_by appears in job payload."""
    result = run_synthesis_for_tenant(
        tenant_id=test_tenant_id,
        agent_id=test_agent_id,
        max_clusters=1,
        triggered_by="test_suite",
    )
    
    assert "job_id" in result
    
    # Check job payload
    set_tenant_context(test_tenant_id)
    job_rows = _db_execute_rows(
        "SELECT payload FROM memory_service.synthesis_jobs WHERE id = %s",
        (result["job_id"],),
        tenant_id=test_tenant_id,
    )
    
    if job_rows:
        import json
        payload = json.loads(job_rows[0][0]) if isinstance(job_rows[0][0], str) else job_rows[0][0]
        assert payload.get("triggered_by") == "test_suite"


@pytest.mark.integration
def test_result_has_duration(test_tenant_id, test_agent_id):
    """Test 5: Result includes duration_ms."""
    result = run_synthesis_for_tenant(
        tenant_id=test_tenant_id,
        agent_id=test_agent_id,
        max_clusters=1,
    )
    
    assert "duration_ms" in result
    assert result["duration_ms"] > 0


@pytest.mark.integration
def test_job_id_is_uuid(test_tenant_id, test_agent_id):
    """Test 6: job_id is a valid UUID."""
    result = run_synthesis_for_tenant(
        tenant_id=test_tenant_id,
        agent_id=test_agent_id,
        max_clusters=1,
    )
    
    from uuid import UUID
    assert "job_id" in result
    # Should parse without error
    UUID(result["job_id"])
