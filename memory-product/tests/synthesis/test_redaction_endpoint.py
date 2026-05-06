"""HTTP-level integration tests for POST /memories/{memory_id}/redact endpoint.

Tests the redaction cascade endpoint using FastAPI TestClient.
Requires MEMORY_DB_CONN env var (tests are skipped otherwise).
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
from fastapi.testclient import TestClient

from api.main import app



# ============================================================
# Test fixtures and helpers
# ============================================================

@pytest.fixture(scope="module")
def db_conn():
    """Get database connection from environment."""
    db_url = os.environ.get("MEMORY_DB_CONN") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("MEMORY_DB_CONN or DATABASE_URL not set; skipping DB integration tests")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture
def test_tenant(db_conn):
    """Create a test tenant with API key."""
    tenant_id = str(uuid4())
    api_key = f"zl_live_{uuid4().hex[:24]}"
    
    # Hash the API key
    import hashlib
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Rollback any pending transaction first
    db_conn.rollback()

    try:
        with db_conn.cursor() as cur:
            # Create tenant with API key
            cur.execute(
                """
                INSERT INTO memory_service.tenants (id, name, api_key_hash, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (tenant_id, f"test-redaction-endpoint-{tenant_id[:8]}", api_key_hash),
            )
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        raise

    yield {"id": tenant_id, "api_key": api_key}

    # Cleanup
    try:
        db_conn.rollback()  # Clear any pending transaction
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM memory_service.tenants WHERE id = %s", (tenant_id,))
        db_conn.commit()
    except Exception:
        db_conn.rollback()


@pytest.fixture
def client():
    """Create FastAPI TestClient."""
    return TestClient(app)


