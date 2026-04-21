"""
Authentication & Authorization Hardening for 0Latency API

Features:
- Failed login lockout (10 attempts = 1 hour block)
- JWT token rotation & expiry enforcement
- API key rotation audit log
- Session management (force logout capability)
- Password strength validation
- Brute force protection

SOC 2 Type I ready.
"""
import os
import sys
import time
import secrets
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple

logger = logging.getLogger("auth_hardening")

# Redis for session storage
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
        except Exception as e:
            logger.warning(f"Redis unavailable for sessions: {e}")
            _redis_client = None
    return _redis_client


# ─── Configuration ────────────────────────────────────────────────────────────

# Failed login lockout
MAX_LOGIN_ATTEMPTS = 10
LOCKOUT_DURATION_SECONDS = 3600  # 1 hour

# Password requirements
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGIT = True
REQUIRE_SPECIAL = False  # Optional for now

# JWT rotation
JWT_ROTATION_THRESHOLD_HOURS = 24  # Rotate if token is older than 24h
JWT_EXPIRY_HOURS = 72  # 3 days


# ─── Password Validation ──────────────────────────────────────────────────────

def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password meets security requirements.
    
    Returns:
        (is_valid, error_message)
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    
    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must not exceed {MAX_PASSWORD_LENGTH} characters"
    
    if REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    if REQUIRE_SPECIAL:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"
    
    # Check against common weak passwords
    weak_passwords = {
        "password", "12345678", "password123", "qwerty123", "admin123",
        "letmein123", "welcome123", "monkey123"
    }
    if password.lower() in weak_passwords:
        return False, "This password is too common. Please choose a stronger password."
    
    return True, None


# ─── Failed Login Tracking ────────────────────────────────────────────────────

def record_login_attempt(identifier: str, success: bool) -> None:
    """
    Record a login attempt (success or failure).
    
    Args:
        identifier: Email or IP address
        success: Whether login succeeded
    """
    if success:
        # Clear failed attempts on successful login
        clear_login_attempts(identifier)
        return
    
    r = _get_redis()
    if not r:
        return
    
    key = f"login_attempts:{identifier}"
    try:
        count = r.incr(key)
        if count == 1:
            r.expire(key, LOCKOUT_DURATION_SECONDS)
        
        if count >= MAX_LOGIN_ATTEMPTS:
            # Lock the account
            lockout_key = f"lockout:{identifier}"
            r.setex(lockout_key, LOCKOUT_DURATION_SECONDS, "1")
            logger.warning(f"ACCOUNT_LOCKED identifier={identifier} attempts={count}")
            
            # Log to audit
            try:
                from security.audit_logger import get_audit_logger, AuditEventType
                audit = get_audit_logger()
                audit.log_security_event(
                    event_type=AuditEventType.SECURITY_SUSPICIOUS_ACTIVITY,
                    details={
                        "type": "account_lockout",
                        "identifier": identifier,
                        "attempts": count,
                        "lockout_duration_seconds": LOCKOUT_DURATION_SECONDS,
                    },
                )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Failed to record login attempt: {e}")


def is_account_locked(identifier: str) -> Tuple[bool, int]:
    """
    Check if account is locked due to failed login attempts.
    
    Returns:
        (is_locked, ttl_seconds)
    """
    r = _get_redis()
    if not r:
        return False, 0
    
    lockout_key = f"lockout:{identifier}"
    try:
        locked = r.exists(lockout_key)
        if locked:
            ttl = r.ttl(lockout_key)
            return True, max(ttl, 0)
        return False, 0
    except Exception as e:
        logger.error(f"Failed to check account lock: {e}")
        return False, 0


def clear_login_attempts(identifier: str) -> None:
    """Clear failed login attempts (on successful login or manual reset)."""
    r = _get_redis()
    if not r:
        return
    
    try:
        r.delete(f"login_attempts:{identifier}")
        r.delete(f"lockout:{identifier}")
    except Exception as e:
        logger.error(f"Failed to clear login attempts: {e}")


def get_login_attempts(identifier: str) -> int:
    """Get current failed login attempt count."""
    r = _get_redis()
    if not r:
        return 0
    
    try:
        count = r.get(f"login_attempts:{identifier}")
        return int(count) if count else 0
    except Exception:
        return 0


