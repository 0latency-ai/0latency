"""
Enterprise Audit Logging System for 0Latency API

Comprehensive audit trail for:
- API access (all endpoints with tenant_id, IP, user_agent, timestamp)
- Authentication events (login success/fail, logout, key regeneration)
- Data access (who accessed what memories when)
- Admin actions (tenant management, plan changes, etc.)

Retention Policy:
- General logs: 90 days
- Auth events: 1 year
- Compliance exports available

SOC 2 Type I ready.
"""
import os
import sys
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

# DB connection
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logger = logging.getLogger("audit")


class AuditEventType(str, Enum):
    """Audit event categories for classification."""
    # API Access
    API_CALL = "api_call"
    
    # Authentication
    AUTH_LOGIN_SUCCESS = "auth_login_success"
    AUTH_LOGIN_FAILED = "auth_login_failed"
    AUTH_LOGOUT = "auth_logout"
    AUTH_REGISTER = "auth_register"
    AUTH_TOKEN_REFRESH = "auth_token_refresh"
    AUTH_PASSWORD_RESET = "auth_password_reset"
    
    # API Key Management
    KEY_GENERATED = "key_generated"
    KEY_REGENERATED = "key_regenerated"
    KEY_REVOKED = "key_revoked"
    
    # Data Access
    MEMORY_CREATED = "memory_created"
    MEMORY_RECALLED = "memory_recalled"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_deleted"
    MEMORY_EXPORTED = "memory_exported"
    
    # Admin Actions
    ADMIN_TENANT_CREATED = "admin_tenant_created"
    ADMIN_TENANT_UPDATED = "admin_tenant_updated"
    ADMIN_TENANT_DELETED = "admin_tenant_deleted"
    ADMIN_PLAN_CHANGED = "admin_plan_changed"
    ADMIN_USER_IMPERSONATION = "admin_user_impersonation"
    
    # Security Events
    SECURITY_RATE_LIMIT_HIT = "security_rate_limit_hit"
    SECURITY_INVALID_TOKEN = "security_invalid_token"
    SECURITY_UNAUTHORIZED_ACCESS = "security_unauthorized_access"
    SECURITY_SUSPICIOUS_ACTIVITY = "security_suspicious_activity"
    
    # Compliance
    GDPR_DATA_EXPORT = "gdpr_data_export"
    GDPR_DATA_DELETE = "gdpr_data_delete"
    GDPR_CONSENT_GIVEN = "gdpr_consent_given"
    GDPR_CONSENT_REVOKED = "gdpr_consent_revoked"


