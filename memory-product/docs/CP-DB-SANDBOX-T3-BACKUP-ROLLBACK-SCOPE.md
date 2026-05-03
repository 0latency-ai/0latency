# CP-DB-SANDBOX T3 — Backup Automation + Rollback Testing Harness

**Task:** Wrap Alembic with a script that takes a `pg_dump` before every prod migration, retains the last 10 dumps, and provides a test harness that verifies every migration's `downgrade()` actually reverses its `upgrade()` on staging.
**Mode:** Autonomous, no halts.
**Estimated wall-clock:** 25–45 min for CC.

---

## Goal

After T3:
- `bash scripts/db_migrate.sh up` runs: backup prod → apply to staging → verify → apply to prod. One command, no surprises.
- `bash scripts/db_migrate.sh down` runs the equivalent rollback flow.
- Backups land in `/var/backups/0latency/` (created if missing), retain last 10.
- A pytest harness `tests/migrations/test_rollback.py` exists that, for every Alembic revision newer than baseline, applies it to staging, snapshots the schema, downgrades, snapshots again, and verifies the schema returned to pre-upgrade state.

---

## In scope

- `scripts/db_migrate.sh` — wraps Alembic, handles backups, prompts for confirmation on prod apply.
- `scripts/db_backup.sh` — standalone backup script (pg_dump → /var/backups/0latency/), retention policy.
- `scripts/db_restore.sh` — restore from a named backup. Confirms target before clobbering.
- `tests/migrations/test_rollback.py` — pytest harness for rollback testing.
- `docs/MIGRATIONS.md` updated with the new flow.

---

## Out of scope

- Backups of any DB other than prod's `memory_service`.
- Off-machine backup storage (S3, etc.) — local disk only for now; flag as followup.
- Continuous archiving / WAL shipping (overkill for this stage).
- Restoring partial backups.
- Rollback testing of pre-baseline SQL migrations (those are history; testing them adds zero safety).

---

## Inputs at start

- T2 committed: Alembic configured, prod and staging both at `0001_baseline`.
- `git status` clean.

---

## Steps

### Step 1 — Pre-flight

```bash
cd /root/.openclaw/workspace/memory-product
git status                              # GATE: clean
git log -1 --oneline                    # confirm T2 is HEAD
set -a && source .env && set +a
alembic current 2>&1 | tail -3          # confirm prod at 0001_baseline
alembic -x env=staging current 2>&1 | tail -3  # confirm staging at 0001_baseline
mkdir -p /var/backups/0latency && chmod 700 /var/backups/0latency
```

**HALT** if dirty, or either env not at `0001_baseline`.

### Step 2 — Write `scripts/db_backup.sh`

```bash
#!/usr/bin/env bash
# Backup prod DB to /var/backups/0latency/ with timestamped filename.
# Retains last 10 backups; older ones removed.
set -euo pipefail

BACKUP_DIR="/var/backups/0latency"
RETAIN=10

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

TS=$(date -u +%Y%m%dT%H%M%SZ)
DB_NAME=$(echo "$DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')
OUT="$BACKUP_DIR/${DB_NAME}_${TS}.sql.gz"

echo "Backing up $DB_NAME to $OUT..."
pg_dump "$DATABASE_URL" --no-owner --no-privileges | gzip > "$OUT"

# Verify the backup is non-empty and gunzip-able
if ! gunzip -t "$OUT"; then
  echo "ERROR: backup archive is corrupt"
  rm -f "$OUT"
  exit 1
fi

SIZE=$(stat -c %s "$OUT")
if [[ "$SIZE" -lt 1024 ]]; then
  echo "ERROR: backup is suspiciously small ($SIZE bytes)"
  exit 1
fi

# Retention: keep last $RETAIN by mtime
ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +$((RETAIN + 1)) | xargs -r rm -f

echo "Backup OK: $OUT ($SIZE bytes)"
echo "$OUT"   # last line is the path, scriptable
```

`chmod +x scripts/db_backup.sh`

### Step 3 — Write `scripts/db_restore.sh`

