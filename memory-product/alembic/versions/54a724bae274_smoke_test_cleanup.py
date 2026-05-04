"""smoke_test_cleanup

Revision ID: 54a724bae274
Revises: eb51b79421a9
Create Date: 2026-05-04

Removes the migration_smoke_test column added in 0002 (eb51b79421a9). Net schema
effect of 0002+0003 is zero. This is technically Tier 3 (DROP COLUMN) per the
protocol, but safe for the smoke test since the column was just added with no
data depending on it.
"""
from alembic import op
import sqlalchemy as sa

revision = '54a724bae274'
down_revision = 'eb51b79421a9'
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
