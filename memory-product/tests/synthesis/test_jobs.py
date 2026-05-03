"""Tests for synthesis jobs persistence layer.

DB-integration tests. Requires MEMORY_DB_CONN env var.
Creates synthetic test data and cleans up in teardown.
"""

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.synthesis.jobs import (
    InvalidJobStateTransition,
    cancel_job,
    claim_next_queued_job,
    complete_job,
    create_job,
    fail_job,
    get_job,
    list_jobs,
    start_job,
)


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
                (tenant_id, f"test-jobs-{tenant_id[:8]}", f"test-hash-{tenant_id[:8]}"),
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


# ============================================================
# Tests
# ============================================================

@pytest.mark.integration
def test_create_job_returns_uuid_in_queued_status(db_conn, test_tenant):
    """Creating a job should return a UUID and set status to 'queued'."""
    try:
        job_id = create_job(
            tenant_id=test_tenant,
            agent_id='test-agent',
            job_type='synthesis_run',
            payload={'role_scope': 'public'}
        )
        
        # Verify it's a valid UUID string
        assert len(job_id) == 36
        assert '-' in job_id
        
        # Verify status is queued
        job = get_job(job_id, test_tenant)
        assert job is not None
        assert job['status'] == 'queued'
        assert job['agent_id'] == 'test-agent'
        assert job['job_type'] == 'synthesis_run'
        assert job['payload'] == {'role_scope': 'public'}
        
    finally:
        pass  # Cleanup via tenant deletion


@pytest.mark.integration
def test_full_lifecycle_succeed(db_conn, test_tenant):
    """Full happy path: create → start → complete → get."""
    try:
        # Create
        job_id = create_job(
            tenant_id=test_tenant,
            agent_id='test-agent-succeed',
            job_type='cluster_then_synthesize',
            payload={'recency_window': 48}
        )
        
        job = get_job(job_id, test_tenant)
        assert job['status'] == 'queued'
        assert job['started_at'] is None
        assert job['completed_at'] is None
        
        # Start
        start_job(job_id)
        job = get_job(job_id, test_tenant)
        assert job['status'] == 'running'
        assert job['started_at'] is not None
        assert job['completed_at'] is None
        
        # Complete
        result = {'cluster_count': 5, 'synthesis_ids': ['abc', 'def'], 'tokens_used': 1200}
        complete_job(job_id, result)
        job = get_job(job_id, test_tenant)
        assert job['status'] == 'succeeded'
        assert job['completed_at'] is not None
        assert job['result'] == result
        
    finally:
        pass


@pytest.mark.integration
def test_full_lifecycle_fail(db_conn, test_tenant):
    """Full failure path: create → start → fail → get."""
    try:
        # Create
        job_id = create_job(
            tenant_id=test_tenant,
            agent_id='test-agent-fail',
            job_type='manual_trigger',
            payload={}
        )
        
        # Start
        start_job(job_id)
        
        # Fail
        error_msg = 'Database connection timeout after 30s'
        fail_job(job_id, error_msg)
        
        job = get_job(job_id, test_tenant)
        assert job['status'] == 'failed'
        assert job['completed_at'] is not None
        assert job['error'] == error_msg
        assert job['result'] is None
        
    finally:
        pass


@pytest.mark.integration
def test_cancel_queued_job(db_conn, test_tenant):
    """Cancel a queued job before it starts."""
    try:
        # Create
        job_id = create_job(
            tenant_id=test_tenant,
            agent_id='test-agent-cancel',
            job_type='synthesis_run',
            payload={}
        )
        
        # Cancel without starting
        cancel_job(job_id)
        
        job = get_job(job_id, test_tenant)
        assert job['status'] == 'cancelled'
        assert job['completed_at'] is not None
        assert job['started_at'] is None
        
    finally:
        pass


