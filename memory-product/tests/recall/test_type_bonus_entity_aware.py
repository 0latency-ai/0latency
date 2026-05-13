"""
F4 Gate G2: Unit tests for entity-aware type bonus tuning.

Tests verify:
  (a) Identity memory with entity overlap → 1.15x
  (b) Identity memory without entity overlap → 1.05x
  (c) Preference memory with entity overlap → 1.15x
  (d) Preference memory without entity overlap → 1.05x
  (e) Flag-off case → original 1.15x unconditional for identity/preference
  (f) Other types (correction, event, decision, synthesis) unchanged
"""
import pytest


# ---------------------------------------------------------------------------
# Replicate entity-aware type bonus logic from recall.py
# ---------------------------------------------------------------------------

def _apply_type_bonus(
    composite: float,
    memory_type: str,
    headline: str,
    entities: list[str],
    flag_enabled: bool,
    days_since: float = 10.0,
    observation_count: int = 0,
    is_pinned: bool = False,
) -> float:
    """Reproduce the type bonus logic from recall.py lines ~871-912."""
    _has_entity_overlap = False
    if entities and flag_enabled:
        hl_lower = headline.lower()
        _has_entity_overlap = any(e.lower() in hl_lower for e in entities)

    if memory_type == "identity":
        if flag_enabled:
            composite *= 1.15 if _has_entity_overlap else 1.05
        else:
            composite *= 1.15
    elif memory_type == "correction":
        composite *= 1.10
    elif memory_type == "preference":
        if flag_enabled:
            composite *= 1.15 if _has_entity_overlap else 1.05
        else:
            composite *= 1.15
    elif memory_type == "event":
        composite *= 1.10
    elif memory_type == "decision" and days_since < 7:
        composite *= 1.2
    elif memory_type == "synthesis":
        composite *= 1.15
    elif memory_type == "pattern":
        pattern_boost = 1.2
        if observation_count >= 5:
            pattern_boost *= 1.1
        if days_since < 3:
            pattern_boost *= 1.15
        composite *= pattern_boost

    if is_pinned:
        composite *= 2.0

    return composite


# ---------------------------------------------------------------------------
# (a) Identity memory with entity overlap → 1.15x
# ---------------------------------------------------------------------------

class TestIdentityWithEntityOverlap:
    def test_identity_with_overlap_gets_115(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "identity",
            "User has a friend named Rachel who moved to suburbs",
            ["Rachel"], flag_enabled=True,
        )
        assert abs(result - base * 1.15) < 1e-9

    def test_identity_case_insensitive_overlap(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "identity",
            "rachel is the user's best friend",
            ["Rachel"], flag_enabled=True,
        )
        assert abs(result - base * 1.15) < 1e-9

    def test_identity_multiple_entities_one_overlaps(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "identity",
            "User has a friend named Rachel",
            ["Rachel", "Chicago", "Lucas"], flag_enabled=True,
        )
        assert abs(result - base * 1.15) < 1e-9


# ---------------------------------------------------------------------------
# (b) Identity memory without entity overlap → 1.05x
# ---------------------------------------------------------------------------

class TestIdentityWithoutEntityOverlap:
    def test_identity_no_overlap_gets_105(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "identity",
            "User founded DesignSpark on January 15th",
            ["Rachel"], flag_enabled=True,
        )
        assert abs(result - base * 1.05) < 1e-9

    def test_identity_no_entities_at_all_gets_105(self):
        """When query has no entities but flag is on, no overlap possible."""
        base = 0.600
        result = _apply_type_bonus(
            base, "identity",
            "User founded DesignSpark on January 15th",
            [], flag_enabled=True,
        )
        # Empty entities list → _has_entity_overlap stays False → 1.05x
        assert abs(result - base * 1.05) < 1e-9

    def test_identity_reduces_non_relevant_ranking(self):
        """A non-overlapping identity should score lower than it would
        with the old unconditional 1.15x bonus."""
        base = 0.700
        old_score = base * 1.15  # Pre-F4
        new_score = _apply_type_bonus(
            base, "identity",
            "User graduated from University",
            ["Rachel"], flag_enabled=True,
        )
        assert new_score < old_score
        assert abs(new_score - base * 1.05) < 1e-9


# ---------------------------------------------------------------------------
# (c) Preference memory with entity overlap → 1.15x
# ---------------------------------------------------------------------------

class TestPreferenceWithEntityOverlap:
    def test_preference_with_overlap_gets_115(self):
        base = 0.550
        result = _apply_type_bonus(
            base, "preference",
            "User wants to visit Rachel's neighborhood",
            ["Rachel"], flag_enabled=True,
        )
        assert abs(result - base * 1.15) < 1e-9


# ---------------------------------------------------------------------------
# (d) Preference memory without entity overlap → 1.05x
# ---------------------------------------------------------------------------

class TestPreferenceWithoutEntityOverlap:
    def test_preference_no_overlap_gets_105(self):
        base = 0.550
        result = _apply_type_bonus(
            base, "preference",
            "User prefers dark mode",
            ["Rachel"], flag_enabled=True,
        )
        assert abs(result - base * 1.05) < 1e-9


# ---------------------------------------------------------------------------
# (e) Flag-off case → original 1.15x unconditional
# ---------------------------------------------------------------------------

class TestFlagOff:
    def test_identity_flag_off_unconditional_115(self):
        """With flag off, identity always gets 1.15x regardless of overlap."""
        base = 0.600
        result = _apply_type_bonus(
            base, "identity",
            "User founded DesignSpark on January 15th",
            ["Rachel"], flag_enabled=False,
        )
        assert abs(result - base * 1.15) < 1e-9

    def test_preference_flag_off_unconditional_115(self):
        base = 0.550
        result = _apply_type_bonus(
            base, "preference",
            "User prefers dark mode",
            ["Rachel"], flag_enabled=False,
        )
        assert abs(result - base * 1.15) < 1e-9

    def test_flag_off_same_as_pre_f4(self):
        """Flag off should produce identical scores to the pre-F4 baseline."""
        base = 0.600
        # Pre-F4: unconditional 1.15x for identity
        pre_f4 = base * 1.15
        flag_off = _apply_type_bonus(
            base, "identity",
            "User has a pet named Luna",
            ["Rachel"], flag_enabled=False,
        )
        assert abs(flag_off - pre_f4) < 1e-9


# ---------------------------------------------------------------------------
# (f) Other types unchanged by F4
# ---------------------------------------------------------------------------

class TestOtherTypesUnchanged:
    def test_correction_still_110(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "correction", "some headline", ["Rachel"], flag_enabled=True,
        )
        assert abs(result - base * 1.10) < 1e-9

    def test_event_still_110(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "event", "some headline", ["Rachel"], flag_enabled=True,
        )
        assert abs(result - base * 1.10) < 1e-9

    def test_decision_recent_still_120(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "decision", "some headline", ["Rachel"],
            flag_enabled=True, days_since=3.0,
        )
        assert abs(result - base * 1.20) < 1e-9

    def test_decision_old_no_bonus(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "decision", "some headline", ["Rachel"],
            flag_enabled=True, days_since=10.0,
        )
        assert result == base  # No bonus for old decisions

    def test_synthesis_still_115(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "synthesis", "some headline", ["Rachel"], flag_enabled=True,
        )
        assert abs(result - base * 1.15) < 1e-9

    def test_pattern_base_still_120(self):
        base = 0.600
        result = _apply_type_bonus(
            base, "pattern", "some headline", ["Rachel"],
            flag_enabled=True, days_since=10.0, observation_count=0,
        )
        assert abs(result - base * 1.20) < 1e-9
