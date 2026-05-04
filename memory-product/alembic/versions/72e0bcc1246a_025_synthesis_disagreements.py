"""025_synthesis_disagreements

Revision ID: 72e0bcc1246a
Revises: a70dd7b2538c
Create Date: 2026-05-04 06:58:01.756028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72e0bcc1246a'
down_revision: Union[str, Sequence[str], None] = 'a70dd7b2538c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.
    
    Actual column names verified from synthesis_audit_events:
    - tenant_id, target_memory_id, event_type, actor, event_payload, occurred_at
    """
    
    # 1. Extend event_type CHECK constraint to include new consensus event type
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
            'webhook_fired'::text,
            'prompt_version_changed'::text,
            'policy_changed'::text,
            'rate_limit_blocked'::text,
            'state_transition'::text
        ]));
    """)
    
    # 2. Create synthesis_disagreements table
    op.execute("""
        CREATE TABLE memory_service.synthesis_disagreements (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
          consensus_synthesis_id uuid NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
          cluster_id text NOT NULL,
          candidate_count int NOT NULL CHECK (candidate_count >= 2),
          disagreement_payload jsonb NOT NULL,
          detected_at timestamptz NOT NULL DEFAULT now(),
          reviewed_at timestamptz,
          reviewer text,
          resolution text
        );
    """)
    
    # 3. Create indexes
    op.execute("""
        CREATE INDEX idx_synthesis_disagreements_tenant_detected
          ON memory_service.synthesis_disagreements (tenant_id, detected_at DESC);
    """)
    
    op.execute("""
        CREATE INDEX idx_synthesis_disagreements_synthesis
          ON memory_service.synthesis_disagreements (consensus_synthesis_id);
    """)
    
    op.execute("""
        CREATE INDEX idx_synthesis_disagreements_unresolved
          ON memory_service.synthesis_disagreements (tenant_id, detected_at DESC)
          WHERE resolution IS NULL;
    """)
    
    # 4. Create trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION memory_service.emit_disagreement_audit()
        RETURNS TRIGGER AS $$
        BEGIN
          INSERT INTO memory_service.synthesis_audit_events
            (tenant_id, target_memory_id, event_type, actor, event_payload, occurred_at)
          VALUES
            (NEW.tenant_id,
             NEW.consensus_synthesis_id,
             'consensus_disagreement_logged',
             'system',
             jsonb_build_object(
               'disagreement_id', NEW.id,
               'cluster_id', NEW.cluster_id,
               'candidate_count', NEW.candidate_count
             ),
             NEW.detected_at);
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 5. Create trigger
    op.execute("""
        CREATE TRIGGER trg_disagreement_audit
          AFTER INSERT ON memory_service.synthesis_disagreements
          FOR EACH ROW EXECUTE FUNCTION memory_service.emit_disagreement_audit();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop in reverse order
    op.execute("DROP TRIGGER IF EXISTS trg_disagreement_audit ON memory_service.synthesis_disagreements;")
    op.execute("DROP FUNCTION IF EXISTS memory_service.emit_disagreement_audit();")
    op.execute("DROP INDEX IF EXISTS memory_service.idx_synthesis_disagreements_unresolved;")
    op.execute("DROP INDEX IF EXISTS memory_service.idx_synthesis_disagreements_synthesis;")
    op.execute("DROP INDEX IF EXISTS memory_service.idx_synthesis_disagreements_tenant_detected;")
    op.execute("DROP TABLE IF EXISTS memory_service.synthesis_disagreements;")
    
    # Restore original CHECK constraint (remove consensus_disagreement_logged)
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
            'webhook_fired'::text,
            'prompt_version_changed'::text,
            'policy_changed'::text,
            'rate_limit_blocked'::text,
            'state_transition'::text
        ]));
    """)
