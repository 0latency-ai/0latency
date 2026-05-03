# Migrations

**Tooling:** Alembic, configured for prod (default) and staging (`-x env=staging`).
**Version table:** `memory_service.alembic_version`.
**Baseline:** `0001_baseline` represents schema state at end of hand-applied SQL migrations 001-023.

## Create a new migration

```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
alembic revision -m "short_description"
# Edit the generated file in alembic/versions/
```

Inside the generated file, `upgrade()` and `downgrade()` use `op.execute()` for raw SQL or Alembic's `op.add_column()` etc. for typed operations.

## Apply migrations

**Always test on staging first.**

```bash
alembic -x env=staging upgrade head    # apply to staging
# verify behavior
alembic upgrade head                    # apply to prod
```

T3 (next) automates the staging-first flow including pre-migration backup. After T3 ships, prefer `bash scripts/db_migrate.sh up` over raw alembic.

## Rollback

```bash
alembic -x env=staging downgrade -1    # revert most recent on staging
alembic downgrade -1                    # revert most recent on prod
```

## Existing SQL migrations

`migrations/001_*.sql` through `migrations/023_*.sql` are historical reference. Do not modify or re-apply. New schema work goes through Alembic only.

## Recommended flow (T3 onward)

For every new migration:

```bash
# 1. Author the migration
alembic revision -m "short_description"
# Edit alembic/versions/NNNN_short_description.py

# 2. Apply via the wrapped flow (backup + staging-first + prod)
bash scripts/db_migrate.sh up

# 3. Verify rollback testability (run BEFORE prod apply for safety)
pytest tests/migrations/test_rollback.py -v
```

The wrapped flow:
- Takes a timestamped `pg_dump` of prod (gzipped, /var/backups/0latency/, retains last 10)
- Resets staging from prod schema, applies the migration there first
- Pauses 5 seconds before prod apply (Ctrl+C to abort)
- Verifies prod ended at the expected head

If a migration breaks staging, prod is never touched. If it breaks prod despite passing staging, restore from the timestamped backup:

```bash
bash scripts/db_restore.sh --confirm /var/backups/0latency/FILENAME.sql.gz
```
