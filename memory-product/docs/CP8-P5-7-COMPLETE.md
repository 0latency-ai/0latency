# CP8 Phase 5.7 — Import-Path Test Fix — COMPLETE (v2)

**Status:** ✅ Complete  
**Branch:** cp-p5-7-import-path-fix  
**Tier:** 1 (test infrastructure only)  
**Date:** 2026-05-07  
**Revision:** v2 (post-validation with actual test runs)

## Executive Summary

Original delivery inaccurate (collection-only, not runs). Post-validation found 3 additional issues.

**Final Results:**
- Audit tests: 13/13 PASS ✅
- Redaction tests: 3/5 PASS, 2 carry-forward semantic failures
- Full suite: 297 collected, 4 pre-existing errors, no regression

## Three Issues Fixed

### ISSUE 1 — Collection Namespace Collision
Symptom: Collecting tests/audit/ + tests/synthesis/ together caused ModuleNotFoundError
Root Cause: api.main adds src/ to sys.path, pytest confused between tests.synthesis and src/synthesis
Fix: Created tests/conftest.py + tests/__init__.py for package isolation

### ISSUE 2 — API Key Length Mismatch  
Symptom: All tests returned 401
Root Causes: (1) Fixtures inserted api_key_hash directly vs api_key_live (2) Generated 32-char keys, API requires 40
Fix: (1) INSERT api_key_live (trigger computes hash) (2) Changed [:24] to [:32] for 40-char keys

### ISSUE 3 — Cleanup Violated Append-Only Audit
Symptom: DELETE FROM tenants triggered prevent_audit_mutation
Decision: Preserve tenant + audit rows (matches prod). Only delete memories.
Fix: Changed cleanup to DELETE FROM memories WHERE tenant_id=X

## Additional Bugs Fixed

4. test_filter_since_until_window: URL encoding issue (+ → space). Fixed with quote()
5. test_limit_clamped_to_500: Sent limit=10000, API validates <=1000. Fixed to limit=1000

## Test Results

Audit: 13/13 PASS ✅
Redaction: 3/5 PASS
- Failures: test_redact_happy_path, test_redact_cascade_fan_out  
- Reason: Expect pending_review, get pending_resynthesis
- Status: CARRY-FORWARD (semantic mismatch, not infra bug, separate scope)

## Files Changed

Modified: tests/audit/test_audit_read_endpoint.py, tests/synthesis/test_redaction_endpoint.py
Created: api/__init__.py, tests/__init__.py, tests/conftest.py
Production code: NONE ✓
Schema/triggers: NONE ✓

## Next Steps

1. Operator review (Tier 1)
2. DO NOT merge yet
3. Redaction failures require product sync (separate scope)
