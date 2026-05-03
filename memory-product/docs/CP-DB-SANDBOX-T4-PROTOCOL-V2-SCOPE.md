# CP-DB-SANDBOX T4 — Protocol v2 + Cutover Smoke

**Task:** Update `docs/AUTONOMY-PROTOCOL.md` to v2 introducing Tier-1/2/3 migration policy. Run an end-to-end cutover smoke (a fake migration through the new pipeline). Update scope-doc template to reflect new tier-aware halts.
**Mode:** Autonomous with one halt for cutover smoke confirm.
**Estimated wall-clock:** 20–45 min for CC.

---

## Goal

After T4:
- `docs/AUTONOMY-PROTOCOL.md` is v2, classifies migrations into Tier 1/2/3 with explicit rules for what CC can do autonomously vs. what halts for review.
- `docs/SCOPE-DOC-TEMPLATE.md` includes a "Migration tier" field.
- A test migration has been authored, applied to staging via `db_migrate.sh up`, applied to prod, and verified — proving the pipeline works end-to-end.
- Last-touch: the test migration is downgraded and removed (it adds nothing; it was just a smoke).

---

## In scope

- Rewrite `docs/AUTONOMY-PROTOCOL.md` to v2.
- Update `docs/SCOPE-DOC-TEMPLATE.md`.
- Author `alembic/versions/0002_smoke_test.py` — adds a single boolean column `migration_smoke_test BOOLEAN DEFAULT FALSE` to `memory_service.tenants`. Pure additive Tier-1.
- Run the migration through `db_migrate.sh up`.
- Verify on prod.
- Author `alembic/versions/0003_smoke_test_cleanup.py` that drops the column. Run via `db_migrate.sh up`. (The cleanup is also a real migration, so it exercises the pipeline twice.)
- Verify both pre-existing rollback tests pass.

---

## Out of scope

- Translating the existing 23 SQL migrations into Alembic (still out of scope, reaffirmed).
- Any change to memory_api code.
- Deploying anything beyond the migration files themselves.
- Removing the smoke migrations from history (they stay as the first real migrations through the pipeline, even if they net-zero the schema).

---

## Inputs at start

- T3 committed and pushed.
- `git status` clean.
- `db_migrate.sh status` reports prod and staging both at `0001_baseline`.

---

## Steps

### Step 1 — Pre-flight

```bash
cd /root/.openclaw/workspace/memory-product
git status                              # GATE: clean
git log -1 --oneline                    # confirm T3 is HEAD
set -a && source .env && set +a
bash scripts/db_migrate.sh status
```

**HALT** if dirty or unexpected revision state.

### Step 2 — Rewrite `docs/AUTONOMY-PROTOCOL.md`

Update v1 → v2. Critical changes:

- New section: **Migration Tiers**
  - **Tier 1 (autonomous):** Additive, fully reversible, non-data. New column with default value. New index. New table. CHECK-constraint widening (adding allowed values, never removing). New ENUM values appended. CC can apply autonomously through `scripts/db_migrate.sh up` after verifying:
    - The migration's `downgrade()` is non-empty.
    - The pre-migration backup succeeded.
    - Staging applied cleanly.
    - Rollback test passes for the new revision.
  - **Tier 2 (halt for human apply):** Schema-changing in ways that touch existing rows: NOT NULL added to existing column with backfill, column rename, type change, FK addition with cascade, CHECK constraint narrowing. CC writes the migration, dry-runs on staging, runs the rollback test, then halts with a review note. Justin runs `db_migrate.sh up`.
  - **Tier 3 (always human):** Destructive — DROP TABLE, DROP COLUMN, data backfill that cannot be reversed mechanically, anything irreversible. Halts even if the rest of the chain succeeds. Justin reviews, applies manually if at all.
- Update "Halt-and-handoff rules" — the rule "Schema change needed → halt" becomes "Tier 2 or 3 schema change → halt; Tier 1 → proceed via db_migrate.sh up after verification."
- Update "What this protocol explicitly does NOT do" — remove "No production migrations from autonomous runs"; replace with "No Tier 2 or 3 migrations from autonomous runs."
- Add a new section: **Migration verification gate (Tier 1)** with the three checks CC must run before applying.
- Bump version header to `v2 — 2026-05-04`.

### Step 3 — Update `docs/SCOPE-DOC-TEMPLATE.md`

Add a top-level field after the existing header:

```markdown
**Migration tier (if any):** Tier 1 (autonomous) | Tier 2 (halt) | Tier 3 (manual) | None
```

Add to the halt-conditions section a default line:

```markdown
- Migration tier escalation: if implementation reveals the migration is actually a higher tier than scoped, halt.
```

### Step 4 — Author smoke migration `0002`

```bash
alembic revision -m "smoke_test_add_column"
```

Edit the generated file in `alembic/versions/`:

```python
"""smoke_test_add_column

Revision ID: 0002_<hash>
Revises: 0001_baseline
Create Date: 2026-05-04

End-to-end smoke for db_migrate.sh pipeline. Adds a boolean column to
memory_service.tenants with a default. Tier 1 (additive, reversible).

Paired with 0003_smoke_test_cleanup which drops the column. Net effect
on schema: zero. The migrations exist as evidence the pipeline works.
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_<hash>'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'tenants',
        sa.Column('migration_smoke_test', sa.Boolean(), server_default='false', nullable=False),
        schema='memory_service',
    )


def downgrade():
    op.drop_column('tenants', 'migration_smoke_test', schema='memory_service')
```

