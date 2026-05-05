"""027_add_read_to_synthesis_audit_event_type

Revision ID: ce42a2cd8bff
Revises: 3f06f969c94f
Create Date: 2026-05-05 01:13:21.875966

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce42a2cd8bff'
down_revision: Union[str, Sequence[str], None] = '3f06f969c94f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALLOWED_EVENT_TYPES_OLD = [
    'synthesis_written', 'redacted', 'resynthesized', 'consensus_run',
    'consensus_disagreement_logged', 'synthesis_candidate_prepared',
    'webhook_fired', 'prompt_version_changed', 'policy_changed',
    'rate_limit_blocked', 'state_transition', 'consensus_run_started',
    'consensus_skipped_insufficient_agents',
    'consensus_failed_insufficient_candidates', 'consensus_merge_failed',
    'consensus_disagreement_write_failed'
]
ALLOWED_EVENT_TYPES_NEW = ALLOWED_EVENT_TYPES_OLD + ['read']


def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
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
