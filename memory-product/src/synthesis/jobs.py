"""
Synthesis Jobs — Persistent Job State Management

DB-backed job queue for synthesis operations.
Replaces in-memory jobs dict; survives memory-api restarts.

Status state machine (allowed transitions):
  queued → running (start_job)
  queued → cancelled (cancel_job before pickup)
  running → succeeded (complete_job)
  running → failed (fail_job)
  running → cancelled (cancel_job mid-run, rare)

Any other transition raises InvalidJobStateTransition.

Tenant scoping:
- All operations are tenant-scoped where applicable
- get_job and list_jobs enforce tenant isolation
- claim_next_queued_job is global (for cron worker) but tenant-aware

Error truncation:
- Errors are truncated to 4000 chars before storage to prevent unbounded payloads

claim_next_queued_job semantics:
- Uses SELECT...FOR UPDATE SKIP LOCKED for atomic job claiming
- Prevents double-processing by concurrent workers
- Returns None if no queued jobs available
"""

import json
from typing import Optional
from datetime import datetime

from src.storage_multitenant import _db_execute_rows, set_tenant_context


class InvalidJobStateTransition(Exception):
    """Raised when attempting an invalid job status transition."""
    pass


def create_job(
    tenant_id: str,
    agent_id: str,
    job_type: str,
    payload: dict,
) -> str:
    """Insert a new job in 'queued' status. Returns job_id (uuid str)."""
    set_tenant_context(tenant_id)
    
    query = """
        INSERT INTO memory_service.synthesis_jobs
        (tenant_id, agent_id, job_type, payload, status)
        VALUES (%s, %s, %s, %s, 'queued')
        RETURNING id
    """
    
    result = _db_execute_rows(
        query,
        (tenant_id, agent_id, job_type, json.dumps(payload)),
        tenant_id=tenant_id
    )
    
    return str(result[0][0])


def start_job(job_id: str) -> None:
    """Set status='running', started_at=now(). Idempotent if already running."""
    # First get the current status to validate transition
    query_status = """
        SELECT status, tenant_id FROM memory_service.synthesis_jobs WHERE id = %s
    """
    
    # Use a temporary tenant context to fetch
    from src.storage_multitenant import _get_connection_pool
    import psycopg2
    
    pool = _get_connection_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(query_status, (job_id,))
        row = cur.fetchone()
        
        if not row:
            raise ValueError(f"Job {job_id} not found")
        
        current_status, tenant_id = row
        
        # Validate transition
        if current_status == 'running':
            # Idempotent - already running
            return
        elif current_status != 'queued':
            raise InvalidJobStateTransition(
                f"Cannot start job in status '{current_status}'. Only 'queued' jobs can be started."
            )
        
        # Set tenant context and update
        set_tenant_context(tenant_id)
        
        update_query = """
            UPDATE memory_service.synthesis_jobs
            SET status = 'running', started_at = NOW()
            WHERE id = %s AND status = 'queued'
        """
        
        _db_execute_rows(update_query, (job_id,), tenant_id=tenant_id, fetch_results=False)
        
    finally:
        cur.close()
        pool.putconn(conn)


def complete_job(job_id: str, result: dict) -> None:
    """Set status='succeeded', completed_at=now(), result=<dict>."""
    # Get current status and tenant
    query_status = """
        SELECT status, tenant_id FROM memory_service.synthesis_jobs WHERE id = %s
    """
    
    from src.storage_multitenant import _get_connection_pool
    pool = _get_connection_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(query_status, (job_id,))
        row = cur.fetchone()
        
        if not row:
            raise ValueError(f"Job {job_id} not found")
        
        current_status, tenant_id = row
        
        if current_status != 'running':
            raise InvalidJobStateTransition(
                f"Cannot complete job in status '{current_status}'. Only 'running' jobs can be completed."
            )
        
        set_tenant_context(tenant_id)
        
        update_query = """
            UPDATE memory_service.synthesis_jobs
            SET status = 'succeeded', completed_at = NOW(), result = %s
            WHERE id = %s
        """
        
        _db_execute_rows(
            update_query,
            (json.dumps(result), job_id),
            tenant_id=tenant_id,
            fetch_results=False
        )
        
    finally:
        cur.close()
        pool.putconn(conn)


def fail_job(job_id: str, error: str) -> None:
    """Set status='failed', completed_at=now(), error=<msg> (truncated to 4000 chars)."""
    # Truncate error to 4000 chars
    error_truncated = error[:4000]
    
    # Get current status and tenant
    query_status = """
        SELECT status, tenant_id FROM memory_service.synthesis_jobs WHERE id = %s
    """
    
    from src.storage_multitenant import _get_connection_pool
    pool = _get_connection_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(query_status, (job_id,))
        row = cur.fetchone()
        
        if not row:
            raise ValueError(f"Job {job_id} not found")
        
        current_status, tenant_id = row
        
        if current_status != 'running':
            raise InvalidJobStateTransition(
                f"Cannot fail job in status '{current_status}'. Only 'running' jobs can be failed."
            )
        
        set_tenant_context(tenant_id)
        
        update_query = """
            UPDATE memory_service.synthesis_jobs
            SET status = 'failed', completed_at = NOW(), error = %s
            WHERE id = %s
        """
        
        _db_execute_rows(
            update_query,
            (error_truncated, job_id),
            tenant_id=tenant_id,
            fetch_results=False
        )
        
    finally:
        cur.close()
        pool.putconn(conn)


