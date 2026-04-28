"""Tests for synthesis state machine pure-Python logic.

No database required. Tests state transition validation only.
"""

import pytest

from src.synthesis.state_machine import (
    IllegalTransitionError,
    SOURCE_STATES,
    SOURCE_TRANSITIONS,
    SYNTHESIS_STATES,
    SYNTHESIS_TRANSITIONS,
    is_terminal_source,
    is_terminal_synthesis,
    validate_source_transition,
    validate_synthesis_transition,
)


# ============================================================
# Source state machine tests
# ============================================================

class TestSourceStates:
    """Test source state machine definitions."""

    def test_source_states_complete(self):
        """All expected source states are defined."""
        assert SOURCE_STATES == {'active', 'redacted', 'modified', 'pending_resynthesis'}

    def test_source_transitions_complete(self):
        """All source states have transition definitions."""
        assert set(SOURCE_TRANSITIONS.keys()) == SOURCE_STATES


class TestSourceTransitions:
    """Test valid source state transitions."""

    def test_active_to_redacted(self):
        """active → redacted is legal."""
        validate_source_transition('active', 'redacted')  # Should not raise

    def test_active_to_modified(self):
        """active → modified is legal."""
        validate_source_transition('active', 'modified')  # Should not raise

    def test_modified_to_active(self):
        """modified → active is legal (revert modification)."""
        validate_source_transition('modified', 'active')  # Should not raise

    def test_modified_to_redacted(self):
        """modified → redacted is legal."""
        validate_source_transition('modified', 'redacted')  # Should not raise

    def test_pending_resynthesis_to_active(self):
        """pending_resynthesis → active is legal (recovery)."""
        validate_source_transition('pending_resynthesis', 'active')  # Should not raise

    def test_pending_resynthesis_to_redacted(self):
        """pending_resynthesis → redacted is legal (recovery)."""
        validate_source_transition('pending_resynthesis', 'redacted')  # Should not raise

    def test_pending_resynthesis_to_modified(self):
        """pending_resynthesis → modified is legal (recovery)."""
        validate_source_transition('pending_resynthesis', 'modified')  # Should not raise


class TestIllegalSourceTransitions:
    """Test illegal source state transitions."""

    def test_active_to_pending_resynthesis_blocked(self):
        """active → pending_resynthesis is NOT allowed (Phase 2-4 internal)."""
        with pytest.raises(IllegalTransitionError) as exc_info:
            validate_source_transition('active', 'pending_resynthesis')
        assert 'active → pending_resynthesis' in str(exc_info.value)

    def test_modified_to_pending_resynthesis_blocked(self):
        """modified → pending_resynthesis is NOT allowed (Phase 2-4 internal)."""
        with pytest.raises(IllegalTransitionError) as exc_info:
            validate_source_transition('modified', 'pending_resynthesis')
        assert 'modified → pending_resynthesis' in str(exc_info.value)

    def test_redacted_is_terminal(self):
        """redacted → anything is NOT allowed (terminal state)."""
        with pytest.raises(IllegalTransitionError):
            validate_source_transition('redacted', 'active')

        with pytest.raises(IllegalTransitionError):
            validate_source_transition('redacted', 'modified')

        with pytest.raises(IllegalTransitionError):
            validate_source_transition('redacted', 'pending_resynthesis')

    def test_invalid_from_state(self):
        """Invalid from_state raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_source_transition('invalid', 'active')
        assert 'Invalid source state: invalid' in str(exc_info.value)

    def test_invalid_to_state(self):
        """Invalid to_state raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_source_transition('active', 'invalid')
        assert 'Invalid source state: invalid' in str(exc_info.value)


class TestTerminalSourceStates:
    """Test source terminal state detection."""

    def test_redacted_is_terminal(self):
        """redacted is terminal."""
        assert is_terminal_source('redacted') is True

    def test_active_not_terminal(self):
        """active is not terminal."""
        assert is_terminal_source('active') is False

    def test_modified_not_terminal(self):
        """modified is not terminal."""
        assert is_terminal_source('modified') is False

    def test_pending_resynthesis_not_terminal(self):
        """pending_resynthesis is not terminal."""
        assert is_terminal_source('pending_resynthesis') is False

    def test_invalid_state_raises(self):
        """Invalid state raises ValueError."""
        with pytest.raises(ValueError):
            is_terminal_source('invalid')


