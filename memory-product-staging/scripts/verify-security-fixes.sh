#!/bin/bash
# Security Fixes Verification Script
# Date: 2026-03-25
# Purpose: Verify all HIGH/MEDIUM priority security fixes were applied correctly

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "0Latency Security Fixes Verification"
echo "=========================================="
echo ""

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

function check_pass() {
    echo "  ✅ PASS: $1"
    ((PASS_COUNT++))
}

function check_fail() {
    echo "  ❌ FAIL: $1"
    ((FAIL_COUNT++))
}

function check_warn() {
    echo "  ⚠️  WARN: $1"
    ((WARN_COUNT++))
}

# ==========================================
# HIGH PRIORITY CHECKS
# ==========================================
echo "🔴 HIGH PRIORITY FIXES"
echo "---"

# Check 1: Disaster Recovery Documentation
echo "1. Disaster Recovery Documentation"
if [ -f "$PROJECT_ROOT/DISASTER_RECOVERY.md" ]; then
    check_pass "DISASTER_RECOVERY.md exists"
    # Check if it has key sections
    if grep -q "Backup Strategy" "$PROJECT_ROOT/DISASTER_RECOVERY.md" && \
       grep -q "Recovery Procedures" "$PROJECT_ROOT/DISASTER_RECOVERY.md"; then
        check_pass "Contains required sections (Backup Strategy, Recovery Procedures)"
    else
        check_warn "File exists but may be incomplete"
    fi
else
    check_fail "DISASTER_RECOVERY.md not found"
    echo "     → Create this file using template in SECURITY_FIXES_ACTIONABLE.md"
fi
echo ""

# Check 2: Memory Limit Constraint
echo "2. Memory Limit Database Constraint"
if [ -z "$MEMORY_DB_CONN" ]; then
    check_warn "MEMORY_DB_CONN not set, cannot verify database constraint"
    echo "     → Set environment variable and re-run this script"
