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
