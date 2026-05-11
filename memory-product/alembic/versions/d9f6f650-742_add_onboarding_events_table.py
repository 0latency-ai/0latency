"""add onboarding_events table

Revision ID: f1a2b3c4d5e6
Revises: b64d6554297a
Create Date: 2026-05-10

Tier 1 (additive, reversible). Tracks time-to-first-memory for onboarding optimization.

Context: CP9 Phase 2 Track B1. Captures structured telemetry when tenants successfully
add their first memory across all install paths (SDK, CLI, MCP, Web). Event includes:
install_path, elapsed_seconds from tenant creation, tenant_id, agent_id, timestamp.

Enables data-driven onboarding funnel analysis and <60s time-to-first-memory optimization.

Pattern: One-shot event per tenant, gated by NOT EXISTS check in application layer.
Atomic with memory write (both succeed or both fail).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'f1a2b3c4d5e6'
down_revision = '137b48ae1497'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE memory_service.onboarding_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
            agent_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            install_path TEXT NOT NULL,
            elapsed_seconds NUMERIC NOT NULL,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX idx_onboarding_events_tenant_id 
        ON memory_service.onboarding_events(tenant_id)
    """)

    op.execute("""
        CREATE INDEX idx_onboarding_events_path 
        ON memory_service.onboarding_events(install_path)
    """)

    op.execute("""
        CREATE INDEX idx_onboarding_events_created_at 
        ON memory_service.onboarding_events(created_at)
    """)

    op.execute("""
        COMMENT ON TABLE memory_service.onboarding_events IS
            'Tracks first-memory telemetry for onboarding funnel optimization (CP9 P2 T1)';
    """)

    op.execute("""
        COMMENT ON COLUMN memory_service.onboarding_events.install_path IS
            'Origin: sdk, cli, mcp, web, unknown. Sent via X-Install-Path header.';
    """)

    op.execute("""
        COMMENT ON COLUMN memory_service.onboarding_events.elapsed_seconds IS
            'Time from tenant creation to first successful memory write (NOW() - tenants.created_at)';
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS memory_service.onboarding_events CASCADE")