def create_test_memory(db_conn, tenant_id, memory_type='raw_turn', **kwargs):
    """Helper to create a test memory row."""
    memory_id = str(uuid4())

    defaults = {
        'headline': f'test-redaction-endpoint-{memory_id[:8]}',
        'context': f'test context',
        'full_content': f'test full content',
        'agent_id': f'test-agent-redaction',
        'memory_type': memory_type,
        'redaction_state': 'active',
        'synthesis_state': kwargs.get('synthesis_state'),
        'source_memory_ids': kwargs.get('source_memory_ids'),
    }
    defaults.update(kwargs)

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_service.memories
            (id, tenant_id, agent_id, headline, context, full_content, memory_type, redaction_state, synthesis_state, source_memory_ids)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[])
            """,
            (
                memory_id,
                tenant_id,
                defaults['agent_id'],
                defaults['headline'],
                defaults['context'],
                defaults['full_content'],
                defaults['memory_type'],
                defaults['redaction_state'],
                defaults['synthesis_state'],
                defaults['source_memory_ids'],
            ),
        )
    db_conn.commit()

    return memory_id


def cleanup_test_memories(db_conn, prefix='test-redaction-endpoint-'):
    """Cleanup test memories by headline prefix."""
    try:
        db_conn.rollback()  # Clear any pending transaction
        with db_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM memory_service.memories WHERE headline LIKE %s",
                (f'{prefix}%',),
            )
        db_conn.commit()
    except Exception:
        db_conn.rollback()


# ============================================================
# Endpoint tests
# ============================================================

class TestRedactionEndpoint:
    """Test POST /memories/{memory_id}/redact endpoint."""

    def test_redact_happy_path(self, client, db_conn, test_tenant):
        """Test 1: POST to /memories/{valid_id}/redact with reason, expect 202, check job_id and cascade_count."""
        try:
            # Create atom memory
            atom_id = create_test_memory(db_conn, test_tenant["id"], memory_type='raw_turn')

            # Create synthesis row referencing atom
            syn_id = create_test_memory(
                db_conn,
                test_tenant["id"],
                memory_type='synthesis',
                synthesis_state='valid',
                source_memory_ids=[atom_id],
            )

            # POST to redaction endpoint
            response = client.post(
                f"/memories/{atom_id}/redact",
                headers={"X-API-Key": test_tenant["api_key"]},
                json={"reason": "GDPR deletion request"},
            )

            # Verify response
            assert response.status_code == 202
            data = response.json()
            assert "job_id" in data
            assert "cascade_count" in data
            assert "redacted_memory_id" in data
            assert data["redacted_memory_id"] == atom_id
            assert data["cascade_count"] == 1  # One synthesis affected

            # Verify database state
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT redaction_state FROM memory_service.memories WHERE id = %s",
                    (atom_id,),
                )
                assert cur.fetchone()[0] == 'redacted'

                cur.execute(
                    "SELECT synthesis_state FROM memory_service.memories WHERE id = %s",
                    (syn_id,),
                )
                assert cur.fetchone()[0] == 'pending_review'

        finally:
            cleanup_test_memories(db_conn)

    def test_redact_cascade_fan_out(self, client, db_conn, test_tenant):
        """Test 2: Set up a memory cited by 3 syntheses, redact it, expect cascade_count == 3."""
        try:
            # Create one atom
            atom_id = create_test_memory(db_conn, test_tenant["id"], memory_type='raw_turn')

            # Create 3 synthesis rows all referencing the same atom
            syn_ids = []
            for i in range(3):
                syn_id = create_test_memory(
                    db_conn,
                    test_tenant["id"],
                    memory_type='synthesis',
                    synthesis_state='valid',
                    source_memory_ids=[atom_id],
                )
                syn_ids.append(syn_id)

            # Redact the atom
            response = client.post(
                f"/memories/{atom_id}/redact",
                headers={"X-API-Key": test_tenant["api_key"]},
                json={"reason": "Fan-out test"},
            )

            # Verify cascade count
            assert response.status_code == 202
            data = response.json()
            assert data["cascade_count"] == 3

            # Verify all 3 syntheses transitioned to pending_review
            with db_conn.cursor() as cur:
                for syn_id in syn_ids:
                    cur.execute(
                        "SELECT synthesis_state FROM memory_service.memories WHERE id = %s",
                        (syn_id,),
                    )
                    assert cur.fetchone()[0] == 'pending_review'

        finally:
            cleanup_test_memories(db_conn)

    def test_redact_auth_failure(self, client, db_conn, test_tenant):
        """Test 3: POST without X-API-Key header, expect 401."""
        try:
            # Create atom
            atom_id = create_test_memory(db_conn, test_tenant["id"], memory_type='raw_turn')

            # POST without API key
            response = client.post(
                f"/memories/{atom_id}/redact",
                json={"reason": "Test reason"},
            )

            # Verify 401 response
            assert response.status_code == 401
            assert "X-API-Key" in response.json()["detail"] or "Missing" in response.json()["detail"]

        finally:
            cleanup_test_memories(db_conn)

    def test_redact_nonexistent_memory(self, client, db_conn, test_tenant):
        """Test 4: POST with random UUID, expect 404."""
        try:
            # Use a random UUID that doesn't exist
            nonexistent_id = str(uuid4())

            # POST to redaction endpoint
            response = client.post(
                f"/memories/{nonexistent_id}/redact",
                headers={"X-API-Key": test_tenant["api_key"]},
                json={"reason": "Test reason"},
            )

            # Verify 404 response
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

        finally:
            cleanup_test_memories(db_conn)

    def test_redact_missing_reason(self, client, db_conn, test_tenant):
        """Test 5: POST without reason in body, expect 422."""
        try:
            # Create atom
            atom_id = create_test_memory(db_conn, test_tenant["id"], memory_type='raw_turn')

            # POST without reason field
            response = client.post(
                f"/memories/{atom_id}/redact",
                headers={"X-API-Key": test_tenant["api_key"]},
                json={},
            )

            # Verify 422 response
            assert response.status_code == 422
            assert "reason" in response.json()["detail"].lower()

            # Also test with empty reason
            response2 = client.post(
                f"/memories/{atom_id}/redact",
                headers={"X-API-Key": test_tenant["api_key"]},
                json={"reason": ""},
            )

            assert response2.status_code == 422

        finally:
            cleanup_test_memories(db_conn)
