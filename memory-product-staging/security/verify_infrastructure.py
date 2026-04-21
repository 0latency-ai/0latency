"""
Security Infrastructure Verification Script

Run this to verify all security components are working correctly.
"""
import sys
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

def test_audit_logger():
    """Test audit logging system."""
    from audit_logger import get_audit_logger, AuditEventType
    
    print("Testing Audit Logger...")
    audit = get_audit_logger()
    
    # Log various events
    audit.log_auth_login(
        email="verify@test.com",
        success=True,
        ip_address="127.0.0.1",
        user_agent="VerificationScript/1.0",
        method="test"
    )
    
    logs = audit.get_logs(limit=1)
    assert len(logs) > 0, "No audit logs found"
    assert logs[0]['event_type'] == 'auth_login_success', "Wrong event type"
    
    print("  ✓ Audit logger working")
    return True


def test_rate_limiter():
    """Test rate limiting system."""
    from rate_limiter_enhanced import (
        ENDPOINT_LIMITS,
        GLOBAL_IP_LIMIT_RPM,
        get_rate_limit_headers
    )
    
    print("Testing Rate Limiter...")
    
    # Verify configuration
    assert '/auth/email/login' in ENDPOINT_LIMITS, "Auth endpoint limits missing"
    assert ENDPOINT_LIMITS['/auth/email/login'] == 10, "Wrong limit for login"
    assert GLOBAL_IP_LIMIT_RPM > 0, "Global IP limit not set"
    
    # Test header generation
    headers = get_rate_limit_headers("test-tenant", 100)
    assert 'X-RateLimit-Limit' in headers, "Missing rate limit header"
    assert headers['X-RateLimit-Limit'] == '100', "Wrong limit in header"
    
    print("  ✓ Rate limiter configured")
    return True


def test_auth_hardening():
    """Test authentication hardening."""
    from auth_hardening import (
        validate_password_strength,
        MAX_LOGIN_ATTEMPTS,
        LOCKOUT_DURATION_SECONDS,
        MIN_PASSWORD_LENGTH
    )
    
    print("Testing Auth Hardening...")
    
    # Test password validation
    valid, msg = validate_password_strength("Test1234")
    assert valid == True, f"Strong password rejected: {msg}"
    
    valid, msg = validate_password_strength("weak")
    assert valid == False, "Weak password accepted"
    
    # Verify configuration
    assert MAX_LOGIN_ATTEMPTS == 10, "Wrong max login attempts"
    assert LOCKOUT_DURATION_SECONDS == 3600, "Wrong lockout duration"
    assert MIN_PASSWORD_LENGTH == 8, "Wrong min password length"
    
    print("  ✓ Auth hardening configured")
    return True


def test_database_migration():
    """Test database schema."""
    from storage_multitenant import _get_connection_pool
    
    print("Testing Database Migration...")
    
    pool = _get_connection_pool()
    conn = pool.getconn()
    
    try:
        with conn.cursor() as cur:
            # Check if audit_logs table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'memory_service' 
                    AND table_name = 'audit_logs'
                )
            """)
            exists = cur.fetchone()[0]
            assert exists, "audit_logs table not found"
            
            # Check indexes
            cur.execute("""
                SELECT COUNT(*) FROM pg_indexes
                WHERE schemaname = 'memory_service' 
                AND tablename = 'audit_logs'
            """)
            index_count = cur.fetchone()[0]
            assert index_count >= 8, f"Not enough indexes (found {index_count}, expected 8+)"
            
            # Check views
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.views
                WHERE table_schema = 'memory_service'
                AND table_name IN ('recent_auth_events', 'failed_logins', 'api_usage_24h')
            """)
            view_count = cur.fetchone()[0]
            assert view_count == 3, f"Not all views created (found {view_count}, expected 3)"
            
            # Check cleanup function
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = 'memory_service'
                    AND p.proname = 'cleanup_audit_logs'
                )
            """)
            func_exists = cur.fetchone()[0]
            assert func_exists, "cleanup_audit_logs function not found"
            
        print("  ✓ Database migration applied correctly")
        print(f"    - audit_logs table: exists")
        print(f"    - Indexes: {index_count}")
        print(f"    - Views: {view_count}")
        print(f"    - cleanup function: exists")
        return True
    finally:
        pool.putconn(conn)


def test_module_imports():
    """Test all security modules can be imported."""
    print("Testing Module Imports...")
    
    # Import individual modules
    from audit_logger import AuditLogger, AuditEventType, get_audit_logger
    from rate_limiter_enhanced import (
        check_rate_limit, check_ip_rate_limit, check_endpoint_rate_limit
    )
    from auth_hardening import (
        validate_password_strength, record_login_attempt, is_account_locked
    )
    
    print("  ✓ All modules import successfully")
    return True


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Security Infrastructure Verification")
    print("=" * 60)
    print()
    
    tests = [
        ("Module Imports", test_module_imports),
        ("Database Migration", test_database_migration),
        ("Audit Logger", test_audit_logger),
        ("Rate Limiter", test_rate_limiter),
        ("Auth Hardening", test_auth_hardening),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
            print()
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"  ✗ {name} failed: {e}")
            print()
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if error:
            print(f"       Error: {error}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All security infrastructure components verified!")
        print("\nReady for:")
        print("  - Production deployment")
        print("  - SOC 2 Type I audit")
        print("  - Security review")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
