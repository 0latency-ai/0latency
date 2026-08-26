#!/usr/bin/env python3
"""
The query-independence invariant for the cross-agent scorer.

Measured on 2026-08-26: 104 of 134 sub-day rows cleared the 0.4 selection gate
with similarity forced to ZERO. When the query-independent terms can reach the
gate on their own, selection stops being a relevance decision -- the same rows
are returned regardless of what was asked, and the similarity term is decoration
on a write-date filter.

That property is not a consequence of any particular weight setting, so it
survives tuning and has to be asserted directly:

    max over all rows of (every term that does not read the query)
        must be strictly below the selection gate

Only `similarity` reads the query. `recency`, `importance` and `access` are
functions of the row alone, so a row can carry all three at ceiling while being
completely unrelated to the question.

Weights and half-life are read from the PRODUCTION _load_agent_config, and the
gate from the PRODUCTION CROSS_AGENT_L0_THRESHOLD, so a future rebalance that
walks back into this trap fails here rather than shipping.
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
from recall import (_load_agent_config, _cross_agent_recency,
                    CROSS_AGENT_L0_THRESHOLD)

THOMAS = "44c3080d-c196-407d-a606-4ea9f62ba0fc"


def query_independent_ceiling(cfg):
    """Largest composite a row can reach without matching the query at all.

    Ceilings are taken from the production computations rather than assumed:

      recency    _cross_agent_recency is monotone non-increasing in age, so its
                 supremum over the valid domain is at age zero.
      importance min(importance * (1 + 0.1*min(reinforcement,5)), 1.0) -> 1.0
      access     min(access_count / 10, 1.0)                           -> 1.0
    """
    hl = cfg["recency_half_life_days"]
    return (cfg["recency_weight"] * _cross_agent_recency(0.0, hl)
            + cfg["importance_weight"] * 1.0
            + cfg["access_weight"] * 1.0)


class TestCeilingComputationIsSound(unittest.TestCase):
    """Prove the checker itself works, so a red result below means a real defect."""

    def test_recency_ceiling_is_at_age_zero(self):
        for hl in (0.5, 3, 14, 30):
            top = _cross_agent_recency(0.0, hl)
            d = 0.0
            while d <= 60.0:
                self.assertLessEqual(_cross_agent_recency(d, hl), top + 1e-12)
                d += 0.01

    def test_checker_passes_a_safe_configuration(self):
        """A config whose query-independent mass is small must pass."""
        safe = {"recency_weight": 0.10, "semantic_weight": 0.65,
                "importance_weight": 0.10, "access_weight": 0.05,
                "recency_half_life_days": 30}
        self.assertLess(query_independent_ceiling(safe), CROSS_AGENT_L0_THRESHOLD)

    def test_checker_rejects_an_unsafe_configuration(self):
        """And one whose query-independent mass reaches the gate must fail."""
        unsafe = {"recency_weight": 0.35, "semantic_weight": 0.40,
                  "importance_weight": 0.15, "access_weight": 0.10,
                  "recency_half_life_days": 3}
        self.assertGreaterEqual(query_independent_ceiling(unsafe),
                                CROSS_AGENT_L0_THRESHOLD)

    def test_similarity_is_the_only_query_dependent_term(self):
        """Guards the premise. If a query-reading term is added to the scorer,
        this list and the ceiling above must be revisited."""
        import inspect
        src = inspect.getsource(recall.recall_cross_agent)
        body = src[src.index("for c in candidates:"):src.index("scored.append")]
        for term in ("semantic_weight * semantic_sim", "recency_weight * recency",
                     "importance_weight * importance", "access_weight * access_freq"):
            self.assertIn(term, " ".join(body.split()),
                          "cross-agent composite changed shape; revisit the "
                          "query-independent ceiling")


class TestQueryIndependentCeiling(unittest.TestCase):
    """The invariant, against live configuration.

    NOTE: test_code_fallback_config is EXPECTED TO FAIL on the current tree.
    It documents a live defect (0.600 ceiling against a 0.400 gate) and is
    deliberately not neutralised -- see the commit message. Do not mark it
    expectedFailure; that would turn it green and hide exactly what it exists
    to surface.
    """

    def _assert_invariant(self, cfg, label):
        ceiling = query_independent_ceiling(cfg)
        self.assertLess(
            ceiling, CROSS_AGENT_L0_THRESHOLD,
            f"\n  {label}: a row can reach {ceiling:.4f} of composite without "
            f"matching the query at all, against a selection gate of "
            f"{CROSS_AGENT_L0_THRESHOLD:.4f}.\n"
            f"  rec={cfg['recency_weight']}*{_cross_agent_recency(0.0, cfg['recency_half_life_days']):.4f} "
            f"imp={cfg['importance_weight']}*1.0 acc={cfg['access_weight']}*1.0\n"
            f"  Selection is therefore not a relevance decision for such rows.")

    def test_code_fallback_config(self):
        """The hardcoded fallbacks every unconfigured agent runs on."""
        cfg = {"recency_weight": 0.35, "semantic_weight": 0.4,
               "importance_weight": 0.15, "access_weight": 0.1,
               "recency_half_life_days": 3}
        self._assert_invariant(cfg, "code fallbacks (_load_agent_config)")

    def test_user_justin_live_config(self):
        cfg = _load_agent_config("user-justin", tenant_id=THOMAS)
        self._assert_invariant(cfg, "user-justin @ tenant thomas")


if __name__ == "__main__":
    unittest.main(verbosity=2)
