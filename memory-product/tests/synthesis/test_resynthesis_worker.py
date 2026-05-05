"""Worker-level integration tests for resynthesis worker.

Tests the process_pending_resynthesis worker function.
Requires MEMORY_DB_CONN env var (tests are skipped otherwise).
"""

import os
import json
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

from src.synthesis.resynthesis_worker import process_pending_resynthesis


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
    """Create a test tenant with default policy."""
    tenant_id = str(uuid4())

    # Rollback any pending transaction first
    db_conn.rollback()

    try:
        with db_conn.cursor() as cur:
            # Create tenant (synthesis_policy will be set to default automatically)
            cur.execute(
                """
                INSERT INTO memory_service.tenants (id, name, api_key_hash, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (tenant_id, f"test-resynthesis-worker-{tenant_id[:8]}", f"test-hash-{tenant_id[:8]}"),
            )
            # Update tenant plan to enterprise for higher synthesis quotas
            cur.execute(
                "UPDATE memory_service.tenants SET plan = 'enterprise' WHERE id = %s",
                (tenant_id,)
            )
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        raise

    yield tenant_id

    # Cleanup
    try:
        db_conn.rollback()  # Clear any pending transaction
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM memory_service.tenants WHERE id = %s", (tenant_id,))
        db_conn.commit()
    except Exception:
        db_conn.rollback()


def create_test_memory(db_conn, tenant_id, memory_type='raw_turn', **kwargs):
    """Helper to create a test memory row."""
    memory_id = str(uuid4())

    defaults = {
        'headline': f'test-resynthesis-worker-{memory_id[:8]}',
        'context': f'test context',
        'full_content': f'test full content',
        'agent_id': f'test-agent-worker',
        'memory_type': memory_type,
        'redaction_state': 'active',
        'synthesis_state': kwargs.get('synthesis_state'),
        'source_memory_ids': kwargs.get('source_memory_ids'),
        'metadata': kwargs.get('metadata', {}),
    }
    defaults.update(kwargs)

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_service.memories
            (id, tenant_id, agent_id, headline, context, full_content, memory_type, redaction_state, synthesis_state, source_memory_ids, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[], %s::jsonb)
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
                json.dumps(defaults['metadata']),
            ),
        )
    db_conn.commit()

    return memory_id


def cleanup_test_memories(db_conn, prefix='test-resynthesis-worker-'):
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
# Worker tests
# ============================================================

class TestResynthesisWorker:
    """Test process_pending_resynthesis worker function."""

    def test_worker_rebuilds_synthesis_with_filtered_sources(self, db_conn, test_tenant):
        """Test 1: Set up synthesis with 3 sources, redact 1, call worker, verify new synthesis has 2 sources."""
        try:
            # Create 3 atom memories
            atom_ids = []
            for i in range(3):
                atom_id = create_test_memory(db_conn, test_tenant, memory_type='raw_turn')
                atom_ids.append(atom_id)

            # Redact the second atom
            with db_conn.cursor() as cur:
                cur.execute(
                    "UPDATE memory_service.memories SET redaction_state = 'redacted' WHERE id = %s",
                    (atom_ids[1],),
                )
            db_conn.commit()

            # Create synthesis row in pending_resynthesis state with all 3 sources
            cluster_id = str(uuid4())
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='pending_resynthesis',
                source_memory_ids=atom_ids,
                metadata={'cluster_id': cluster_id},
            )

            # Call worker
            result = process_pending_resynthesis(test_tenant, limit=10)

            # Verify worker processed the row
            assert result['processed'] == 1
            assert result['succeeded'] == 1
            assert result['failed'] == 0
            assert len(result['rebuilt']) == 1

            # Verify old synthesis row is marked resynthesized
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT synthesis_state, superseded_by
                    FROM memory_service.memories
                    WHERE id = %s
                    """,
                    (syn_id,),
                )
                row = cur.fetchone()
                assert row[0] == 'resynthesized'
                new_synthesis_id = row[1]
                assert new_synthesis_id is not None

                # Verify new synthesis has only 2 sources (excluding the redacted one)
                cur.execute(
                    "SELECT source_memory_ids FROM memory_service.memories WHERE id = %s",
                    (new_synthesis_id,),
                )
                new_sources = cur.fetchone()[0]
                # Parse PostgreSQL array
                if isinstance(new_sources, str):
                    new_sources = new_sources.strip("{}").split(",") if new_sources.strip("{}") else []
                assert len(new_sources) == 2
                assert str(atom_ids[1]) not in [str(s) for s in new_sources]
                assert str(atom_ids[0]) in [str(s) for s in new_sources]
                assert str(atom_ids[2]) in [str(s) for s in new_sources]

        finally:
            cleanup_test_memories(db_conn)

    def test_worker_idempotent(self, db_conn, test_tenant):
        """Test 2: Call worker twice on same rows, verify second call processes 0 rows."""
        try:
            # Create atom
            atom_id = create_test_memory(db_conn, test_tenant, memory_type='raw_turn')

            # Create synthesis in pending_resynthesis state
            cluster_id = str(uuid4())
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='pending_resynthesis',
                source_memory_ids=[atom_id],
                metadata={'cluster_id': cluster_id},
            )

            # First worker call
            result1 = process_pending_resynthesis(test_tenant, limit=10)
            assert result1['processed'] == 1
            assert result1['succeeded'] == 1

            # Second worker call should process 0 rows
            result2 = process_pending_resynthesis(test_tenant, limit=10)
            assert result2['processed'] == 0
            assert result2['succeeded'] == 0
            assert result2['failed'] == 0

        finally:
            cleanup_test_memories(db_conn)

    def test_worker_handles_all_sources_redacted(self, db_conn, test_tenant):
        """Test 3: Degenerate case - all sources redacted, verify old row marked resynthesized with superseded_by=NULL."""
        try:
            # Create 2 atoms and immediately redact them
            atom_ids = []
            for i in range(2):
                atom_id = create_test_memory(
                    db_conn,
                    test_tenant,
                    memory_type='raw_turn',
                    redaction_state='redacted',
                )
                atom_ids.append(atom_id)

            # Create synthesis in pending_resynthesis state with all redacted sources
            cluster_id = str(uuid4())
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='pending_resynthesis',
                source_memory_ids=atom_ids,
                metadata={'cluster_id': cluster_id},
            )

            # Call worker
            result = process_pending_resynthesis(test_tenant, limit=10)

            # Verify worker processed the row
            assert result['processed'] == 1
            assert result['succeeded'] == 1
            assert len(result['rebuilt']) == 1
            assert result['rebuilt'][0]['new_id'] is None  # No new synthesis created

            # Verify old synthesis is marked resynthesized with NULL superseded_by
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT synthesis_state, superseded_by
                    FROM memory_service.memories
                    WHERE id = %s
                    """,
                    (syn_id,),
                )
                row = cur.fetchone()
                assert row[0] == 'resynthesized'
                assert row[1] is None  # superseded_by should be NULL

            # Verify audit event was written with degenerate flag
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_payload
                    FROM memory_service.synthesis_audit_events
                    WHERE tenant_id = %s
                      AND target_memory_id = %s
                      AND event_type = 'resynthesized'
                    ORDER BY occurred_at DESC
                    LIMIT 1
                    """,
                    (test_tenant, syn_id),
                )
                payload = cur.fetchone()
                assert payload is not None
                assert payload[0]['degenerate'] is True

        finally:
            cleanup_test_memories(db_conn)

    def test_worker_skip_locked(self, db_conn, test_tenant):
        """Test 4: Verify worker doesn't double-process rows (use transaction isolation)."""
        try:
            # Create atom
            atom_id = create_test_memory(db_conn, test_tenant, memory_type='raw_turn')

            # Create synthesis in pending_resynthesis state
            cluster_id = str(uuid4())
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='pending_resynthesis',
                source_memory_ids=[atom_id],
                metadata={'cluster_id': cluster_id},
            )

            # Open a separate connection and start a transaction that locks the row
            from src.storage_multitenant import _get_connection_pool
            pool = _get_connection_pool()
            lock_conn = pool.getconn()
            
            try:
                lock_conn.autocommit = False
                lock_cur = lock_conn.cursor()
                
                # Lock the synthesis row
                lock_cur.execute(
                    """
                    SELECT id FROM memory_service.memories
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (syn_id,),
                )
                
                # Call worker while row is locked - should skip locked row
                result = process_pending_resynthesis(test_tenant, limit=10)
                
                # Verify worker skipped the locked row
                assert result['processed'] == 0
                assert result['succeeded'] == 0
                assert result['failed'] == 0
                
                # Rollback and release lock
                lock_conn.rollback()
                
            finally:
                pool.putconn(lock_conn)

            # Now call worker again - should process the row
            result2 = process_pending_resynthesis(test_tenant, limit=10)
            assert result2['processed'] == 1
            assert result2['succeeded'] == 1

        finally:
            cleanup_test_memories(db_conn)
