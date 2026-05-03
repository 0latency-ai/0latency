"""Tests for synthesis clustering engine.

DB-integration tests. Requires MEMORY_DB_CONN env var.
Creates synthetic test data and cleans up in teardown.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Register pgvector type
try:
    from pgvector.psycopg2 import register_vector
except ImportError:
    register_vector = None

from src.synthesis.clustering import Cluster, find_clusters


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
    if register_vector is not None:
        register_vector(conn)
    yield conn
    conn.close()


@pytest.fixture
def test_tenant(db_conn):
    """Create a test tenant."""
    tenant_id = str(uuid4())

    db_conn.rollback()

    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_service.tenants (id, name, api_key_hash, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (tenant_id, f"test-clustering-{tenant_id[:8]}", f"test-hash-{tenant_id[:8]}"),
            )
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        raise

    yield tenant_id

    # Cleanup
    try:
        db_conn.rollback()
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM memory_service.tenants WHERE id = %s", (tenant_id,))
        db_conn.commit()
    except Exception:
        db_conn.rollback()


def create_test_memory(db_conn, tenant_id, agent_id='test-agent-clustering', **kwargs):
    """Helper to create a test memory row with embedding."""
    memory_id = str(uuid4())

    # Generate a simple embedding (384 dimensions, normalized)
    import random
    embedding = [random.gauss(0, 1) for _ in range(384)]
    magnitude = sum(x * x for x in embedding) ** 0.5
    embedding = [x / magnitude for x in embedding]

    # Allow override of embedding for similarity tests
    if 'embedding' in kwargs:
        embedding = kwargs.pop('embedding')

    defaults = {
        'headline': f'test-clustering-{memory_id[:8]}',
        'context': f'test context',
        'full_content': f'test full content',
        'memory_type': 'fact',
        'is_pinned': False,
        'redaction_state': 'active',
        'created_at': datetime.now(timezone.utc) - timedelta(hours=100),  # 100hr old (within 48-720hr window)
    }
    defaults.update(kwargs)

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_service.memories
            (id, tenant_id, agent_id, headline, context, full_content, memory_type, 
             is_pinned, redaction_state, created_at, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                memory_id,
                tenant_id,
                agent_id,
                defaults['headline'],
                defaults['context'],
                defaults['full_content'],
                defaults['memory_type'],
                defaults['is_pinned'],
                defaults['redaction_state'],
                defaults['created_at'],
                embedding,
            ),
        )
    db_conn.commit()

    return memory_id


def cleanup_test_memories(db_conn, prefix='test-clustering-'):
    """Cleanup test memories by headline prefix."""
    try:
        db_conn.rollback()
        with db_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM memory_service.memories WHERE headline LIKE %s",
                (f'{prefix}%',),
            )
        db_conn.commit()
    except Exception:
        db_conn.rollback()


# ============================================================
# Tests
# ============================================================

@pytest.mark.integration
def test_returns_empty_when_no_candidates(db_conn, test_tenant):
    """Fresh tenant with no atoms should return empty list."""
    try:
        clusters = find_clusters(
            tenant_id=test_tenant,
            agent_id='agent-with-no-memories',
            role_scope='public',
        )
        assert clusters == []
    finally:
        cleanup_test_memories(db_conn)


@pytest.mark.integration
def test_clusters_meet_min_size(db_conn, test_tenant):
    """No returned cluster should have fewer than min_cluster_size atoms."""
    agent_id = 'test-agent-min-size'
    
    try:
        # Create a cluster of similar embeddings (size 5)
        base_embedding = [1.0] + [0.0] * 383
        magnitude = sum(x * x for x in base_embedding) ** 0.5
        base_embedding = [x / magnitude for x in base_embedding]
        
        for i in range(5):
            # Add slight noise to make them similar but not identical
            noisy_embedding = [x + (i * 0.01) for x in base_embedding]
            mag = sum(x * x for x in noisy_embedding) ** 0.5
            noisy_embedding = [x / mag for x in noisy_embedding]
            
            create_test_memory(
                db_conn, test_tenant, agent_id=agent_id,
                headline=f'similar-atom-{i}',
                embedding=noisy_embedding
            )
        
        # Create 2 isolated atoms (should not form a cluster)
        for i in range(2):
            random_embedding = [(i + 1) * 0.1 if j == i else 0.0 for j in range(384)]
            mag = sum(x * x for x in random_embedding) ** 0.5
            random_embedding = [x / mag for x in random_embedding]
            
            create_test_memory(
                db_conn, test_tenant, agent_id=agent_id,
                headline=f'isolated-atom-{i}',
                embedding=random_embedding
            )
        
        clusters = find_clusters(
            tenant_id=test_tenant,
            agent_id=agent_id,
            min_cluster_size=3,
        )
        
        # Should have 1 cluster of size 5, no cluster of size 2
        assert all(len(c.memory_ids) >= 3 for c in clusters)
        
    finally:
        cleanup_test_memories(db_conn)


@pytest.mark.integration
def test_clusters_respect_max_size(db_conn, test_tenant):
    """Over-size clusters should be split if scipy available."""
    agent_id = 'test-agent-max-size'
    
    try:
        # Create 30 very similar atoms (should trigger split)
        base_embedding = [1.0] + [0.0] * 383
        magnitude = sum(x * x for x in base_embedding) ** 0.5
        base_embedding = [x / magnitude for x in base_embedding]
        
        for i in range(30):
            noisy_embedding = [x + (i * 0.001) for x in base_embedding]
            mag = sum(x * x for x in noisy_embedding) ** 0.5
            noisy_embedding = [x / mag for x in noisy_embedding]
            
            create_test_memory(
                db_conn, test_tenant, agent_id=agent_id,
                headline=f'large-cluster-atom-{i}',
                embedding=noisy_embedding
            )
        
        # Should split into multiple clusters, each <= max_cluster_size
        try:
            clusters = find_clusters(
                tenant_id=test_tenant,
                agent_id=agent_id,
                max_cluster_size=15,
                min_cluster_size=3,
            )
            
            assert all(len(c.memory_ids) <= 15 for c in clusters)
            
        except RuntimeError as e:
            # If scipy not installed, expect specific error message
            if 'scipy is required' in str(e):
                pytest.skip("scipy not installed; skipping max_size split test")
            else:
                raise
        
    finally:
        cleanup_test_memories(db_conn)


@pytest.mark.integration
def test_pinned_atoms_excluded(db_conn, test_tenant):
    """Pinned atoms must not appear in any cluster."""
    agent_id = 'test-agent-pinned'
    
    try:
        # Create cluster of similar embeddings
        base_embedding = [1.0] + [0.0] * 383
        magnitude = sum(x * x for x in base_embedding) ** 0.5
        base_embedding = [x / magnitude for x in base_embedding]
        
        pinned_id = None
        unpinned_ids = []
        
        for i in range(5):
            noisy_embedding = [x + (i * 0.01) for x in base_embedding]
            mag = sum(x * x for x in noisy_embedding) ** 0.5
            noisy_embedding = [x / mag for x in noisy_embedding]
            
            mem_id = create_test_memory(
                db_conn, test_tenant, agent_id=agent_id,
                headline=f'pinned-test-atom-{i}',
                embedding=noisy_embedding,
                is_pinned=(i == 0)  # First one is pinned
            )
            
            if i == 0:
                pinned_id = mem_id
            else:
                unpinned_ids.append(mem_id)
        
        clusters = find_clusters(
            tenant_id=test_tenant,
            agent_id=agent_id,
            min_cluster_size=3,
        )
        
        # Verify pinned atom not in any cluster
        for cluster in clusters:
            assert pinned_id not in [str(mid) for mid in cluster.memory_ids]
        
    finally:
        cleanup_test_memories(db_conn)


@pytest.mark.integration
def test_recency_window_filter(db_conn, test_tenant):
    """Atoms <48hr old must be excluded."""
    agent_id = 'test-agent-recency'
    
    try:
        base_embedding = [1.0] + [0.0] * 383
        magnitude = sum(x * x for x in base_embedding) ** 0.5
        base_embedding = [x / magnitude for x in base_embedding]
        
        recent_id = None
        old_ids = []
        
        # Create 1 recent atom (<48hr)
        noisy_embedding = [x for x in base_embedding]
        recent_id = create_test_memory(
            db_conn, test_tenant, agent_id=agent_id,
            headline='recent-atom',
            embedding=noisy_embedding,
            created_at=datetime.now(timezone.utc) - timedelta(hours=24)  # 24hr old
        )
        
        # Create 4 old atoms (>48hr, within 720hr)
        for i in range(4):
            noisy_embedding = [x + (i * 0.01) for x in base_embedding]
            mag = sum(x * x for x in noisy_embedding) ** 0.5
            noisy_embedding = [x / mag for x in noisy_embedding]
            
            mem_id = create_test_memory(
                db_conn, test_tenant, agent_id=agent_id,
                headline=f'old-atom-{i}',
                embedding=noisy_embedding,
                created_at=datetime.now(timezone.utc) - timedelta(hours=100)  # 100hr old
            )
            old_ids.append(mem_id)
        
        clusters = find_clusters(
            tenant_id=test_tenant,
            agent_id=agent_id,
            recency_window_hours_min=48,
            min_cluster_size=3,
        )
        
        # Verify recent atom not in any cluster
        for cluster in clusters:
            assert recent_id not in [str(mid) for mid in cluster.memory_ids]
        
    finally:
        cleanup_test_memories(db_conn)


@pytest.mark.integration
def test_redacted_atoms_excluded(db_conn, test_tenant):
    """Atoms with redaction_state='redacted' must not appear in clusters."""
    agent_id = 'test-agent-redacted'
    
    try:
        base_embedding = [1.0] + [0.0] * 383
        magnitude = sum(x * x for x in base_embedding) ** 0.5
        base_embedding = [x / magnitude for x in base_embedding]
        
        redacted_id = None
        active_ids = []
        
        for i in range(5):
            noisy_embedding = [x + (i * 0.01) for x in base_embedding]
            mag = sum(x * x for x in noisy_embedding) ** 0.5
            noisy_embedding = [x / mag for x in noisy_embedding]
            
            mem_id = create_test_memory(
                db_conn, test_tenant, agent_id=agent_id,
                headline=f'redaction-test-atom-{i}',
                embedding=noisy_embedding,
                redaction_state='redacted' if i == 0 else 'active'
            )
            
            if i == 0:
                redacted_id = mem_id
            else:
                active_ids.append(mem_id)
        
        clusters = find_clusters(
            tenant_id=test_tenant,
            agent_id=agent_id,
            min_cluster_size=3,
        )
        
        # Verify redacted atom not in any cluster
        for cluster in clusters:
            assert redacted_id not in [str(mid) for mid in cluster.memory_ids]
        
    finally:
        cleanup_test_memories(db_conn)
