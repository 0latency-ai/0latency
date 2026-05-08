"""028_add_webhook_tables

Revision ID: d4e8f2a1b9c0
Revises: b64d6554297a
Create Date: 2026-05-08 00:00:00.000000

Migration 028: Add webhook infrastructure tables
Tier 2: Creates tenant_webhooks and webhook_deliveries tables (additive, reversible)
Required for CP8 P5.4 diff webhooks feature.

NOTE: Drops old webhooks tables from feature gap implementation (empty, not in use).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e8f2a1b9c0'
down_revision: Union[str, Sequence[str], None] = 'b64d6554297a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create webhook tables and extend audit event types."""

    # Drop old webhook tables if they exist (from feature gap implementation)
    op.execute("DROP TABLE IF EXISTS memory_service.webhook_deliveries CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_service.webhooks CASCADE")

    # Create tenant_webhooks table
    op.execute("""
        CREATE TABLE memory_service.tenant_webhooks (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
            name          text NOT NULL,
            url           text NOT NULL,
            secret        text NOT NULL,
            event_types   text[] NOT NULL DEFAULT ARRAY['synthesis.replaced'],
            enabled       boolean NOT NULL DEFAULT true,
            deleted_at    timestamptz,
            created_at    timestamptz NOT NULL DEFAULT now(),
            updated_at    timestamptz NOT NULL DEFAULT now(),
            last_success_at timestamptz,
            last_failure_at timestamptz,
            consecutive_failures integer NOT NULL DEFAULT 0,
            CONSTRAINT chk_webhook_url_https CHECK (url ~* '^https://'),
            CONSTRAINT chk_webhook_name_len  CHECK (char_length(name) BETWEEN 1 AND 100)
        )
    """)

    # Create index on tenant_webhooks
    op.execute("""
        CREATE INDEX idx_tenant_webhooks_tenant_enabled
          ON memory_service.tenant_webhooks(tenant_id, enabled)
          WHERE enabled = true AND deleted_at IS NULL
    """)

    # Create webhook_deliveries table
    op.execute("""
        CREATE TABLE memory_service.webhook_deliveries (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            webhook_id      uuid NOT NULL REFERENCES memory_service.tenant_webhooks(id) ON DELETE CASCADE,
            tenant_id       uuid NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
            event_id        uuid NOT NULL,
            event_type      text NOT NULL,
            payload         jsonb NOT NULL,
            status          text NOT NULL DEFAULT 'pending',
            attempt_count   integer NOT NULL DEFAULT 0,
            next_attempt_at timestamptz NOT NULL DEFAULT now(),
            last_attempt_at timestamptz,
            last_status_code integer,
            last_error      text,
            created_at      timestamptz NOT NULL DEFAULT now(),
            updated_at      timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT chk_delivery_status CHECK (status IN ('pending','delivered','failed','dead'))
        )
    """)

    # Create indexes on webhook_deliveries
    op.execute("""
        CREATE INDEX idx_webhook_deliveries_due
          ON memory_service.webhook_deliveries(next_attempt_at)
          WHERE status = 'pending'
    """)

    op.execute("""
        CREATE INDEX idx_webhook_deliveries_tenant_event
          ON memory_service.webhook_deliveries(tenant_id, event_id)
    """)

    op.execute("""
        CREATE INDEX idx_webhook_deliveries_status_created
          ON memory_service.webhook_deliveries(status, created_at DESC)
    """)

    # Extend synthesis_audit_events event_type CHECK constraint
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check
    """)

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
            'decision_outcome_recorded',
            'webhook_created',
            'webhook_updated',
            'webhook_deleted',
            'webhook_auto_disabled',
            'webhook_dead_lettered'
        ))
    """)


def downgrade() -> None:
    """Drop webhook tables and revert audit event types."""

    # Drop webhook tables in reverse order
    op.execute("DROP TABLE IF EXISTS memory_service.webhook_deliveries CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_service.tenant_webhooks CASCADE")

    # Revert synthesis_audit_events event_type CHECK constraint
    op.execute("""
        ALTER TABLE memory_service.synthesis_audit_events
        DROP CONSTRAINT IF EXISTS synthesis_audit_events_event_type_check
    """)

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