### Step 5 — Run the migration through the new pipeline

```bash
bash scripts/db_migrate.sh up 2>&1 | tee /tmp/migrate-up-output.txt
```

**Gate:** exit 0, both staging and prod end at `0002_<hash>`.

Verify on prod:

```bash
psql "$DATABASE_URL" -c "\d memory_service.tenants" | grep migration_smoke_test
```

**Gate:** column exists.

### Step 6 — Run rollback test

```bash
pytest tests/migrations/test_rollback.py -v --tb=short 2>&1 | tee /tmp/rollback-test-output.txt
```

**Gate:** test for `0002` passes.

### Step 7 — Author cleanup migration `0003`

```bash
alembic revision -m "smoke_test_cleanup"
```

```python
"""smoke_test_cleanup

Revision ID: 0003_<hash>
Revises: 0002_<hash>
Create Date: 2026-05-04

Removes the migration_smoke_test column added in 0002. Net schema
effect of 0002+0003 is zero.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_<hash>'
down_revision = '0002_<hash>'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('tenants', 'migration_smoke_test', schema='memory_service')


def downgrade():
    op.add_column(
        'tenants',
        sa.Column('migration_smoke_test', sa.Boolean(), server_default='false', nullable=False),
        schema='memory_service',
    )
```

**Note:** This migration is technically Tier 3 (DROP COLUMN). For the smoke we run it through the autonomous pipeline anyway because we know it's reversing a column we just added that has no data depending on it — but the protocol is being violated in the smoke for the smoke's sake. Document this in the commit message.

### Step 8 — HALT for cutover smoke confirm

CC writes `CP-DB-SANDBOX-T4-CUTOVER-REVIEW.md`:

```markdown
# CP-DB-SANDBOX T4 — Cutover Smoke Review

The new migration pipeline successfully applied 0002_smoke_test_add_column
to staging then prod. The column is now live on memory_service.tenants
with default false, no rows touched.

Next step is to apply 0003_smoke_test_cleanup which drops the column.
This is technically Tier 3 (DROP COLUMN) per the new protocol, but in
this case we know:
- The column was added 5 minutes ago.
- No data depends on it (newly-added with default false).
- Dropping returns the schema to baseline state.

To approve the cleanup:

```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
bash scripts/db_migrate.sh up
```

Or to skip the cleanup and leave the column in place (it's harmless):

```bash
echo "Leaving smoke column in place; 0003 stays unapplied."
```

After running, paste into CC:

```
Cutover smoke complete (or skipped). Resume T4 from Step 9.
```
```

CC exits cleanly. No commits at this point.

### Step 9 — (Resumed) Verify final state and run rollback tests

```bash
bash scripts/db_migrate.sh status
pytest tests/migrations/test_rollback.py -v 2>&1 | tee /tmp/rollback-final-output.txt
```

**Gate:** both 0002 and 0003 (if applied) pass rollback testing.

### Step 10 — Commit and push

```bash
git add docs/AUTONOMY-PROTOCOL.md docs/SCOPE-DOC-TEMPLATE.md alembic/versions/0002_*.py alembic/versions/0003_*.py
git status
```

Commit message:

```
CP-DB-SANDBOX T4: protocol v2 + cutover smoke

AUTONOMY-PROTOCOL v2:
- Migration Tier 1 (additive, reversible) is now autonomous via
  scripts/db_migrate.sh up after verification gates pass
- Tier 2 (schema-changing existing rows) halts for human apply
- Tier 3 (destructive) always manual

Cutover smoke: 0002 added a boolean column via the new pipeline;
0003 dropped it. Both passed rollback testing on staging. Net
schema effect: zero.

Verification receipts:
[CC fills in: db_migrate.sh up output for 0002]
[CC fills in: rollback test output for 0002]
[CC fills in: db_migrate.sh up output for 0003 OR skip note]
[CC fills in: alembic current for prod and staging]

Files: docs/AUTONOMY-PROTOCOL.md (rewritten v2),
       docs/SCOPE-DOC-TEMPLATE.md (+migration tier field),
       alembic/versions/0002_*.py (NEW),
       alembic/versions/0003_*.py (NEW)
```

```bash
git commit -F /tmp/t4-commit-msg.txt
git push origin master
```

**Final gate:** push exits 0.

---

## Halt conditions

1. Step 5 `db_migrate.sh up` fails on staging or prod for 0002. Halt — pipeline broken before going live.
2. Step 6 rollback test fails. Halt — 0002 has a bad downgrade.
3. Step 8 review halt is mandatory.
4. `.env` shows in `git status`. Halt.

---

## Definition of done

1. `docs/AUTONOMY-PROTOCOL.md` v2 with Tier-1/2/3 policy committed.
2. `docs/SCOPE-DOC-TEMPLATE.md` updated.
3. `db_migrate.sh up` ran successfully end-to-end at least once on a real migration.
4. Rollback testing harness verified working on a real migration.
5. Single commit pushed.
6. Pipeline is now ready for the next CP's first migration to use.
