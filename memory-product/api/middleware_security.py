"""
Security middleware for 0Latency API
Lightweight integration layer for audit logging and rate limiting
"""
import sys
import os
import uuid
from fastapi import Request, HTTPException
import time
import logging

logger = logging.getLogger("zerolatency.security")

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security import AuditLogger, AuditEventType, check_ip_rate_limit
from observability import ErrorTracker, ErrorLevel

# Initialize singletons
_audit_logger = None
_error_tracker = None

def get_audit_logger():
    global _audit_logger
    if _audit_logger is None:
        try:
            _audit_logger = AuditLogger()
        except Exception as e:
            logger.warning(f"AuditLogger init failed: {e}")
            return None
    return _audit_logger

def get_error_tracker():
    global _error_tracker
    if _error_tracker is None:
        try:
            _error_tracker = ErrorTracker()
        except Exception as e:
            logger.warning(f"ErrorTracker init failed: {e}")
            return None
    return _error_tracker

async def security_middleware(request: Request, call_next):
    """
    Security middleware - runs before every API request.
    Designed to NEVER break the API - all failures are logged and swallowed.
    """
    # Let CORS preflight through immediately
    if request.method == "OPTIONS":
        return await call_next(request)

    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    tenant_id = "anon"
    client_ip = request.client.host if request.client else "unknown"

    # IP rate limiting (best effort - don't break API if Redis is down)
    try:
        check_ip_rate_limit(client_ip)
    except HTTPException:
        raise  # Re-raise rate limit responses
    except Exception:
        pass  # Redis down? Continue without rate limiting
    
    # Process the actual request
    response = await call_next(request)
    
    # Post-request: audit logging (best effort)
    try:
        if hasattr(request, "state") and hasattr(request.state, "tenant_id"):
            tenant_id = request.state.tenant_id
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        audit = get_audit_logger()
        if audit:
            # Pass None for anonymous requests (can't store "anon" as UUID)
            db_tenant_id = tenant_id if tenant_id != "anon" else None
            audit.log_api_call(
                tenant_id=db_tenant_id,
                endpoint=request.url.path,
                method=request.method,
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent", "unknown"),
                status_code=response.status_code,
                request_id=request_id,
                latency_ms=latency_ms
            )
    except Exception as e:
        # NEVER let audit logging break the API
        logger.warning(f"Audit log failed: {e}")
    
    return response
