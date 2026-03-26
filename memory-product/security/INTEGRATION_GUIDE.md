# Security Infrastructure Integration Guide

**Status:** ✅ Verified & Ready for Integration  
**Date:** March 25, 2026

---

## Quick Start

All security components have been built and tested. Follow these steps to integrate them into the 0Latency API.

## Step 1: Verify Installation

```bash
cd /root/.openclaw/workspace/memory-product
python3 security/verify_infrastructure.py
```

**Expected output:**
```
🎉 All security infrastructure components verified!

Ready for:
  - Production deployment
  - SOC 2 Type I audit
  - Security review
```

---

## Step 2: Integrate Audit Logging

### Option A: Automatic API Call Logging (Recommended)

Add to `api/main.py` middleware:

```python
from security.audit_logger import get_audit_logger
import time

@app.middleware("http")
async def security_audit_middleware(request: Request, call_next):
    """Log all API calls to audit system."""
    audit = get_audit_logger()
    start = time.time()
    request_id = str(uuid.uuid4())[:8]
    
    # Store request ID for downstream use
    request.state.request_id = request_id
    
    response = await call_next(request)
    
    # Log API call if tenant context available
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id:
        latency_ms = int((time.time() - start) * 1000)
        audit.log_api_call(
            tenant_id=tenant_id,
            endpoint=request.url.path,
            method=request.method,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            status_code=response.status_code,
            request_id=request_id,
            latency_ms=latency_ms,
        )
    
    return response
```

### Option B: Manual Logging in Specific Endpoints

```python
from security.audit_logger import get_audit_logger

@router.post("/api/v1/store")
async def store_memory(req: StoreRequest, tenant: dict = Depends(get_tenant)):
    audit = get_audit_logger()
    
    # ... business logic ...
    
    # Log memory access
    audit.log_memory_access(
        tenant_id=tenant["id"],
        action="created",
        memory_id=memory_id,
        agent_id=req.agent_id,
        count=1
    )
    
    return {"id": memory_id}
```

---

## Step 3: Integrate Auth Hardening

### Update Login Endpoints

**File:** `api/auth.py`

```python
from security.auth_hardening import (
    check_brute_force_protection,
    record_login_attempt,
    validate_password_strength,
    create_session
)
from security.audit_logger import get_audit_logger

@router.post("/email/login")
async def email_login(req: EmailLoginRequest, request: Request):
    audit = get_audit_logger()
    
    # 1. Check brute force protection
    try:
        check_brute_force_protection(req.email)
        check_brute_force_protection(request.client.host)
    except HTTPException as e:
        # Log lockout event
        audit.log_auth_login(
            email=req.email,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            failure_reason="Account locked"
        )
        raise
    
    # 2. Verify credentials
    user = find_user_by_email(req.email)
    if not user or not bcrypt.verify(req.password, user["password_hash"]):
        # Record failed attempt
        record_login_attempt(req.email, success=False)
        record_login_attempt(request.client.host, success=False)
        
        # Log failure
        audit.log_auth_login(
            email=req.email,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            failure_reason="Invalid credentials"
        )
        
        raise HTTPException(401, detail="Invalid email or password")
    
    # 3. Success - clear attempts and create session
    record_login_attempt(req.email, success=True)
    record_login_attempt(request.client.host, success=True)
    
    token = create_jwt(user)
    
    session_id = create_session(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        jwt_token=token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    # Log success
    audit.log_auth_login(
        email=req.email,
        success=True,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        user_id=user["id"],
        method="email"
    )
    
    return {"token": token, "session_id": session_id, "user": user}
```

### Update Registration Endpoints

```python
@router.post("/email/register")
async def email_register(req: EmailRegisterRequest):
    # 1. Validate password strength
    valid, error_msg = validate_password_strength(req.password)
    if not valid:
        raise HTTPException(400, detail=error_msg)
    
    # ... rest of registration logic ...
```

---

## Step 4: Integrate Enhanced Rate Limiting

### Add to Middleware

**File:** `api/main.py`

```python
from security.rate_limiter_enhanced import (
    check_ip_rate_limit,
    check_endpoint_rate_limit,
    detect_slow_request,
    get_rate_limit_headers
)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Multi-layer rate limiting."""
    start = time.time()
    
    # 1. Global IP rate limit (DDoS protection)
    check_ip_rate_limit(request.client.host)
    
    # 2. Per-endpoint rate limit
    tenant_id = getattr(request.state, "tenant_id", None)
    identifier = tenant_id or request.client.host
    check_endpoint_rate_limit(request.url.path, identifier)
    
    response = await call_next(request)
    
    # 3. Detect slow requests
    if tenant_id:
        detect_slow_request(start, request.url.path, tenant_id)
    
    # 4. Add rate limit headers
    if tenant_id:
        headers = get_rate_limit_headers(tenant_id, rate_limit_rpm=300)  # Get from tenant plan
        for key, value in headers.items():
            response.headers[key] = value
    
    return response
```

