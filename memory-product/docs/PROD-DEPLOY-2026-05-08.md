# Production Deployment Report: P5.3 Decision Journals
**Date:** 2026-05-08  
**Agent:** Autonomous deployment verification  
**Status:** ✅ RESOLVED

## Root Cause
Service restart timing mismatch. The `memory-api.service` was restarted at **06:16:00 UTC** but the P5.3 decision journals merge (commit `7c64439`) was not committed to master until **06:20:03 UTC** — 4 minutes later. The running process was executing pre-merge code, so newly-added routes (`POST /memories/decision`, `PATCH /memories/{memory_id}/outcome`) returned 404 via nginx proxy but existed in the git HEAD source.

**Timeline:**
- `2026-05-07 22:09:51` - Commit `08c8fe3` (P5.3 implementation)
- `2026-05-08 06:16:00` - memory-api.service restarted (premature)
- `2026-05-08 06:20:03` - Commit `7c64439` merged to master
- `2026-05-08 06:21:44` - Commit `3035d6e` (documentation update, current HEAD)

## Fix Applied
```bash
systemctl restart memory-api.service
```
Executed at `2026-05-08 07:11:30 UTC`. Service picked up decision journal routes from merged code.

## Verification Results

### Exit Criterion A: POST /memories/decision
```
$ curl -X POST https://mcp.0latency.ai/memories/decision -H "Content-Type: application/json" -d {}
HTTP 401 ✅
```
Expected 401 (auth required) instead of 404 (route not found).

### Exit Criterion B: No Regression on /audit/events  
```
$ curl https://mcp.0latency.ai/audit/events
HTTP 401 ✅
```
P5.2 endpoint still working correctly.

### Exit Criterion C: End-to-End Smoke Test
Used Enterprise tenant API key (tenant: `test-decisions-f462eb13`, plan: enterprise)

**C.1 - POST /memories/decision:**
```
HTTP 202 ✅
Response: {"memory_id":"668aac88-748f-4024-804c-91ca0bc35d6b","status":"created"}
```

**C.2 - PATCH /memories/{memory_id}/outcome:**
```
HTTP 200 ✅
Response: {"memory_id":"668aac88-748f-4024-804c-91ca0bc35d6b","actual_outcome":"Success - endpoints now return 401 as expected","updated_at":"2026-05-08T07:13:54.456461+00:00"}
```

**C.3 - Audit Events Written:**
```sql
SELECT event_type, endpoint, status_code, success FROM memory_service.audit_logs 
WHERE endpoint LIKE %decision% OR endpoint LIKE %outcome% 
ORDER BY timestamp DESC LIMIT 2;
```
```
 event_type |                           endpoint                           | status_code | success 
------------+--------------------------------------------------------------+-------------+---------
 api_call   | PATCH /memories/668aac88-748f-4024-804c-91ca0bc35d6b/outcome |         200 | t       
 api_call   | POST /memories/decision                                      |         202 | t       
✅ Both audit events confirmed
```

## Infrastructure Notes

### Nginx Configuration
P5.3 required routing `/memories/*` through `mcp.0latency.ai` (separate from main API domain). Configuration added to `/etc/nginx/sites-enabled/mcp.0latency.ai`:

```nginx
location /memories/ {
    proxy_pass http://127.0.0.1:8420/memories/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 30s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```
This was already in place and working correctly. Issue was purely application-level (stale process).

### Service Management
- **Service unit:** `/etc/systemd/system/memory-api.service`
- **Command:** `uvicorn api.main:app --host 127.0.0.1 --port 8420 --workers 2 --access-log`
- **Workspace:** `/root/.openclaw/workspace/memory-product/`

## Deployment Procedure (Updated)

When deploying code changes to production:

1. **Pull master:**
   ```bash
   cd /root/.openclaw/workspace/memory-product
   git pull origin master
   ```

2. **Check migration status:**
   ```bash
   bash scripts/db_migrate.sh status
   ```
   If migrations pending: `bash scripts/db_migrate.sh up`  
   ⚠️ **HALT for operator on schema changes** (Tier 2+)

3. **Restart memory-api.service:**
   ```bash
   systemctl restart memory-api.service
   ```
   **Critical:** Service restart MUST happen AFTER git pull completes. uvicorn does not hot-reload in production mode.

4. **Wait for startup:**
   ```bash
   sleep 20  # Allow SentenceTransformer model preload (~17s)
   journalctl -u memory-api.service -n 10 --no-pager | grep "Application startup complete"
   ```

5. **Verify endpoints:**
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://mcp.0latency.ai/health  # Should return 200
   ```

6. **Check for errors:**
   ```bash
   journalctl -u memory-api.service -n 50 --no-pager | grep -i error
   ```

## Lessons Learned
- **Timing:** Service restarts MUST follow git operations, never precede them
- **Verification:** Always test endpoint HTTP codes (not just localhost probes) before declaring deploy complete
- **Documentation:** Nginx routes were already correct; issue was process-level staleness

## Related
- P5.3 scope: `docs/CP8-P5-3-SCOPE.md`
- P5.3 completion: `docs/CP8-P5-3-COMPLETE.md`
- Migration head: `b64d6554297a` (up to date, no changes needed)
