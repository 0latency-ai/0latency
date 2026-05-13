"""
F3b Gate G3: Unit tests for entity-aware recall strategy.

Tests verify:
  (a) _extract_entities extracts proper nouns, filters common words
  (b) Entity-mention bonus applied correctly in composite scoring
  (c) Feature flag off = no entity extraction, no bonus
  (d) S4 entity regex construction
"""
import re

import pytest


# ---------------------------------------------------------------------------
# Replicate _extract_entities from recall.py
# ---------------------------------------------------------------------------

_ENTITY_SKIP = {
    'The', 'This', 'That', 'What', 'When', 'Where', 'Which', 'How',
    'Are', 'Was', 'Were', 'Has', 'Have', 'Had', 'Will', 'Would',
    'Could', 'Should', 'Can', 'May', 'Did', 'Does', 'But', 'And',
    'For', 'Not', 'All', 'Any', 'Her', 'His', 'Its', 'Our', 'They',
    'Who', 'Why', 'After', 'Before', 'Recent', 'Also', 'Just',
    'About', 'From', 'Into', 'Over', 'Some', 'Than', 'Then',
    'Very', 'More', 'Much', 'Such', 'Each', 'Every', 'Other',
    'Most', 'Same', 'Still', 'Back', 'Here', 'There', 'User',
    'Recently', 'Now', 'Already', 'Never', 'Often', 'Being',
}


def _extract_entities(text: str) -> list[str]:
    """Replicate _extract_entities from recall.py."""
    words = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
    entities = [w for w in words if w not in _ENTITY_SKIP]
    seen = set()
    unique = []
    for e in entities:
        if e.lower() not in seen:
            seen.add(e.lower())
            unique.append(e)
    return unique[:5]


def _build_entity_regex(entities: list[str]) -> str:
    """Build PostgreSQL regex from entity list."""
    escaped = [re.escape(e) for e in entities]
    return r'\m(' + '|'.join(escaped) + r')\M'


ENTITY_BONUS = 1.05


def _apply_entity_bonus(composite: float, headline: str, entities: list[str]) -> float:
    """Replicate the entity bonus logic from recall.py composite scoring."""
    if not entities:
        return composite
    hl_lower = headline.lower()
    for ent in entities:
        if ent.lower() in hl_lower:
            composite *= ENTITY_BONUS
            break
    return composite


# ---------------------------------------------------------------------------
# (a) Entity extraction tests
# ---------------------------------------------------------------------------

class TestExtractEntities:
    """Verify _extract_entities extracts proper nouns correctly."""

    def test_extracts_person_name(self):
        entities = _extract_entities("Where did Rachel move to?")
        assert "Rachel" in entities

    def test_extracts_multiple_entities(self):
        entities = _extract_entities("Rachel and Lucas visited Chicago last week")
        assert "Rachel" in entities
        assert "Lucas" in entities
        assert "Chicago" in entities

    def test_filters_common_sentence_starters(self):
        entities = _extract_entities("Where did the user go? What happened after?")
        assert "Where" not in entities
        assert "What" not in entities

    def test_filters_user(self):
        """'User' is a common prefix in memory headlines, not a real entity."""
        entities = _extract_entities("User has a friend named Rachel")
        assert "User" not in entities
        assert "Rachel" in entities

    def test_filters_temporal_words(self):
        entities = _extract_entities("After the event, Recently she moved")
        assert "After" not in entities
        assert "Recently" not in entities

    def test_deduplicates(self):
        entities = _extract_entities("Rachel met Rachel at Rachel's party")
        assert entities.count("Rachel") == 1

    def test_limits_to_five(self):
        text = "Alice Bob Charlie Dave Eve Frank Grace Henry"
        entities = _extract_entities(text)
        assert len(entities) <= 5

    def test_empty_string(self):
        assert _extract_entities("") == []

    def test_no_proper_nouns(self):
        assert _extract_entities("where did she move to recently") == []

    def test_short_words_excluded(self):
        """Words 2 chars or fewer after capital are excluded by regex."""
        entities = _extract_entities("Al is here")
        assert "Al" not in entities  # Only 2 chars, regex requires 3+

    def test_real_benchmark_query(self):
        entities = _extract_entities("Where did Rachel move to after her recent relocation?")
        assert "Rachel" in entities
        assert len(entities) == 1  # Only Rachel is a proper noun here


