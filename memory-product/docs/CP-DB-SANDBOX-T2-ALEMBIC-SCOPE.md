# CP-DB-SANDBOX T2 — Alembic Integration + Baseline Import

**Task:** Add Alembic to the project, configure it for prod and staging, import all 23 existing SQL migrations as a single baseline revision, and stamp prod at that baseline.
**Mode:** Autonomous with one halt for baseline confirm.
**Estimated wall-clock:** 30–60 min for CC.

---

## Goal

Make Alembic the source of truth for migration state. After T2:
- `alembic/versions/` contains the project's migration history.
- The first revision is `0001_baseline` representing the schema as of HEAD before T2 started.
- Prod `memory_service.alembic_version` table records that prod is at `0001_baseline`.
- Staging is upgradable from empty to baseline via `alembic -x env=staging upgrade head`.
- `alembic upgrade head` is a no-op against prod (already at head).

This unlocks future migrations: instead of hand-walking `psql < file.sql`, we run `alembic revision -m "..."` and `alembic upgrade head`.

---

## In scope

- `pip install alembic` (with `--break-system-packages` per project convention).
- `alembic.ini` configured to read DB URL from env var.
- `alembic/env.py` configured to use `DATABASE_URL` by default, `STAGING_DATABASE_URL` when `-x env=staging` is passed.
- `alembic/versions/0001_baseline.py` — empty up()/down() since the schema already exists; this revision exists purely to mark "prod is at this state."
- Stamp prod with `0001_baseline` (no schema change, just inserts the version row).
- Verify staging can `upgrade head` from empty (re-runs `staging_reset.sh` then stamps).
- `docs/MIGRATIONS.md` — how to write and apply a new migration via Alembic.
- Existing 23 SQL migration files stay in `migrations/` for reference but become read-only history. New migrations go through Alembic.

---

## Out of scope

- Translating the 23 existing SQL migrations into Alembic Python migrations (waste of time — the schema is the source of truth, not the migration files).
- Adding SQLAlchemy ORM models (CP9 territory).
- Auto-generation from models (requires SQLAlchemy ORM first).
- Removing or renaming `migrations/*.sql` files.
- Hooking Alembic into the FastAPI app startup (manual invocation only for now).

---

## Inputs at start

- T1 committed and pushed: staging DB exists, `STAGING_DATABASE_URL` set.
- `git status` clean.

---

## Steps

### Step 1 — Pre-flight

```bash
cd /root/.openclaw/workspace/memory-product
git status                              # GATE: clean
git log -1 --oneline                    # confirm T1 is HEAD
set -a && source .env && set +a
psql "$STAGING_DATABASE_URL" -c "SELECT 1" | head -3   # GATE: staging reachable
```

**HALT** if dirty, or staging unreachable.

### Step 2 — Install Alembic

```bash
pip install alembic --break-system-packages 2>&1 | tail -5
alembic --version
```

**Gate:** `alembic --version` prints a version string.

Add `alembic` to `requirements.txt` (find it; if absent, find the canonical Python deps file in repo and add there).

### Step 3 — Initialize Alembic

```bash
cd /root/.openclaw/workspace/memory-product
alembic init alembic
```

This creates `alembic/`, `alembic.ini`, `alembic/env.py`, `alembic/versions/`, `alembic/script.py.mako`.

### Step 4 — Configure `alembic.ini`

