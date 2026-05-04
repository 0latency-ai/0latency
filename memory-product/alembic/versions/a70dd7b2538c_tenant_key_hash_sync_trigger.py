"""tenant key hash sync trigger

Revision ID: a70dd7b2538c
Revises: 54a724bae274
Create Date: 2026-05-04

Tier 1 (additive, reversible). Permanently seals api_key_hash drift by
auto-recomputing the hash whenever api_key_live is INSERTed or UPDATEd.

Context: 27/110 tenants drifted (24.5%) due to /admin/rotate-key bug at
api/main.py:3025 writing only api_key_hash without api_key_live. Application
bug fixed in commit 24eec83. This trigger makes the failure mode
mathematically impossible at the DB layer regardless of future app bugs.

Replaces: migrations/024_tenant_key_hash_trigger.sql
"""
from alembic import op


revision = 'a70dd7b2538c'
down_revision = '54a724bae274'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("""
        CREATE OR REPLACE FUNCTION memory_service.sync_api_key_hash()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.api_key_live IS NOT NULL THEN
                NEW.api_key_hash := encode(digest(NEW.api_key_live, 'sha256'), 'hex');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER tenant_api_key_hash_sync
            BEFORE INSERT OR UPDATE OF api_key_live
            ON memory_service.tenants
            FOR EACH ROW
            WHEN (NEW.api_key_live IS NOT NULL)
            EXECUTE FUNCTION memory_service.sync_api_key_hash();
    """)

    op.execute("""
        COMMENT ON FUNCTION memory_service.sync_api_key_hash IS
            'Auto-recompute api_key_hash when api_key_live is written. Prevents hash drift.';
    """)

    op.execute("""
        COMMENT ON TRIGGER tenant_api_key_hash_sync ON memory_service.tenants IS
            'Maintains invariant: api_key_hash = sha256(api_key_live). Prevents manual UPDATE bugs.';
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS tenant_api_key_hash_sync ON memory_service.tenants")
    op.execute("DROP FUNCTION IF EXISTS memory_service.sync_api_key_hash()")
    # NOTE: pgcrypto extension intentionally NOT dropped — other tables may depend on it.
