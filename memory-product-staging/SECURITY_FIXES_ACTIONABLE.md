# 0Latency Security Audit - Actionable Fixes

**Priority Fixes from Security Audit (2026-03-25)**

## 🔴 HIGH PRIORITY

### 1. Document Backup & Disaster Recovery Strategy

**Issue**: No documented backup strategy or failover plan for Supabase outages.

**Location**: Infrastructure/Documentation

**Fix**:

Create `/root/.openclaw/workspace/memory-product/DISASTER_RECOVERY.md`:

```markdown
# Disaster Recovery Plan - 0Latency API

## Current Architecture
- **Primary DB**: Supabase PostgreSQL (AWS us-east-1)
- **Backups**: Supabase Point-in-Time Recovery (PITR) - 7 days
- **RTO**: 4 hours
- **RPO**: 15 minutes (Supabase backup frequency)

## Backup Strategy

### Automated Backups (Supabase Native)
- **Frequency**: Continuous WAL archiving
- **Retention**: 7 days (Pro plan)
- **Storage**: Supabase S3 buckets (encrypted)
- **Recovery**: Via Supabase dashboard or CLI

### Supplementary Exports
```bash
# Daily export job (cron)
0 2 * * * /usr/local/bin/backup-0latency.sh
```

Script: `scripts/backup-0latency.sh`
```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
pg_dump $MEMORY_DB_CONN > /backups/0latency-$DATE.sql
aws s3 cp /backups/0latency-$DATE.sql s3://0latency-backups/
find /backups -name "*.sql" -mtime +30 -delete
```

### Recovery Procedures

#### Scenario 1: Supabase Total Outage
1. Check status: https://status.supabase.com
2. If prolonged (>2h):
   - Restore latest backup to new Supabase project
   - Update `MEMORY_DB_CONN` environment variable
   - Restart API servers
   - Estimated downtime: 2-4 hours

#### Scenario 2: Data Corruption
1. Identify corruption timestamp
2. Request PITR from Supabase support (ticket via dashboard)
3. Restore to specific point-in-time
4. Verify data integrity via test queries
5. Resume operations

## Testing
- **Monthly**: Test restore from backup to staging environment
- **Quarterly**: Full DR drill with failover simulation
```

**Implementation Checklist**:
- [ ] Create DISASTER_RECOVERY.md
- [ ] Set up daily export cron job
- [ ] Configure S3/R2 backup storage
- [ ] Document Supabase support contacts
- [ ] Schedule monthly DR test
- [ ] Add monitoring for backup job failures

---

### 2. Fix Memory Limit Race Condition

**Issue**: Concurrent bulk imports can bypass memory limit checks.

**Location**: `api/main.py` (affects `/extract`, `/memories/seed`, `/memories/import`, `/memories/import-thread`)

**Current Code** (vulnerable):
```python
# Check happens outside transaction
count_rows = _db_execute_rows("""
    SELECT COUNT(*) FROM memory_service.memories
    WHERE tenant_id = %s::UUID AND superseded_at IS NULL
""", (tenant["id"],), tenant_id=tenant["id"])
current_count = int(count_rows[0][0]) if count_rows else 0
if current_count >= tenant["memory_limit"]:
    raise HTTPException(429, detail=f"Memory limit reached...")

# Later: insert happens
store_memories(memories, tenant["id"])  # Could exceed limit if concurrent
```

**Fix Option 1: Database Constraint** (Recommended)

Add migration `migrations/add_memory_limit_constraint.sql`:
```sql
-- Create function to check tenant memory count
CREATE OR REPLACE FUNCTION memory_service.check_memory_limit()
RETURNS TRIGGER AS $$
DECLARE
    current_count INTEGER;
    max_limit INTEGER;
BEGIN
    -- Count non-superseded memories for this tenant
    SELECT COUNT(*) INTO current_count
    FROM memory_service.memories
    WHERE tenant_id = NEW.tenant_id 
      AND superseded_at IS NULL;
    
    -- Get limit for tenant
    SELECT memory_limit INTO max_limit
    FROM memory_service.tenants
    WHERE id = NEW.tenant_id;
    
    -- Check if limit would be exceeded
    IF current_count >= max_limit THEN
        RAISE EXCEPTION 'Memory limit exceeded for tenant % (limit: %, current: %)', 
            NEW.tenant_id, max_limit, current_count
        USING ERRCODE = '23514';  -- check_violation
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on INSERT
CREATE TRIGGER enforce_memory_limit
    BEFORE INSERT ON memory_service.memories
    FOR EACH ROW
    EXECUTE FUNCTION memory_service.check_memory_limit();
```

