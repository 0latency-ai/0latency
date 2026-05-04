"""smoke_test_add_column

Revision ID: eb51b79421a9
Revises: 0001_baseline
Create Date: 2026-05-04

End-to-end smoke for db_migrate.sh pipeline. Adds a boolean column to
memory_service.tenants with a default. Tier 1 (additive, reversible).

Paired with 0003_smoke_test_cleanup which drops the column. Net effect
on schema: zero. The migrations exist as evidence the pipeline works.
"""
from alembic import op
import sqlalchemy as sa

revision = 'eb51b79421a9'
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
