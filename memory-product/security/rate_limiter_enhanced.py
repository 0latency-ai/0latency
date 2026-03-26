"""
Enhanced Rate Limiting for 0Latency API

Multi-layer rate limiting:
1. Per-tenant limits (based on plan tier)
2. Global IP-based limits (DDoS protection)
3. Per-endpoint limits (auth endpoints more restrictive)
4. Slow request detection

Redis-backed with in-memory fallback.
Cloudflare integration ready.
"""
import os
import sys
import time
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
from fastapi import HTTPException

logger = logging.getLogger("rate_limiter")

# Redis client
import redis as _redis

_redis_client = None


def _get_redis():
    """Get or create Redis connection."""
    global _redis_client
    if _redis_client is None:
        try:
            redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
            _redis_client = _redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
            _redis_client.ping()
            logger.info("Redis rate limiter connected")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
            _redis_client = None
    return _redis_client


# In-memory fallback storage
_in_memory_buckets: Dict[str, Tuple[int, float]] = {}


def _clean_in_memory():
    """Clean expired in-memory rate limit buckets."""
    now = time.time()
    expired = [k for k, (_, exp) in _in_memory_buckets.items() if now > exp]
    for k in expired:
        del _in_memory_buckets[k]


# ─── Rate Limit Configuration ────────────────────────────────────────────────

# Per-endpoint rate limits (requests per minute)
ENDPOINT_LIMITS = {
    # Auth endpoints (more restrictive)
    "/auth/email/login": 10,
    "/auth/email/register": 5,
    "/auth/simple-login": 10,
    "/auth/simple-signup": 5,
    "/auth/api-key/regenerate": 3,
    "/auth/verify-email": 20,
    "/auth/resend-verification": 5,
    
    # API endpoints (standard)
    "/api/v1/extract": 100,
    "/api/v1/recall": 200,
    "/api/v1/store": 100,
    
    # Default for all other endpoints
    "_default": 300,
}

# Global IP limits (requests per minute, across all tenants)
GLOBAL_IP_LIMIT_RPM = 600  # 10 req/sec burst tolerance

# Slow request threshold (seconds)
SLOW_REQUEST_THRESHOLD = 30.0


# ─── Rate Limiting Functions ──────────────────────────────────────────────────