@pytest.mark.integration
def test_invalid_transition_raises(db_conn, test_tenant):
    """Trying to complete a queued job (not started) should raise InvalidJobStateTransition."""
    try:
        # Create
        job_id = create_job(
            tenant_id=test_tenant,
            agent_id='test-agent-invalid',
            job_type='synthesis_run',
            payload={}
        )
        
        # Try to complete without starting
        with pytest.raises(InvalidJobStateTransition) as exc_info:
            complete_job(job_id, {'result': 'data'})
        
        assert "Cannot complete job in status 'queued'" in str(exc_info.value)
        
        # Verify job is still queued
        job = get_job(job_id, test_tenant)
        assert job['status'] == 'queued'
        
    finally:
        pass


@pytest.mark.integration
def test_list_jobs_tenant_scoped(db_conn, test_tenant):
    """List jobs should only return jobs for the specified tenant."""
    # Create a second tenant
    tenant2_id = str(uuid4())
    
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_service.tenants (id, name, api_key_hash, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (tenant2_id, f"test-jobs2-{tenant2_id[:8]}", f"test-hash2-{tenant2_id[:8]}"),
            )
        db_conn.commit()
        
        # Create jobs in both tenants
        job1_id = create_job(test_tenant, 'agent-a', 'synthesis_run', {'key': 'val1'})
        job2_id = create_job(test_tenant, 'agent-a', 'synthesis_run', {'key': 'val2'})
        job3_id = create_job(tenant2_id, 'agent-b', 'synthesis_run', {'key': 'val3'})
        
        # List for tenant 1
        jobs_t1 = list_jobs(test_tenant)
        assert len(jobs_t1) == 2
        job_ids_t1 = {j['id'] for j in jobs_t1}
        assert job1_id in job_ids_t1
        assert job2_id in job_ids_t1
        assert job3_id not in job_ids_t1
        
        # List for tenant 2
        jobs_t2 = list_jobs(tenant2_id)
        assert len(jobs_t2) == 1
        assert jobs_t2[0]['id'] == job3_id
        
    finally:
        # Cleanup tenant 2
        try:
            db_conn.rollback()
            with db_conn.cursor() as cur:
                cur.execute("DELETE FROM memory_service.tenants WHERE id = %s", (tenant2_id,))
            db_conn.commit()
        except Exception:
            db_conn.rollback()


@pytest.mark.integration
def test_claim_next_queued_atomic(db_conn, test_tenant):
    """Claim next queued job atomically - concurrent claims should get different jobs."""
    try:
        # Create 3 queued jobs
        job1_id = create_job(test_tenant, 'agent-1', 'synthesis_run', {'order': 1})
        job2_id = create_job(test_tenant, 'agent-2', 'synthesis_run', {'order': 2})
        job3_id = create_job(test_tenant, 'agent-3', 'synthesis_run', {'order': 3})
        
        time.sleep(0.1)  # Ensure created_at ordering
        
        claimed_jobs = []
        errors = []
        
        def claim_worker():
            try:
                job = claim_next_queued_job(tenant_id=test_tenant)
                if job:
                    claimed_jobs.append(job['id'])
            except Exception as e:
                errors.append(str(e))
        
        # Run 3 threads concurrently
        threads = [threading.Thread(target=claim_worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify no errors
        assert len(errors) == 0, f"Errors during claiming: {errors}"
        
        # Verify all 3 jobs were claimed exactly once
        assert len(claimed_jobs) == 3
        assert len(set(claimed_jobs)) == 3  # No duplicates
        assert set(claimed_jobs) == {job1_id, job2_id, job3_id}
        
        # Verify all are now in 'running' status
        for job_id in [job1_id, job2_id, job3_id]:
            job = get_job(job_id, test_tenant)
            assert job['status'] == 'running'
        
    finally:
        pass


@pytest.mark.integration
def test_error_truncation(db_conn, test_tenant):
    """Failing with a 10000-char error should truncate to 4000 chars."""
    try:
        # Create and start a job
        job_id = create_job(test_tenant, 'agent-error', 'synthesis_run', {})
        start_job(job_id)
        
        # Fail with a very long error (10000 chars)
        long_error = 'X' * 10000
        fail_job(job_id, long_error)
        
        # Verify error is truncated to 4000
        job = get_job(job_id, test_tenant)
        assert job['status'] == 'failed'
        assert len(job['error']) == 4000
        assert job['error'] == 'X' * 4000
        
    finally:
        pass
