"""024_synthesis_state_backfill_and_cascade_events

Revision ID: 7fc534bdbff2
Revises: ce42a2cd8bff
Create Date: 2026-05-05 17:26:47.909070

Tier: 1 (additive, reversible)
Reason: P5.1 Stage 2 - Redaction cascade implementation
  1. Backfill synthesis_state NULL -> 'valid' for existing synthesis rows
  2. Add new audit event types for cascade flow
  3. Add 'pending_resynthesis' to synthesis_state CHECK constraint
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7fc534bdbff2'
down_revision: Union[str, Sequence[str], None] = 'ce42a2cd8bff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Previous event types (from migration ce42a2cd8bff)
ALLOWED_EVENT_TYPES_OLD = [
    'synthesis_written', 'redacted', 'resynthesized', 'consensus_run',
    'consensus_disagreement_logged', 'synthesis_candidate_prepared',
    'webhook_fired', 'prompt_version_changed', 'policy_changed',
    'rate_limit_blocked', 'state_transition', 'consensus_run_started',
    'consensus_skipped_insufficient_agents',
    'consensus_failed_insufficient_candidates', 'consensus_merge_failed',
    'consensus_disagreement_write_failed', 'read'
]

# Add cascade-related event types
ALLOWED_EVENT_TYPES_NEW = ALLOWED_EVENT_TYPES_OLD + [
    'redaction_cascade_initiated',
    'redaction_cascade_overflow'
]

# Synthesis state values
SYNTHESIS_STATES_OLD = ['valid', 'pending_review', 'invalidated', 'resynthesized']
SYNTHESIS_STATES_NEW = SYNTHESIS_STATES_OLD + ['pending_resynthesis']


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Extend synthesis_audit_events CHECK constraint with new event types
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        DROP CONSTRAINT synthesis_audit_events_event_type_check;
    """)
    new_list = ", ".join(f"'{e}'::text" for e in ALLOWED_EVENT_TYPES_NEW)
    op.execute(f"""
        ALTER TABLE memory_service.synthesis_audit_events
        ADD CONSTRAINT synthesis_audit_events_event_type_check
        CHECK (event_type = ANY (ARRAY[{new_list}]));
    """)
    
    # Step 2: Extend memories synthesis_state CHECK constraint with pending_resynthesis
    op.execute("""
        ALTER TABLE memory_service.memories
        DROP CONSTRAINT check_synthesis_state;
    """)
    states_list = ", ".join(f"'{s}'::text" for s in SYNTHESIS_STATES_NEW)
    op.execute(f"""
        ALTER TABLE memory_service.memories
        ADD CONSTRAINT check_synthesis_state
        CHECK ((synthesis_state IS NULL) OR (synthesis_state = ANY (ARRAY[{states_list}])));
    """)
    
    # Step 3: Backfill synthesis_state for existing synthesis rows
    op.execute("""
        UPDATE memory_service.memories
        SET synthesis_state = 'valid'
        WHERE memory_type = 'synthesis'
          AND synthesis_state IS NULL;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Restore old event_type CHECK constraint
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        DROP CONSTRAINT synthesis_audit_events_event_type_check;
    """)
    old_list = ", ".join(f"'{e}'::text" for e in ALLOWED_EVENT_TYPES_OLD)
    op.execute(f"""
        ALTER TABLE memory_service.synthesis_audit_events
        ADD CONSTRAINT synthesis_audit_events_event_type_check
        CHECK (event_type = ANY (ARRAY[{old_list}]));
    """)
    
    # Restore old synthesis_state CHECK constraint
    op.execute("""
        ALTER TABLE memory_service.memories
        DROP CONSTRAINT check_synthesis_state;
    """)
    old_states = ", ".join(f"'{s}'::text" for s in SYNTHESIS_STATES_OLD)
    op.execute(f"""
        ALTER TABLE memory_service.memories
        ADD CONSTRAINT check_synthesis_state
        CHECK ((synthesis_state IS NULL) OR (synthesis_state = ANY (ARRAY[{old_states}])));
    """)
    
    # Note: We don't reverse the synthesis_state backfill
    # The backfilled 'valid' state is the correct end state
