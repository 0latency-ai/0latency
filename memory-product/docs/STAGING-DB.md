# Staging DB

**Name:** `memory_service_staging`
**Host:** same Postgres cluster as prod (DigitalOcean managed)
**Connection:** `STAGING_DATABASE_URL` in `.env`
**Schema:** cloned from prod (memory_service schema only)
**Data:** none — staging is for migration testing, not data dogfooding

## Reset

```bash
set -a && source .env && set +a
bash scripts/staging_reset.sh
```

## Apply a migration to staging

```bash
psql "$STAGING_DATABASE_URL" < migrations/NNN_my_migration.sql
```

(After T2 ships Alembic, this becomes `alembic -x env=staging upgrade head`.)
