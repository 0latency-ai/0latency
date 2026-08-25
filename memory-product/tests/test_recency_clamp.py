#!/usr/bin/env python3
"""
Unit tests for q22-recency-clamp: days_since floor, IQR spread, feature flag.
"""
import math
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Setup path (same pattern as test_scoring_invariants.py)
sys.path.insert(0, "/root/.openclaw/workspace/memory-product/src")
sys.path.insert(0, "/root/.openclaw/workspace/memory-product")

# Load env
env_path = Path("/root/.openclaw/workspace/memory-product/.env")
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = val

# Force local embeddings for testing
os.environ["RECALL_USE_VOYAGE"] = "false"
os.environ["RECALL_KEYWORD_MATCH_ENABLED"] = "false"
os.environ["RECALL_ENTITY_STRATEGY_ENABLED"] = "false"
os.environ["RECALL_TYPE_BONUS_ENTITY_AWARE"] = "false"

from recall import _compute_signal_spread_iqr, _compute_signal_spread, _compute_adaptive_weights


class TestRecencyClamp(unittest.TestCase):
    """Test the recency clamp computation in isolation (pure math, no DB)."""

    HALF_LIFE = 30.0

    def _compute_recency(self, days_since, clamp_enabled=True):
        """Mirror the recall.py recency computation with optional clamp."""
        if clamp_enabled:
            days_since = max(0.0, days_since)
        return math.exp(-0.693 * days_since / max(self.HALF_LIFE, 0.01))

    def test_future_30d_clamped(self):
        """event_at = now+30d -> recency == 1.0 (clamped), NOT ~4.64"""
        result = self._compute_recency(-30.0, clamp_enabled=True)
        self.assertAlmostEqual(result, 1.0, places=6,
                               msg="Future event_at must clamp to recency=1.0")

    def test_now_recency(self):
        """event_at = now -> recency == 1.0"""
        result = self._compute_recency(0.0, clamp_enabled=True)
        self.assertAlmostEqual(result, 1.0, places=6)

    def test_7d_ago_unchanged(self):
        """event_at = 7d ago -> recency unchanged from old behavior"""
        result_clamped = self._compute_recency(7.0, clamp_enabled=True)
        result_unclamped = self._compute_recency(7.0, clamp_enabled=False)
        self.assertAlmostEqual(result_clamped, result_unclamped, places=10,
                               msg="Past dates must be untouched by clamp")
        self.assertAlmostEqual(result_clamped, math.exp(-0.693 * 7 / 30), places=4)

    def test_30d_ago_unchanged(self):
        """event_at = 30d ago -> recency ~ 0.5 (half-life, unchanged)"""
        result_clamped = self._compute_recency(30.0, clamp_enabled=True)
        result_unclamped = self._compute_recency(30.0, clamp_enabled=False)
        self.assertAlmostEqual(result_clamped, result_unclamped, places=10,
                               msg="Past dates must be untouched by clamp")
        self.assertAlmostEqual(result_clamped, 0.5, places=2)

    def test_year_2600_clamped_no_overflow(self):
        """event_at = year 2600 -> recency == 1.0, no OverflowError."""
        result = self._compute_recency(-209710.0, clamp_enabled=True)
        self.assertAlmostEqual(result, 1.0, places=6,
                               msg="Year 2600 event_at must clamp to 1.0")

    def test_year_2600_unclamped_overflows(self):
        """Flag OFF -> year-2600 input still raises OverflowError."""
        with self.assertRaises(OverflowError):
            self._compute_recency(-209710.0, clamp_enabled=False)


class TestIQRSpread(unittest.TestCase):
    """Test the IQR spread function."""

    def test_iqr_basic(self):
        """IQR of a uniform distribution."""
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        result = _compute_signal_spread_iqr(scores)
        # Q1 = scores[2] = 0.3, Q3 = scores[6] = 0.7, IQR = 0.4
        self.assertAlmostEqual(result, 0.4, places=4)

    def test_iqr_empty(self):
        """IQR of <2 elements returns 0."""
        self.assertEqual(_compute_signal_spread_iqr([]), 0.0)
        self.assertEqual(_compute_signal_spread_iqr([0.5]), 0.0)

    def test_iqr_robust_to_outliers(self):
        """IQR ignores extreme outliers that std-dev would amplify."""
        normal = [0.45 + 0.01 * i for i in range(47)]
        outliers = [4.0, 4.0, 4.0]
        scores = normal + outliers
        iqr = _compute_signal_spread_iqr(scores)
        std = _compute_signal_spread(scores)
        self.assertLess(iqr, std,
                        msg="IQR must be more robust to outliers than std-dev")
        self.assertGreater(iqr, 0.0)
        self.assertLess(iqr, 1.0)


