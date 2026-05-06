"""025_audit_events_query_index

Revision ID: 9e8131cc23a1
Revises: 7fc534bdbff2
Create Date: 2026-05-06 19:56:52.022449

Tier: 1 (additive, reversible)
Reason: P5.2 audit log read endpoint query optimization
  Composite index (tenant_id, occurred_at DESC) for efficient tenant-filtered
  time-series queries on synthesis_audit_events.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e8131cc23a1'
down_revision: Union[str, Sequence[str], None] = '7fc534bdbff2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add composite index for tenant-filtered time-series queries
    # Using IF NOT EXISTS pattern for idempotence
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_synthesis_audit_events_tenant_time
        ON memory_service.synthesis_audit_events (tenant_id, occurred_at DESC);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the composite index
    op.execute("""
        DROP INDEX IF EXISTS memory_service.idx_synthesis_audit_events_tenant_time;
    """)
