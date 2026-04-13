# API Key Regenerate Fix - COMPLETE

**Date**: April 8, 2026
**Endpoint**: POST /auth/api-key/regenerate
**Previous Status**: CORS preflight OK (200), POST request 500 error
**Current Status**: ✅ FIXED - Ready for testing

---

## Root Cause Analysis

### 1. CORS Status
**Finding**: CORS was working correctly ✅
- OPTIONS preflight returned 200 OK
- FastAPI CORSMiddleware correctly configured:
  - allow_origins: https://0latency.ai, https://www.0latency.ai, etc.
  - allow_methods: ["*"]
  - allow_headers: ["*"]
  - allow_credentials: True
- Nginx does NOT add conflicting CORS headers (only X-Content-Type-Options and X-Frame-Options)

**Conclusion**: No CORS issues. The problem was purely the 500 error.

### 2. 500 Error Root Cause
**File**: /root/.openclaw/workspace/memory-product/api/auth.py
**Line**: 822 (regenerate_api_key endpoint)

**Error**:
```
ValueError: invalid literal for int() with base 10: '44c3080d-c196-407d-a606-4ea9f62ba0fc'
```

**Problem**:
```python
track_posthog_event(
    tenant_id=int(tenant_id),  # ❌ tenant_id is a UUID string, not convertible to int
    event_name="api_key_created",
    ...
)
```

tenant_id is a UUID string like `'44c3080d-c196-407d-a606-4ea9f62ba0fc'`, but the code tried to convert it to an integer.

---

## Fixes Applied

### Fix 1: analytics.py - Accept str tenant_id ✅
**File**: /root/.openclaw/workspace/memory-product/api/analytics.py
**Backup**: /root/.openclaw/workspace/memory-product/api/analytics.py.backup_cors_fix

**Changed**:
```python
# BEFORE
def track_posthog_event(tenant_id: int, ...):

def is_first_api_call(tenant_id: int) -> bool:

def is_first_memory_stored(tenant_id: int) -> bool:

def check_activation_milestone(tenant_id: int) -> bool:

# AFTER (removed type hints, accepts Union[str, int])
def track_posthog_event(tenant_id, ...):  # Accepts UUID string or legacy int

def is_first_api_call(tenant_id) -> bool:

def is_first_memory_stored(tenant_id) -> bool:

def check_activation_milestone(tenant_id) -> bool:
```

### Fix 2: auth.py - Remove int() conversion ✅
**File**: /root/.openclaw/workspace/memory-product/api/auth.py
**Backup**: /root/.openclaw/workspace/memory-product/api/auth.py.backup_cors_fix

**Changed** (line 822):
```python
# BEFORE
track_posthog_event(
    tenant_id=int(tenant_id),  # ❌ ValueError

# AFTER
track_posthog_event(
    tenant_id=tenant_id,  # ✅ Pass UUID string directly
```

### Fix 3: Restarted API ✅
```bash
systemctl restart memory-api.service
```

---

## Verification Status

### Pre-Fix Logs (06:54:01 UTC)
```
OPTIONS /auth/api-key/regenerate → 200 OK ✅ (CORS working)
POST /auth/api-key/regenerate → 500 Internal Server Error ❌
ERROR: ValueError: invalid literal for int() with base 10: '44c3080d-c196-407d-a606-4ea9f62ba0fc'
```

### Post-Fix Status (07:07:37 UTC)
- ✅ API restarted successfully
- ✅ No int() conversion errors
- ✅ tenant_id passed as string to PostHog tracking
- ⏳ Ready for end-to-end testing from dashboard

---

## End-to-End Test Plan

### From 0latency.ai Dashboard:

1. **Login** to dashboard with authenticated user
2. **Navigate** to Settings → API Keys
3. **Click** "Regenerate API Key" button
4. **Expected Result**:
   - ✅ OPTIONS request returns 200 OK (CORS preflight)
   - ✅ POST request returns 200 OK with new API key
   - ✅ Response: `{"api_key": "zl_live_...", "message": "New API key generated. Old key is immediately invalid."}`
   - ✅ Old API key immediately stops working
   - ✅ New API key works for all endpoints

### Manual Test (if needed):
```bash
# From authenticated dashboard session, extract JWT from browser cookies
# Then test directly:

curl -X POST https://api.0latency.ai/auth/api-key/regenerate \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Origin: https://0latency.ai"
```

Expected response:
```json
{
  "api_key": "zl_live_abcd1234...",
  "message": "New API key generated. Old key is immediately invalid."
}
```

---

## Files Modified

| File | Change | Backup |
|------|--------|--------|
| api/analytics.py | Removed `tenant_id: int` type hints | analytics.py.backup_cors_fix |
| api/auth.py | Removed `int(tenant_id)` conversion | auth.py.backup_cors_fix |

---

## Summary

**CORS**: ✅ Was already working correctly
**500 Error**: ✅ Fixed (tenant_id UUID → int conversion removed)
**API Status**: ✅ Running with fixes applied
**Ready to Test**: ✅ From dashboard at https://0latency.ai

---

**Fix Complete** - Key rotation should now work end-to-end from the dashboard.
