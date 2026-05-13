"""
F2 Gate G2: Unit tests for keyword-match factor in composite ranking.

Tests verify:
  (a) keyword match adds expected 0.15 bonus to composite score
  (b) no keyword match adds zero bonus
  (c) feature flag off = identical behaviour to pre-F2 weights
"""
import math
import re
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers that replicate the scoring logic from recall.py
# ---------------------------------------------------------------------------

# Default weights from _load_agent_config
DEFAULT_WEIGHTS = {
    "semantic_weight": 0.4,
    "recency_weight": 0.35,
    "importance_weight": 0.15,
    "access_weight": 0.1,
}

KEYWORD_MATCH_WEIGHT = 0.15  # Added when flag is on
RECENCY_REDUCTION = 0.15     # Taken from recency when flag is on
HALF_LIFE_DAYS = 3.0


def _compute_composite(
    semantic_sim: float,
    days_since: float,
    importance_raw: float,
    reinforcement_count: int,
    access_count: int,
    keyword_matched: bool,
    flag_enabled: bool,
    half_life_days: float = HALF_LIFE_DAYS,
) -> float:
    """Reproduce the composite formula from recall.py lines ~757-780."""
    w = dict(DEFAULT_WEIGHTS)
    kw_weight = 0.0

    if flag_enabled:
        kw_weight = KEYWORD_MATCH_WEIGHT
        w["recency_weight"] = max(w["recency_weight"] - RECENCY_REDUCTION, 0.05)

    recency = math.exp(-0.693 * days_since / max(half_life_days, 0.01))
    importance = importance_raw * (1 + 0.1 * min(reinforcement_count, 5))
    importance = min(importance, 1.0)
    access_freq = min(access_count / 10, 1.0)
    kw_score = 1.0 if keyword_matched else 0.0

    composite = (
        w["semantic_weight"] * semantic_sim
        + w["recency_weight"] * recency
        + w["importance_weight"] * importance
        + w["access_weight"] * access_freq
        + kw_weight * kw_score
    )
    return composite


# ---------------------------------------------------------------------------
# Keyword extraction helper (mirrors the logic in recall.py ~line 726-737)
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    'this', 'that', 'with', 'from', 'what', 'when', 'where', 'which', 'about',
    'have', 'been', 'will', 'would', 'could', 'should', 'their', 'there',
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her',
    'was', 'one', 'our', 'out', 'did', 'does', 'how', 'who', 'why',
    'after', 'before', 'into', 'than', 'then', 'also', 'just', 'very',
}


def _extract_keywords(query: str) -> str:
    """Replicate keyword extraction from recall.py."""
    words = re.findall(r'\b[a-zA-Z]{3,}\b', query[:2000].lower())
    filtered = [w for w in words if w not in _STOP_WORDS][:8]
    sanitized = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in filtered]
    sanitized = [w for w in sanitized if w]
    return ' OR '.join(sanitized) if sanitized else '__no_keywords__'


# ---------------------------------------------------------------------------
# (a) Keyword match adds expected bonus
# ---------------------------------------------------------------------------

class TestKeywordMatchBonus:
    """When RECALL_KEYWORD_MATCH_ENABLED=true and a candidate matches the
    keyword query, it should receive a 0.15 bonus in the composite score."""

    def test_keyword_match_adds_015_bonus(self):
        """Matched candidate scores exactly 0.15 higher than unmatched
        (all else equal)."""
        params = dict(
            semantic_sim=0.6,
            days_since=2.0,
            importance_raw=0.7,
            reinforcement_count=1,
            access_count=3,
            flag_enabled=True,
        )
        score_matched = _compute_composite(keyword_matched=True, **params)
        score_unmatched = _compute_composite(keyword_matched=False, **params)
        assert abs((score_matched - score_unmatched) - KEYWORD_MATCH_WEIGHT) < 1e-9

    def test_keyword_match_can_change_ranking(self):
        """A lower-similarity candidate WITH keyword match can outrank a
        higher-similarity candidate WITHOUT keyword match."""
        base = dict(
            days_since=2.0,
            importance_raw=0.7,
            reinforcement_count=1,
            access_count=3,
            flag_enabled=True,
        )
        # Higher semantic but no keyword match
        high_sim = _compute_composite(semantic_sim=0.7, keyword_matched=False, **base)
        # Lower semantic but keyword match
        low_sim_kw = _compute_composite(semantic_sim=0.55, keyword_matched=True, **base)
        # 0.15 bonus should overcome 0.15 * 0.4 = 0.06 semantic gap
        assert low_sim_kw > high_sim

    def test_recency_weight_reduced_when_flag_on(self):
        """When the flag is on, recency_weight should be 0.20 (not 0.35)."""
        # High-recency candidate should have less impact with flag on
        params = dict(
            semantic_sim=0.5,
            importance_raw=0.5,
            reinforcement_count=0,
            access_count=0,
            keyword_matched=False,
        )
        score_flag_off = _compute_composite(days_since=0.1, flag_enabled=False, **params)
        score_flag_on = _compute_composite(days_since=0.1, flag_enabled=True, **params)
        # Recency contribution is smaller with flag on (0.20 vs 0.35)
        # The difference comes from the recency component
        recency_val = math.exp(-0.693 * 0.1 / HALF_LIFE_DAYS)
        expected_diff = (0.35 - 0.20) * recency_val  # 0.15 * ~0.977 ≈ 0.147
        assert abs((score_flag_off - score_flag_on) - expected_diff) < 1e-9