Apply migration:
```bash
psql $MEMORY_DB_CONN -f migrations/add_memory_limit_constraint.sql
```

**Fix Option 2: Application-Level Lock** (Alternative)

Update `storage_multitenant.py`:
```python
import threading

_tenant_locks = {}
_tenant_locks_mutex = threading.Lock()

def _get_tenant_lock(tenant_id: str) -> threading.Lock:
    """Get or create lock for tenant."""
    with _tenant_locks_mutex:
        if tenant_id not in _tenant_locks:
            _tenant_locks[tenant_id] = threading.Lock()
        return _tenant_locks[tenant_id]

def store_memories(memories: list[dict], tenant_id: str) -> list[str]:
    """Store memories with atomic limit check."""
    lock = _get_tenant_lock(tenant_id)
    
    with lock:  # Serialize access per tenant
        # Check limit
        count_rows = _db_execute_rows("""
            SELECT COUNT(*) FROM memory_service.memories
            WHERE tenant_id = %s::UUID AND superseded_at IS NULL
        """, (tenant_id,), tenant_id=tenant_id)
        current_count = int(count_rows[0][0]) if count_rows else 0
        
        # Get tenant limit
        limit_rows = _db_execute_rows("""
            SELECT memory_limit FROM memory_service.tenants WHERE id = %s::UUID
        """, (tenant_id,), tenant_id=tenant_id)
        memory_limit = int(limit_rows[0][0]) if limit_rows else 10000
        
        if current_count + len(memories) > memory_limit:
            raise ValueError(f"Would exceed memory limit ({memory_limit})")
        
        # Insert (still protected by lock)
        # ... rest of insert logic
```

**Recommended**: Use **Option 1 (Database Constraint)** because:
- More reliable (enforced at DB level)
- Survives application restarts
- No application-level lock coordination needed
- Works across multiple API server instances

---

## 🟡 MEDIUM PRIORITY

### 3. Environment-Aware CORS Configuration

**Issue**: Localhost and IP address allowed in production CORS.

**Location**: `api/main.py`

**Current Code**:
```python
_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", 
    "https://164.90.156.169,https://0latency.ai,https://www.0latency.ai,https://api.0latency.ai,http://localhost:3000"
).split(",")
```

**Fix**:

```python
# Production-safe CORS
_CORS_ORIGINS_PROD = [
    "https://0latency.ai",
    "https://www.0latency.ai", 
    "https://api.0latency.ai"
]

_CORS_ORIGINS_DEV = _CORS_ORIGINS_PROD + [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:3000"
]

# Staging can include the DO droplet IP if needed
_CORS_ORIGINS_STAGING = _CORS_ORIGINS_PROD + [
    "https://164.90.156.169"
]

# Select based on environment
ENV = os.environ.get("ENVIRONMENT", "production").lower()

if ENV == "development":
    _CORS_ORIGINS = _CORS_ORIGINS_DEV
elif ENV == "staging":
    _CORS_ORIGINS = _CORS_ORIGINS_STAGING
else:  # production
    _CORS_ORIGINS = _CORS_ORIGINS_PROD

# Allow override via env var (for custom deployments)
if os.environ.get("CORS_ORIGINS"):
    _CORS_ORIGINS = os.environ["CORS_ORIGINS"].split(",")

logger.info(f"CORS origins configured: {_CORS_ORIGINS} (env={ENV})")
```

**Deployment Checklist**:
- [ ] Set `ENVIRONMENT=production` in production `.env`
- [ ] Set `ENVIRONMENT=development` in local dev
- [ ] Set `ENVIRONMENT=staging` on staging server (if needed)
- [ ] Remove hardcoded IP from default list
- [ ] Verify CORS with browser DevTools after deployment

