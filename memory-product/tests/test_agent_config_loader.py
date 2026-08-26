#!/usr/bin/env python3
"""
Unit tests for the agent_config loader: explicit-zero handling.

Every test here imports and calls the PRODUCTION _load_agent_config. The DB
round-trip is stubbed at _db_execute_rows -- the seam below the function under
test -- so the loader's own coercion logic is what runs. Nothing is re-implemented
locally; a mirror of the coercion would pass even if production still used
truthiness, which is the failure mode these tests exist to prevent.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, "/root/.openclaw/workspace/memory-product/src")
sys.path.insert(0, "/root/.openclaw/workspace/memory-product")

env_path = Path("/root/.openclaw/workspace/memory-product/.env")
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = val

os.environ["RECALL_USE_VOYAGE"] = "false"

import recall
from recall import _load_agent_config


class _StubRows:
    """Capture the SQL and params the loader issues, and return a canned row."""

    def __init__(self, row):
        self.row = row
        self.query = None
        self.params = None
        self.tenant_id = None

    def __call__(self, query, params=None, tenant_id=None, fetch_results=True):
        self.query = query
        self.params = params
        self.tenant_id = tenant_id
        return [self.row] if self.row is not None else []


def _row(recency=0.35, semantic=0.4, importance=0.15, access=0.1,
         half_life=3, budget=4000):
    return (budget, recency, semantic, importance, access, half_life, "{}", "{}")


class TestConfiguredZero(unittest.TestCase):
    """A deliberately configured 0.0 must survive the loader as 0.0."""

    def _load_with(self, row):
        stub = _StubRows(row)
        orig = recall._db_execute_rows
        recall._db_execute_rows = stub
        try:
            return _load_agent_config("user-justin", tenant_id="t"), stub
        finally:
            recall._db_execute_rows = orig

    def test_configured_zero_recency_yields_zero(self):
        """The headline case: recency_weight=0.0 must not become 0.35."""
        cfg, _ = self._load_with(_row(recency=0.0))
        self.assertEqual(cfg["recency_weight"], 0.0,
                         "configured recency_weight=0.0 was silently replaced by the "
                         "default -- recency cannot be disabled through config")

    def test_configured_zero_every_numeric_weight(self):
        """Every numeric column, not just recency, must honour an explicit 0."""
        cfg, _ = self._load_with(_row(recency=0.0, semantic=0.0, importance=0.0,
                                      access=0.0, half_life=0, budget=0))
        self.assertEqual(cfg["recency_weight"], 0.0)
        self.assertEqual(cfg["semantic_weight"], 0.0)
        self.assertEqual(cfg["importance_weight"], 0.0)
        self.assertEqual(cfg["access_weight"], 0.0)
        self.assertEqual(cfg["recency_half_life_days"], 0)
        self.assertEqual(cfg["context_budget"], 0)

    def test_null_still_falls_back_to_default(self):
        """NULL is absence of configuration and must still take the default."""
        cfg, _ = self._load_with(_row(recency=None, semantic=None, importance=None,
                                      access=None, half_life=None, budget=None))
        self.assertEqual(cfg["recency_weight"], 0.35)
        self.assertEqual(cfg["semantic_weight"], 0.4)
        self.assertEqual(cfg["importance_weight"], 0.15)
        self.assertEqual(cfg["access_weight"], 0.1)
        self.assertEqual(cfg["recency_half_life_days"], 3)
        self.assertEqual(cfg["context_budget"], 4000)

    def test_nonzero_values_pass_through(self):
        cfg, _ = self._load_with(_row(recency=0.2, semantic=0.6, half_life=14))
        self.assertAlmostEqual(cfg["recency_weight"], 0.2)
        self.assertAlmostEqual(cfg["semantic_weight"], 0.6)
        self.assertEqual(cfg["recency_half_life_days"], 14)


if __name__ == "__main__":
    unittest.main(verbosity=2)
