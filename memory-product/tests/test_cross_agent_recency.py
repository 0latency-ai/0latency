#!/usr/bin/env python3
"""
Unit tests for the cross-agent recency signal.

Every test imports and calls the PRODUCTION _cross_agent_recency from
src/recall.py. Nothing here re-implements the recency curve. A local mirror is
precisely how the Q22 tests stayed green for three months while the production
path was unfixed, so the assertions below are written against the real function
and will go red if it is changed underneath them.
"""
import math
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
from recall import _cross_agent_recency

HALF_LIVES = (0.5, 3.0, 14.0, 30.0)
GATE = 0.4
RECENCY_WEIGHT = 0.35


class TestContinuityAtOneDay(unittest.TestCase):
    """The 0.4169 composite cliff at exactly one day must be gone."""

    def test_continuous_across_the_one_day_boundary(self):
        """Left and right limits at days_since == 1 must agree."""
        for hl in HALF_LIVES:
            for eps in (1e-6, 1e-9, 1e-12):
                lo = _cross_agent_recency(1.0 - eps, hl)
                hi = _cross_agent_recency(1.0 + eps, hl)
                self.assertAlmostEqual(
                    lo, hi, places=5,
                    msg=f"discontinuity at 1 day (half_life={hl}, eps={eps}): "
                        f"{lo} vs {hi}, jump={abs(lo - hi)}")

    def test_boundary_value_is_the_plain_decay(self):
        """At the boundary the taper has reached 1.0, so it is pure decay."""
        for hl in HALF_LIVES:
            self.assertAlmostEqual(_cross_agent_recency(1.0, hl),
                                   math.exp(-0.693 / hl), places=9)

    def test_composite_jump_at_boundary_is_below_one_percent_of_the_gate(self):
        """The regression under test: the jump used to exceed the gate itself."""
        for hl in HALF_LIVES:
            jump = abs(_cross_agent_recency(1.0 - 1e-9, hl)
                       - _cross_agent_recency(1.0 + 1e-9, hl)) * RECENCY_WEIGHT
            self.assertLess(jump, GATE * 0.01,
                            f"composite jump {jump} at half_life={hl}")

    def test_no_discontinuity_anywhere_on_the_curve(self):
        """Scan the whole domain, not just the known boundary."""
        for hl in HALF_LIVES:
            step = 0.001
            prev = _cross_agent_recency(0.0, hl)
            d = step
            while d <= 40.0:
                cur = _cross_agent_recency(d, hl)
                self.assertLess(abs(cur - prev), 0.01,
                                f"jump of {abs(cur - prev)} between "
                                f"{d - step} and {d} (half_life={hl})")
                prev = cur
                d += step


class TestBounded(unittest.TestCase):
    """Recency must sit on the same [0,1] scale as every other signal."""

    def test_never_exceeds_one(self):
        for hl in HALF_LIVES:
            d = 0.0
            while d <= 40.0:
                self.assertLessEqual(_cross_agent_recency(d, hl), 1.0,
                                     f"recency > 1 at {d} days (half_life={hl})")
                d += 0.005

    def test_never_negative(self):
        for hl in HALF_LIVES:
            for d in (0.0, 0.5, 1.0, 7.0, 30.0, 99.0, 1000.0):
                self.assertGreaterEqual(_cross_agent_recency(d, hl), 0.0)

    def test_recency_alone_cannot_clear_the_selection_gate(self):
        """The core defect: a minutes-old row scored 0.875 against a 0.4 gate."""
        for hl in HALF_LIVES:
            for d in (0.0, 0.001, 0.01, 0.1, 0.5, 0.99):
                contribution = RECENCY_WEIGHT * _cross_agent_recency(d, hl)
                self.assertLess(
                    contribution, GATE,
                    f"recency alone contributes {contribution} at {d} days "
                    f"(half_life={hl}), which clears the {GATE} gate without "
                    f"any relevance")

    def test_monotone_non_increasing(self):
        for hl in HALF_LIVES:
            d = 0.0
            prev = _cross_agent_recency(0.0, hl)
            while d <= 40.0:
                cur = _cross_agent_recency(d, hl)
                self.assertLessEqual(cur, prev + 1e-12,
                                     f"recency increased with age at {d} "
                                     f"(half_life={hl})")
                prev = cur
                d += 0.005


class TestBoostIsConfigurable(unittest.TestCase):
    """The boost peak is a tunable, and 1.0 means plain decay."""

    def test_boost_max_of_one_is_plain_decay(self):
        orig = recall.CROSS_AGENT_SUBDAY_BOOST_MAX
        recall.CROSS_AGENT_SUBDAY_BOOST_MAX = 1.0
        try:
            for hl in HALF_LIVES:
                for d in (0.0, 0.25, 0.5, 0.75, 0.999):
                    self.assertAlmostEqual(_cross_agent_recency(d, hl),
                                           math.exp(-0.693 * d / hl), places=9)
        finally:
            recall.CROSS_AGENT_SUBDAY_BOOST_MAX = orig

    def test_still_continuous_at_other_boost_settings(self):
        orig = recall.CROSS_AGENT_SUBDAY_BOOST_MAX
        try:
            for bm in (1.0, 1.5, 2.5, 10.0):
                recall.CROSS_AGENT_SUBDAY_BOOST_MAX = bm
                for hl in HALF_LIVES:
                    lo = _cross_agent_recency(1.0 - 1e-9, hl)
                    hi = _cross_agent_recency(1.0 + 1e-9, hl)
                    self.assertAlmostEqual(lo, hi, places=5,
                                           msg=f"boost_max={bm} half_life={hl}")
        finally:
            recall.CROSS_AGENT_SUBDAY_BOOST_MAX = orig



class TestNegativeAgeClamp(unittest.TestCase):
    """Nothing is more recent than now — cross-agent parity with 8d8785c."""

    def test_future_rows_do_not_exceed_a_present_row(self):
        for hl in HALF_LIVES:
            at_now = _cross_agent_recency(0.0, hl)
            for ahead in (1.9, 5.9, 34.9, 79.9, 111.9, 126.9):
                self.assertLessEqual(
                    _cross_agent_recency(-ahead, hl), at_now,
                    f"a row {ahead} days in the future outscored a row written "
                    f"now (half_life={hl})")

    def test_negative_age_is_still_bounded(self):
        for hl in HALF_LIVES:
            for ahead in (0.5, 10.0, 100.0, 1000.0, 100000.0):
                r = _cross_agent_recency(-ahead, hl)
                self.assertLessEqual(r, 1.0)
                self.assertGreaterEqual(r, 0.0)

    def test_far_future_does_not_raise_overflow(self):
        """Unclamped, exp() overflows past roughly -3000 days and the caller
        turns that into a silently dropped candidate."""
        for hl in HALF_LIVES:
            try:
                _cross_agent_recency(-365 * 600, hl)
            except OverflowError:
                self.fail(f"OverflowError at half_life={hl}; days_since is not "
                          f"floored at zero")

    def test_clamp_matches_the_primary_path_treatment(self):
        """recall_fixed floors days_since before exp(); so must this."""
        for hl in HALF_LIVES:
            self.assertAlmostEqual(_cross_agent_recency(-50.0, hl),
                                   _cross_agent_recency(0.0, hl), places=12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