# ---------------------------------------------------------------------------
# (b) No keyword match adds zero bonus
# ---------------------------------------------------------------------------

class TestNoKeywordMatchZeroBonus:
    """When a candidate does NOT match the keyword query, it gets zero bonus
    from the keyword_match_weight dimension."""

    def test_unmatched_kw_score_is_zero(self):
        """Unmatched candidate composite identical to baseline (no kw dimension)."""
        params = dict(
            semantic_sim=0.6,
            days_since=2.0,
            importance_raw=0.7,
            reinforcement_count=1,
            access_count=3,
        )
        score_unmatched = _compute_composite(keyword_matched=False, flag_enabled=True, **params)
        # Manually compute expected (with reduced recency_weight=0.20)
        recency = math.exp(-0.693 * 2.0 / HALF_LIFE_DAYS)
        importance = 0.7 * (1 + 0.1 * 1)  # 0.77
        access_freq = 3 / 10  # 0.3
        expected = (0.4 * 0.6) + (0.20 * recency) + (0.15 * importance) + (0.1 * 0.3) + (0.15 * 0.0)
        assert abs(score_unmatched - expected) < 1e-9

    def test_all_unmatched_preserves_original_ordering(self):
        """If no candidates match keywords, relative ordering should be the
        same as without the keyword dimension (just with reduced recency)."""
        base = dict(
            importance_raw=0.7,
            reinforcement_count=1,
            access_count=3,
            keyword_matched=False,
            flag_enabled=True,
        )
        # Two candidates differing only in semantic sim
        a = _compute_composite(semantic_sim=0.7, days_since=2.0, **base)
        b = _compute_composite(semantic_sim=0.5, days_since=2.0, **base)
        assert a > b  # Higher sim still wins when neither matches keywords


# ---------------------------------------------------------------------------
# (c) Feature flag off = identical to pre-F2 behaviour
# ---------------------------------------------------------------------------

class TestFeatureFlagOff:
    """When RECALL_KEYWORD_MATCH_ENABLED is false, the composite formula
    must produce identical scores to the pre-F2 baseline."""

    def test_weights_unchanged_when_flag_off(self):
        """With flag off, keyword_match_weight=0 and recency_weight=0.35."""
        params = dict(
            semantic_sim=0.6,
            days_since=2.0,
            importance_raw=0.7,
            reinforcement_count=1,
            access_count=3,
            keyword_matched=True,  # Even if "matched", bonus should be 0
            flag_enabled=False,
        )
        score = _compute_composite(**params)

        # Compute pre-F2 baseline manually (no keyword dimension)
        recency = math.exp(-0.693 * 2.0 / HALF_LIFE_DAYS)
        importance = 0.7 * (1 + 0.1 * 1)
        access_freq = 0.3
        baseline = (0.4 * 0.6) + (0.35 * recency) + (0.15 * importance) + (0.1 * access_freq)
        assert abs(score - baseline) < 1e-9

    def test_flag_off_ignores_keyword_match(self):
        """Matched and unmatched candidates score identically when flag is off."""
        params = dict(
            semantic_sim=0.6,
            days_since=2.0,
            importance_raw=0.7,
            reinforcement_count=1,
            access_count=3,
            flag_enabled=False,
        )
        score_matched = _compute_composite(keyword_matched=True, **params)
        score_unmatched = _compute_composite(keyword_matched=False, **params)
        assert score_matched == score_unmatched

    def test_flag_off_recency_weight_035(self):
        """Pre-F2 recency weight (0.35) used when flag is off."""
        # Same candidate scored with flag on vs off, no keyword match
        params = dict(
            semantic_sim=0.5,
            days_since=1.0,
            importance_raw=0.5,
            reinforcement_count=0,
            access_count=0,
            keyword_matched=False,
        )
        score_off = _compute_composite(flag_enabled=False, **params)
        score_on = _compute_composite(flag_enabled=True, **params)
        # Flag-on has lower recency_weight (0.20 vs 0.35), so score_off > score_on
        # for a recent memory with no keyword match
        assert score_off > score_on


# ---------------------------------------------------------------------------
# Keyword extraction tests
# ---------------------------------------------------------------------------

class TestKeywordExtraction:
    """Verify the keyword extraction logic that builds the tsquery."""

    def test_extracts_content_words(self):
        query = "Where did Rachel move to after her recent relocation?"
        result = _extract_keywords(query)
        # "rachel", "move", "recent", "relocation" survive stop-word filter
        assert "rachel" in result
        assert "move" in result
        assert "recent" in result
        assert "relocation" in result

    def test_removes_stop_words(self):
        query = "Where did Rachel move to after her recent relocation?"
        result = _extract_keywords(query)
        assert "where" not in result
        assert "did" not in result
        assert "after" not in result
        assert "her" not in result

    def test_joins_with_or(self):
        query = "Rachel moved to suburbs"
        result = _extract_keywords(query)
        assert " OR " in result

    def test_limits_to_8_keywords(self):
        query = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo"
        result = _extract_keywords(query)
        parts = result.split(" OR ")
        assert len(parts) <= 8

    def test_empty_after_stop_words_returns_fallback(self):
        query = "the and for are but not"
        result = _extract_keywords(query)
        assert result == "__no_keywords__"

    def test_short_words_filtered(self):
        """Words shorter than 3 characters are excluded by the regex."""
        query = "I am an ox"
        result = _extract_keywords(query)
        # None of these survive: "i"(1), "am"(2), "an"(2), "ox"(2)
        assert result == "__no_keywords__"
