"""026_api_keys_webhooks_memories_columns

Revision ID: 3f06f969c94f
Revises: 72e0bcc1246a
Create Date: 2026-05-04 19:10:50.705213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f06f969c94f'
down_revision: Union[str, Sequence[str], None] = '72e0bcc1246a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create api_keys table
    op.execute("""
    CREATE TABLE memory_service.api_keys (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES memory_service.tenants(id),
      key_hash text NOT NULL UNIQUE,
      status text NOT NULL DEFAULT 'active',
      created_at timestamptz NOT NULL DEFAULT now(),
      rotated_at timestamptz,
      revoked_at timestamptz,
      revoke_at timestamptz,
      last_used_at timestamptz,
      metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
      CONSTRAINT api_keys_status_chk CHECK (status IN ('active', 'rotating', 'revoked'))
    )
    """)
    
    op.execute("""
    CREATE INDEX idx_api_keys_tenant_status ON memory_service.api_keys(tenant_id, status)
    """)
    
    op.execute("""
    CREATE INDEX idx_api_keys_hash ON memory_service.api_keys(key_hash)
    """)
    
    op.execute("""
    CREATE INDEX idx_api_keys_revoke_at ON memory_service.api_keys(revoke_at) 
    WHERE status='rotating' AND revoke_at IS NOT NULL
    """)
    
    # Create webhook_endpoints table
    op.execute("""
    CREATE TABLE memory_service.webhook_endpoints (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES memory_service.tenants(id),
      url text NOT NULL,
      event_types text[] NOT NULL,
      secret text,
      active boolean NOT NULL DEFAULT true,
      failure_count int NOT NULL DEFAULT 0,
      last_failure_at timestamptz,
      last_success_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now()
    )
    """)
    
    op.execute("""
    CREATE INDEX idx_webhook_endpoints_tenant_active 
    ON memory_service.webhook_endpoints(tenant_id, active)
    """)
    
    # Create webhook_dlq table
    op.execute("""
    CREATE TABLE memory_service.webhook_dlq (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      endpoint_id uuid NOT NULL REFERENCES memory_service.webhook_endpoints(id) ON DELETE CASCADE,
      event_type text NOT NULL,
      payload jsonb NOT NULL,
      attempts int NOT NULL DEFAULT 0,
      last_error text,
      first_attempt_at timestamptz NOT NULL DEFAULT now(),
      last_attempt_at timestamptz,
      resolved_at timestamptz,
      resolution text
    )
    """)
    
    op.execute("""
    CREATE INDEX idx_webhook_dlq_unresolved 
    ON memory_service.webhook_dlq(endpoint_id, last_attempt_at) 
    WHERE resolved_at IS NULL
    """)
    
    # Add new columns to memories table
    op.execute("""
    ALTER TABLE memory_service.memories
      ADD COLUMN IF NOT EXISTS freshness_score float,
      ADD COLUMN IF NOT EXISTS last_validated_at timestamptz,
      ADD COLUMN IF NOT EXISTS pattern_type text,
      ADD COLUMN IF NOT EXISTS observation_count int,
      ADD COLUMN IF NOT EXISTS last_observation_at timestamptz,
      ADD COLUMN IF NOT EXISTS triggering_event_ids uuid[],
      ADD COLUMN IF NOT EXISTS decision_text text,
      ADD COLUMN IF NOT EXISTS alternatives_considered text[],
      ADD COLUMN IF NOT EXISTS rationale text,
      ADD COLUMN IF NOT EXISTS predicted_outcome text,
      ADD COLUMN IF NOT EXISTS actual_outcome text
    """)
    
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_memories_pattern_type 
    ON memory_service.memories(tenant_id, pattern_type) 
    WHERE memory_type='pattern'
    """)
    
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_memories_decision 
    ON memory_service.memories(tenant_id, agent_id) 
    WHERE memory_type='decision'
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes on memories first
    op.execute("DROP INDEX IF EXISTS memory_service.idx_memories_decision")
    op.execute("DROP INDEX IF EXISTS memory_service.idx_memories_pattern_type")
    
    # Drop columns from memories
    op.execute("""
    ALTER TABLE memory_service.memories
      DROP COLUMN IF EXISTS actual_outcome,
      DROP COLUMN IF EXISTS predicted_outcome,
      DROP COLUMN IF EXISTS rationale,
      DROP COLUMN IF EXISTS alternatives_considered,
      DROP COLUMN IF EXISTS decision_text,
      DROP COLUMN IF EXISTS triggering_event_ids,
      DROP COLUMN IF EXISTS last_observation_at,
      DROP COLUMN IF EXISTS observation_count,
      DROP COLUMN IF EXISTS pattern_type,
      DROP COLUMN IF EXISTS last_validated_at,
      DROP COLUMN IF EXISTS freshness_score
    """)
    
    # Drop webhook_dlq table
    op.execute("DROP TABLE IF EXISTS memory_service.webhook_dlq")
    
    # Drop webhook_endpoints table
    op.execute("DROP TABLE IF EXISTS memory_service.webhook_endpoints")
    
    # Drop api_keys table
    op.execute("DROP TABLE IF EXISTS memory_service.api_keys")