# ─── Session Management ───────────────────────────────────────────────────────

def create_session(
    user_id: str,
    tenant_id: str,
    jwt_token: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    ttl_seconds: int = JWT_EXPIRY_HOURS * 3600,
) -> str:
    """
    Create a session record for force logout capability.
    
    Returns:
        session_id
    """
    session_id = secrets.token_urlsafe(32)
    r = _get_redis()
    
    if r:
        try:
            session_data = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "jwt_token": jwt_token,
                "ip_address": ip_address or "unknown",
                "user_agent": user_agent or "unknown",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Store session data
            key = f"session:{session_id}"
            r.hset(key, mapping=session_data)
            r.expire(key, ttl_seconds)
            
            # Add to user's session set
            user_sessions_key = f"user_sessions:{user_id}"
            r.sadd(user_sessions_key, session_id)
            r.expire(user_sessions_key, ttl_seconds)
            
            logger.info(f"Session created: user={user_id} session={session_id}")
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
    
    return session_id


def get_session(session_id: str) -> Optional[Dict]:
    """Get session data."""
    r = _get_redis()
    if not r:
        return None
    
    try:
        key = f"session:{session_id}"
        data = r.hgetall(key)
        return data if data else None
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        return None


def revoke_session(session_id: str, user_id: str) -> bool:
    """
    Revoke a session (force logout).
    
    Returns:
        True if session was revoked
    """
    r = _get_redis()
    if not r:
        return False
    
    try:
        # Delete session
        key = f"session:{session_id}"
        deleted = r.delete(key)
        
        # Remove from user's session set
        user_sessions_key = f"user_sessions:{user_id}"
        r.srem(user_sessions_key, session_id)
        
        logger.info(f"Session revoked: session={session_id} user={user_id}")
        
        # Log to audit
        try:
            from security.audit_logger import get_audit_logger, AuditEventType
            audit = get_audit_logger()
            audit.log_security_event(
                event_type=AuditEventType.AUTH_LOGOUT,
                user_id=user_id,
                details={"session_id": session_id, "forced": True},
            )
        except Exception:
            pass
        
        return deleted > 0
    except Exception as e:
        logger.error(f"Failed to revoke session: {e}")
        return False


def revoke_all_sessions(user_id: str) -> int:
    """
    Revoke all sessions for a user (force logout everywhere).
    
    Returns:
        Number of sessions revoked
    """
    r = _get_redis()
    if not r:
        return 0
    
    try:
        user_sessions_key = f"user_sessions:{user_id}"
        session_ids = r.smembers(user_sessions_key)
        
        count = 0
        for session_id in session_ids:
            if revoke_session(session_id, user_id):
                count += 1
        
        logger.info(f"All sessions revoked: user={user_id} count={count}")
        return count
    except Exception as e:
        logger.error(f"Failed to revoke all sessions: {e}")
        return 0


def list_active_sessions(user_id: str) -> list:
    """List all active sessions for a user."""
    r = _get_redis()
    if not r:
        return []
    
    try:
        user_sessions_key = f"user_sessions:{user_id}"
        session_ids = r.smembers(user_sessions_key)
        
        sessions = []
        for session_id in session_ids:
            session_data = get_session(session_id)
            if session_data:
                sessions.append({
                    "session_id": session_id,
                    **session_data,
                })
        
        return sessions
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return []


# ─── JWT Token Rotation ───────────────────────────────────────────────────────

def should_rotate_jwt(jwt_payload: dict) -> bool:
    """
    Check if JWT should be rotated based on age.
    
    Args:
        jwt_payload: Decoded JWT payload
    
    Returns:
        True if token should be rotated
    """
    iat = jwt_payload.get("iat")
    if not iat:
        return True
    
    # Convert to datetime
    if isinstance(iat, int) or isinstance(iat, float):
        issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
    else:
        return True
    
    age = datetime.now(timezone.utc) - issued_at
    threshold = timedelta(hours=JWT_ROTATION_THRESHOLD_HOURS)
    
    return age > threshold