### Per-Tenant Rate Limiting (existing logic)

The existing `check_rate_limit()` function in `main.py` can now be replaced with:

```python
from security.rate_limiter_enhanced import check_rate_limit

# In your tenant authentication logic
tenant = get_tenant_by_api_key(api_key)
check_rate_limit(tenant["id"], tenant["rate_limit_rpm"])
```

---

## Step 5: Add GDPR Endpoints

### Data Export

```python
from security.audit_logger import get_audit_logger

@router.get("/api/v1/tenant/export")
async def export_tenant_data(claims: dict = Depends(require_jwt), request: Request):
    """GDPR Article 20: Right to data portability."""
    audit = get_audit_logger()
    tenant_id = claims["tenant_id"]
    
    # Log GDPR action
    audit.log_gdpr_action(
        tenant_id=tenant_id,
        user_id=claims["sub"],
        action="export",
        ip_address=request.client.host,
        details={"format": "json"}
    )
    
    # Export all memories
    memories = get_all_memories(tenant_id)
    entities = get_all_entities(tenant_id)
    
    return {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
        "memories": memories,
        "entities": entities,
        "total_memories": len(memories)
    }
```

### Data Deletion

```python
@router.delete("/api/v1/tenant/data")
async def delete_all_tenant_data(
    claims: dict = Depends(require_jwt),
    request: Request,
    confirm: str = Query(..., description="Type 'DELETE' to confirm")
):
    """GDPR Article 17: Right to erasure."""
    if confirm != "DELETE":
        raise HTTPException(400, detail="Confirmation required")
    
    audit = get_audit_logger()
    tenant_id = claims["tenant_id"]
    
    # Log GDPR action BEFORE deletion
    audit.log_gdpr_action(
        tenant_id=tenant_id,
        user_id=claims["sub"],
        action="delete",
        ip_address=request.client.host,
        details={"confirmation": confirm}
    )
    
    # Delete all data
    delete_all_memories(tenant_id)
    delete_all_entities(tenant_id)
    delete_tenant(tenant_id)
    
    return {"message": "All data deleted successfully"}
```

---

## Step 6: Session Management Endpoints

### List Active Sessions

```python
from security.auth_hardening import list_active_sessions, revoke_session, revoke_all_sessions

@router.get("/auth/sessions")
async def get_active_sessions(claims: dict = Depends(require_jwt)):
    """List all active sessions for current user."""
    sessions = list_active_sessions(claims["sub"])
    return {"sessions": sessions, "count": len(sessions)}
```

### Revoke Session

```python
@router.post("/auth/session/revoke")
async def revoke_user_session(
    session_id: str,
    claims: dict = Depends(require_jwt)
):
    """Force logout a specific session."""
    success = revoke_session(session_id, claims["sub"])
    if not success:
        raise HTTPException(404, detail="Session not found")
    return {"message": "Session revoked"}
```

### Revoke All Sessions

```python
@router.post("/auth/session/revoke-all")
async def revoke_all_user_sessions(claims: dict = Depends(require_jwt)):
    """Force logout everywhere."""
    count = revoke_all_sessions(claims["sub"])
    return {"message": f"Revoked {count} session(s)"}
```

---

## Step 7: Admin & Monitoring Endpoints

### Security Stats Dashboard

```python
from security.auth_hardening import get_security_stats

@router.get("/admin/security/stats")
async def security_stats(admin_key: str = Header(..., alias="X-Admin-Key")):
    """Security metrics for admin dashboard."""
    if admin_key != os.environ.get("MEMORY_ADMIN_KEY"):
        raise HTTPException(403, detail="Admin access required")
    
    stats = get_security_stats()
    return stats
```

### Unlock Account (Admin)

```python
from security.auth_hardening import unlock_account

@router.post("/admin/security/unlock")
async def admin_unlock_account(
    identifier: str,
    admin_key: str = Header(..., alias="X-Admin-Key")
):
    """Manually unlock a locked account."""
    if admin_key != os.environ.get("MEMORY_ADMIN_KEY"):
        raise HTTPException(403, detail="Admin access required")
    
    unlock_account(identifier, admin_user_id="admin")
    return {"message": f"Account {identifier} unlocked"}
```

### Audit Log Query

```python
from security.audit_logger import get_audit_logger, AuditEventType

@router.get("/admin/audit-logs")
async def query_audit_logs(
    tenant_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    admin_key: str = Header(..., alias="X-Admin-Key")
):
    """Query audit logs (admin only)."""
    if admin_key != os.environ.get("MEMORY_ADMIN_KEY"):
        raise HTTPException(403, detail="Admin access required")
    
    audit = get_audit_logger()
    
    event_type_enum = AuditEventType(event_type) if event_type else None
    
    logs = audit.get_logs(
        tenant_id=tenant_id,
        event_type=event_type_enum,
        limit=limit
    )
    
    return {"logs": logs, "count": len(logs)}
```

---

## Step 8: Scheduled Maintenance