def check_rate_limit(
    tenant_id: str,
    rate_limit_rpm: int,
    identifier: Optional[str] = None,
) -> None:
    """
    Check if tenant has exceeded their rate limit.
    
    Args:
        tenant_id: Tenant UUID
        rate_limit_rpm: Requests per minute allowed for this tenant
        identifier: Additional identifier (e.g., endpoint name) for sub-limits
    
    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    r = _get_redis()
    key = f"rl:tenant:{tenant_id}"
    if identifier:
        key += f":{identifier}"
    
    if r:
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, 60)
            
            if count > rate_limit_rpm:
                ttl = max(r.ttl(key), 1)
                logger.warning(f"RATE_LIMIT tenant={tenant_id} limit={rate_limit_rpm} count={count} ttl={ttl}")
                
                # Log to audit
                try:
                    from security.audit_logger import get_audit_logger, AuditEventType
                    audit = get_audit_logger()
                    audit.log_security_event(
                        event_type=AuditEventType.SECURITY_RATE_LIMIT_HIT,
                        tenant_id=tenant_id,
                        details={"limit": rate_limit_rpm, "count": count, "identifier": identifier},
                    )
                except Exception:
                    pass
                
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"Rate limit exceeded ({rate_limit_rpm} requests/min). Retry after {ttl}s.",
                        "limit": rate_limit_rpm,
                        "retry_after": ttl,
                    },
                    headers={"Retry-After": str(ttl)},
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Redis rate-limit check failed, using in-memory: {e}")
    
    # In-memory fallback
    _clean_in_memory()
    now = time.time()
    count, expires_at = _in_memory_buckets.get(key, (0, now + 60))
    
    if now > expires_at:
        count = 0
        expires_at = now + 60
    
    count += 1
    _in_memory_buckets[key] = (count, expires_at)
    
    if count > rate_limit_rpm:
        ttl = int(expires_at - now)
        logger.warning(f"RATE_LIMIT_MEMORY tenant={tenant_id} limit={rate_limit_rpm} count={count}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded ({rate_limit_rpm} requests/min). Retry after {ttl}s.",
                "limit": rate_limit_rpm,
                "retry_after": ttl,
            },
            headers={"Retry-After": str(ttl)},
        )


def check_ip_rate_limit(ip_address: str) -> None:
    """
    Check global IP-based rate limit (DDoS protection).
    
    Args:
        ip_address: Client IP address
    
    Raises:
        HTTPException: 429 if IP exceeds global limit
    """
    r = _get_redis()
    key = f"rl:ip:{ip_address}"
    
    if r:
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, 60)
            
            if count > GLOBAL_IP_LIMIT_RPM:
                ttl = max(r.ttl(key), 1)
                logger.warning(f"IP_RATE_LIMIT ip={ip_address} limit={GLOBAL_IP_LIMIT_RPM} count={count}")
                
                # Log to audit
                try:
                    from security.audit_logger import get_audit_logger, AuditEventType
                    audit = get_audit_logger()
                    audit.log_security_event(
                        event_type=AuditEventType.SECURITY_RATE_LIMIT_HIT,
                        ip_address=ip_address,
                        details={"limit": GLOBAL_IP_LIMIT_RPM, "count": count, "type": "ip_global"},
                    )
                except Exception:
                    pass
                
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"Global rate limit exceeded from your IP. Retry after {ttl}s.",
                        "retry_after": ttl,
                    },
                    headers={"Retry-After": str(ttl)},
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Redis IP rate-limit check failed: {e}")
    
    # In-memory fallback
    _clean_in_memory()
    now = time.time()
    count, expires_at = _in_memory_buckets.get(key, (0, now + 60))
    
    if now > expires_at:
        count = 0
        expires_at = now + 60
    
    count += 1
    _in_memory_buckets[key] = (count, expires_at)
    
    if count > GLOBAL_IP_LIMIT_RPM:
        ttl = int(expires_at - now)
        logger.warning(f"IP_RATE_LIMIT_MEMORY ip={ip_address} limit={GLOBAL_IP_LIMIT_RPM} count={count}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Global rate limit exceeded. Retry after {ttl}s.",
                "retry_after": ttl,
            },
            headers={"Retry-After": str(ttl)},
        )


def check_endpoint_rate_limit(endpoint: str, identifier: str) -> None:
    """
    Check per-endpoint rate limit.
    
    Args:
        endpoint: API endpoint path
        identifier: Unique identifier (tenant_id or IP)
    
    Raises:
        HTTPException: 429 if endpoint limit exceeded
    """
    limit = ENDPOINT_LIMITS.get(endpoint, ENDPOINT_LIMITS["_default"])
    
    r = _get_redis()
    key = f"rl:endpoint:{endpoint}:{identifier}"
    
    if r:
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, 60)
            
            if count > limit:
                ttl = max(r.ttl(key), 1)
                logger.warning(f"ENDPOINT_RATE_LIMIT endpoint={endpoint} id={identifier} limit={limit} count={count}")
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "endpoint_rate_limit_exceeded",
                        "message": f"Rate limit for {endpoint} exceeded ({limit}/min). Retry after {ttl}s.",
                        "limit": limit,
                        "retry_after": ttl,
                    },
                    headers={"Retry-After": str(ttl)},
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Redis endpoint rate-limit check failed: {e}")
    
    # In-memory fallback
    _clean_in_memory()
    now = time.time()
    count, expires_at = _in_memory_buckets.get(key, (0, now + 60))
    
    if now > expires_at:
        count = 0
        expires_at = now + 60
    
    count += 1
    _in_memory_buckets[key] = (count, expires_at)
    
    if count > limit:
        ttl = int(expires_at - now)
        logger.warning(f"ENDPOINT_RATE_LIMIT_MEMORY endpoint={endpoint} limit={limit} count={count}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "endpoint_rate_limit_exceeded",
                "message": f"Rate limit for {endpoint} exceeded ({limit}/min). Retry after {ttl}s.",
                "limit": limit,
                "retry_after": ttl,
            },
            headers={"Retry-After": str(ttl)},
        )


def detect_slow_request(start_time: float, endpoint: str, tenant_id: Optional[str] = None):
    """
    Detect and log slow requests.
    
    Args:
        start_time: Request start timestamp
        endpoint: API endpoint
        tenant_id: Tenant ID (if available)
    """
    elapsed = time.time() - start_time
    
    if elapsed > SLOW_REQUEST_THRESHOLD:
        logger.warning(f"SLOW_REQUEST endpoint={endpoint} tenant={tenant_id} duration={elapsed:.2f}s")
        
        # Log to audit
        try:
            from security.audit_logger import get_audit_logger, AuditEventType
            audit = get_audit_logger()
            audit.log_security_event(
                event_type=AuditEventType.SECURITY_SUSPICIOUS_ACTIVITY,
                tenant_id=tenant_id,
                endpoint=endpoint,
                details={"type": "slow_request", "duration_seconds": elapsed},
            )
        except Exception:
            pass


def get_rate_limit_headers(
    tenant_id: str,
    rate_limit_rpm: int,
) -> Dict[str, str]:
    """
    Get rate limit headers for response.
    
    Returns:
        Dict of headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
    """
    r = _get_redis()
    key = f"rl:tenant:{tenant_id}"
    
    remaining = rate_limit_rpm
    reset = int(time.time()) + 60
    
    if r:
        try:
            current = int(r.get(key) or 0)
            remaining = max(0, rate_limit_rpm - current)
            ttl = r.ttl(key)
            if ttl > 0:
                reset = int(time.time()) + ttl
        except Exception:
            pass
    
    return {
        "X-RateLimit-Limit": str(rate_limit_rpm),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset),
    }


def clear_rate_limits(tenant_id: str):
    """
    Clear all rate limits for a tenant (admin action).
    
    Args:
        tenant_id: Tenant UUID
    """
    r = _get_redis()
    if r:
        try:
            # Find and delete all keys for this tenant
            pattern = f"rl:tenant:{tenant_id}*"
            for key in r.scan_iter(match=pattern):
                r.delete(key)
            logger.info(f"Cleared rate limits for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to clear rate limits: {e}")