```bash
#!/usr/bin/env bash
# Restore prod DB from a named backup. Refuses unless --confirm flag passed.
set -euo pipefail

if [[ "${1:-}" != "--confirm" ]] || [[ -z "${2:-}" ]]; then
  echo "Usage: $0 --confirm /var/backups/0latency/FILENAME.sql.gz"
  echo "Restores prod DB from the named backup. Existing data will be replaced."
  exit 1
fi

BACKUP_FILE="$2"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "ERROR: backup not found: $BACKUP_FILE"
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set"
  exit 1
fi

echo "Restoring $BACKUP_FILE to $DATABASE_URL..."
echo "Press Ctrl+C in the next 5 seconds to abort."
sleep 5

gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"
echo "Restore complete."
```

`chmod +x scripts/db_restore.sh`

### Step 4 — Write `scripts/db_migrate.sh`

```bash
#!/usr/bin/env bash
# Migrate flow: backup prod -> apply to staging -> apply to prod.
# Usage: db_migrate.sh up | down | status
set -euo pipefail

MODE="${1:-status}"

if [[ -z "${DATABASE_URL:-}" ]] || [[ -z "${STAGING_DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL and STAGING_DATABASE_URL must be set"
  exit 1
fi

case "$MODE" in
  status)
    echo "=== Prod ==="
    alembic current
    echo "=== Staging ==="
    alembic -x env=staging current
    echo "=== Pending ==="
    alembic history | head -10
    ;;

  up)
    echo "=== Step 1: backup prod ==="
    BACKUP=$(bash scripts/db_backup.sh | tail -1)
    echo "Backup: $BACKUP"

    echo "=== Step 2: reset staging from prod schema ==="
    bash scripts/staging_reset.sh
    alembic -x env=staging stamp 0001_baseline

    echo "=== Step 3: apply pending migrations to staging ==="
    alembic -x env=staging upgrade head

    echo "=== Step 4: verify staging health ==="
    psql "$STAGING_DATABASE_URL" -c "SELECT version_num FROM memory_service.alembic_version;"

    echo "=== Step 5: apply to prod ==="
    echo "Applying to prod in 5 seconds. Ctrl+C to abort."
    sleep 5
    alembic upgrade head

    echo "=== Step 6: verify prod ==="
    alembic current
    echo "Migration complete. Backup retained at $BACKUP"
    ;;

  down)
    echo "=== Step 1: backup prod ==="
    BACKUP=$(bash scripts/db_backup.sh | tail -1)
    echo "Backup: $BACKUP"

    echo "=== Step 2: downgrade staging by 1 ==="
    alembic -x env=staging downgrade -1

    echo "=== Step 3: verify staging health ==="
    psql "$STAGING_DATABASE_URL" -c "SELECT version_num FROM memory_service.alembic_version;"

    echo "=== Step 4: downgrade prod by 1 ==="
    echo "Downgrading prod in 5 seconds. Ctrl+C to abort."
    sleep 5
    alembic downgrade -1

    echo "=== Step 5: verify prod ==="
    alembic current
    echo "Downgrade complete. Backup at $BACKUP can restore the prior state if needed."
    ;;

  *)
    echo "Usage: $0 up | down | status"
    exit 1
    ;;
esac
```

`chmod +x scripts/db_migrate.sh`

### Step 5 — Write rollback test harness

`tests/migrations/test_rollback.py`:

