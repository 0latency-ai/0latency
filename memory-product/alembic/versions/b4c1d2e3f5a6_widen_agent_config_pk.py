"""widen agent_config pk to (agent_id, tenant_id)

Revision ID: b4c1d2e3f5a6
Revises: a3_parent_memory_ids_gin
Create Date: 2026-08-26

Tier 3 (constraint drop). DO NOT APPLY AUTONOMOUSLY -- human runs this.

Problem
-------
memory_service.agent_config carries a NOT NULL tenant_id with an FK to tenants,
but its primary key is `agent_id` alone. The table was built single-tenant and
the tenant column was added later without widening the key, so the table can
physically hold only ONE row per agent_id across the entire installation.

Two consequences, both live:

1. _load_agent_config (src/recall.py) filters on agent_id with no tenant
   predicate. Isolation is delegated to RLS, but agent_config has
   relforcerowsecurity = false and the app connects as doadmin, the table
   owner, so RLS is bypassed. Verified 2026-08-25: with tenant context set to
   thomas, `WHERE agent_id='thomas'` returns the Default Tenant's row.

2. The predicate cannot simply be added, because there is nowhere to put the
   rows it would need. agent_id='default' is used by 17 tenants and resolves,
   for all of them, to a single Default Tenant row carrying
   recency_half_life_days = 14 against a code fallback of 3. Adding the
   predicate without this migration silently moves 16 tenants to the fallback,
   three of which wrote memories within the last week.

This revision makes the per-tenant rows storable. It deliberately does NOT add
the loader predicate -- that lands separately, after this is applied, so the
data exists before the query starts requiring it.

Reversibility
-------------
downgrade() restores the single-column key, which requires first deleting the
per-tenant rows this migration creates -- otherwise the narrow key cannot be
rebuilt. That deletion is mechanical and scoped to rows this revision inserted
(default, non-Default-Tenant), but it IS data loss on the way back, which is
what places this at Tier 3 rather than Tier 2.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b4c1d2e3f5a6'
down_revision = 'a3_parent_memory_ids_gin'
branch_labels = None
depends_on = None

DEFAULT_TENANT = '00000000-0000-0000-0000-000000000000'


def upgrade():
    # 1. Widen the key. Dropping agent_config_pkey is the destructive step.
    op.execute("""
    ALTER TABLE memory_service.agent_config
        DROP CONSTRAINT agent_config_pkey;
    """)
    op.execute("""
    ALTER TABLE memory_service.agent_config
        ADD CONSTRAINT agent_config_pkey PRIMARY KEY (agent_id, tenant_id);
    """)

    # 2. Replicate the shared 'default' row to every tenant that currently
    #    resolves to it through the cross-tenant bleed, preserving the values
    #    those tenants are being served today (half_life 14 included). After
    #    this, adding the loader's tenant predicate is behaviour-preserving
    #    for them rather than a silent reset to the code fallbacks.
    #
    #    'echo' and 'thomas' are deliberately NOT replicated. Their rows carry
    #    values identical to the code fallbacks (0.35/0.4/0.15/0.1/3), so
    #    orphaning them under a tenant-scoped lookup is a no-op. Only 'default'
    #    diverges from the fallbacks, and only 'default' is load-bearing.
    op.execute("""
    INSERT INTO memory_service.agent_config
        (agent_id, tenant_id, context_budget, recency_weight, semantic_weight,
         importance_weight, access_weight, recency_half_life_days,
         extraction_model, embedding_model, identity, user_profile, metadata)
    SELECT src.agent_id,
           t.tenant_id,
           src.context_budget, src.recency_weight, src.semantic_weight,
           src.importance_weight, src.access_weight, src.recency_half_life_days,
           src.extraction_model, src.embedding_model,
           src.identity, src.user_profile, src.metadata
    FROM memory_service.agent_config src
    CROSS JOIN LATERAL (
        SELECT DISTINCT m.tenant_id
        FROM memory_service.memories m
        WHERE m.agent_id = 'default'
    ) AS t
    WHERE src.agent_id = 'default'
      AND src.tenant_id = '00000000-0000-0000-0000-000000000000'::uuid
    ON CONFLICT (agent_id, tenant_id) DO NOTHING;
    """)


def downgrade():
    # The narrow key cannot be rebuilt while duplicate agent_ids exist, so the
    # replicated rows must go first. Scoped to exactly what upgrade() inserted:
    # agent_id='default' for tenants other than the Default Tenant.
    op.execute("""
    DELETE FROM memory_service.agent_config
    WHERE agent_id = 'default'
      AND tenant_id <> '00000000-0000-0000-0000-000000000000'::uuid;
    """)
    op.execute("""
    ALTER TABLE memory_service.agent_config
        DROP CONSTRAINT agent_config_pkey;
    """)
    op.execute("""
    ALTER TABLE memory_service.agent_config
        ADD CONSTRAINT agent_config_pkey PRIMARY KEY (agent_id);
    """)
