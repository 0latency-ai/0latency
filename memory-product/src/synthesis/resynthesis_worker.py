"""
Resynthesis worker — picks up pending_resynthesis synthesis rows,
rebuilds them without redacted sources, supersedes the originals.

Idempotent: re-running on a row that has already moved past
pending_resynthesis is a no-op.

Concurrency: uses SELECT ... FOR UPDATE SKIP LOCKED so multiple
worker invocations don't double-process.
"""

import json
import logging
from typing import Optional
from uuid import UUID

from src.storage_multitenant import _get_connection_pool, set_tenant_context
from .writer import synthesize_cluster, _write_audit_event
from .redaction import transition_synthesis_state
from .clustering import Cluster

logger = logging.getLogger(__name__)


def process_pending_resynthesis(tenant_id: str, limit: int = 10) -> dict:
    """
    Process up to `limit` pending_resynthesis rows for a tenant.
    
    Returns: {
        'processed': int,
        'succeeded': int,
        'failed': int,
        'rebuilt': [{'old_id': uuid, 'new_id': uuid}],
        'errors': [{'old_id': uuid, 'error': str}],
    }
    """
    pool = _get_connection_pool()
    conn = pool.getconn()
    
    processed = 0
    succeeded = 0
    failed = 0
    rebuilt = []
    errors = []
    
    def parse_uuid_array(pg_array):
        """Parse PostgreSQL UUID array string to Python list."""
        if isinstance(pg_array, list):
            return pg_array
        if isinstance(pg_array, str):
            # Remove braces and split by comma
            return pg_array.strip("{}").split(",") if pg_array.strip("{}") else []
        return pg_array
    
    try:
        set_tenant_context(tenant_id)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Claim pending_resynthesis rows using SKIP LOCKED
        cur.execute(
            """
            SELECT id, source_memory_ids, metadata, agent_id
            FROM memory_service.memories
            WHERE memory_type = 'synthesis'
              AND synthesis_state = 'pending_resynthesis'
              AND tenant_id = %s
            ORDER BY updated_at ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (tenant_id, limit)
        )
        
        rows = cur.fetchall()
        
        # Parse PostgreSQL arrays
        parsed_rows = []
        for row in rows:
            old_id, source_memory_ids, metadata, agent_id = row
            parsed_rows.append((old_id, parse_uuid_array(source_memory_ids), metadata, agent_id))
        rows = parsed_rows
        
        for row in rows:
            old_id, source_memory_ids, metadata, agent_id = row
            processed += 1
            
            try:
                # Fetch current redaction state of all source memories
                cur.execute(
                    """
                    SELECT id, redaction_state
                    FROM memory_service.memories
                    WHERE id = ANY(%s::uuid[])
                    """,
                    (source_memory_ids,)
                )
                source_states = {str(r[0]): r[1] for r in cur.fetchall()}
                
                # Filter out redacted sources
                filtered_source_ids = [
                    sid for sid in source_memory_ids
                    if source_states.get(str(sid)) != 'redacted'
                ]
                
                excluded_source_ids = [
                    str(sid) for sid in source_memory_ids
                    if str(sid) not in [str(fid) for fid in filtered_source_ids]
                ]
                
                # Degenerate case: all sources redacted
                if not filtered_source_ids:
                    # Mark as resynthesized with no successor
                    cur.execute(
                        """
                        UPDATE memory_service.memories
                        SET synthesis_state = 'resynthesized',
                            superseded_by = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (old_id,)
                    )
                    
                    # Emit audit event
                    cur.execute(
                        """
                        INSERT INTO memory_service.synthesis_audit_events
                        (tenant_id, target_memory_id, event_type, actor, event_payload)
                        VALUES (%s, %s, 'resynthesized', 'system', %s::jsonb)
                        """,
                        (
                            tenant_id,
                            str(old_id),
                            json.dumps({
                                'old_synthesis_id': str(old_id),
                                'new_synthesis_id': None,
                                'source_memory_ids_excluded': excluded_source_ids,
                                'degenerate': True,
                            })
                        )
                    )
                    
                    succeeded += 1
                    rebuilt.append({'old_id': str(old_id), 'new_id': None})
                    conn.commit()
                    continue
                
                # Rebuild with filtered sources
                cluster = Cluster(
                    memory_ids=[UUID(sid) for sid in filtered_source_ids],
                    centroid_embedding=[],  # synthesize_cluster recalculates
                    cluster_signature=""  # synthesize_cluster recalculates
                )
                
                # Commit current transaction first to release lock
                conn.commit()
                
                # synthesize_cluster writes its own transaction
                result = synthesize_cluster(
                    cluster=cluster,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    persist=True,
                )
                
                # Check if synthesis succeeded
                if not result.success or result.synthesis_id is None:
                    raise ValueError(f"Synthesis failed: {result.rejected_reason}")
                
                # Start new transaction for update
                cur = conn.cursor()
                new_synthesis_id = result.synthesis_id
                
                # Update old row: set superseded_by and transition to resynthesized
                cur.execute(
                    """
                    UPDATE memory_service.memories
                    SET synthesis_state = 'resynthesized',
                        superseded_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (str(new_synthesis_id) if new_synthesis_id else None, old_id)
                )
                
                # Emit audit event
                cur.execute(
                    """
                    INSERT INTO memory_service.synthesis_audit_events
                    (tenant_id, target_memory_id, event_type, actor, event_payload)
                    VALUES (%s, %s, 'resynthesized', 'system', %s::jsonb)
                    """,
                    (
                        tenant_id,
                        str(old_id),
                        json.dumps({
                            'old_synthesis_id': str(old_id),
                            'new_synthesis_id': str(new_synthesis_id),
                            'source_memory_ids_excluded': excluded_source_ids,
                        })
                    )
                )
                
                conn.commit()
                succeeded += 1
                rebuilt.append({'old_id': str(old_id), 'new_id': str(new_synthesis_id)})
                
            except Exception as e:
                conn.rollback()
                failed += 1
                error_msg = str(e)[:500]
                errors.append({'old_id': str(old_id), 'error': error_msg})
                logger.error(f"Failed to resynthesize {old_id}: {e}")
        
        return {
            'processed': processed,
            'succeeded': succeeded,
            'failed': failed,
            'rebuilt': rebuilt,
            'errors': errors,
        }
        
    finally:
        conn.rollback()  # Clean up any uncommitted transaction
        pool.putconn(conn)
