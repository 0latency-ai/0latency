# CP-DB-SANDBOX T1 — Staging DB Provision

**Task:** Provision a staging Postgres database on the same DigitalOcean instance, schema-cloned from prod, accessible via `STAGING_DATABASE_URL` in `.env`.
**Mode:** Autonomous.
**Estimated wall-clock:** 15–30 min for CC.

---

## Goal

Stand up `memory_service_staging` as a separate database on the existing prod Postgres cluster. Schema-only clone (no data) — staging is for migration testing, not data dogfooding. Wire it into `.env` and verify connectivity.

---

## In scope

- Create new database `memory_service_staging` on the existing Postgres cluster.
- Create role `memory_service_staging_user` with full privileges on the new DB.
- Clone schema from prod `memory_service_db` using `pg_dump --schema-only` → `psql`.
- Add `STAGING_DATABASE_URL` to `.env` and `.env.example` (sanitized).
- Verify: same tables, same constraints, same indexes as prod (count match).
- Add `scripts/staging_reset.sh` — drops and re-clones staging schema from prod (for clean-slate testing).
- Document the staging DB in `docs/STAGING-DB.md`.

---

## Out of scope

- Data clone (schema only — staging is a lab, not a replica).
- A second Postgres instance (uses existing cluster, separate DB).
- Any change to prod schema or data.
- Any change to `memory-api` service (still points at prod).
- Migration tooling (T2's job).

---

## Inputs at start

- HEAD: clean
- `.env` has `DATABASE_URL` pointing at prod
- Postgres superuser access via `psql "$DATABASE_URL"` (already verified by every prior CP8 work)

---

## Steps

### Step 1 — Pre-flight

```bash
cd /root/.openclaw/workspace/memory-product
git status                              # GATE: must be clean
git pull origin master
set -a && source .env && set +a
psql "$DATABASE_URL" -c "SELECT current_database(), current_user;" | head -5
psql "$DATABASE_URL" -c "\l" | grep memory_service  # confirm prod DB exists, staging does not
```

**HALT** if working tree dirty, or if `memory_service_staging` already exists.

### Step 2 — Create staging DB and role

```bash
# Generate a strong random password, store in /tmp temporarily for .env update
STAGING_PW=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
echo "$STAGING_PW" > /tmp/staging_pw.txt
chmod 600 /tmp/staging_pw.txt

psql "$DATABASE_URL" <<EOF
CREATE DATABASE memory_service_staging;
CREATE ROLE memory_service_staging_user WITH LOGIN PASSWORD '${STAGING_PW}';
GRANT ALL PRIVILEGES ON DATABASE memory_service_staging TO memory_service_staging_user;
EOF
```

**Gate:** `psql "$DATABASE_URL" -c "\l" | grep memory_service_staging` returns a row.

### Step 3 — Clone schema from prod

Identify the actual prod DB name (it's whatever `DATABASE_URL` points at; parse it):

```bash
PROD_DB=$(echo "$DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')
echo "Prod DB: $PROD_DB"
```

Dump schema, restore to staging:

```bash
pg_dump "$DATABASE_URL" --schema-only --no-owner --no-privileges \
  --schema=memory_service \
  --schema=public \
  > /tmp/prod_schema.sql

# Build staging connection string
STAGING_URL=$(echo "$DATABASE_URL" | sed "s|/${PROD_DB}|/memory_service_staging|")

# Restore schema (extensions first via separate connection as superuser)
psql "$DATABASE_URL" -c "\\c memory_service_staging" -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;" 2>&1 | tail -5

psql "$STAGING_URL" < /tmp/prod_schema.sql 2>&1 | tail -20
```

**HALT** if `pg_dump` exits non-zero, or `psql` restore reports any ERROR (warnings about existing extensions are fine).

### Step 4 — Verify schema parity

```bash
# Table count
PROD_TABLES=$(psql "$DATABASE_URL" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='memory_service';" | tr -d ' ')
STAGING_TABLES=$(psql "$STAGING_URL" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='memory_service';" | tr -d ' ')
echo "Prod tables: $PROD_TABLES, Staging tables: $STAGING_TABLES"

# Constraint count
PROD_CONS=$(psql "$DATABASE_URL" -t -c "SELECT count(*) FROM information_schema.table_constraints WHERE table_schema='memory_service';" | tr -d ' ')
STAGING_CONS=$(psql "$STAGING_URL" -t -c "SELECT count(*) FROM information_schema.table_constraints WHERE table_schema='memory_service';" | tr -d ' ')
echo "Prod constraints: $PROD_CONS, Staging constraints: $STAGING_CONS"

# Index count
PROD_IDX=$(psql "$DATABASE_URL" -t -c "SELECT count(*) FROM pg_indexes WHERE schemaname='memory_service';" | tr -d ' ')
STAGING_IDX=$(psql "$STAGING_URL" -t -c "SELECT count(*) FROM pg_indexes WHERE schemaname='memory_service';" | tr -d ' ')
echo "Prod indexes: $PROD_IDX, Staging indexes: $STAGING_IDX"
```

**Gate:** all three counts match exactly.

**HALT** if any mismatch — write the diff into the BLOCKED note.

### Step 5 — Update `.env` and `.env.example`

Append `STAGING_DATABASE_URL=...` to `.env` (real password) and to `.env.example` (placeholder).

```bash
# Build the URL with the password we generated
STAGING_PW_VAL=$(cat /tmp/staging_pw.txt)
STAGING_HOST=$(echo "$DATABASE_URL" | sed -E 's|^[a-z]+://[^@]+@([^:/]+).*|\1|')
STAGING_PORT=$(echo "$DATABASE_URL" | sed -E 's|^[a-z]+://[^@]+@[^:]+:([0-9]+).*|\1|')
STAGING_FULL_URL="postgresql://memory_service_staging_user:${STAGING_PW_VAL}@${STAGING_HOST}:${STAGING_PORT}/memory_service_staging"

# Append to .env if not present
grep -q '^STAGING_DATABASE_URL=' .env || echo "STAGING_DATABASE_URL=${STAGING_FULL_URL}" >> .env

# Append placeholder to .env.example if not present
grep -q '^STAGING_DATABASE_URL=' .env.example || echo "STAGING_DATABASE_URL=postgresql://memory_service_staging_user:CHANGE_ME@HOST:PORT/memory_service_staging" >> .env.example

# Cleanup
rm -f /tmp/staging_pw.txt /tmp/prod_schema.sql
```

**Gate:** `grep -c STAGING_DATABASE_URL .env` returns 1.

### Step 6 — Verify connectivity using `.env`

```bash
set -a && source .env && set +a
psql "$STAGING_DATABASE_URL" -c "SELECT current_database(), current_user, version();" | head -5
psql "$STAGING_DATABASE_URL" -c "SELECT count(*) FROM memory_service.memories;"  # should be 0 — schema only
```

**Gate:** connection succeeds, count is 0.

### Step 7 — Write `scripts/staging_reset.sh`

Drops and re-clones the staging schema. For when test runs leave staging dirty.

```bash
mkdir -p scripts
cat > scripts/staging_reset.sh <<'BASH'
#!/usr/bin/env bash
# Reset staging DB schema from prod. Drops all data in staging.
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]] || [[ -z "${STAGING_DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL and STAGING_DATABASE_URL must be set"
  exit 1
fi

PROD_DB=$(echo "$DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')
STAGING_DB=$(echo "$STAGING_DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')

if [[ "$STAGING_DB" != "memory_service_staging" ]]; then
  echo "ERROR: STAGING_DATABASE_URL doesn't point at memory_service_staging — refusing"
  exit 1
fi

echo "Resetting $STAGING_DB from $PROD_DB..."

# Drop and recreate the memory_service schema in staging
psql "$STAGING_DATABASE_URL" -c "DROP SCHEMA IF EXISTS memory_service CASCADE; CREATE SCHEMA memory_service;"

# Re-import schema
pg_dump "$DATABASE_URL" --schema-only --no-owner --no-privileges \
  --schema=memory_service \
  | psql "$STAGING_DATABASE_URL"

echo "Staging reset complete."
BASH
chmod +x scripts/staging_reset.sh
```

**Gate:** `bash scripts/staging_reset.sh` runs cleanly end-to-end (run it once to verify).

### Step 8 — Documentation

Write `docs/STAGING-DB.md`:

```markdown
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
```

### Step 9 — Commit and push

```bash
git add .env.example scripts/staging_reset.sh docs/STAGING-DB.md
git status   # GATE: only those 3 files (NOT .env)
git diff --cached --stat
```

**CRITICAL:** `.env` MUST NOT be committed. If `git status` shows `.env` staged, halt and write BLOCKED note.

Commit message:

```
CP-DB-SANDBOX T1: provision staging DB

memory_service_staging now lives on the same Postgres cluster as prod,
schema-cloned (no data), accessible via STAGING_DATABASE_URL.

Verification receipts:
[CC fills in: table/constraint/index parity counts from Step 4]
[CC fills in: staging_reset.sh test run output]
[CC fills in: SELECT count(*) FROM memory_service.memories on staging = 0]

Files: scripts/staging_reset.sh (NEW), docs/STAGING-DB.md (NEW),
       .env.example (+1 line)
```

```bash
git commit -F /tmp/t1-commit-msg.txt
git push origin master
```

**Final gate:** push exits 0.

---

## Halt conditions (specific to this task)

1. `memory_service_staging` already exists at start. Halt — needs human review (might be from a prior failed run; manual cleanup required).
2. Schema parity check fails (table/constraint/index counts don't match). Halt — dump the diff.
3. Connectivity test in Step 6 fails. Halt — likely password escape issue.
4. `.env` shows up in `git status` as staged. Halt immediately — secret leak risk.

---

## Definition of done

1. `memory_service_staging` exists, schema matches prod (counts identical).
2. `STAGING_DATABASE_URL` works in a fresh shell after `source .env`.
3. `scripts/staging_reset.sh` runs cleanly.
4. `docs/STAGING-DB.md` exists and accurately describes the setup.
5. Single commit pushed; `.env` NOT in commit.
6. No BLOCKED note exists.
