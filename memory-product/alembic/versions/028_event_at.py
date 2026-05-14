"""028: add nullable event_at column to memories

Tier 1 migration: adds nullable column with no default, no backfill.
Temporal scoring prefers event_at when present, falls back to created_at.

Revision ID: 028_event_at
Revises: f1_voyage_001
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa


revision = '028_event_at'
down_revision = 'f1_voyage_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add nullable event_at column — represents when the event actually
    # occurred, as opposed to created_at which represents ingest time.
    # When not set, temporal scoring falls back to created_at.
    op.add_column(
        'memories',
        sa.Column('event_at', sa.DateTime(timezone=True), nullable=True),
        schema='memory_service'
    )

    # Add index for temporal queries — partial index on non-null values only
    op.create_index(
        'idx_memories_event_at',
        'memories',
        ['event_at'],
        schema='memory_service',
        postgresql_where=sa.text('event_at IS NOT NULL')
    )


def downgrade():
    op.drop_index(
        'idx_memories_event_at',
        table_name='memories',
        schema='memory_service'
    )
    op.drop_column(
        'memories',
        'event_at',
        schema='memory_service'
    )