def cancel_job(job_id: str) -> None:
    """Set status='cancelled', completed_at=now(). Only works on queued/running jobs."""
    # Get current status and tenant
    query_status = """
        SELECT status, tenant_id FROM memory_service.synthesis_jobs WHERE id = %s
    """
    
    from src.storage_multitenant import _get_connection_pool
    pool = _get_connection_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(query_status, (job_id,))
        row = cur.fetchone()
        
        if not row:
            raise ValueError(f"Job {job_id} not found")
        
        current_status, tenant_id = row
        
        if current_status not in ('queued', 'running'):
            raise InvalidJobStateTransition(
                f"Cannot cancel job in status '{current_status}'. Only 'queued' or 'running' jobs can be cancelled."
            )
        
        set_tenant_context(tenant_id)
        
        update_query = """
            UPDATE memory_service.synthesis_jobs
            SET status = 'cancelled', completed_at = NOW()
            WHERE id = %s
        """
        
        _db_execute_rows(
            update_query,
            (job_id,),
            tenant_id=tenant_id,
            fetch_results=False
        )
        
    finally:
        cur.close()
        pool.putconn(conn)


def get_job(job_id: str, tenant_id: str) -> Optional[dict]:
    """Tenant-scoped fetch. Returns full row as dict or None if not found."""
    set_tenant_context(tenant_id)
    
    query = """
        SELECT id, tenant_id, agent_id, job_type, status, payload, result, error,
               created_at, started_at, completed_at
        FROM memory_service.synthesis_jobs
        WHERE id = %s AND tenant_id = %s
    """
    
    result = _db_execute_rows(query, (job_id, tenant_id), tenant_id=tenant_id)
    
    if not result:
        return None
    
    row = result[0]
    return {
        'id': str(row[0]),
        'tenant_id': str(row[1]),
        'agent_id': row[2],
        'job_type': row[3],
        'status': row[4],
        'payload': row[5] if isinstance(row[5], dict) else json.loads(row[5]) if row[5] else {},
        'result': row[6] if isinstance(row[6], dict) else json.loads(row[6]) if row[6] else None,
        'error': row[7],
        'created_at': row[8],
        'started_at': row[9],
        'completed_at': row[10],
    }


def list_jobs(
    tenant_id: str,
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List recent jobs scoped to tenant; optional agent + status filters."""
    set_tenant_context(tenant_id)
    
    query = """
        SELECT id, tenant_id, agent_id, job_type, status, payload, result, error,
               created_at, started_at, completed_at
        FROM memory_service.synthesis_jobs
        WHERE tenant_id = %s
    """
    
    params = [tenant_id]
    
    if agent_id:
        query += " AND agent_id = %s"
        params.append(agent_id)
    
    if status:
        query += " AND status = %s"
        params.append(status)
    
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    
    results = _db_execute_rows(query, tuple(params), tenant_id=tenant_id)
    
    jobs = []
    for row in results:
        jobs.append({
            'id': str(row[0]),
            'tenant_id': str(row[1]),
            'agent_id': row[2],
            'job_type': row[3],
            'status': row[4],
            'payload': row[5] if isinstance(row[5], dict) else json.loads(row[5]) if row[5] else {},
            'result': row[6] if isinstance(row[6], dict) else json.loads(row[6]) if row[6] else None,
            'error': row[7],
            'created_at': row[8],
            'started_at': row[9],
            'completed_at': row[10],
        })
    
    return jobs


def claim_next_queued_job(tenant_id: Optional[str] = None) -> Optional[dict]:
    """
    Atomically claim one queued job for processing using SELECT...FOR UPDATE SKIP LOCKED.
    Sets status='running', started_at=now(), returns the row.
    Returns None if no queued jobs.
    Used by the cron worker (T6, future task).
    """
    from src.storage_multitenant import _get_connection_pool
    import psycopg2
    
    pool = _get_connection_pool()
    conn = pool.getconn()
    
    try:
        conn.autocommit = False
        cur = conn.cursor()
        
        # Build query with optional tenant filter
        query = """
            SELECT id, tenant_id, agent_id, job_type, status, payload, result, error,
                   created_at, started_at, completed_at
            FROM memory_service.synthesis_jobs
            WHERE status = 'queued'
        """
        
        params = []
        if tenant_id:
            query += " AND tenant_id = %s"
            params.append(tenant_id)
        
        query += """
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """
        
        cur.execute(query, tuple(params))
        row = cur.fetchone()
        
        if not row:
            conn.rollback()
            return None
        
        job_id = row[0]
        job_tenant_id = str(row[1])
        
        # Update to running
        update_query = """
            UPDATE memory_service.synthesis_jobs
            SET status = 'running', started_at = NOW()
            WHERE id = %s
        """
        
        cur.execute(update_query, (job_id,))
        conn.commit()
        
        # Return job as dict
        return {
            'id': str(row[0]),
            'tenant_id': str(row[1]),
            'agent_id': row[2],
            'job_type': row[3],
            'status': 'running',  # Updated status
            'payload': row[5] if isinstance(row[5], dict) else json.loads(row[5]) if row[5] else {},
            'result': row[6] if isinstance(row[6], dict) else json.loads(row[6]) if row[6] else None,
            'error': row[7],
            'created_at': row[8],
            'started_at': datetime.now(),  # Just set
            'completed_at': row[10],
        }
        
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()
        pool.putconn(conn)
