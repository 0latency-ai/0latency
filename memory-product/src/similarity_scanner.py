"""
Similarity Scanner - Phase 1 of Self-Improving Memory
Scans for similar memories after each write and queues them for review.

NON-DESTRUCTIVE: This module ONLY observes and queues. It does NOT modify existing memories.
"""

import os
import json
import asyncio
import psycopg2
import psycopg2.pool
from datetime import datetime, timezone
import logging

logger = logging.getLogger("similarity_scanner")

SIMILARITY_THRESHOLD = 0.82  # Configurable threshold for similar memory detection

# Get DB connection from environment
def _get_db_conn_str():
    return os.environ["MEMORY_DB_CONN"]

# Global connection pool
_scanner_pool = None

def _get_scanner_pool():
    global _scanner_pool
    if _scanner_pool is None:
        _scanner_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=3,
            dsn=_get_db_conn_str()
        )
    return _scanner_pool


async def scan_for_similar_memories(
    new_memory_id: str,
    tenant_id: str,
    agent_id: str,
    embedding: list,
):
    """
    After a new memory is written, check if any existing memories
    are very similar. If so, queue them for classification review.
    
    This function MUST NOT block the write response.
    It MUST NOT modify any existing memories.
    It only INSERTS into consolidation_queue.
    
    Args:
        new_memory_id: UUID of the newly created memory
        tenant_id: Tenant ID for isolation
        agent_id: Agent namespace
        embedding: The embedding vector (list of floats)
    """
    try:
        # Get connection pool
        pool = _get_scanner_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        
        try:
            # Set tenant context for RLS
            cur.execute("BEGIN")
            cur.execute("SELECT memory_service.set_tenant_context(%s)", (tenant_id,))
            
            # Convert embedding to pgvector format
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            
            # Query pgvector for top 5 most similar memories for this agent
            # EXCLUDE the memory we just wrote (new_memory_id)
            # Use cosine distance: 1 - (embedding <=> query_embedding)
            query = """
                SELECT id, 1 - (embedding <=> %s::vector) as similarity
                FROM memory_service.memories
                WHERE tenant_id = %s::UUID
                AND agent_id = %s
                AND id != %s::UUID
                AND superseded_at IS NULL
                AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT 5
            """
            
            cur.execute(query, (embedding_str, tenant_id, agent_id, new_memory_id, embedding_str))
            results = cur.fetchall()
            
            similar_count = 0
            
            for row in results:
                memory_id_b = str(row[0])
                similarity = float(row[1])
                
                if similarity > SIMILARITY_THRESHOLD:
                    # Check if this pair already exists in the queue (avoid duplicates)
                    cur.execute("""
                        SELECT id FROM memory_service.consolidation_queue
                        WHERE tenant_id = %s::UUID
                        AND (
                            (memory_id_a = %s::UUID AND memory_id_b = %s::UUID)
                            OR (memory_id_a = %s::UUID AND memory_id_b = %s::UUID)
                        )
                    """, (tenant_id, new_memory_id, memory_id_b, memory_id_b, new_memory_id))
                    
                    existing = cur.fetchone()
                    
                    if not existing:
                        # Insert into consolidation queue
                        cur.execute("""
                            INSERT INTO memory_service.consolidation_queue 
                            (tenant_id, agent_id, memory_id_a, memory_id_b, similarity_score, status)
                            VALUES (%s::UUID, %s, %s::UUID, %s::UUID, %s, 'pending')
                        """, (tenant_id, agent_id, new_memory_id, memory_id_b, similarity))
                        
                        similar_count += 1
                        logger.info(f"Queued similar pair: {new_memory_id} <-> {memory_id_b} (similarity: {similarity:.3f})")
            
            cur.execute("COMMIT")
            
            # Log activity
            log_path = f"/root/logs/similarity-scanner-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a") as f:
                timestamp = datetime.now(timezone.utc).isoformat()
                f.write(f"{timestamp} | tenant={tenant_id} | agent={agent_id} | "
                       f"new_memory={new_memory_id} | similar_found={similar_count}\n")
            
            logger.info(f"Similarity scan complete: {similar_count} similar memories found for {new_memory_id}")
            
        except Exception as e:
            cur.execute("ROLLBACK")
            logger.error(f"Similarity scan failed: {e}")
            # Log error but don't raise - this is fire-and-forget
            log_path = f"/root/logs/similarity-scanner-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a") as f:
                timestamp = datetime.now(timezone.utc).isoformat()
                f.write(f"{timestamp} | ERROR | tenant={tenant_id} | agent={agent_id} | error={str(e)}\n")
        
        finally:
            if cur:
                cur.close()
            if conn:
                pool.putconn(conn)
                
    except Exception as e:
        logger.error(f"Similarity scanner outer error: {e}")
        # Fire-and-forget - don't propagate errors


def scan_for_similar_memories_sync(
    new_memory_id: str,
    tenant_id: str,
    agent_id: str,
    embedding: list,
):
    """
    Synchronous wrapper for similarity scanner.
    Runs the async function in the background without blocking.
    """
    import threading
    
    def _run_async_scan():
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                scan_for_similar_memories(new_memory_id, tenant_id, agent_id, embedding)
            )
            loop.close()
        except Exception as e:
            logger.error(f"Background similarity scan failed: {e}")
    
    # Fire in background thread
    thread = threading.Thread(target=_run_async_scan, daemon=True)
    thread.start()


# Convenience function for direct integration
def trigger_similarity_scan(memory_id: str, tenant_id: str, agent_id: str, embedding: list):
    """
    Trigger a similarity scan for a newly written memory.
    Non-blocking, fire-and-forget.
    """
    scan_for_similar_memories_sync(memory_id, tenant_id, agent_id, embedding)
