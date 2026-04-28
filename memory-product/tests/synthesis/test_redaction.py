"""Tests for redaction cascade service layer.

DB-integration tests. Requires MEMORY_DB_CONN env var (tests are skipped otherwise).
Creates synthetic test data and cleans up in finally blocks.
"""

import json
import os
from datetime import datetime
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

from src.synthesis.policy import save_policy
from src.synthesis.redaction import (
    RedactionCascadeError,
    cascade_to_synthesis,
    transition_source_state,
    transition_synthesis_state,
)
from src.synthesis.state_machine import IllegalTransitionError


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
    """Create a test tenant with default policy.

    Note: synthesis_policy column has a default value from Migration 016,
    so we don't need to call save_policy explicitly.
    """
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
                (tenant_id, f"test-task8-{tenant_id[:8]}", f"test-hash-{tenant_id[:8]}"),
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


def create_test_memory(db_conn, tenant_id, memory_type='atom', **kwargs):
    """Helper to create a test memory row."""
    memory_id = str(uuid4())

    defaults = {
        'headline': f'test-task8-{memory_id[:8]}',
        'context': f'test context',
        'full_content': f'test full content',
        'agent_id': f'test-agent-task8',
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def cleanup_test_memories(db_conn, prefix='test-task8-'):
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
# Source state transition tests
# ============================================================

class TestSourceStateTransitions:
    """Test source memory state transitions."""

    def test_active_to_redacted_cascades_to_pending_review(self, db_conn, test_tenant):
        """Transitioning source to redacted cascades to pending_review on synthesis rows."""
        try:
            # Create atom
            atom_id = create_test_memory(db_conn, test_tenant, memory_type='atom')

            # Create synthesis row referencing atom
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='valid',
                source_memory_ids=[atom_id],
            )

            # Transition atom to redacted
            result = transition_source_state(
                atom_id,
                'redacted',
                db_conn,
                reason='GDPR deletion test',
            )

            # Verify transition result
            assert result['memory_id'] == atom_id
            assert result['old_state'] == 'active'
            assert result['new_state'] == 'redacted'
            assert len(result['cascade_summary']) == 1
            assert result['cascade_summary'][0]['synthesis_id'] == syn_id
            assert result['cascade_summary'][0]['old_state'] == 'valid'
            assert result['cascade_summary'][0]['new_state'] == 'pending_review'

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

            # Verify audit events written
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM memory_service.synthesis_audit_events
                    WHERE tenant_id = %s
                      AND event_type = 'state_transition'
                    """,
                    (test_tenant,),
                )
                # Should have 2 events: source transition + synthesis cascade
                assert cur.fetchone()[0] >= 2

        finally:
            cleanup_test_memories(db_conn)

    def test_redacted_is_terminal(self, db_conn, test_tenant):
        """Attempting to transition from redacted state raises IllegalTransitionError."""
        try:
            # Create atom already redacted
            atom_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='atom',
                redaction_state='redacted',
            )

            # Try to transition back to active
            with pytest.raises(IllegalTransitionError) as exc_info:
                transition_source_state(atom_id, 'active', db_conn)

            assert 'redacted → active' in str(exc_info.value)

        finally:
            cleanup_test_memories(db_conn)

    def test_modified_cascades_to_pending_review(self, db_conn, test_tenant):
        """Transitioning source to modified cascades to pending_review (same as redacted)."""
        try:
            # Create atom
            atom_id = create_test_memory(db_conn, test_tenant, memory_type='atom')

            # Create synthesis row
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='valid',
                source_memory_ids=[atom_id],
            )

            # Transition atom to modified
            result = transition_source_state(atom_id, 'modified', db_conn)

            # Verify cascade happened
            assert len(result['cascade_summary']) == 1
            assert result['cascade_summary'][0]['new_state'] == 'pending_review'

            # Verify database state
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT synthesis_state FROM memory_service.memories WHERE id = %s",
                    (syn_id,),
                )
                assert cur.fetchone()[0] == 'pending_review'

        finally:
            cleanup_test_memories(db_conn)


# ============================================================
# Cascade behavior tests
# ============================================================

class TestCascadeBehavior:
    """Test cascade logic and policy integration."""

    def test_resynthesize_without_path_raises_notimplemented(self, db_conn, test_tenant):
        """Setting policy to use resynthesize_without raises NotImplementedError."""
        try:
            # Create atom and synthesis
            atom_id = create_test_memory(db_conn, test_tenant, memory_type='atom')
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='valid',
                source_memory_ids=[atom_id],
            )

            # Update tenant policy to use resynthesize_without
            policy = DEFAULT_POLICY_STANDARD.copy()
            policy['redaction_rules']['on_source_redacted'] = 'resynthesize_without'
            save_policy(test_tenant, policy, db_conn)
            db_conn.commit()

            # Attempt transition
            with pytest.raises(NotImplementedError) as exc_info:
                transition_source_state(atom_id, 'redacted', db_conn)

            assert 'resynthesize_without' in str(exc_info.value)
            assert 'Phase 2-4' in str(exc_info.value)

        finally:
            cleanup_test_memories(db_conn)
            # Restore default policy
            save_policy(test_tenant, DEFAULT_POLICY_STANDARD, db_conn)
            db_conn.commit()

    def test_full_cluster_cascade_depth_raises_notimplemented(self, db_conn, test_tenant):
        """Setting cascade_depth to full_cluster raises NotImplementedError."""
        try:
            # Create atom and synthesis
            atom_id = create_test_memory(db_conn, test_tenant, memory_type='atom')
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='valid',
                source_memory_ids=[atom_id],
            )

            # Update tenant policy to use full_cluster
            policy = DEFAULT_POLICY_STANDARD.copy()
            policy['redaction_rules']['cascade_depth'] = 'full_cluster'
            save_policy(test_tenant, policy, db_conn)
            db_conn.commit()

            # Attempt transition
            with pytest.raises(NotImplementedError) as exc_info:
                transition_source_state(atom_id, 'redacted', db_conn)

            assert 'full_cluster' in str(exc_info.value)
            assert 'Phase 2-4' in str(exc_info.value)

        finally:
            cleanup_test_memories(db_conn)
            # Restore default policy
            save_policy(test_tenant, DEFAULT_POLICY_STANDARD, db_conn)
            db_conn.commit()


# ============================================================
# Synthesis state transition tests
# ============================================================

class TestSynthesisStateTransitions:
    """Test synthesis memory state transitions."""

    def test_pending_review_to_valid(self, db_conn, test_tenant):
        """Manual approval: pending_review → valid."""
        try:
            # Create synthesis row in pending_review state
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='pending_review',
                source_memory_ids=[str(uuid4())],
            )

            # Transition to valid
            result = transition_synthesis_state(
                syn_id,
                'valid',
                db_conn,
                reason='Manual review approved',
            )

            assert result['old_state'] == 'pending_review'
            assert result['new_state'] == 'valid'

            # Verify database
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT synthesis_state FROM memory_service.memories WHERE id = %s",
                    (syn_id,),
                )
                assert cur.fetchone()[0] == 'valid'

        finally:
            cleanup_test_memories(db_conn)

    def test_invalidated_to_valid_blocked(self, db_conn, test_tenant):
        """invalidated → valid is not allowed."""
        try:
            # Create synthesis row in invalidated state
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='invalidated',
                source_memory_ids=[str(uuid4())],
            )

            # Attempt transition to valid
            with pytest.raises(IllegalTransitionError) as exc_info:
                transition_synthesis_state(syn_id, 'valid', db_conn)

            assert 'invalidated → valid' in str(exc_info.value)

        finally:
            cleanup_test_memories(db_conn)


# ============================================================
# Audit logging tests
# ============================================================

class TestAuditEvents:
    """Test audit event logging."""

    def test_audit_events_written(self, db_conn, test_tenant):
        """State transitions write audit events correctly."""
        try:
            # Create atom and synthesis
            atom_id = create_test_memory(db_conn, test_tenant, memory_type='atom')
            syn_id = create_test_memory(
                db_conn,
                test_tenant,
                memory_type='synthesis',
                synthesis_state='valid',
                source_memory_ids=[atom_id],
            )

            # Get initial audit event count
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM memory_service.synthesis_audit_events
                    WHERE tenant_id = %s AND event_type = 'state_transition'
                    """,
                    (test_tenant,),
                )
                initial_count = cur.fetchone()[0]

            # Perform 3 state transitions
            # 1. Source: active → modified
            transition_source_state(atom_id, 'modified', db_conn, reason='Test 1')

            # 2. Source: modified → active
            transition_source_state(atom_id, 'active', db_conn, reason='Test 2')

            # 3. Synthesis: valid → pending_review (manual)
            transition_synthesis_state(syn_id, 'pending_review', db_conn, reason='Test 3')

            # Verify audit events
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM memory_service.synthesis_audit_events
                    WHERE tenant_id = %s AND event_type = 'state_transition'
                    """,
                    (test_tenant,),
                )
                final_count = cur.fetchone()[0]

            # Should have written at least 5 events:
            # - 2 for atom transitions (active→modified, modified→active)
            # - 2 for cascade from atom transitions (synthesis valid→pending_review each time)
            # - 1 for manual synthesis transition
            # Total: 5 minimum
            assert final_count >= initial_count + 5

            # Verify event payload structure
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_payload
                    FROM memory_service.synthesis_audit_events
                    WHERE tenant_id = %s
                      AND event_type = 'state_transition'
                      AND target_memory_id = %s
                    ORDER BY occurred_at DESC
                    LIMIT 1
                    """,
                    (test_tenant, syn_id),
                )
                payload = cur.fetchone()[0]
                assert 'old_state' in payload
                assert 'new_state' in payload
                assert 'state_type' in payload

        finally:
            cleanup_test_memories(db_conn)