---

## 🟢 LOW PRIORITY

### 4. Remove Verification Tokens from Logs

**Issue**: Email verification URLs (with tokens) logged to console.

**Location**: `api/auth.py:email_register()`

**Current Code**:
```python
verification_token = _create_verification_token(user["id"])
verification_url = f"{SITE_BASE}/verify.html?token={verification_token}"
logger.info(f"EMAIL_VERIFICATION user={user['email']} url={verification_url}")
```

**Fix**:
```python
verification_token = _create_verification_token(user["id"])
verification_url = f"{SITE_BASE}/verify.html?token={verification_token}"

# Log event without exposing token
logger.info(f"EMAIL_VERIFICATION_SENT user={user['email']} token_id={verification_token[:8]}...")

# TODO: Send actual email instead of logging
# send_verification_email(user['email'], verification_url)
```

**Implementation Checklist**:
- [ ] Update log statement to remove full token
- [ ] Wire up email sending (Cloudflare Email Workers or AWS SES)
- [ ] Add email template for verification
- [ ] Test email delivery in staging

---

### 5. Consider Argon2 Migration (Optional)

**Issue**: bcrypt is secure but argon2 is more modern.

**Location**: `api/auth.py`

**Current**: bcrypt (12 rounds)  
**Alternative**: argon2id (winner of Password Hashing Competition 2015)

**Benefits**:
- Better resistance to GPU/ASIC cracking
- Configurable memory hardness (prevents parallelization)
- More modern standard

**Implementation** (if needed in future):
```python
# Replace:
from passlib.hash import bcrypt
# With:
from passlib.hash import argon2

# Usage is identical:
password_hash = argon2.hash(password)
verified = argon2.verify(password, password_hash)
```

**Note**: This is **LOW priority** because:
- bcrypt is still industry standard and secure
- Migration would require rehashing all existing passwords
- No active threat requiring immediate change
- Could be done during next major version

**Decision**: **Defer unless compliance/audit requires it.**

---

## Quick Win Checklist

Fixes that can be implemented in <30 minutes:

- [ ] **5 min**: Add `DISASTER_RECOVERY.md` documentation
- [ ] **10 min**: Update CORS to environment-aware config  
- [ ] **5 min**: Remove verification token from logs
- [ ] **30 min**: Apply memory limit database constraint
- [ ] **15 min**: Set up daily backup cron job

**Total Quick Wins Time**: ~65 minutes

---

## Testing After Fixes

### Test Memory Limit Fix:
```bash
# Create test script: test_concurrent_import.sh
#!/bin/bash
API_KEY="zl_live_test..."

# Start 3 concurrent bulk imports
for i in {1..3}; do
  curl -X POST https://api.0latency.ai/memories/import \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"agent_id":"test","content":"'$(head -c 5000 /dev/urandom | base64)'"}' &
done

wait
# Expected: 1 succeeds, others get 429 (or all succeed if under limit)
# But NEVER exceed tenant memory_limit in final count
```

### Test CORS Fix:
```javascript
// Browser console on https://0latency.ai
fetch('https://api.0latency.ai/health')
  .then(r => r.json())
  .then(console.log)
// Should work

// From random domain:
// Should fail with CORS error
```

### Test Backup Restore:
```bash
# Restore yesterday's backup to staging
pg_restore -d $STAGING_DB /backups/0latency-20260324.sql
# Run API tests against staging
pytest tests/ --api-url=https://staging.api.0latency.ai
```

---

## Monitoring Recommendations

Add alerts for:
1. **Memory limit abuse**: Alert if any tenant exceeds 95% of limit repeatedly
2. **Backup failures**: Email if daily backup job fails
3. **CORS errors**: Log and alert on spike in CORS rejections (could indicate attack)
4. **Rate limit hits**: Alert if free tier hitting limits (could indicate bot)

---

**Document Created**: 2026-03-25  
**Priority**: Execute HIGH priority fixes within 48 hours  
**Review Date**: 2026-04-25 (30 days post-fixes)
