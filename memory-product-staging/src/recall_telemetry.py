"""
Recall Telemetry - Phase 1 of Self-Improving Memory
Tracks which memories are recalled and how they perform.

This enables future improvements by measuring recall quality.
"""

import threading
from datetime import datetime, timezone
from storage_multitenant import _db_execute, _get_connection_pool
import logging

logger = logging.getLogger("recall_telemetry")


def log_recall_telemetry(
    tenant_id: str,
    agent_id: str,
    query_text: str,
    recalled_memory_ids: list,
    recall_latency_ms: int,
):
    """
    Log recall telemetry data to track which memories are retrieved.
    
    This is fire-and-forget and must not block the recall response.
    
    Args:
        tenant_id: Tenant UUID
        agent_id: Agent namespace
        query_text: The search query/context
        recalled_memory_ids: List of memory UUIDs that were returned
        recall_latency_ms: How long the recall took in milliseconds
    """
    def _log_async():
        try:
            pool = _get_connection_pool()
            conn = pool.getconn()
            cur = conn.cursor()
            
            try:
                cur.execute("BEGIN")
                cur.execute("SELECT memory_service.set_tenant_context(%s)", (tenant_id,))
                
                # Convert memory IDs to PostgreSQL UUID array format
                memory_ids_array = "{" + ",".join(str(mid) for mid in recalled_memory_ids) + "}"
                
                cur.execute("""
                    INSERT INTO memory_service.recall_telemetry 
                    (tenant_id, agent_id, query_text, recalled_memory_ids, recall_latency_ms, memories_returned)
                    VALUES (%s::UUID, %s, %s, %s::UUID[], %s, %s)
                """, (
                    tenant_id,
                    agent_id,
                    query_text[:1000],  # Truncate long queries
                    memory_ids_array,
                    recall_latency_ms,
                    len(recalled_memory_ids)
                ))
                
                cur.execute("COMMIT")
                
                logger.debug(f"Recall telemetry logged: agent={agent_id}, memories={len(recalled_memory_ids)}, latency={recall_latency_ms}ms")
                
            except Exception as e:
                cur.execute("ROLLBACK")
                logger.error(f"Failed to log recall telemetry: {e}")
            
            finally:
                if cur:
                    cur.close()
                if conn:
                    pool.putconn(conn)
                    
        except Exception as e:
            logger.error(f"Recall telemetry outer error: {e}")
    
    # Fire in background thread - don't block recall response
    thread = threading.Thread(target=_log_async, daemon=True)
    thread.start()


def trigger_recall_telemetry(tenant_id: str, agent_id: str, query_text: str, 
                             recalled_memory_ids: list, recall_latency_ms: int):
    """
    Trigger recall telemetry logging.
    Non-blocking, fire-and-forget.
    """
    try:
        log_recall_telemetry(tenant_id, agent_id, query_text, recalled_memory_ids, recall_latency_ms)
    except Exception:
        pass  # Fire-and-forget, don't propagate errors
