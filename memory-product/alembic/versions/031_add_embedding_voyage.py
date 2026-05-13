"""031_add_embedding_voyage_column

Revision ID: f1_voyage_001
Revises: 227434ffc89e
Create Date: 2026-05-13

Migration 031: Add Voyage embedding column
Tier 1: Additive column + index (additive, reversible, no NOT NULL)
Required for F1: Voyage voyage-3-large embedding (1024-dim).

Adds:
- embedding_voyage vector(1024) column (nullable, for parallel rollout)
- HNSW index on embedding_voyage for cosine distance search
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f1_voyage_001'
down_revision: Union[str, Sequence[str], None] = '227434ffc89e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE memory_service.memories "
        "ADD COLUMN IF NOT EXISTS embedding_voyage vector(1024)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "idx_memories_embedding_voyage_hnsw "
        "ON memory_service.memories "
        "USING hnsw (embedding_voyage vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS memory_service.idx_memories_embedding_voyage_hnsw")
    op.execute("ALTER TABLE memory_service.memories DROP COLUMN IF EXISTS embedding_voyage")
