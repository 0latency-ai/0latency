"""CP-RECALL: add default_agent_id to tenants

Revision ID: cprecall_default_agent_id
Revises: 028_event_at
Create Date: 2026-06-25

Tier 1 (additive, reversible). Adds memory_service.tenants.default_agent_id and
backfills the user-justin tenant. Supports namespace default-resolution so unscoped
recalls resolve to a tenant-configured agent instead of the polluted 'default' agent.

No inner BEGIN/COMMIT: alembic env.py wraps run_migrations in a transaction.
"""
from alembic import op


revision = 'cprecall_default_agent_id'
down_revision = '028_event_at'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE memory_service.tenants
    ADD COLUMN IF NOT EXISTS default_agent_id text;
    """)
    op.execute("""
    UPDATE memory_service.tenants
    SET default_agent_id = 'user-justin'
    WHERE id = '44c3080d-c196-407d-a606-4ea9f62ba0fc';
    """)


def downgrade():
    op.execute("""
    ALTER TABLE memory_service.tenants
    DROP COLUMN IF EXISTS default_agent_id;
    """)
