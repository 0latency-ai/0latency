"""HTTP-level integration tests for decision journal endpoints.

Tests POST /memories/decision and PATCH /memories/{memory_id}/outcome endpoints.
Covers tier gates, validation, cross-tenant isolation, and DB-level CHECK enforcement.
"""

import sys
import os

# Add parent directory to path for api.main import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

# Try to import FastAPI TestClient
try:
    from fastapi.testclient import TestClient
    from api.main import app
    FASTAPI_AVAILABLE = True
    SKIP_REASON = ''
except (ImportError, ModuleNotFoundError) as e:
    FASTAPI_AVAILABLE = False
    SKIP_REASON = f"FastAPI or api.main import failed: {e}"


# ============================================================
# Test fixtures
# ============================================================

@pytest.fixture(scope="module")
def db_conn():
    """Get database connection from environment."""
    db_url = os.environ.get("MEMORY_DB_CONN") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("MEMORY_DB_CONN or DATABASE_URL not set")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    yield conn
    conn.close()


def _create_tenant(db_conn, tier="enterprise"):
    """Helper to create test tenant with specific tier and 40-char API key."""
    tenant_id = str(uuid4())
    # Use 40-char API key format (40 hex chars after zl_live_ prefix)
    api_key = f"zl_live_{uuid4().hex[:32]}"

    db_conn.rollback()
    
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_service.tenants (id, name, api_key_live, plan, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (tenant_id, f"test-decisions-{tenant_id[:8]}", api_key, tier),
        )
    db_conn.commit()
    
    return {"id": tenant_id, "api_key": api_key, "tier": tier}


@pytest.fixture
def enterprise_tenant(db_conn):
    """Create enterprise tenant."""
    tenant = _create_tenant(db_conn, "enterprise")
    yield tenant
    
    # Cleanup: delete memories only, preserve audit events (append-only)
    db_conn.rollback()
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM memory_service.memories WHERE tenant_id = %s", (tenant["id"],))
    db_conn.commit()


@pytest.fixture
def free_tenant(db_conn):
    """Create free tier tenant."""
    tenant = _create_tenant(db_conn, "free")
    yield tenant
    db_conn.rollback()
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM memory_service.memories WHERE tenant_id = %s", (tenant["id"],))
    db_conn.commit()


@pytest.fixture
def pro_tenant(db_conn):
    """Create pro tier tenant."""
    tenant = _create_tenant(db_conn, "pro")
    yield tenant
    db_conn.rollback()
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM memory_service.memories WHERE tenant_id = %s", (tenant["id"],))
    db_conn.commit()


@pytest.fixture
def scale_tenant(db_conn):
    """Create scale tier tenant."""
    tenant = _create_tenant(db_conn, "scale")
    yield tenant
    db_conn.rollback()
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM memory_service.memories WHERE tenant_id = %s", (tenant["id"],))
    db_conn.commit()


@pytest.fixture
def client():
    """Create FastAPI TestClient."""
    return TestClient(app)


