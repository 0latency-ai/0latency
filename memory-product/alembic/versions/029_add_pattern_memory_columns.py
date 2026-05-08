"""029_add_pattern_memory_columns

Revision ID: e7f9c2d3b1a4
Revises: d4e8f2a1b9c0
Create Date: 2026-05-08 00:00:00.000000

Migration 029: Add pattern memory columns
Tier 1: Additive columns for pattern memory type (additive, reversible, no NOT NULL)
Required for CP8 P5.5 pattern memory feature.

Columns added:
- pattern_type: Type of pattern (e.g., 'correction', 'preference_confirmation')
- observation_count: Number of observations contributing to this pattern
- last_observation_at: Timestamp of most recent observation
- triggering_event_ids: Array of feedback event IDs that triggered pattern creation
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e7f9c2d3b1a4'
down_revision: Union[str, Sequence[str], None] = 'd4e8f2a1b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pattern memory columns to memories table."""
    
    # Add pattern_type column (nullable text)
    op.execute("""
        ALTER TABLE memory_service.memories 
        ADD COLUMN IF NOT EXISTS pattern_type TEXT;
    """)
    
    # Add observation_count column (nullable integer)
    op.execute("""
        ALTER TABLE memory_service.memories 
        ADD COLUMN IF NOT EXISTS observation_count INTEGER;
    """)
    
    # Add last_observation_at column (nullable timestamp with time zone)
    op.execute("""
        ALTER TABLE memory_service.memories 
        ADD COLUMN IF NOT EXISTS last_observation_at TIMESTAMP WITH TIME ZONE;
    """)
    
    # Add triggering_event_ids column (uuid array with default empty array)
    op.execute("""
        ALTER TABLE memory_service.memories 
        ADD COLUMN IF NOT EXISTS triggering_event_ids UUID[] DEFAULT '{}';
    """)


def downgrade() -> None:
    """Remove pattern memory columns from memories table."""
    
    op.execute("""
        ALTER TABLE memory_service.memories DROP COLUMN IF EXISTS triggering_event_ids;
    """)
    
    op.execute("""
        ALTER TABLE memory_service.memories DROP COLUMN IF EXISTS last_observation_at;
    """)
    
    op.execute("""
        ALTER TABLE memory_service.memories DROP COLUMN IF EXISTS observation_count;
    """)
    
    op.execute("""
        ALTER TABLE memory_service.memories DROP COLUMN IF EXISTS pattern_type;
    """)