class AuditLogger:
    """Enterprise audit logger with database persistence."""
    
    def __init__(self, db_execute_fn=None):
        """
        Initialize audit logger.
        
        Args:
            db_execute_fn: Function to execute SQL (optional, will create direct connection)
        """
        self.db_execute = db_execute_fn
        self._pool = None
        
        if not self.db_execute:
            try:
                # Use direct connection pool for audit logs (not tenant-scoped)
                from storage_multitenant import _get_connection_pool
                self._pool = _get_connection_pool()
                self.db_execute = self._execute_direct
            except ImportError:
                logger.warning("DB connection not available — audit logs will be console-only")
    
    def _execute_direct(self, query: str, params: tuple = None):
        """Execute query directly without tenant context."""
        if not self._pool:
            return []
        
        conn = self._pool.getconn()
        try:
            if conn.status == 0:  # psycopg2.extensions.STATUS_READY
                conn.autocommit = True
            elif not conn.autocommit:
                try:
                    conn.commit()
                except Exception:
                    conn.rollback()
                conn.autocommit = True
            
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    return cur.fetchall()
                return []
        finally:
            self._pool.putconn(conn)
    
    def log(
        self,
        event_type: AuditEventType,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        message: Optional[str] = None,
    ):
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (from AuditEventType enum)
            tenant_id: Tenant UUID
            user_id: User UUID (if applicable)
            endpoint: API endpoint path
            ip_address: Client IP address
            user_agent: Client User-Agent header
            status_code: HTTP status code
            request_id: Request ID for correlation
            metadata: Additional structured data (JSON)
            success: Whether the action succeeded
            message: Human-readable message
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Structured log to console
        log_entry = {
            "event_id": event_id,
            "event_type": event_type.value,
            "timestamp": timestamp.isoformat(),
            "tenant_id": tenant_id,
            "user_id": user_id,
            "endpoint": endpoint,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status_code": status_code,
            "request_id": request_id,
            "success": success,
            "message": message,
            "metadata": metadata,
        }
        
        logger.info(f"AUDIT: {log_entry}")
        
        # Persist to database
        if self.db_execute:
            try:
                # Convert metadata to JSON string
                metadata_json = json.dumps(metadata) if metadata else None
                
                self.db_execute("""
                    INSERT INTO memory_service.audit_logs (
                        id, event_type, timestamp, tenant_id, user_id,
                        endpoint, ip_address, user_agent, status_code,
                        request_id, success, message, metadata
                    ) VALUES (
                        %s::UUID, %s, %s, %s::UUID, %s::UUID,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s::jsonb
                    )
                """, (
                    event_id,
                    event_type.value,
                    timestamp,
                    tenant_id,
                    user_id,
                    endpoint,
                    ip_address,
                    user_agent,
                    status_code,
                    request_id,
                    success,
                    message,
                    metadata_json,
                ))
            except Exception as e:
                logger.error(f"Failed to persist audit log: {e}")
    
    def log_api_call(
        self,
        tenant_id: str,
        endpoint: str,
        method: str,
        ip_address: str,
        user_agent: str,
        status_code: int,
        request_id: str,
        latency_ms: int,
        agent_id: Optional[str] = None,
    ):
        """Log an API call (for all endpoints)."""
        self.log(
            event_type=AuditEventType.API_CALL,
            tenant_id=tenant_id,
            endpoint=f"{method} {endpoint}",
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
            request_id=request_id,
            metadata={
                "method": method,
                "latency_ms": latency_ms,
                "agent_id": agent_id,
            },
            success=status_code < 400,
        )
    
    def log_auth_login(
        self,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        user_id: Optional[str] = None,
        method: str = "email",  # email, github, google
        failure_reason: Optional[str] = None,
    ):
        """Log authentication attempt."""
        event_type = AuditEventType.AUTH_LOGIN_SUCCESS if success else AuditEventType.AUTH_LOGIN_FAILED
        self.log(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            message=f"Login {'successful' if success else 'failed'}: {email} via {method}",
            metadata={
                "email": email,
                "method": method,
                "failure_reason": failure_reason,
            },
        )
    
    def log_logout(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        forced: bool = False,
    ):
        """Log user logout."""
        self.log(
            event_type=AuditEventType.AUTH_LOGOUT,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            message=f"Logout {'(forced by admin)' if forced else '(user-initiated)'}",
            metadata={"forced": forced},
        )
    
    def log_api_key_action(
        self,
        tenant_id: str,
        action: str,  # generated, regenerated, revoked
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ):
        """Log API key lifecycle events."""
        event_map = {
            "generated": AuditEventType.KEY_GENERATED,
            "regenerated": AuditEventType.KEY_REGENERATED,
            "revoked": AuditEventType.KEY_REVOKED,
        }
        event_type = event_map.get(action, AuditEventType.KEY_GENERATED)
        
        self.log(
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            message=f"API key {action}",
        )
    
    def log_memory_access(
        self,
        tenant_id: str,
        action: str,  # created, recalled, updated, deleted, exported
        memory_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        count: int = 1,
    ):
        """Log memory data access."""
        event_map = {
            "created": AuditEventType.MEMORY_CREATED,
            "recalled": AuditEventType.MEMORY_RECALLED,
            "updated": AuditEventType.MEMORY_UPDATED,
            "deleted": AuditEventType.MEMORY_DELETED,
            "exported": AuditEventType.MEMORY_EXPORTED,
        }
        event_type = event_map.get(action, AuditEventType.MEMORY_CREATED)
        
        self.log(
            event_type=event_type,
            tenant_id=tenant_id,
            ip_address=ip_address,
            message=f"Memory {action}: {count} record(s)",
            metadata={
                "memory_id": memory_id,
                "agent_id": agent_id,
                "count": count,
            },
        )
    
    def log_admin_action(
        self,
        admin_user_id: str,
        action_type: AuditEventType,
        target_tenant_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ):
        """Log administrative actions."""
        metadata = {"target_user_id": target_user_id}
        if details:
            metadata.update(details)
        
        self.log(
            event_type=action_type,
            tenant_id=target_tenant_id,
            user_id=admin_user_id,
            ip_address=ip_address,
            message=f"Admin action: {action_type.value}",
            metadata=metadata,
        )
    
    def log_gdpr_action(
        self,
        tenant_id: str,
        user_id: str,
        action: str,  # export, delete, consent_given, consent_revoked
        ip_address: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log GDPR compliance actions."""
        event_map = {
            "export": AuditEventType.GDPR_DATA_EXPORT,
            "delete": AuditEventType.GDPR_DATA_DELETE,
            "consent_given": AuditEventType.GDPR_CONSENT_GIVEN,
            "consent_revoked": AuditEventType.GDPR_CONSENT_REVOKED,
        }
        event_type = event_map.get(action, AuditEventType.GDPR_DATA_EXPORT)
        
        self.log(
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            message=f"GDPR: {action}",
            metadata=details,
        )
    
    def log_security_event(
        self,
        event_type: AuditEventType,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log security-related events."""
        self.log(
            event_type=event_type,
            tenant_id=tenant_id,
            ip_address=ip_address,
            endpoint=endpoint,
            message=f"Security event: {event_type.value}",
            metadata=details,
        )
    
    # ─── Query & Export Methods ───────────────────────────────────────────────
    
    def get_logs(
        self,
        tenant_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit logs with filters."""
        if not self.db_execute:
            return []
        
        conditions = []
        params = []
        
        if tenant_id:
            conditions.append("tenant_id = %s::UUID")
            params.append(tenant_id)
        
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type.value)
        
        if start_date:
            conditions.append("timestamp >= %s")
            params.append(start_date)
        
        if end_date:
            conditions.append("timestamp <= %s")
            params.append(end_date)
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        
        try:
            rows = self.db_execute(f"""
                SELECT id, event_type, timestamp, tenant_id, user_id,
                       endpoint, ip_address, user_agent, status_code,
                       request_id, success, message, metadata
                FROM memory_service.audit_logs
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT %s
            """, tuple(params) if params else None)
            
            return [
                {
                    "id": str(r[0]),
                    "event_type": r[1],
                    "timestamp": r[2].isoformat() if r[2] else None,
                    "tenant_id": str(r[3]) if r[3] else None,
                    "user_id": str(r[4]) if r[4] else None,
                    "endpoint": r[5],
                    "ip_address": r[6],
                    "user_agent": r[7],
                    "status_code": r[8],
                    "request_id": r[9],
                    "success": r[10],
                    "message": r[11],
                    "metadata": r[12],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {e}")
            return []
    
    def get_auth_failures(
        self,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Count recent authentication failures (for lockout enforcement)."""
        if not self.db_execute:
            return 0
        
        if not since:
            since = datetime.now(timezone.utc) - timedelta(hours=1)
        
        conditions = ["event_type = %s", "timestamp >= %s", "success = false"]
        params = [AuditEventType.AUTH_LOGIN_FAILED.value, since]
        
        if email:
            conditions.append("metadata->>'email' = %s")
            params.append(email)
        
        if ip_address:
            conditions.append("ip_address = %s")
            params.append(ip_address)
        
        try:
            rows = self.db_execute(f"""
                SELECT COUNT(*) 
                FROM memory_service.audit_logs
                WHERE {' AND '.join(conditions)}
            """, tuple(params))
            
            return rows[0][0] if rows else 0
        except Exception as e:
            logger.error(f"Failed to count auth failures: {e}")
            return 0
    
    def cleanup_old_logs(self, retention_days: int = 90):
        """Delete audit logs older than retention period (except auth events = 365 days)."""
        if not self.db_execute:
            return
        
        cutoff_general = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_auth = datetime.now(timezone.utc) - timedelta(days=365)
        
        try:
            # Delete general logs older than 90 days
            self.db_execute("""
                DELETE FROM memory_service.audit_logs
                WHERE timestamp < %s
                  AND event_type NOT LIKE 'auth_%%'
                  AND event_type NOT LIKE 'key_%%'
            """, (cutoff_general,))
            
            # Delete auth/key logs older than 1 year
            self.db_execute("""
                DELETE FROM memory_service.audit_logs
                WHERE timestamp < %s
                  AND (event_type LIKE 'auth_%%' OR event_type LIKE 'key_%%')
            """, (cutoff_auth,))
            
            logger.info(f"Audit log cleanup completed (retention: {retention_days}d general, 365d auth)")
        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}")


# ─── Global Instance ──────────────────────────────────────────────────────────

_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
