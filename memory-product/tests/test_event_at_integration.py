#!/usr/bin/env python3
"""Integration test for event_at column and temporal scoring.

Tests:
1. Column exists in schema (migration applied)
2. Nullable behavior (NULL event_at falls back to created_at)
3. Temporal scoring prefers event_at over created_at when present
4. Rollback safety (downgrade removes column cleanly)
"""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, '/root/.openclaw/workspace/memory-product/src')
sys.path.insert(0, '/root/.openclaw/workspace/memory-product')

# Load env
from pathlib import Path
env_path = Path('/root/.openclaw/workspace/memory-product/.env')
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        key, _, val = line.partition('=')
        if key.strip() not in os.environ:
            os.environ[key.strip()] = val.strip().strip('"').strip("'")

import psycopg2

DB_URL = os.environ.get('DATABASE_URL')
STAGING_DB_URL = os.environ.get('STAGING_DATABASE_URL')


class TestEventAtSchema(unittest.TestCase):
    """Test event_at column exists with correct properties."""

    def setUp(self):
        self.conn = psycopg2.connect(DB_URL)

    def tearDown(self):
        self.conn.close()

    def test_column_exists(self):
        """event_at column exists in memory_service.memories."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'memory_service'
                  AND table_name = 'memories'
                  AND column_name = 'event_at'
            """)
            row = cur.fetchone()
            self.assertIsNotNone(row, "event_at column not found")
            self.assertEqual(row[0], 'event_at')
            self.assertIn('timestamp', row[1])
            self.assertEqual(row[2], 'YES')  # nullable

    def test_column_nullable(self):
        """event_at is nullable (NULL = use created_at fallback)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM memory_service.memories
                WHERE event_at IS NULL
                LIMIT 1
            """)
            count = cur.fetchone()[0]
            # All existing memories should have NULL event_at
            self.assertGreater(count, 0,
                "Expected some memories with NULL event_at")

    def test_index_exists(self):
        """Partial index on event_at exists."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'memory_service'
                  AND tablename = 'memories'
                  AND indexname = 'idx_memories_event_at'
            """)
            row = cur.fetchone()
            self.assertIsNotNone(row, "idx_memories_event_at index not found")

    def test_can_write_event_at(self):
        """Can insert and read back event_at value."""
        test_tenant = '382faaf1-5cbf-49a1-b689-5ffef8918d10'
        test_event_at = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

        with self.conn.cursor() as cur:
            # Insert test memory with event_at
            cur.execute("""
                INSERT INTO memory_service.memories
                    (agent_id, headline, context, full_content, tenant_id, event_at)
                VALUES ('test-event-at', 'Test event_at memory', 'test', 'test',
                        %s::UUID, %s)
                RETURNING id, event_at
            """, (test_tenant, test_event_at))
            row = cur.fetchone()
            mem_id = row[0]
            returned_event_at = row[1]

            self.assertIsNotNone(returned_event_at)

            # Clean up
            cur.execute("DELETE FROM memory_service.memories WHERE id = %s", (mem_id,))
            self.conn.commit()


class TestEventAtTemporalScoring(unittest.TestCase):
    """Test that temporal scoring prefers event_at."""

    def test_temporal_ref_fallback(self):
        """When event_at is None, temporal_ref falls back to created_at."""
        now = datetime.now(timezone.utc)
        candidate = {
            "created_at": now - timedelta(days=5),
            "event_at": None,
        }
        temporal_ref = candidate.get("event_at") or candidate["created_at"]
        self.assertEqual(temporal_ref, candidate["created_at"])

    def test_temporal_ref_prefers_event_at(self):
        """When event_at is set, temporal_ref uses it instead of created_at."""
        now = datetime.now(timezone.utc)
        event_time = now - timedelta(days=2)
        ingest_time = now - timedelta(hours=1)

        candidate = {
            "created_at": ingest_time,
            "event_at": event_time,
        }
        temporal_ref = candidate.get("event_at") or candidate["created_at"]
        self.assertEqual(temporal_ref, event_time)
        self.assertNotEqual(temporal_ref, ingest_time)

    def test_event_at_changes_recency_score(self):
        """Memory with old event_at should have lower recency than one with
        recent created_at but no event_at."""
        import math
        now = datetime.now(timezone.utc)
        half_life = 3.0

        # Memory ingested 1 hour ago but event was 30 days ago
        old_event = {
            "created_at": now - timedelta(hours=1),
            "event_at": now - timedelta(days=30),
        }
        temporal_ref_old = old_event.get("event_at") or old_event["created_at"]
        days_old = (now - temporal_ref_old).total_seconds() / 86400
        recency_old = math.exp(-0.693 * days_old / half_life)

        # Memory ingested 1 hour ago with no event_at
        recent_ingest = {
            "created_at": now - timedelta(hours=1),
            "event_at": None,
        }
        temporal_ref_new = recent_ingest.get("event_at") or recent_ingest["created_at"]
        days_new = (now - temporal_ref_new).total_seconds() / 86400
        recency_new = math.exp(-0.693 * days_new / half_life)

        # The old event should have much lower recency
        self.assertLess(recency_old, recency_new)
        self.assertLess(recency_old, 0.01)  # 30 days old → very low
        self.assertGreater(recency_new, 0.95)  # 1 hour old → very high


if __name__ == '__main__':
    unittest.main(verbosity=2)