Edit `alembic.ini`:
- Comment out the default `sqlalchemy.url` line (we'll set it programmatically).
- Set `script_location = alembic`.
- Leave the rest at defaults.

### Step 5 — Configure `alembic/env.py`

Replace the generated `env.py` with one that:
- Reads `DATABASE_URL` from env by default.
- Reads `STAGING_DATABASE_URL` when invoked with `-x env=staging`.
- Sets the `version_table_schema` to `memory_service` so the version row lives alongside our other tables.
- Does NOT use SQLAlchemy ORM autogenerate (no `target_metadata` — set to `None`).

Reference shape:

```python
import os
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# Choose DB URL based on -x env=staging flag
x_args = context.get_x_argument(as_dictionary=True)
env_target = x_args.get('env', 'prod')

if env_target == 'staging':
    db_url = os.environ.get('STAGING_DATABASE_URL')
elif env_target == 'prod':
    db_url = os.environ.get('DATABASE_URL')
else:
    raise RuntimeError(f"Unknown env: {env_target}")

if not db_url:
    raise RuntimeError(f"DB URL not set for env={env_target}")

config.set_main_option('sqlalchemy.url', db_url)

target_metadata = None  # no autogenerate; manual revisions only

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table='alembic_version',
            version_table_schema='memory_service',
        )
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

Drop the offline-mode block (we always have a live DB).

### Step 6 — Create `0001_baseline` revision

```bash
alembic revision -m "baseline" --rev-id 0001_baseline
```

Edit `alembic/versions/0001_baseline.py`:

```python
"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-04

This revision marks the schema state as of all SQL migrations 001-023
that were hand-applied prior to Alembic adoption. It is a no-op when
applied to prod (already at this state). When applied to a fresh DB,
it would need the prior SQL migrations to have been run first; staging
gets there via scripts/staging_reset.sh which clones prod's schema.
"""
from alembic import op

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # No-op. Schema state captured by prior SQL migrations 001-023.
    pass


def downgrade():
    # No-op. Cannot meaningfully downgrade past baseline.
    pass
```

### Step 7 — HALT for baseline confirm

**This is the human-review halt.** CC writes `CP-DB-SANDBOX-T2-BASELINE-REVIEW.md` to workspace root with:

```markdown
# CP-DB-SANDBOX T2 — Baseline Review

About to stamp prod's `memory_service.alembic_version` table with revision `0001_baseline`.

This is a non-destructive write — it adds one row to a new table that didn't exist before. It cannot affect existing data.

After this stamp, all future migrations go through Alembic. Existing SQL migrations 001-023 become historical reference only.

## To approve

```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
alembic stamp 0001_baseline
psql "$DATABASE_URL" -c "SELECT version_num FROM memory_service.alembic_version;"
```

Expected output: `0001_baseline`.

## To resume CC

After running the above, paste into the CC session:

```
Baseline stamped on prod. Resume T2 from Step 8.
```
```

CC then exits cleanly. No commits at this point — `git status` shows `alembic/` and `alembic.ini` as untracked.

### Step 8 — (Resumed) Verify staging upgrade

```bash
# Reset staging to clean prod schema
bash scripts/staging_reset.sh

# Stamp staging at baseline (since the schema came from prod, it's already at baseline state)
alembic -x env=staging stamp 0001_baseline

# Verify
psql "$STAGING_DATABASE_URL" -c "SELECT version_num FROM memory_service.alembic_version;"
```

**Gate:** staging shows `0001_baseline`.

### Step 9 — Verify alembic upgrade head is no-op

```bash
alembic upgrade head 2>&1 | tail -5    # against prod
alembic -x env=staging upgrade head 2>&1 | tail -5    # against staging
```

**Gate:** both report "Running upgrade" → no actual operations (since baseline is no-op), or report "already at head".

### Step 10 — Write `docs/MIGRATIONS.md`

```markdown
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
```

### Step 11 — Commit and push

```bash
git add alembic.ini alembic/ docs/MIGRATIONS.md requirements.txt
git status   # GATE: only Alembic-related files staged (NOT .env)
git diff --cached --stat
```

Commit message in `/tmp/t2-commit-msg.txt`:

```
CP-DB-SANDBOX T2: Alembic integration + baseline import

Alembic is now the source of truth for migration state.
- env.py reads DATABASE_URL by default, STAGING_DATABASE_URL with -x env=staging
- 0001_baseline marks the schema as of hand-applied SQL migrations 001-023
- Prod stamped at 0001_baseline; staging stamped at 0001_baseline
- Existing migrations/*.sql are historical reference only; new work via Alembic

Verification receipts:
[CC fills in: alembic --version output]
[CC fills in: prod alembic_version row content]
[CC fills in: staging alembic_version row content]
[CC fills in: alembic upgrade head no-op output for both envs]

Files: alembic.ini (NEW), alembic/env.py (NEW), alembic/versions/0001_baseline.py
       (NEW), alembic/script.py.mako (NEW), docs/MIGRATIONS.md (NEW),
       requirements.txt (+1 line)
```

```bash
git commit -F /tmp/t2-commit-msg.txt
git push origin master
```

**Final gate:** push exits 0.

---

## Halt conditions

1. `pip install alembic` fails. Halt.
2. `alembic init` fails or refuses (already initialized). Halt — needs cleanup.
3. Step 7 baseline review halt is mandatory — do not proceed without resume prompt.
4. Staging `alembic upgrade head` fails after stamp. Halt — env.py likely misconfigured for `-x env=staging`.
5. `.env` shows in `git status`. Halt — secret leak risk.

---

## Definition of done

1. Alembic installed and importable.
2. `alembic.ini` and `alembic/env.py` configured.
3. `0001_baseline` revision exists.
4. Prod `memory_service.alembic_version` shows `0001_baseline`.
5. Staging stamped at `0001_baseline` after fresh schema clone.
6. `alembic upgrade head` is a no-op on both envs.
7. `docs/MIGRATIONS.md` written.
8. Single commit pushed; `.env` not committed.
