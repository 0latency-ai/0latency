"""CP-THOMAS Chain A / A3: GIN index for raw_turn -> atom lineage lookups

Revision ID: a3_parent_memory_ids_gin
Revises: cprecall_default_agent_id
Create Date: 2026-08-21

Tier 1 (additive, reversible, no data change).

Lineage between a raw_turn and the atoms extracted from it is not a column -- it
lives in the child atom's metadata->'parent_memory_ids' jsonb array. There was no
index able to serve that lookup, so the operational question "did this turn extract
anything?" was a seq scan over the whole memories table.

Measured on prod (57,936 rows) before this migration:

    EXPLAIN ANALYZE
    SELECT id FROM memory_service.memories
    WHERE metadata->'parent_memory_ids' @> to_jsonb('<raw_turn_uuid>'::text);

    Seq Scan  ...  Execution Time: 635.326 ms   Buffers: shared hit=14048
    Rows Removed by Filter: 57926

After:

    Bitmap Index Scan on idx_memories_parent_memory_ids
              ...  Execution Time:   0.117 ms   Buffers: shared hit=7

~5,400x on execution time, 14,048 -> 7 buffers. Index size 1,104 kB.

Why a dedicated expression index rather than the existing idx_memories_metadata_gin:
that index (gin on the whole metadata column, jsonb_ops) can only serve the
top-level containment spelling
`metadata @> jsonb_build_object('parent_memory_ids', jsonb_build_array(...))`,
which measured 9-17 ms and required callers to know the trick. It cannot serve the
natural `metadata->'parent_memory_ids' @> ...` arrow form at all. jsonb_path_ops on
the extracted array indexes only what this lookup needs -- 1.1 MB against the
8.7 MB whole-metadata index -- and serves the arrow form directly.

APPLIED OUT OF BAND: the index was created on prod with CREATE INDEX CONCURRENTLY
on 2026-08-21 so the live memories table was never locked. alembic's env.py wraps
run_migrations in a transaction, and CONCURRENTLY cannot run inside one, so this
migration uses the plain form guarded by IF NOT EXISTS -- on prod it is a no-op that
only advances the version stamp; on a fresh database it builds the index normally.

Known follow-up, deliberately NOT in this migration: the full lineage census still
costs ~1.0 s, but that cost is now entirely the outer scan over 10,508 raw_turn rows
(idx_memories_raw_turn_parents is btree(id) WHERE memory_type='raw_turn', so ordering
by created_at forces ~5,000 heap fetches). The per-turn lineage subquery itself is
0.16 ms. A (memory_type, created_at DESC) index would fix the census; that is a
separate change with its own justification.
"""
from alembic import op


revision = 'a3_parent_memory_ids_gin'
down_revision = 'cprecall_default_agent_id'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_memories_parent_memory_ids
    ON memory_service.memories
    USING gin ((metadata -> 'parent_memory_ids') jsonb_path_ops);
    """)


def downgrade():
    op.execute("""
    DROP INDEX IF EXISTS memory_service.idx_memories_parent_memory_ids;
    """)
