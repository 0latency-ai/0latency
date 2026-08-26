"""default agent per tenant

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-05-12

Tier 1 (registry backfill, reversible). Ensures "default" agent exists in registry.

Context: CP-FALLBACK-FIX P0. API contract specifies agent_id is optional on omit,
resolving to "default" (not tenant UUID). Dashboard requires default agent to be a
first-class registry entry for proper rendering.

Pattern: INSERT single shared "default" agent. Idempotent, safe to re-run.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    INSERT INTO memory_service.agent_config (tenant_id, agent_id)
    VALUES ('00000000-0000-0000-0000-000000000000', 'default')
    ON CONFLICT (agent_id) DO NOTHING;
    """)


def downgrade():
    op.execute("""
    DELETE FROM memory_service.agent_config 
    WHERE agent_id = 'default';
    """)