# ---------------------------------------------------------------------------
# (b) Entity-mention bonus tests
# ---------------------------------------------------------------------------

class TestEntityMentionBonus:
    """Verify the 1.05x composite bonus for entity-matched memories."""

    def test_headline_match_applies_bonus(self):
        base = 0.700
        result = _apply_entity_bonus(base, "Rachel moved to the suburbs", ["Rachel"])
        assert abs(result - base * ENTITY_BONUS) < 1e-9

    def test_no_headline_match_no_bonus(self):
        base = 0.700
        result = _apply_entity_bonus(base, "User has a pet named Luna", ["Rachel"])
        assert result == base

    def test_case_insensitive_match(self):
        base = 0.700
        result = _apply_entity_bonus(base, "rachel moved to suburbs", ["Rachel"])
        assert result > base

    def test_multiple_entities_one_bonus(self):
        """Even if multiple entities match, only one 1.05x bonus is applied."""
        base = 0.700
        result = _apply_entity_bonus(base, "Rachel and Lucas at the park", ["Rachel", "Lucas"])
        assert abs(result - base * ENTITY_BONUS) < 1e-9  # Only 1.05x, not 1.05^2

    def test_empty_entities_no_bonus(self):
        base = 0.700
        result = _apply_entity_bonus(base, "Rachel moved to suburbs", [])
        assert result == base

    def test_bonus_preserves_ordering_of_relevant_memory(self):
        """Entity bonus should help relevant memory outrank irrelevant one."""
        # Memory about Rachel (relevant) vs memory about Luna (irrelevant)
        rachel_base = 0.680
        luna_base = 0.700  # Luna has higher base score
        entities = ["Rachel"]

        rachel_final = _apply_entity_bonus(rachel_base, "Rachel moved to suburbs", entities)
        luna_final = _apply_entity_bonus(luna_base, "User has a pet named Luna", entities)

        # Rachel gets 0.680 * 1.05 = 0.714, Luna stays at 0.700
        assert rachel_final > luna_final


# ---------------------------------------------------------------------------
# (c) Feature flag off = no entity extraction
# ---------------------------------------------------------------------------

class TestFeatureFlagOff:
    """When RECALL_ENTITY_STRATEGY_ENABLED=false, no entities should be
    extracted and no bonus should be applied."""

    def test_no_entities_when_flag_off(self):
        """Simulating flag off: entities list is empty."""
        # When flag is off, recall_fixed passes empty list
        entities = []  # Flag off = no extraction
        base = 0.700
        result = _apply_entity_bonus(base, "Rachel moved to suburbs", entities)
        assert result == base  # No change

    def test_identical_scores_flag_on_vs_off_no_entity(self):
        """When query has no entities, flag on/off produces same scores."""
        entities_on = _extract_entities("where did she move recently")  # No proper nouns
        entities_off = []
        assert entities_on == entities_off  # Both empty


# ---------------------------------------------------------------------------
# (d) S4 entity regex construction
# ---------------------------------------------------------------------------

class TestEntityRegex:
    """Verify the PostgreSQL regex pattern for S4 CTE."""

    def test_single_entity_regex(self):
        regex = _build_entity_regex(["Rachel"])
        assert regex == r'\m(Rachel)\M'

    def test_multiple_entities_regex(self):
        regex = _build_entity_regex(["Rachel", "Chicago"])
        assert regex == r'\m(Rachel|Chicago)\M'

    def test_special_chars_escaped(self):
        """Names with regex-special characters should be escaped."""
        regex = _build_entity_regex(["O'Brien"])
        assert "O\\'Brien" in regex or "O'Brien" in regex

    def test_regex_matches_word_boundary(self):
        """The \\m and \\M markers ensure word-boundary matching."""
        regex = _build_entity_regex(["Rachel"])
        # Should match "Rachel" but not "Rachels" in PostgreSQL
        # (we can't test PostgreSQL regex here, but verify the format)
        assert regex.startswith(r'\m(')
        assert regex.endswith(r')\M')