class TestAdaptiveSpreadWithOutliers(unittest.TestCase):
    """Gate G3: adaptive spread function with future-dated outliers."""

    def test_adaptive_spread_with_future_outliers(self):
        """3 future-dated outliers among 50 normal values -- no exception, finite float."""
        normal_recencies = [math.exp(-0.693 * d / 30.0) for d in range(50)]
        outlier_recencies = [1.0, 1.0, 1.0]
        all_recencies = normal_recencies + outlier_recencies
        semantic_scores = [0.7 + 0.005 * i for i in range(53)]
        result = _compute_adaptive_weights(
            all_recencies, semantic_scores,
            base_semantic=0.55, base_recency=0.15,
            base_importance=0.20, base_access=0.10,
        )
        self.assertEqual(len(result), 9)
        for i, val in enumerate(result):
            self.assertTrue(math.isfinite(val),
                            f"Adaptive weight element {i} is not finite: {val}")



class TestClampIsWired(unittest.TestCase):
    """Regression guard for the failure that lost this fix once already.

    The math tests above run against a local mirror of the recency computation,
    so they pass whether or not recall_fixed actually applies the clamp.
    q22-recency-clamp was reverted out of the tree while those tests would still
    have gone green. These assert the wiring itself.
    """

    def test_flag_defaults_on(self):
        import recall
        self.assertTrue(recall.RECENCY_CLAMP_ENABLED,
                        msg="RECENCY_CLAMP_ENABLED must default true")

    def test_recall_fixed_clamps_days_since(self):
        """recall_fixed must floor days_since before exp(), not just the mirror."""
        import inspect, recall
        src = inspect.getsource(recall.recall_fixed)
        self.assertIn("max(0.0, days_since)", src,
                      msg="recall_fixed lost the days_since floor [q22-recency-clamp]")

    def test_adaptive_uses_iqr_for_recency(self):
        """The recency spread input must be the outlier-robust metric."""
        import inspect, recall
        src = inspect.getsource(recall._compute_adaptive_weights)
        self.assertIn("_compute_signal_spread_iqr(recency_scores)", src,
                      msg="adaptive spread reverted to std-dev [q22-recency-clamp]")

    def test_outliers_do_not_saturate_recency_informative(self):
        """The protective property, behaviourally.

        Models the real store: user-justin is 99.28% >= 30 days old, so every
        normal recency is ~0 and recency carries no query-discriminative signal.
        Three future-dated event_at rows then produce recency >> 1 (the values
        below are the ones measured in prod on 2026-08-25).

        Under std-dev spread those outliers inflate the spread enough to drive
        recency_informative to ~1.0, so Phase 1 redistributes nothing and the
        outlier dominates ranking. Under IQR the spread stays ~0, recency is
        correctly judged degenerate, and its weight is redistributed to
        semantic. This asserts the contrast, which is the whole point of the
        IQR swap in q22-recency-clamp.
        """
        import recall

        # 99-day-old store: recency is identically ~0 across the board
        normal = [math.exp(-0.693 * d / 3.0) for d in range(95, 135)]
        scores = normal + [2.05e11, 6.4e9, 1.3e8]
        semantic = [0.5 + 0.004 * i for i in range(len(scores))]

        self.assertLess(_compute_signal_spread_iqr(scores),
                        _compute_signal_spread(scores),
                        msg="IQR must be more robust than std-dev here")

        def adaptive():
            return _compute_adaptive_weights(
                scores, semantic,
                base_semantic=0.40, base_recency=0.35,
                base_importance=0.15, base_access=0.10,
            )

        # IQR path (flag on, the shipped behaviour)
        self.assertTrue(recall.RECENCY_CLAMP_ENABLED)
        (_, rec_w_iqr, _, _, _, _, _, rec_info_iqr, _) = adaptive()

        # std-dev path (flag off) — the pre-fix behaviour, for contrast
        recall.RECENCY_CLAMP_ENABLED = False
        try:
            (_, rec_w_std, _, _, _, _, _, rec_info_std, _) = adaptive()
        finally:
            recall.RECENCY_CLAMP_ENABLED = True

        self.assertGreater(rec_info_std, 0.99,
                           msg="std-dev should saturate on these outliers")
        self.assertLess(rec_info_iqr, 0.1,
                        msg="IQR must not let outliers fake informative recency")
        self.assertLess(rec_w_iqr, 0.35 * 0.1,
                        msg="degenerate recency weight was not redistributed")
        self.assertGreater(rec_w_std, rec_w_iqr,
                           msg="the fix must reduce recency weight, not raise it")


if __name__ == "__main__":
    unittest.main()
