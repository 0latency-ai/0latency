"""add consensus_fallback_to_single_agent event type

Revision ID: 227434ffc89e
Revises: merge_20260512
Create Date: 2026-05-13 00:43:35.132139

Tier 1 (additive CHECK constraint, reversible). Adds consensus_fallback_to_single_agent
event type to synthesis_audit_events.event_type CHECK constraint.

Context: CP9.3 Phase A. When run_consensus() fails (insufficient agents, candidate
failures, merge failures), tier_gates logs structured failure event, emits audit row,
and falls through to run_single_agent(). Enables tracking of consensus-to-single-agent
fallback path in production.

NOTE: This migration is applied via `alembic stamp` only - the constraint change was
already applied directly to the production database via off-path SQL. This migration
canonicalizes that change in the Alembic history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '227434ffc89e'
down_revision: Union[str, Sequence[str], None] = 'merge_20260512'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add consensus_fallback_to_single_agent to event_type CHECK constraint."""
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check;
        
        ALTER TABLE memory_service.synthesis_audit_events
        ADD CONSTRAINT synthesis_audit_events_event_type_check CHECK (
          event_type = ANY (ARRAY[
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
            'consensus_fallback_to_single_agent'::text,
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
          ])
        );
    """)


def downgrade() -> None:
    """Remove consensus_fallback_to_single_agent from event_type CHECK constraint."""
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check;
        
        ALTER TABLE memory_service.synthesis_audit_events
        ADD CONSTRAINT synthesis_audit_events_event_type_check CHECK (
          event_type = ANY (ARRAY[
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
          ])
        );
    """)
