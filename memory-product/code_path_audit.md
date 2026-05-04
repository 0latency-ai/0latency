# Code Path Audit: api_key_live Write Operations

## Summary
- **Total write sites found**: 6
- **Buggy sites**: 1 (FIXED)
- **Correct sites**: 5

## Detailed Audit

### 🔴 BUGGY (FIXED)
| File | Line | Function | Issue | Status |
|------|------|----------|-------|--------|
| api/main.py | 3025 | rotate_api_key | UPDATE only set api_key_hash, not api_key_live | ✅ FIXED |

**Impact**: Every key rotation created hash drift. 27/110 tenants affected (24.5%).

**Fix**: Added api_key_live to SET clause and new_key to parameters.

### ✅ CORRECT
| File | Line | Function | Operation | Verification |
|------|------|----------|-----------|--------------|
| api/auth.py | 580 | oauth_callback | UPDATE sets both api_key_live and api_key_hash | ✓ Correct |
| api/auth.py | 783 | google_callback | UPDATE sets both api_key_live and api_key_hash | ✓ Correct |
| api/auth.py | 871 | regenerate_api_key | UPDATE sets both api_key_hash and api_key_live | ✓ Correct |
| src/storage_multitenant.py | 780 | create_tenant | INSERT sets both api_key_hash and api_key_live | ✓ Correct |
| api/main.py | 3220 | fix_github_tenant | UPDATE sets both api_key_live and api_key_hash | ✓ Correct (one-off admin fix) |

### Endpoints Audited
- ✅ /admin/rotate-key/{tenant_id} - FIXED
- ✅ /admin/revoke-key/{tenant_id} - Does not touch api_key fields
- ✅ /admin/reactivate/{tenant_id} - Does not touch api_key fields  
- ✅ OAuth callbacks (auto-generate) - Correct
- ✅ Tenant creation - Correct

## Root Cause
The rotate_api_key endpoint generated a new key and hash but only stored the hash,
leaving api_key_live with the old value. This caused immediate hash drift on every rotation.