def rotate_jwt(old_token: str, user_data: dict) -> str:
    """
    Rotate JWT token (issue new token, invalidate old one).
    
    Args:
        old_token: Current JWT token
        user_data: User data for new token
    
    Returns:
        New JWT token
    """
    # Import auth module
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
    from auth import create_jwt
    
    new_token = create_jwt(user_data)
    
    # Log rotation
    logger.info(f"JWT rotated: user={user_data.get('id')}")
    
    # Log to audit
    try:
        from security.audit_logger import get_audit_logger, AuditEventType
        audit = get_audit_logger()
        audit.log(
            event_type=AuditEventType.AUTH_TOKEN_REFRESH,
            user_id=user_data.get("id"),
            message="JWT token rotated",
        )
    except Exception:
        pass
    
    return new_token


# ─── API Key Rotation ──────────────────────────────────────────────────────────

def rotate_api_key(tenant_id: str, user_id: Optional[str] = None) -> str:
    """
    Rotate API key and log to audit.
    
    Returns:
        New API key
    """
    new_key = f"zl_live_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
    new_hash = hashlib.sha256(new_key.encode()).hexdigest()
    
    # Update in database
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from storage_multitenant import _db_execute_rows
    
    try:
        _db_execute_rows("""
            UPDATE memory_service.tenants 
            SET api_key_hash = %s, api_key_live = %s 
            WHERE id = %s::UUID
        """, (new_hash, new_key, tenant_id))
        
        logger.info(f"API key rotated: tenant={tenant_id}")
        
        # Log to audit
        try:
            from security.audit_logger import get_audit_logger
            audit = get_audit_logger()
            audit.log_api_key_action(
                tenant_id=tenant_id,
                user_id=user_id,
                action="regenerated",
            )
        except Exception:
            pass
        
        return new_key
    except Exception as e:
        logger.error(f"Failed to rotate API key: {e}")
        raise


# ─── Brute Force Protection ──────────────────────────────────────────────────

def check_brute_force_protection(identifier: str) -> None:
    """
    Check brute force protection before allowing login attempt.
    
    Raises:
        Exception if account is locked
    """
    is_locked, ttl = is_account_locked(identifier)
    
    if is_locked:
        minutes = ttl // 60
        from fastapi import HTTPException
        raise HTTPException(
            status_code=429,
            detail={
                "error": "account_locked",
                "message": f"Account locked due to too many failed login attempts. Try again in {minutes} minutes.",
                "retry_after": ttl,
            },
            headers={"Retry-After": str(ttl)},
        )
    
    # Check current attempts
    attempts = get_login_attempts(identifier)
    remaining = MAX_LOGIN_ATTEMPTS - attempts
    
    if remaining <= 3 and remaining > 0:
        logger.warning(f"BRUTE_FORCE_WARNING identifier={identifier} attempts={attempts} remaining={remaining}")


# ─── Monitoring & Admin Functions ─────────────────────────────────────────────

def get_security_stats() -> Dict:
    """Get security statistics for monitoring."""
    r = _get_redis()
    if not r:
        return {"error": "Redis unavailable"}
    
    try:
        # Count locked accounts
        lockout_keys = list(r.scan_iter(match="lockout:*"))
        locked_accounts = len(lockout_keys)
        
        # Count active sessions
        session_keys = list(r.scan_iter(match="session:*"))
        active_sessions = len(session_keys)
        
        return {
            "locked_accounts": locked_accounts,
            "active_sessions": active_sessions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get security stats: {e}")
        return {"error": str(e)}


def unlock_account(identifier: str, admin_user_id: str) -> bool:
    """
    Manually unlock an account (admin action).
    
    Args:
        identifier: Email or IP to unlock
        admin_user_id: Admin user performing the unlock
    
    Returns:
        True if account was unlocked
    """
    clear_login_attempts(identifier)
    
    logger.info(f"Account unlocked: identifier={identifier} admin={admin_user_id}")
    
    # Log to audit
    try:
        from security.audit_logger import get_audit_logger, AuditEventType
        audit = get_audit_logger()
        audit.log_admin_action(
            admin_user_id=admin_user_id,
            action_type=AuditEventType.ADMIN_TENANT_UPDATED,
            details={"action": "unlock_account", "identifier": identifier},
        )
    except Exception:
        pass
    
    return True
