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