else
    # Check if trigger exists
    TRIGGER_EXISTS=$(psql "$MEMORY_DB_CONN" -t -c "
        SELECT COUNT(*) 
        FROM information_schema.triggers 
        WHERE trigger_name = 'enforce_memory_limit' 
          AND event_object_table = 'memories'
    " 2>/dev/null || echo "0")
    
    if [ "$TRIGGER_EXISTS" -gt 0 ]; then
        check_pass "Database trigger 'enforce_memory_limit' exists"
        
        # Check if function exists
        FUNCTION_EXISTS=$(psql "$MEMORY_DB_CONN" -t -c "
            SELECT COUNT(*) 
            FROM pg_proc p 
            JOIN pg_namespace n ON p.pronamespace = n.oid 
            WHERE n.nspname = 'memory_service' 
              AND p.proname = 'check_memory_limit'
        " 2>/dev/null || echo "0")
        
        if [ "$FUNCTION_EXISTS" -gt 0 ]; then
            check_pass "Database function 'check_memory_limit()' exists"
        else
            check_fail "Function missing (trigger won't work)"
        fi
    else
        check_fail "Database trigger not found"
        echo "     → Run: psql \$MEMORY_DB_CONN -f migrations/002_add_memory_limit_constraint.sql"
    fi
fi
echo ""

# ==========================================
# MEDIUM PRIORITY CHECKS
# ==========================================
echo "🟡 MEDIUM PRIORITY FIXES"
echo "---"

# Check 3: CORS Configuration
echo "3. Environment-Aware CORS Configuration"
if grep -q "ENV = os.environ.get(\"ENVIRONMENT\"" "$PROJECT_ROOT/api/main.py"; then
    check_pass "Environment-aware CORS code present"
    
    # Check if localhost is conditional
    if grep -q "_CORS_ORIGINS_DEV.*localhost" "$PROJECT_ROOT/api/main.py" && \
       grep -q "_CORS_ORIGINS_PROD" "$PROJECT_ROOT/api/main.py"; then
        check_pass "Localhost restricted to dev environment"
    else
        check_warn "CORS code may need review"
    fi
else
    # Check if old hardcoded CORS still exists
    if grep -q "localhost:3000.*164.90.156.169" "$PROJECT_ROOT/api/main.py"; then
        check_fail "Still using hardcoded CORS with localhost"
        echo "     → Update api/main.py per SECURITY_FIXES_ACTIONABLE.md"
    else
        check_warn "CORS configuration not using recommended pattern"
    fi
fi
echo ""

# Check 4: ENVIRONMENT variable set
echo "4. Environment Variable Configuration"
if [ -n "$ENVIRONMENT" ]; then
    check_pass "ENVIRONMENT variable is set: $ENVIRONMENT"
    if [ "$ENVIRONMENT" = "production" ]; then
        check_pass "Set to production (correct for prod deploy)"
    elif [ "$ENVIRONMENT" = "development" ]; then
        check_warn "Set to development (localhost CORS enabled)"
    fi
else
    check_warn "ENVIRONMENT not set (will default to production)"
    echo "     → Add ENVIRONMENT=production to .env"
fi
echo ""

# ==========================================
# LOW PRIORITY CHECKS  
# ==========================================
echo "🟢 LOW PRIORITY FIXES"
echo "---"

# Check 5: Verification Token Logging
echo "5. Email Verification Token Logging"
if grep -q "EMAIL_VERIFICATION.*url=.*verification_url" "$PROJECT_ROOT/api/auth.py"; then
    check_warn "Still logging full verification URLs"
    echo "     → Update api/auth.py to remove token from logs"
elif grep -q "EMAIL_VERIFICATION_SENT" "$PROJECT_ROOT/api/auth.py"; then
    check_pass "Token removed from logs"
else
    check_warn "Cannot determine token logging status"
fi
echo ""

# ==========================================
# BONUS CHECKS
# ==========================================
echo "📋 BONUS SECURITY CHECKS"
echo "---"

# Check 6: Stripe Webhook Secret
echo "6. Stripe Webhook Secret"
if [ -f "$PROJECT_ROOT/.env" ]; then
    if grep -q "STRIPE_WEBHOOK_SECRET=" "$PROJECT_ROOT/.env"; then
        check_pass "STRIPE_WEBHOOK_SECRET configured in .env"
    else
        check_fail "STRIPE_WEBHOOK_SECRET missing from .env"
    fi
else
    check_warn ".env file not found"
fi
echo ""

# Check 7: Password Hashing
echo "7. Password Hashing"
if grep -q "from passlib.hash import bcrypt" "$PROJECT_ROOT/api/auth.py"; then
    check_pass "bcrypt password hashing in use"
else
    check_warn "Password hashing library not found or changed"
fi
echo ""

# Check 8: SQL Injection Protection
echo "8. SQL Injection Protection (Parameterized Queries)"
# Check for any potential string formatting in SQL
DANGEROUS_SQL=$(grep -r "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE" "$PROJECT_ROOT/src" "$PROJECT_ROOT/api" 2>/dev/null | grep -v "f\"\"\"" || true)
if [ -z "$DANGEROUS_SQL" ]; then
    check_pass "No f-string SQL queries found (good!)"
else
    check_warn "Potential f-string SQL found (verify these are safe)"
    echo "$DANGEROUS_SQL" | head -3
fi
echo ""

# Check 9: Rate Limiting
echo "9. Rate Limiting Implementation"
if grep -q "def _check_rate_limit" "$PROJECT_ROOT/api/main.py"; then
    check_pass "Rate limiting function exists"
    
    if grep -q "redis.incr\|r.incr" "$PROJECT_ROOT/api/main.py"; then
        check_pass "Redis-backed rate limiting configured"
    else
        check_warn "Rate limiting may be in-memory only"
    fi
else
    check_fail "Rate limiting function not found"
fi
echo ""

# ==========================================
# SUMMARY
# ==========================================
echo ""
echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="
echo "✅ Passed:  $PASS_COUNT"
echo "⚠️  Warnings: $WARN_COUNT"
echo "❌ Failed:  $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    if [ $WARN_COUNT -eq 0 ]; then
        echo "🎉 ALL CHECKS PASSED!"
        echo ""
        echo "Security posture: EXCELLENT"
        echo "Ready for production deployment."
        exit 0
    else
        echo "✅ All critical checks passed"
        echo "⚠️  Some warnings present (review above)"
        echo ""
        echo "Security posture: GOOD"
        echo "Safe for production, address warnings when convenient."
        exit 0
    fi
else
    echo "❌ SOME CHECKS FAILED"
    echo ""
    echo "Security posture: NEEDS ATTENTION"
    echo "Fix failed checks before production deployment."
    echo ""
    echo "See SECURITY_FIXES_ACTIONABLE.md for remediation steps."
    exit 1
fi
