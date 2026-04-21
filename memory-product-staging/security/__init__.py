"""
Security Infrastructure Module for 0Latency API

This module provides enterprise-grade security features:
- Comprehensive audit logging
- Multi-layer rate limiting
- Authentication hardening (brute force protection, session management)
- GDPR compliance foundations

All components are SOC 2 Type I ready.
"""

from .audit_logger import (
    AuditLogger,
    AuditEventType,
    get_audit_logger,
)

from .rate_limiter_enhanced import (
    check_rate_limit,
    check_ip_rate_limit,
    check_endpoint_rate_limit,
    detect_slow_request,
    get_rate_limit_headers,
    clear_rate_limits,
    ENDPOINT_LIMITS,
    GLOBAL_IP_LIMIT_RPM,
)

from .auth_hardening import (
    validate_password_strength,
    record_login_attempt,
    is_account_locked,
    clear_login_attempts,
    get_login_attempts,
    create_session,
    get_session,
    revoke_session,
    revoke_all_sessions,
    list_active_sessions,
    should_rotate_jwt,
    rotate_jwt,
    rotate_api_key,
    check_brute_force_protection,
    get_security_stats,
    unlock_account,
    MAX_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION_SECONDS,
    MIN_PASSWORD_LENGTH,
)

__all__ = [
    # Audit Logger
    "AuditLogger",
    "AuditEventType",
    "get_audit_logger",
    
    # Rate Limiter
    "check_rate_limit",
    "check_ip_rate_limit",
    "check_endpoint_rate_limit",
    "detect_slow_request",
    "get_rate_limit_headers",
    "clear_rate_limits",
    "ENDPOINT_LIMITS",
    "GLOBAL_IP_LIMIT_RPM",
    
    # Auth Hardening
    "validate_password_strength",
    "record_login_attempt",
    "is_account_locked",
    "clear_login_attempts",
    "get_login_attempts",
    "create_session",
    "get_session",
    "revoke_session",
    "revoke_all_sessions",
    "list_active_sessions",
    "should_rotate_jwt",
    "rotate_jwt",
    "rotate_api_key",
    "check_brute_force_protection",
    "get_security_stats",
    "unlock_account",
    "MAX_LOGIN_ATTEMPTS",
    "LOCKOUT_DURATION_SECONDS",
    "MIN_PASSWORD_LENGTH",
]

__version__ = "1.0.0"
