# Agent Operations Manual
**Memory Product Production Environment**

## Deployment Procedures

### Code Deployment (Tier 1 - Autonomous)

When deploying merged code to production:

1. **Verify git state:**
   ```bash
   cd /root/.openclaw/workspace/memory-product
   git fetch origin
   git status
   ```

2. **Pull latest:**
   ```bash
   git pull origin master
   ```

3. **Check migrations:**
   ```bash
   bash scripts/db_migrate.sh status
   ```
   - If migration head matches latest migration: proceed
   - If migrations pending AND no schema changes: `bash scripts/db_migrate.sh up`
   - If schema changes detected: **HALT - Tier 2+ operator approval required**

4. **Restart application service:**
   ```bash
   systemctl restart memory-api.service
   ```
   WARNING: Service restart MUST follow git pull. uvicorn workers do not hot-reload.

5. **Wait for startup (SentenceTransformer preload takes 17-20s):**
   ```bash
   sleep 20
   journalctl -u memory-api.service -n 5 --no-pager | grep "Application startup complete"
   ```

6. **Verify health:**
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://mcp.0latency.ai/health
   curl -s -o /dev/null -w "%{http_code}\n" https://api.0latency.ai/health
   ```

7. **Check for startup errors:**
   ```bash
   journalctl -u memory-api.service -n 50 --no-pager | grep -iE "error|exception|traceback"
   ```

### Nginx Configuration (Tier 1 - Autonomous)

- **Config locations:**
  - Main API: `/etc/nginx/sites-enabled/memory-api`
  - MCP subdomain: `/etc/nginx/sites-enabled/mcp.0latency.ai`
  - Files static: `/etc/nginx/sites-enabled/files-0latency`

- **Before editing:**
  ```bash
  cp /etc/nginx/sites-enabled/config-name /root/config-name.bak.timestamp
  ```

- **After editing:**
  ```bash
  nginx -t
  systemctl reload nginx
  ```

### Service Management

**memory-api.service:**
- Unit file: `/etc/systemd/system/memory-api.service`
- Command: `uvicorn api.main:app --host 127.0.0.1 --port 8420 --workers 2 --access-log`
- Workspace: `/root/.openclaw/workspace/memory-product/`
- Startup time: ~20s (includes SentenceTransformer model preload)

**Useful commands:**
```bash
systemctl status memory-api.service
journalctl -u memory-api.service -f
journalctl -u memory-api.service -n 100 --no-pager
systemctl restart memory-api.service
```

## Tier System

**Tier 1 (Autonomous - No approval needed):**
- Code deploys (pull master + restart service)
- Nginx config edits (with backups)
- Service restarts (memory-api, 0latency-mcp, nginx reload)
- Read-only database queries
- Running `bash scripts/db_migrate.sh up` when migration head matches latest
- Smoke tests with Enterprise tenant API keys (read from DB)

**Tier 2+ (Halt for operator approval):**
- New migrations (alembic revision)
- Schema changes (ALTER TABLE, CREATE TABLE, DROP, etc.)
- Destructive operations (DELETE, TRUNCATE, DROP)
- Tenant table writes (except SELECT for API key reads)
- Any operation with potential for data loss

## Database Access

**Connection:**
```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
psql "$DATABASE_URL"
```

**Safe read-only queries:**
```sql
-- List tables
\dt memory_service.*

-- Check tenant
SELECT id, name, plan, active FROM memory_service.tenants WHERE email = user@example.com;

-- View recent audit logs
SELECT event_type, endpoint, status_code, timestamp 
FROM memory_service.audit_logs 
ORDER BY timestamp DESC LIMIT 20;

-- Check migration status
SELECT version_num FROM alembic_version;
```

## Security Rules
## Migration Discipline

**DROP TABLE halt rule:**
- Any DROP TABLE in a migration → mandatory halt to operator regardless of Tier classification, even if table appears empty
- Before proceeding: grep codebase for table references, confirm zero hits in non-migration code
- If table was superseded: audit and delete the old code path in the same migration commit, never leave orphan modules

**Table supersession protocol:**
- When superseding a table with a new schema, always audit for orphan code referencing the old table
- Delete dead code files in the same commit as the migration that drops the table
- Document the supersession in the migration comment and commit message


- Never log API keys in terminal output, files, or git commits
- Never echo secrets - pipe sensitive data directly to consumers
- File permissions: Scripts inherit umask 0600
- Python error handling: Broad exceptions must re-raise NotImplementedError first
- Database functions: Use _db_execute_rows not _db_execute for SELECT queries
- Migration tool: Always use `bash scripts/db_migrate.sh`, never direct alembic

## Smoke Test Procedure

**Fetch Enterprise API key:**
```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
psql "$DATABASE_URL" -t -c "SELECT api_key_live FROM memory_service.tenants WHERE plan=enterprise AND active=true LIMIT 1"
```

**Test endpoints:**
```bash
# Auth-gated endpoint
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: API_KEY_HERE" https://api.0latency.ai/memories

# Decision journals (Enterprise only)
curl -s -X POST https://mcp.0latency.ai/memories/decision \
  -H "X-API-Key: API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test","headline":"Test","context":"Smoke test","decision_text":"Test decision","rationale":"Verification"}'
```

WARNING: NEVER commit or log the API key value in any output files or git commits.

## CI Collection Smoke Check

**Purpose:** Detect test collection errors (import failures, syntax errors) before running the test suite. Collection errors produce silent "no tests ran" results that appear as green builds but mask broken imports.

**Usage:**
```bash
bash scripts/ci_collection_smoke.sh
```

**Exit codes:**
- `0` - Collection succeeded, safe to run tests
- `3` - Collection errors detected, build should fail

**When to run:**
- Every PR (before running full test suite)
- Before any autonomy test-suite execution
- After major refactoring or import path changes

**Pattern:** Follows scripts/contract_test.py exit-code conventions (0=pass, 1=fail, 2=hollow, 3=collection-error).

## Deployment Incidents

See `docs/PROD-DEPLOY-*.md` for incident reports and deployment verifications.

Latest: `docs/PROD-DEPLOY-2026-05-08.md` (P5.3 timing mismatch resolution)
