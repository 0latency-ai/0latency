"""026_add_decision_journal_columns

Revision ID: cef15800b092
Revises: 9e8131cc23a1
Create Date: 2026-05-07 21:46:23.054750

Migration 026: Add decision journal structured columns + validation
Tier 2: Additive schema change (5 nullable columns + partial index + partial CHECK)
Prerequisites: memory_type='decision' already in CHECK constraint (verified)

Note: Columns may already exist from prior manual migration. Using IF NOT EXISTS.
Adding CHECK constraint and improved index (with created_at DESC) not present in prior schema.
Backfills existing decision rows with context -> decision_text/rationale before constraint.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cef15800b092'
down_revision: Union[str, Sequence[str], None] = '9e8131cc23a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add decision journal columns, index, and constraint."""
    # Add columns with IF NOT EXISTS (idempotent - handles pre-existing columns)
    op.execute("""
        ALTER TABLE memory_service.memories
          ADD COLUMN IF NOT EXISTS decision_text text,
          ADD COLUMN IF NOT EXISTS alternatives_considered text[],
          ADD COLUMN IF NOT EXISTS rationale text,
          ADD COLUMN IF NOT EXISTS predicted_outcome text,
          ADD COLUMN IF NOT EXISTS actual_outcome text
    """)
    
    # Backfill existing decision rows: copy context to decision_text and rationale
    # This makes legacy decision rows compliant with the new CHECK constraint
    op.execute("""
        UPDATE memory_service.memories
        SET decision_text = COALESCE(context, 'Legacy decision (pre-structured)'),
            rationale = COALESCE(context, 'No rationale recorded (legacy row)')
        WHERE memory_type = 'decision'
          AND (decision_text IS NULL OR rationale IS NULL)
    """)
    
    # Create partial index on decision rows for time-ordered retrieval
    # This is MORE specific than any existing idx_memories_decision (which lacks created_at)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_decision_tenant_agent
        ON memory_service.memories (tenant_id, agent_id, created_at DESC)
        WHERE memory_type = 'decision'
    """)
    
    # Add partial CHECK constraint: decision rows MUST have decision_text + rationale
    # Partial constraint so non-decision rows are unaffected
    # Applied AFTER backfill so existing rows comply
    op.execute("""
        ALTER TABLE memory_service.memories
        ADD CONSTRAINT check_decision_required_fields
        CHECK (memory_type != 'decision' OR (decision_text IS NOT NULL AND rationale IS NOT NULL))
    """)


def downgrade() -> None:
    """Remove decision journal columns, index, and constraint."""
    # Drop constraint first
    op.execute("""
        ALTER TABLE memory_service.memories
        DROP CONSTRAINT IF EXISTS check_decision_required_fields
    """)
    
    # Drop index
    op.execute("DROP INDEX IF EXISTS memory_service.idx_memories_decision_tenant_agent")
    
    # Note: We do NOT revert the backfill (UPDATE) - downgrade only removes additive schema
    # Drop columns
    op.execute("""
        ALTER TABLE memory_service.memories
          DROP COLUMN IF EXISTS actual_outcome,
          DROP COLUMN IF EXISTS predicted_outcome,
          DROP COLUMN IF EXISTS rationale,
          DROP COLUMN IF EXISTS alternatives_considered,
          DROP COLUMN IF EXISTS decision_text
    """)