# ============================================================
# Tests
# ============================================================

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_create_decision_all_fields(client, enterprise_tenant, db_conn):
    """Test 1: POST with all required fields returns 202, memory_id, and DB row populated."""
    response = client.post(
        "/memories/decision",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "decision_text": "Adopt microservices architecture",
            "rationale": "Scalability and team autonomy",
            "headline": "Architecture decision",
            "context": "System redesign phase",
            "alternatives_considered": ["Monolith", "Serverless"],
            "predicted_outcome": "Faster deployment cycles",
            "importance": 0.9,
            "metadata": {"project": "rewrite-2026"}
        }
    )
    
    assert response.status_code == 202
    data = response.json()
    assert "memory_id" in data
    assert data["status"] == "created"
    
    # Verify DB row
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT memory_type, decision_text, rationale, alternatives_considered, 
                   predicted_outcome, importance, metadata
            FROM memory_service.memories
            WHERE id = %s
            """,
            (data["memory_id"],)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "decision"
        assert row[1] == "Adopt microservices architecture"
        assert row[2] == "Scalability and team autonomy"
        assert row[3] == ["Monolith", "Serverless"]
        assert row[4] == "Faster deployment cycles"
        assert row[5] == 0.9
        assert row[6]["project"] == "rewrite-2026"


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_create_decision_missing_decision_text(client, enterprise_tenant):
    """Test 2: POST missing decision_text returns 422."""
    response = client.post(
        "/memories/decision",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "rationale": "Some rationale",
            "headline": "Test",
            "context": "Test"
        }
    )
    
    assert response.status_code == 422
    assert "missing_required_fields" in response.json()["detail"]["error"]
    assert "decision_text" in response.json()["detail"]["missing"]


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_create_decision_missing_rationale(client, enterprise_tenant):
    """Test 3: POST missing rationale returns 422."""
    response = client.post(
        "/memories/decision",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "decision_text": "Some decision",
            "headline": "Test",
            "context": "Test"
        }
    )
    
    assert response.status_code == 422
    assert "missing_required_fields" in response.json()["detail"]["error"]
    assert "rationale" in response.json()["detail"]["missing"]


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_create_decision_free_tier_blocked(client, free_tenant):
    """Test 4: POST as Free tier returns 403."""
    response = client.post(
        "/memories/decision",
        headers={"X-API-Key": free_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "decision_text": "Some decision",
            "rationale": "Some rationale",
            "headline": "Test",
            "context": "Test"
        }
    )
    
    assert response.status_code == 403
    assert "decision_journals_enterprise_only" in response.json()["detail"]["error"]


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_create_decision_pro_tier_blocked(client, pro_tenant):
    """Test 5: POST as Pro tier returns 403."""
    response = client.post(
        "/memories/decision",
        headers={"X-API-Key": pro_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "decision_text": "Some decision",
            "rationale": "Some rationale",
            "headline": "Test",
            "context": "Test"
        }
    )
    
    assert response.status_code == 403
    assert "decision_journals_enterprise_only" in response.json()["detail"]["error"]


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_create_decision_scale_tier_blocked(client, scale_tenant):
    """Test 6: POST as Scale tier returns 403."""
    response = client.post(
        "/memories/decision",
        headers={"X-API-Key": scale_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "decision_text": "Some decision",
            "rationale": "Some rationale",
            "headline": "Test",
            "context": "Test"
        }
    )
    
    assert response.status_code == 403
    assert "decision_journals_enterprise_only" in response.json()["detail"]["error"]


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_create_decision_enterprise_allowed(client, enterprise_tenant):
    """Test 7: POST as Enterprise returns 202."""
    response = client.post(
        "/memories/decision",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "decision_text": "Enterprise decision",
            "rationale": "Enterprise rationale",
            "headline": "Test",
            "context": "Test"
        }
    )
    
    assert response.status_code == 202
    assert "memory_id" in response.json()


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_create_decision_empty_alternatives(client, enterprise_tenant):
    """Test 8: POST with empty alternatives_considered returns 202."""
    response = client.post(
        "/memories/decision",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "decision_text": "Solo option decision",
            "rationale": "No alternatives exist",
            "headline": "Test",
            "context": "Test",
            "alternatives_considered": []
        }
    )
    
    assert response.status_code == 202
    assert "memory_id" in response.json()


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_patch_outcome_success(client, enterprise_tenant, db_conn):
    """Test 9: PATCH outcome on decision row returns 200, updates actual_outcome, writes audit event."""
    # Create decision first
    create_resp = client.post(
        "/memories/decision",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={
            "agent_id": "test-agent",
            "decision_text": "Decision to track",
            "rationale": "Testing outcome tracking",
            "headline": "Test",
            "context": "Test",
            "predicted_outcome": "Will succeed"
        }
    )
    assert create_resp.status_code == 202
    memory_id = create_resp.json()["memory_id"]
    
    # Patch outcome
    patch_resp = client.patch(
        f"/memories/{memory_id}/outcome",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={"actual_outcome": "It succeeded!"}
    )
    
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["memory_id"] == memory_id
    assert data["actual_outcome"] == "It succeeded!"
    assert "updated_at" in data
    
    # Verify DB update
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT actual_outcome FROM memory_service.memories WHERE id = %s",
            (memory_id,)
        )
        row = cur.fetchone()
        assert row[0] == "It succeeded!"
        
        # Verify audit event
        cur.execute(
            """
            SELECT event_type FROM memory_service.synthesis_audit_events
            WHERE target_memory_id = %s AND event_type = 'decision_outcome_recorded'
            """,
            (memory_id,)
        )
        audit_row = cur.fetchone()
        assert audit_row is not None


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_patch_outcome_non_decision_memory(client, enterprise_tenant, db_conn):
    """Test 10: PATCH outcome on non-decision memory returns 400."""
    # Create a non-decision memory (fact)
    memory_id = str(uuid4())
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_service.memories 
            (id, tenant_id, agent_id, memory_type, headline, context, full_content, created_at)
            VALUES (%s, %s, 'test-agent', 'fact', 'Test fact', 'Test', 'Test', NOW())
            """,
            (memory_id, enterprise_tenant["id"])
        )
    db_conn.commit()
    
    # Try to patch outcome
    response = client.patch(
        f"/memories/{memory_id}/outcome",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={"actual_outcome": "Should fail"}
    )
    
    assert response.status_code == 400
    assert "decision" in response.json()["detail"].lower()


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_patch_outcome_cross_tenant(client, enterprise_tenant, db_conn):
    """Test 11: PATCH outcome cross-tenant returns 404."""
    # Create another tenant with a decision
    other_tenant = _create_tenant(db_conn, "enterprise")
    memory_id = str(uuid4())
    
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_service.memories 
            (id, tenant_id, agent_id, memory_type, headline, context, full_content, 
             decision_text, rationale, created_at)
            VALUES (%s, %s, 'test-agent', 'decision', 'Test', 'Test',
                    'Test', 'Decision', 'Rationale', NOW())
            """,
            (memory_id, other_tenant["id"])
        )
    db_conn.commit()
    
    # Try to patch from different tenant
    response = client.patch(
        f"/memories/{memory_id}/outcome",
        headers={"X-API-Key": enterprise_tenant["api_key"]},
        json={"actual_outcome": "Cross-tenant attempt"}
    )
    
    assert response.status_code == 404
    
    # Cleanup other tenant
    db_conn.rollback()
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM memory_service.memories WHERE tenant_id = %s", (other_tenant["id"],))
    db_conn.commit()


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason=SKIP_REASON)
def test_db_check_constraint_blocks_invalid_decision(db_conn, enterprise_tenant):
    """Test 12: DB-level raw INSERT of decision without decision_text is blocked by CHECK constraint."""
    memory_id = str(uuid4())
    
    # Try to insert decision row without decision_text (should violate CHECK)
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_service.memories 
                (id, tenant_id, agent_id, memory_type, headline, context, full_content, created_at)
                VALUES (%s, %s, 'test-agent', 'decision', 'Test', 'Test', 'Test', NOW())
                """,
                (memory_id, enterprise_tenant["id"])
            )
        db_conn.commit()
        assert False, "Expected CHECK constraint violation"
    except psycopg2.errors.CheckViolation:
        db_conn.rollback()
        # Expected - CHECK constraint enforced decision_text + rationale required
        pass
