#!/usr/bin/env bash
# Reset staging DB schema from prod. Drops all data in staging.
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]] || [[ -z "${STAGING_DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL and STAGING_DATABASE_URL must be set"
  exit 1
fi

PROD_DB=$(echo "$DATABASE_URL" | sed -E "s|.*/([^?]+).*|\1|")
STAGING_DB=$(echo "$STAGING_DATABASE_URL" | sed -E "s|.*/([^?]+).*|\1|")

if [[ "$STAGING_DB" != "memory_service_staging" ]]; then
  echo "ERROR: STAGING_DATABASE_URL doesn't point at memory_service_staging — refusing"
  exit 1
fi

echo "Resetting $STAGING_DB from $PROD_DB..."

# Build superuser URL for staging (needed for DROP SCHEMA and ownership changes)
STAGING_SUPERUSER_URL=$(echo "$DATABASE_URL" | sed "s|/${PROD_DB}|/${STAGING_DB}|")

# Drop and recreate the memory_service schema in staging (as superuser)
psql "$STAGING_SUPERUSER_URL" -c "DROP SCHEMA IF EXISTS memory_service CASCADE; CREATE SCHEMA memory_service; ALTER SCHEMA memory_service OWNER TO memory_service_staging_user;"

# Re-import schema
pg_dump "$DATABASE_URL" --schema-only --no-owner --no-privileges \
  --schema=memory_service \
  | psql "$STAGING_SUPERUSER_URL"

# Grant ownership and permissions to staging user
psql "$STAGING_SUPERUSER_URL" <<SQL
-- Grant schema permissions
GRANT ALL ON SCHEMA memory_service TO memory_service_staging_user;

-- Transfer ownership of all tables, sequences, and functions
DO \$\$
DECLARE
  r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'memory_service'
  LOOP
    EXECUTE 'ALTER TABLE memory_service.' || quote_ident(r.tablename) || ' OWNER TO memory_service_staging_user';
  END LOOP;
  
  FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'memory_service'
  LOOP
    EXECUTE 'ALTER SEQUENCE memory_service.' || quote_ident(r.sequence_name) || ' OWNER TO memory_service_staging_user';
  END LOOP;
  
  FOR r IN SELECT routine_name FROM information_schema.routines WHERE routine_schema = 'memory_service'
  LOOP
    EXECUTE 'ALTER FUNCTION memory_service.' || quote_ident(r.routine_name) || ' OWNER TO memory_service_staging_user';
  END LOOP;
END\$\$;

-- Grant table and sequence permissions
GRANT ALL ON ALL TABLES IN SCHEMA memory_service TO memory_service_staging_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA memory_service TO memory_service_staging_user;
SQL

echo "Staging reset complete."