### Audit Log Cleanup (Cron Job)

Add to crontab or system scheduler:

```bash
# Run daily at 2 AM UTC
0 2 * * * cd /root/.openclaw/workspace/memory-product && python3 -c "from dotenv import load_dotenv; load_dotenv(); import sys; sys.path.insert(0, 'src'); from storage_multitenant import _get_connection_pool; pool = _get_connection_pool(); conn = pool.getconn(); conn.autocommit = True; cur = conn.cursor(); cur.execute('SELECT * FROM memory_service.cleanup_audit_logs(90, 365)'); pool.putconn(conn); print('Audit logs cleaned')"
```

Or create a dedicated script:

```python
# scripts/cleanup_audit_logs.py
from dotenv import load_dotenv
load_dotenv()

import sys
sys.path.insert(0, 'src')
from storage_multitenant import _get_connection_pool

pool = _get_connection_pool()
conn = pool.getconn()

try:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM memory_service.cleanup_audit_logs(90, 365)")
        result = cur.fetchall()
        print(f"Cleaned up audit logs: {result}")
finally:
    pool.putconn(conn)
```

Run via cron:
```bash
0 2 * * * cd /path/to/memory-product && python3 scripts/cleanup_audit_logs.py
```

---

## Testing Integration

### 1. Test Audit Logging

```bash
curl -X POST https://api.0latency.ai/auth/email/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"wrong"}'

# Check audit logs (admin endpoint)
curl https://api.0latency.ai/admin/audit-logs?limit=10 \
  -H "X-Admin-Key: your-admin-key"
```

### 2. Test Brute Force Protection

```bash
# Trigger 10 failed logins
for i in {1..10}; do
  curl -X POST https://api.0latency.ai/auth/email/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
  sleep 1
done

# 11th attempt should return 429 (account locked)
curl -X POST https://api.0latency.ai/auth/email/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234"}' \
  -v
```

### 3. Test Rate Limiting

```bash
# Rapid requests should trigger rate limit
for i in {1..20}; do
  curl -X POST https://api.0latency.ai/api/v1/extract \
    -H "Authorization: Bearer your-api-key" \
    -H "Content-Type: application/json" \
    -d '{"text":"test"}' &
done
wait
```

### 4. Test Session Management

```bash
# Login
TOKEN=$(curl -X POST https://api.0latency.ai/auth/email/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234"}' | jq -r '.token')

# List sessions
curl https://api.0latency.ai/auth/sessions \
  -H "Authorization: Bearer $TOKEN"

# Revoke all
curl -X POST https://api.0latency.ai/auth/session/revoke-all \
  -H "Authorization: Bearer $TOKEN"
```

---

## Monitoring & Alerts

### Key Metrics to Track

1. **Authentication Failures**
   ```sql
   SELECT COUNT(*) FROM memory_service.failed_logins;
   ```

2. **Locked Accounts**
   ```bash
   redis-cli KEYS "lockout:*" | wc -l
   ```

3. **Rate Limit Hits**
   ```sql
   SELECT COUNT(*) FROM memory_service.audit_logs
   WHERE event_type = 'security_rate_limit_hit'
   AND timestamp > now() - INTERVAL '1 hour';
   ```

4. **Active Sessions**
   ```bash
   redis-cli KEYS "session:*" | wc -l
   ```

### Alert Thresholds

Set up alerts for:
- Failed logins > 100/hour
- Locked accounts > 10 concurrent
- 429 rate limit hits > 1000/hour
- Slow requests (>30s) > 10/hour

---

## Rollback Plan

If integration causes issues:

1. **Disable audit logging:**
   ```python
   # In main.py middleware, comment out audit.log_api_call()
   ```

2. **Disable brute force protection:**
   ```python
   # In auth.py, comment out check_brute_force_protection()
   ```

3. **Disable enhanced rate limiting:**
   ```python
   # Revert to original check_rate_limit() implementation
   ```

All components are modular and can be disabled independently without breaking existing functionality.

---

## Next Steps

1. ✅ Verify all tests pass: `python3 security/verify_infrastructure.py`
2. ⚠️ Integrate audit logging middleware
3. ⚠️ Update authentication endpoints with hardening
4. ⚠️ Add GDPR compliance endpoints
5. ⚠️ Set up monitoring dashboard
6. ⚠️ Schedule audit log cleanup cron job
7. ⚠️ Update API documentation
8. ⚠️ Conduct security review
9. ⚠️ Prepare for SOC 2 audit

---

## Support

**Questions?** Review `SECURITY_INFRASTRUCTURE.md` for detailed documentation.

**Issues?** Check logs:
```bash
# Application logs
tail -f /var/log/memory-api.log

# Audit logs (database)
psql $MEMORY_DB_CONN -c "SELECT * FROM memory_service.audit_logs ORDER BY timestamp DESC LIMIT 20;"

# Redis (sessions, rate limits)
redis-cli MONITOR
```

**Contact:** security@0latency.ai