```python
"""
For every Alembic revision newer than 0001_baseline, verify that
upgrade() followed by downgrade() returns the schema to the pre-upgrade state.

Runs against staging. Requires staging to be at the prior revision before
each test (we reset staging to baseline at the start of the suite).
"""
import os
import subprocess
import hashlib
import pytest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STAGING_URL = os.environ.get("STAGING_DATABASE_URL")


def _run(cmd, **kwargs):
    """Run a shell command, raising on non-zero. Returns stdout."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=str(REPO_ROOT), **kwargs
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\nstderr: {result.stderr}")
    return result.stdout


def _schema_hash(db_url):
    """Hash the schema (table defs + constraints + indexes) for comparison."""
    sql = """
    SELECT string_agg(definition, E'\n' ORDER BY ord) FROM (
      SELECT 1 as ord, table_name || ' ' || column_name || ' ' || data_type as definition
        FROM information_schema.columns
        WHERE table_schema = 'memory_service'
      UNION ALL
      SELECT 2, conname || ' ' || pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid::regclass::text LIKE 'memory_service.%'
      UNION ALL
      SELECT 3, indexname || ' ' || indexdef
        FROM pg_indexes
        WHERE schemaname = 'memory_service'
    ) sub;
    """
    out = subprocess.run(
        ["psql", db_url, "-tA", "-c", sql],
        capture_output=True, text=True, check=True
    ).stdout
    return hashlib.sha256(out.encode()).hexdigest()


def _list_revisions():
    """Return revisions newer than baseline, oldest-first."""
    out = _run("alembic history -r 0001_baseline:head | grep -E '^[a-z0-9_]+ ->' || true")
    revs = []
    for line in out.strip().split("\n"):
        if "->" in line and "(head)" not in line:
            # Format: "<rev> -> <next>, <message>"
            after = line.split("->")[1].strip().split(",")[0].strip()
            revs.append(after)
    # Reverse to get oldest-first
    return list(reversed(revs))


@pytest.fixture(scope="module")
def staging_at_baseline():
    """Reset staging to baseline state once per module."""
    if not STAGING_URL:
        pytest.skip("STAGING_DATABASE_URL not set")
    _run("bash scripts/staging_reset.sh")
    _run("alembic -x env=staging stamp 0001_baseline")
    yield


@pytest.mark.parametrize("rev", _list_revisions() or ["__no_revisions__"])
def test_revision_round_trip(staging_at_baseline, rev):
    """upgrade(rev) then downgrade(-1) must leave schema unchanged."""
    if rev == "__no_revisions__":
        pytest.skip("No revisions newer than baseline yet")

    # Capture pre-upgrade schema hash
    before = _schema_hash(STAGING_URL)

    # Upgrade to this revision
    _run(f"alembic -x env=staging upgrade {rev}")

    # Downgrade back
    _run("alembic -x env=staging downgrade -1")

    # Capture post-downgrade schema hash
    after = _schema_hash(STAGING_URL)

    assert before == after, f"Revision {rev} downgrade did not restore schema. Before: {before[:12]}, After: {after[:12]}"

    # Re-upgrade so we're at the correct state for the next test
    _run(f"alembic -x env=staging upgrade {rev}")
```

### Step 6 — Smoke test the harness

```bash
mkdir -p tests/migrations
# (file written in Step 5)

# Run it — should pass (no revisions yet beyond baseline, so test_revision_round_trip skips)
pytest tests/migrations/test_rollback.py -v --tb=short 2>&1 | tail -20
```

**Gate:** test exits 0, output shows the parametrize skip case ran.

### Step 7 — Update `docs/MIGRATIONS.md`

Append a "Recommended flow" section:

```markdown
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
```

### Step 8 — Commit and push

```bash
git add scripts/db_backup.sh scripts/db_restore.sh scripts/db_migrate.sh tests/migrations/test_rollback.py docs/MIGRATIONS.md
git status   # GATE: only those 5 files staged
```

Commit message:

```
CP-DB-SANDBOX T3: backup automation + rollback test harness

scripts/db_migrate.sh wraps Alembic with: pg_dump prod -> apply staging
-> verify -> apply prod. Retains last 10 backups in /var/backups/0latency.

scripts/db_backup.sh and db_restore.sh available standalone for ad-hoc
backup/restore.

tests/migrations/test_rollback.py parametrizes over every Alembic
revision newer than baseline and verifies upgrade->downgrade round-trips
to identical schema state on staging.

Verification receipts:
[CC fills in: pytest output from Step 6]
[CC fills in: db_backup.sh test run output, file size, gunzip -t result]

Files: scripts/db_backup.sh, db_restore.sh, db_migrate.sh (NEW),
       tests/migrations/test_rollback.py (NEW),
       docs/MIGRATIONS.md (+section)
```

```bash
git commit -F /tmp/t3-commit-msg.txt
git push origin master
```

**Final gate:** push exits 0.

---

## Halt conditions

1. `/var/backups/0latency` cannot be created (disk full, permissions). Halt.
2. `pg_dump` fails on the smoke run. Halt.
3. Rollback test harness errors (not skips) on a fresh DB. Halt.
4. `.env` shows in `git status` as staged. Halt.

---

## Definition of done

1. `scripts/db_migrate.sh up | down | status` works.
2. `scripts/db_backup.sh` produces a valid gzipped pg_dump in `/var/backups/0latency/`, retains 10.
3. `tests/migrations/test_rollback.py` runs cleanly (skipping when no revisions > baseline).
4. `docs/MIGRATIONS.md` updated with new flow.
5. Single commit pushed.
