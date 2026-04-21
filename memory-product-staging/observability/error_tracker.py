"""
Error Tracker - Production-grade error logging with deduplication and grouping
Captures all exceptions with full context and groups similar errors
"""
import os
import sys
import hashlib
import json
import logging
import traceback
import psycopg2
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from functools import wraps

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from storage_multitenant import _get_connection_pool

logger = logging.getLogger("0latency.error_tracker")


class ErrorLevel(str, Enum):
    """Error severity levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def _get_db_connection():
    """Get a connection from the pool"""
    pool = _get_connection_pool()
    return pool.getconn()

def _return_db_connection(conn):
    """Return connection to the pool"""
    pool = _get_connection_pool()
    pool.putconn(conn)


class ErrorTracker:
    """
    Centralized error tracking with deduplication and aggregation
    """
    
    def __init__(self):
        pass
    
    @staticmethod
    def _compute_error_hash(error_type: str, traceback_str: str, endpoint: str = "") -> str:
        """
        Compute a unique hash for error grouping
        Groups similar errors together based on exception type, stack trace pattern, and endpoint
        """
        # Extract just the meaningful part of the stack trace (ignore line numbers)
        lines = traceback_str.split('\n')
        significant_lines = [
            line for line in lines 
            if 'File' in line or 'Error' in line or 'Exception' in line
        ]
        
        # Remove line numbers and memory addresses for better grouping
        normalized = []
        for line in significant_lines:
            # Remove line numbers like "line 123"
            line = line.split(', line ')[0] if ', line ' in line else line
            # Remove memory addresses
            line = ''.join([c for c in line if not c.isdigit() or c.isalpha()])
            normalized.append(line)
        
        hash_input = f"{error_type}:{endpoint}:{''.join(normalized)}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def log_error(
        self,
        error: Exception,
        level: ErrorLevel = ErrorLevel.ERROR,
        tenant_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log an error with full context
        
        Returns:
            error_hash: Unique identifier for this error group
        """
        try:
            error_type = type(error).__name__
            error_message = str(error)
            traceback_str = traceback.format_exc()
            
            # Compute hash for deduplication
            error_hash = self._compute_error_hash(error_type, traceback_str, endpoint or "")
            
            # Prepare context
            context = {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "user_agent": user_agent,
                "ip_address": ip_address,
                "endpoint": endpoint,
                **(extra_context or {})
            }
            
            conn = _get_db_connection()
            cursor = conn.cursor()
            
            try:
                # Insert error log
                cursor.execute("""
                    INSERT INTO error_logs (
                        error_hash, error_type, error_message, stack_trace,
                        level, tenant_id, request_id, user_agent, ip_address,
                        endpoint, context, occurred_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    error_hash, error_type, error_message, traceback_str,
                    level.value, tenant_id, request_id, user_agent, ip_address,
                    endpoint, json.dumps(context), datetime.now(timezone.utc)
                ))
                
                # Update or insert error group
                cursor.execute("""
                    INSERT INTO error_groups (
                        error_hash, error_type, sample_message, sample_stack_trace,
                        first_seen, last_seen, occurrence_count, affected_tenants, level
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, 1, %s, %s
                    )
                    ON CONFLICT (error_hash) DO UPDATE SET
                        last_seen = EXCLUDED.last_seen,
                        occurrence_count = error_groups.occurrence_count + 1,
                        affected_tenants = CASE
                            WHEN %s IS NOT NULL AND NOT (%s = ANY(error_groups.affected_tenants))
                            THEN array_append(error_groups.affected_tenants, %s)
                            ELSE error_groups.affected_tenants
                        END
                """, (
                    error_hash, error_type, error_message, traceback_str,
                    datetime.now(timezone.utc), datetime.now(timezone.utc),
                    [tenant_id] if tenant_id else [],
                    level.value,
                    tenant_id, tenant_id, tenant_id
                ))
                
                conn.commit()
            finally:
                cursor.close()
                _return_db_connection(conn)
            
            # Log to application logger
            logger.error(
                f"ERROR_TRACKED: {error_type} [{error_hash}]",
                extra={
                    "error_hash": error_hash,
                    "error_type": error_type,
                    "level": level.value,
                    "tenant_id": tenant_id,
                    "endpoint": endpoint,
                }
            )
            
            return error_hash
            
        except Exception as e:
            # Fallback logging if database insert fails
            logger.exception(f"Failed to log error to database: {e}")
            return "TRACKING_FAILED"
    
    def get_error_stats(
        self,
        hours: int = 24,
        level: Optional[ErrorLevel] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get error statistics for the specified time window
        """
        conn = None
        try:
            conn = _get_db_connection()
            cursor = conn.cursor()
            
            # Build query
            where_clauses = [f"occurred_at > NOW() - INTERVAL '{hours} hours'"]
            params = []
            
            if level:
                where_clauses.append("level = %s")
                params.append(level.value)
            
            if tenant_id:
                where_clauses.append("tenant_id = %s")
                params.append(tenant_id)
            
            where_sql = " AND ".join(where_clauses)
            
            # Total errors
            cursor.execute(f"""
                SELECT COUNT(*) FROM error_logs WHERE {where_sql}
            """, params)
            total_errors = cursor.fetchone()[0]
            
            # Unique error groups
            cursor.execute(f"""
                SELECT COUNT(DISTINCT error_hash) FROM error_logs WHERE {where_sql}
            """, params)
            unique_errors = cursor.fetchone()[0]
            
            # Error rate (errors per minute)
            cursor.execute(f"""
                SELECT COUNT(*) / GREATEST(EXTRACT(EPOCH FROM (MAX(occurred_at) - MIN(occurred_at))) / 60, 1)
                FROM error_logs WHERE {where_sql}
            """, params)
            error_rate = cursor.fetchone()[0] or 0
            
            # Top errors
            cursor.execute(f"""
                SELECT 
                    eg.error_hash,
                    eg.error_type,
                    eg.sample_message,
                    eg.occurrence_count,
                    eg.affected_tenants,
                    eg.first_seen,
                    eg.last_seen
                FROM error_groups eg
                WHERE eg.error_hash IN (
                    SELECT DISTINCT error_hash FROM error_logs WHERE {where_sql}
                )
                ORDER BY eg.occurrence_count DESC
                LIMIT 10
            """, params)
            
            top_errors = []
            for row in cursor.fetchall():
                top_errors.append({
                    "error_hash": row[0],
                    "error_type": row[1],
                    "sample_message": row[2],
                    "occurrence_count": row[3],
                    "affected_tenants": len(row[4]) if row[4] else 0,
                    "first_seen": row[5].isoformat() if row[5] else None,
                    "last_seen": row[6].isoformat() if row[6] else None,
                })
            
            cursor.close()
            
            return {
                "total_errors": total_errors,
                "unique_error_groups": unique_errors,
                "error_rate_per_minute": round(float(error_rate), 2),
                "top_errors": top_errors,
                "time_window_hours": hours,
            }
            
        except Exception as e:
            logger.exception(f"Failed to get error stats: {e}")
            return {
                "error": str(e),
                "total_errors": 0,
                "unique_error_groups": 0,
                "error_rate_per_minute": 0,
                "top_errors": [],
            }
        finally:
            if conn:
                _return_db_connection(conn)
    
    def get_error_details(self, error_hash: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get detailed information about a specific error group
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get error group summary
            cursor.execute("""
                SELECT 
                    error_hash, error_type, sample_message, sample_stack_trace,
                    occurrence_count, affected_tenants, first_seen, last_seen, level
                FROM error_groups
                WHERE error_hash = %s
            """, (error_hash,))
            
            row = cursor.fetchone()
            if not row:
                return {"error": "Error group not found"}
            
            group_info = {
                "error_hash": row[0],
                "error_type": row[1],
                "sample_message": row[2],
                "sample_stack_trace": row[3],
                "occurrence_count": row[4],
                "affected_tenants": row[5] or [],
                "affected_tenant_count": len(row[5]) if row[5] else 0,
                "first_seen": row[6].isoformat() if row[6] else None,
                "last_seen": row[7].isoformat() if row[7] else None,
                "level": row[8],
            }
            
            # Get recent occurrences
            cursor.execute("""
                SELECT 
                    id, tenant_id, request_id, endpoint, 
                    user_agent, ip_address, context, occurred_at
                FROM error_logs
                WHERE error_hash = %s
                ORDER BY occurred_at DESC
                LIMIT %s
            """, (error_hash, limit))
            
            recent_occurrences = []
            for row in cursor.fetchall():
                recent_occurrences.append({
                    "id": row[0],
                    "tenant_id": row[1],
                    "request_id": row[2],
                    "endpoint": row[3],
                    "user_agent": row[4],
                    "ip_address": row[5],
                    "context": row[6],
                    "occurred_at": row[7].isoformat() if row[7] else None,
                })
            
            cursor.close()
            
            return {
                "group": group_info,
                "recent_occurrences": recent_occurrences,
            }
            
        except Exception as e:
            logger.exception(f"Failed to get error details: {e}")
            return {"error": str(e)}
    
    def get_tenant_errors(self, tenant_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get all errors affecting a specific tenant
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    el.error_hash,
                    el.error_type,
                    el.error_message,
                    el.endpoint,
                    el.occurred_at,
                    eg.occurrence_count
                FROM error_logs el
                JOIN error_groups eg ON el.error_hash = eg.error_hash
                WHERE el.tenant_id = %s
                AND el.occurred_at > NOW() - INTERVAL '%s hours'
                ORDER BY el.occurred_at DESC
            """, (tenant_id, hours))
            
            errors = []
            for row in cursor.fetchall():
                errors.append({
                    "error_hash": row[0],
                    "error_type": row[1],
                    "error_message": row[2],
                    "endpoint": row[3],
                    "occurred_at": row[4].isoformat() if row[4] else None,
                    "total_occurrences": row[5],
                })
            
            cursor.close()
            return errors
            
        except Exception as e:
            logger.exception(f"Failed to get tenant errors: {e}")
            return []


# Global instance
_error_tracker = ErrorTracker()


def log_error(
    error: Exception,
    level: ErrorLevel = ErrorLevel.ERROR,
    **context
) -> str:
    """
    Convenience function to log an error
    """
    return _error_tracker.log_error(error, level=level, **context)


def track_error(level: ErrorLevel = ErrorLevel.ERROR, alert: bool = False):
    """
    Decorator to automatically track errors in endpoints
    
    Usage:
        @track_error(level=ErrorLevel.CRITICAL, alert=True)
        async def my_endpoint(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Extract context from request if available
                request = None
                for arg in args:
                    if hasattr(arg, 'headers'):
                        request = arg
                        break
                
                context = {}
                if request:
                    context['endpoint'] = f"{request.method} {request.url.path}"
                    context['user_agent'] = request.headers.get('user-agent')
                    context['ip_address'] = request.client.host if hasattr(request, 'client') else None
                
                error_hash = log_error(e, level=level, **context)
                
                if alert:
                    from .alerts import send_alert
                    send_alert(
                        f"Error in {context.get('endpoint', 'unknown')}: {type(e).__name__}",
                        level="critical" if level == ErrorLevel.CRITICAL else "error"
                    )
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_hash = log_error(e, level=level)
                
                if alert:
                    from .alerts import send_alert
                    send_alert(
                        f"Error: {type(e).__name__} - {str(e)}",
                        level="critical" if level == ErrorLevel.CRITICAL else "error"
                    )
                
                raise
        
        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        return sync_wrapper
    
    return decorator


def get_error_stats(**kwargs) -> Dict[str, Any]:
    """Convenience function to get error statistics"""
    return _error_tracker.get_error_stats(**kwargs)
