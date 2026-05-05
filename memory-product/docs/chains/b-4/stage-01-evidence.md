# Stage 01 Evidence - Role Filtering on /recall

**Commit SHA:** c927f07

**Outcome:** SHIPPED

## Files Touched
- src/storage_multitenant.py - Added caller_role extraction from api_keys.metadata
- src/recall.py - Added caller_role parameter threading and SQL filter logic
- api/main.py - Pass caller_role from tenant to recall functions

## Verification Commands

### 1. Parse checks
```bash
python3 -c "import ast; ast.parse(open('src/storage_multitenant.py').read())"
python3 -c "import ast; ast.parse(open('src/recall.py').read())"
python3 -c "import ast; ast.parse(open('api/main.py').read())"
```

### 2. Service restart and health check
```bash
systemctl restart memory-api
sleep 35
curl -s http://localhost:8420/health
```

### 3. SQL role filter verification
Test memory inserted with role_tag='admin', then updated to 'public', then NULL.
Filter query: (role_tag IS NULL OR role_tag IN ('public', 'public'))

## Verification Output (last 20 lines)

```
 admin_count 
-------------
           0
(1 row)

UPDATE 1
 after_admin_update 
--------------------
                  0
(1 row)

UPDATE 1
 after_public_update 
---------------------
                   1
(1 row)

UPDATE 1
 after_null_update 
-------------------
                 1
(1 row)

DELETE 1
```

## Health Check Output
```json
{"status":"ok","version":"0.1.0","timestamp":"2026-05-05T00:04:02.624027+00:00","memories_total":9113,"db_pool":{"pool_min":1,"pool_max":5},"redis":"connected"}
```

## Error Log Check
No errors found in journalctl (grep exit code 1 = no matches, excluding analytics_events)

## Summary
Role-based filtering successfully implemented and verified:
- Admin-tagged memories filtered out for public caller_role
- Public-tagged memories visible to public caller_role  
- NULL role_tag memories visible to all (backward compatible)
