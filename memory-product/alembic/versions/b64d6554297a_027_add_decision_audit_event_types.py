"""027_add_decision_audit_event_types

Revision ID: b64d6554297a
Revises: cef15800b092
Create Date: 2026-05-07 22:00:00.000000

Migration 027: Add decision journal audit event types
Tier 1: Extends event_type CHECK constraint (additive, reversible)
Required for CP8 P5.3 decision journal endpoints.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b64d6554297a'
down_revision: Union[str, Sequence[str], None] = 'cef15800b092'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add decision_created and decision_outcome_recorded to event_type CHECK."""
    # Drop existing constraint
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check
    """)
    
    # Recreate with new event types added
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        ADD CONSTRAINT synthesis_audit_events_event_type_check
        CHECK (event_type IN (
            'synthesis_written',
            'redacted',
            'resynthesized',
            'consensus_run',
            'consensus_disagreement_logged',
            'synthesis_candidate_prepared',
            'webhook_fired',
            'prompt_version_changed',
            'policy_changed',
            'rate_limit_blocked',
            'state_transition',
            'consensus_run_started',
            'consensus_skipped_insufficient_agents',
            'consensus_failed_insufficient_candidates',
            'consensus_merge_failed',
            'consensus_disagreement_write_failed',
            'read',
            'redaction_cascade_initiated',
            'redaction_cascade_overflow',
            'decision_created',
            'decision_outcome_recorded'
        ))
    """)


def downgrade() -> None:
    """Remove decision event types from event_type CHECK."""
    # Drop constraint
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check
    """)
    
    # Recreate without decision event types
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        ADD CONSTRAINT synthesis_audit_events_event_type_check
        CHECK (event_type IN (
            'synthesis_written',
            'redacted',
            'resynthesized',
            'consensus_run',
            'consensus_disagreement_logged',
            'synthesis_candidate_prepared',
            'webhook_fired',
            'prompt_version_changed',
            'policy_changed',
            'rate_limit_blocked',
            'state_transition',
            'consensus_run_started',
            'consensus_skipped_insufficient_agents',
            'consensus_failed_insufficient_candidates',
            'consensus_merge_failed',
            'consensus_disagreement_write_failed',
            'read',
            'redaction_cascade_initiated',
            'redaction_cascade_overflow'
        ))
    """)