# ============================================================
# Synthesis state machine tests
# ============================================================

class TestSynthesisStates:
    """Test synthesis state machine definitions."""

    def test_synthesis_states_complete(self):
        """All expected synthesis states are defined."""
        assert SYNTHESIS_STATES == {'valid', 'pending_review', 'invalidated', 'resynthesized'}

    def test_synthesis_transitions_complete(self):
        """All synthesis states have transition definitions."""
        assert set(SYNTHESIS_TRANSITIONS.keys()) == SYNTHESIS_STATES


class TestSynthesisTransitions:
    """Test valid synthesis state transitions."""

    def test_valid_to_pending_review(self):
        """valid → pending_review is legal."""
        validate_synthesis_transition('valid', 'pending_review')  # Should not raise

    def test_valid_to_invalidated(self):
        """valid → invalidated is legal."""
        validate_synthesis_transition('valid', 'invalidated')  # Should not raise

    def test_valid_to_resynthesized(self):
        """valid → resynthesized is legal."""
        validate_synthesis_transition('valid', 'resynthesized')  # Should not raise

    def test_pending_review_to_valid(self):
        """pending_review → valid is legal (manual approval)."""
        validate_synthesis_transition('pending_review', 'valid')  # Should not raise

    def test_pending_review_to_invalidated(self):
        """pending_review → invalidated is legal."""
        validate_synthesis_transition('pending_review', 'invalidated')  # Should not raise

    def test_pending_review_to_resynthesized(self):
        """pending_review → resynthesized is legal."""
        validate_synthesis_transition('pending_review', 'resynthesized')  # Should not raise

    def test_invalidated_to_resynthesized(self):
        """invalidated → resynthesized is legal."""
        validate_synthesis_transition('invalidated', 'resynthesized')  # Should not raise


class TestIllegalSynthesisTransitions:
    """Test illegal synthesis state transitions."""

    def test_invalidated_to_valid_blocked(self):
        """invalidated → valid is NOT allowed."""
        with pytest.raises(IllegalTransitionError) as exc_info:
            validate_synthesis_transition('invalidated', 'valid')
        assert 'invalidated → valid' in str(exc_info.value)

    def test_invalidated_to_pending_review_blocked(self):
        """invalidated → pending_review is NOT allowed."""
        with pytest.raises(IllegalTransitionError):
            validate_synthesis_transition('invalidated', 'pending_review')

    def test_resynthesized_is_terminal(self):
        """resynthesized → anything is NOT allowed (terminal state)."""
        with pytest.raises(IllegalTransitionError):
            validate_synthesis_transition('resynthesized', 'valid')

        with pytest.raises(IllegalTransitionError):
            validate_synthesis_transition('resynthesized', 'pending_review')

        with pytest.raises(IllegalTransitionError):
            validate_synthesis_transition('resynthesized', 'invalidated')

    def test_invalid_from_state(self):
        """Invalid from_state raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_synthesis_transition('invalid', 'valid')
        assert 'Invalid synthesis state: invalid' in str(exc_info.value)

    def test_invalid_to_state(self):
        """Invalid to_state raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_synthesis_transition('valid', 'invalid')
        assert 'Invalid synthesis state: invalid' in str(exc_info.value)


class TestTerminalSynthesisStates:
    """Test synthesis terminal state detection."""

    def test_resynthesized_is_terminal(self):
        """resynthesized is terminal."""
        assert is_terminal_synthesis('resynthesized') is True

    def test_valid_not_terminal(self):
        """valid is not terminal."""
        assert is_terminal_synthesis('valid') is False

    def test_pending_review_not_terminal(self):
        """pending_review is not terminal."""
        assert is_terminal_synthesis('pending_review') is False

    def test_invalidated_not_terminal(self):
        """invalidated is not terminal."""
        assert is_terminal_synthesis('invalidated') is False

    def test_invalid_state_raises(self):
        """Invalid state raises ValueError."""
        with pytest.raises(ValueError):
            is_terminal_synthesis('invalid')
