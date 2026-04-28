"""Synthesis state machine definitions and transition validators.

This module defines the state machines for source memories and synthesis memories.
It provides pure-Python validation of state transitions with no database dependencies.

Two state machines:
1. Source state (redaction_state) — applies to all memories
2. Synthesis state (synthesis_state) — applies only to synthesis rows

All state writes MUST go through transition validation functions in this module.
The database enforces valid current values via CHECK constraints.
This module enforces legal TRANSITIONS between states.
"""

from __future__ import annotations

import logging
from typing import Dict, FrozenSet

logger = logging.getLogger(__name__)


# ============================================================
# Source state machine (memories.redaction_state)
# ============================================================

SOURCE_STATES: FrozenSet[str] = frozenset({
    'active',
    'redacted',
    'modified',
    'pending_resynthesis',
})

# Legal transitions for source states
# Note: pending_resynthesis is Phase 2-4 internal state, not accessible via public API
SOURCE_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    'active': frozenset({'redacted', 'modified'}),
    'modified': frozenset({'active', 'redacted'}),
    'redacted': frozenset(),  # Terminal state
    'pending_resynthesis': frozenset({'active', 'redacted', 'modified'}),
}


# ============================================================
# Synthesis state machine (memories.synthesis_state)
# ============================================================

SYNTHESIS_STATES: FrozenSet[str] = frozenset({
    'valid',
    'pending_review',
    'invalidated',
    'resynthesized',
})

# Legal transitions for synthesis states
SYNTHESIS_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    'valid': frozenset({'pending_review', 'invalidated', 'resynthesized'}),
    'pending_review': frozenset({'valid', 'invalidated', 'resynthesized'}),
    'invalidated': frozenset({'resynthesized'}),
    'resynthesized': frozenset(),  # Terminal state
}


# ============================================================
# Exceptions
# ============================================================

class IllegalTransitionError(ValueError):
    """Raised when attempting an invalid state transition."""
    pass


# ============================================================
# Validation functions
# ============================================================

def validate_source_transition(from_state: str, to_state: str) -> None:
    """Validate a source state transition.

    Args:
        from_state: Current redaction_state value
        to_state: Desired redaction_state value

    Raises:
        IllegalTransitionError: If transition is not allowed
        ValueError: If states are not in SOURCE_STATES

    Examples:
        >>> validate_source_transition('active', 'redacted')  # OK
        >>> validate_source_transition('active', 'pending_resynthesis')  # Raises
        >>> validate_source_transition('redacted', 'active')  # Raises (terminal)
    """
    if from_state not in SOURCE_STATES:
        raise ValueError(f"Invalid source state: {from_state}")
    if to_state not in SOURCE_STATES:
        raise ValueError(f"Invalid source state: {to_state}")

    if to_state not in SOURCE_TRANSITIONS[from_state]:
        legal = sorted(SOURCE_TRANSITIONS[from_state])
        raise IllegalTransitionError(
            f"Illegal source state transition: {from_state} → {to_state}. "
            f"Legal transitions from {from_state}: {legal}"
        )

    logger.debug("Validated source transition: %s → %s", from_state, to_state)


def validate_synthesis_transition(from_state: str, to_state: str) -> None:
    """Validate a synthesis state transition.

    Args:
        from_state: Current synthesis_state value
        to_state: Desired synthesis_state value

    Raises:
        IllegalTransitionError: If transition is not allowed
        ValueError: If states are not in SYNTHESIS_STATES

    Examples:
        >>> validate_synthesis_transition('valid', 'pending_review')  # OK
        >>> validate_synthesis_transition('resynthesized', 'valid')  # Raises (terminal)
        >>> validate_synthesis_transition('invalidated', 'valid')  # Raises
    """
    if from_state not in SYNTHESIS_STATES:
        raise ValueError(f"Invalid synthesis state: {from_state}")
    if to_state not in SYNTHESIS_STATES:
        raise ValueError(f"Invalid synthesis state: {to_state}")

    if to_state not in SYNTHESIS_TRANSITIONS[from_state]:
        legal = sorted(SYNTHESIS_TRANSITIONS[from_state])
        raise IllegalTransitionError(
            f"Illegal synthesis state transition: {from_state} → {to_state}. "
            f"Legal transitions from {from_state}: {legal}"
        )

    logger.debug("Validated synthesis transition: %s → %s", from_state, to_state)


# ============================================================
# Terminal state checks
# ============================================================

def is_terminal_source(state: str) -> bool:
    """Check if a source state is terminal (no outgoing transitions).

    Args:
        state: Source state to check

    Returns:
        True if state is terminal (redacted), False otherwise

    Examples:
        >>> is_terminal_source('redacted')
        True
        >>> is_terminal_source('active')
        False
    """
    if state not in SOURCE_STATES:
        raise ValueError(f"Invalid source state: {state}")
    return state == 'redacted'


def is_terminal_synthesis(state: str) -> bool:
    """Check if a synthesis state is terminal (no outgoing transitions).

    Args:
        state: Synthesis state to check

    Returns:
        True if state is terminal (resynthesized), False otherwise

    Examples:
        >>> is_terminal_synthesis('resynthesized')
        True
        >>> is_terminal_synthesis('valid')
        False
    """
    if state not in SYNTHESIS_STATES:
        raise ValueError(f"Invalid synthesis state: {state}")
    return state == 'resynthesized'
