"""030_add_pattern_audit_event_types

Revision ID: f8a0d3e4c2b5
Revises: e7f9c2d3b1a4
Create Date: 2026-05-08 20:10:00.000000

Migration 030: Add pattern extraction audit event types to synthesis_audit_events constraint
Tier 1: Additive - extends CHECK constraint to allow pattern-related event types

Event types added:
- pattern_extraction_triggered: Manual or cron-triggered pattern extraction job
- pattern_extracted: Individual pattern memory created from feedback analysis
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f8a0d3e4c2b5'
down_revision: Union[str, Sequence[str], None] = 'e7f9c2d3b1a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pattern extraction event types to synthesis_audit_events constraint."""
    
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events 
        DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check;
    """)
    
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events 
        ADD CONSTRAINT synthesis_audit_events_event_type_check 
        CHECK (event_type = ANY (ARRAY[
            'synthesis_written'::text,
            'redacted'::text, 
            'resynthesized'::text,
            'consensus_run'::text,
            'consensus_disagreement_logged'::text,
            'synthesis_candidate_prepared'::text,
            'webhook_fired'::text,
            'prompt_version_changed'::text,
            'policy_changed'::text,
            'rate_limit_blocked'::text,
            'state_transition'::text,
            'consensus_run_started'::text,
            'consensus_skipped_insufficient_agents'::text,
            'consensus_failed_insufficient_candidates'::text,
            'consensus_merge_failed'::text,
            'consensus_disagreement_write_failed'::text,
            'read'::text,
            'redaction_cascade_initiated'::text,
            'redaction_cascade_overflow'::text,
            'decision_created'::text,
            'decision_outcome_recorded'::text,
            'webhook_created'::text,
            'webhook_updated'::text,
            'webhook_deleted'::text,
            'webhook_auto_disabled'::text,
            'webhook_dead_lettered'::text,
            'pattern_extraction_triggered'::text,
            'pattern_extracted'::text
        ]));
    """)


def downgrade() -> None:
    """Remove pattern extraction event types from constraint."""
    
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events 
        DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check;
    """)
    
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events 
        ADD CONSTRAINT synthesis_audit_events_event_type_check 
        CHECK (event_type = ANY (ARRAY[
            'synthesis_written'::text,
            'redacted'::text,
            'resynthesized'::text,
            'consensus_run'::text,
            'consensus_disagreement_logged'::text,
            'synthesis_candidate_prepared'::text,
            'webhook_fired'::text,
            'prompt_version_changed'::text,
            'policy_changed'::text,
            'rate_limit_blocked'::text,
            'state_transition'::text,
            'consensus_run_started'::text,
            'consensus_skipped_insufficient_agents'::text,
            'consensus_failed_insufficient_candidates'::text,
            'consensus_merge_failed'::text,
            'consensus_disagreement_write_failed'::text,
            'read'::text,
            'redaction_cascade_initiated'::text,
            'redaction_cascade_overflow'::text,
            'decision_created'::text,
            'decision_outcome_recorded'::text,
            'webhook_created'::text,
            'webhook_updated'::text,
            'webhook_deleted'::text,
            'webhook_auto_disabled'::text,
            'webhook_dead_lettered'::text
        ]));
    """)
