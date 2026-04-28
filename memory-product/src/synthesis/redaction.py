"""Redaction cascade service layer.

This module implements state transitions for source and synthesis memories,
with automatic cascade logic when source memories are redacted or modified.

All state changes write audit events to memory_service.synthesis_audit_events.
Cascade behavior is controlled by tenant synthesis policies loaded via policy.py.

Phase 1 Implementation:
- mark_pending_review cascade action is fully implemented
- evidence_chain_only cascade depth is fully implemented
- resynthesize_without and invalidate actions raise NotImplementedError (Phase 2-4)
- full_cluster cascade depth raises NotImplementedError (Phase 2-4)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from .policy import load_policy
from .state_machine import (
    IllegalTransitionError,
    validate_source_transition,
    validate_synthesis_transition,
)

logger = logging.getLogger(__name__)


# ============================================================
# Exceptions
# ============================================================

class RedactionCascadeError(RuntimeError):
    """Raised when cascade operation fails due to database errors."""
    pass


# ============================================================
# Source state transitions
# ============================================================

def transition_source_state(
    memory_id: str,
    new_state: str,
    conn,
    *,
    reason: str = '',
) -> Dict[str, Any]:
    """Transition a source memory to a new redaction state.

    Validates the transition, updates the database, logs audit event,
    and triggers cascade if new_state is 'redacted' or 'modified'.

    Args:
        memory_id: UUID of memory to transition
        new_state: Target redaction_state value
        conn: psycopg connection (sync)
        reason: Optional human-readable reason for transition

    Returns:
        Dict with keys:
            - memory_id: UUID
            - old_state: Previous redaction_state
            - new_state: New redaction_state
            - cascade_summary: List of cascade results (empty if no cascade)

    Raises:
        IllegalTransitionError: If transition is not allowed
        RedactionCascadeError: If database operation fails
        ValueError: If memory not found

    Examples:
        >>> result = transition_source_state(mem_id, 'redacted', conn, reason='GDPR request')
        >>> result['cascade_summary']  # List of affected synthesis rows
    """
    try:
        with conn.cursor() as cur:
            # Fetch current state and tenant_id
            cur.execute(
                """
                SELECT redaction_state, tenant_id
                FROM memory_service.memories
                WHERE id = %s
                """,
                (memory_id,),
            )
            row = cur.fetchone()

            if not row:
                raise ValueError(f"Memory {memory_id} not found")

            old_state, tenant_id = row

            # Validate transition
            validate_source_transition(old_state, new_state)

            # Update state
            cur.execute(
                """
                UPDATE memory_service.memories
                SET redaction_state = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (new_state, memory_id),
            )

            # Write audit event
            event_payload = {
                'old_state': old_state,
                'new_state': new_state,
                'reason': reason,
                'state_type': 'source',
            }
            cur.execute(
                """
                INSERT INTO memory_service.synthesis_audit_events
                (tenant_id, target_memory_id, event_type, actor, event_payload)
                VALUES (%s, %s, 'state_transition', 'system', %s)
                """,
                (tenant_id, memory_id, json.dumps(event_payload)),
            )

            logger.info(
                "Transitioned source memory %s: %s → %s (reason: %s)",
                memory_id,
                old_state,
                new_state,
                reason or 'none',
            )

            # Trigger cascade if redacted or modified
            cascade_summary = []
            if new_state in ('redacted', 'modified'):
                cascade_summary = cascade_to_synthesis(
                    memory_id,
                    new_state,
                    conn,
                )

            return {
                'memory_id': memory_id,
                'old_state': old_state,
                'new_state': new_state,
                'cascade_summary': cascade_summary,
            }

    except IllegalTransitionError:
        raise
    except ValueError:
        raise
    except NotImplementedError:
        raise
    except Exception as e:
        logger.error("Failed to transition source state for %s: %s", memory_id, e)
        raise RedactionCascadeError(f"Database error during state transition: {e}") from e


# ============================================================
# Cascade logic
# ============================================================

def cascade_to_synthesis(
    source_memory_id: str,
    source_new_state: str,
    conn,
) -> List[Dict[str, Any]]:
    """Cascade a source state change to dependent synthesis rows.

    Finds all synthesis rows where source_memory_id is in source_memory_ids,
    reads tenant policy to determine cascade action, and applies it.

    Phase 1: Only mark_pending_review and evidence_chain_only are implemented.
    Other actions/depths raise NotImplementedError.

    Args:
        source_memory_id: UUID of source memory that changed
        source_new_state: New redaction_state of source ('redacted' or 'modified')
        conn: psycopg connection (sync)

    Returns:
        List of dicts with keys:
            - synthesis_id: UUID
            - old_state: Previous synthesis_state
            - new_state: New synthesis_state

    Raises:
        NotImplementedError: If policy requires unimplemented action/depth
        RedactionCascadeError: If database operation fails

    Examples:
        >>> results = cascade_to_synthesis(atom_id, 'redacted', conn)
        >>> len(results)  # Number of synthesis rows affected
    """
    try:
        with conn.cursor() as cur:
            # Find all synthesis rows referencing this source
            cur.execute(
                """
                SELECT id, tenant_id, synthesis_state
                FROM memory_service.memories
                WHERE memory_type = 'synthesis'
                  AND %s = ANY(source_memory_ids)
                """,
                (source_memory_id,),
            )
            synthesis_rows = cur.fetchall()

            if not synthesis_rows:
                logger.debug("No synthesis rows reference source %s", source_memory_id)
                return []

            # Group by tenant to load policy once per tenant
            rows_by_tenant: Dict[str, List[tuple]] = {}
            for row in synthesis_rows:
                syn_id, tenant_id, syn_state = row
                if tenant_id not in rows_by_tenant:
                    rows_by_tenant[tenant_id] = []
                rows_by_tenant[tenant_id].append((syn_id, syn_state))

            cascade_results = []

            for tenant_id, rows in rows_by_tenant.items():
                # Load tenant policy
                policy = load_policy(tenant_id, conn)
                redaction_rules = policy['redaction_rules']

                # Check cascade depth
                cascade_depth = redaction_rules['cascade_depth']
                if cascade_depth != 'evidence_chain_only':
                    raise NotImplementedError(
                        f"Phase 2-4 will implement full_cluster cascade depth. "
                        f"Current policy for tenant {tenant_id} requires: {cascade_depth}"
                    )

                # Determine action based on source state
                if source_new_state == 'redacted':
                    action = redaction_rules['on_source_redacted']
                elif source_new_state == 'modified':
                    action = redaction_rules['on_source_modified']
                else:
                    logger.warning(
                        "cascade_to_synthesis called with unexpected state: %s",
                        source_new_state,
                    )
                    continue

                # Phase 1: Only mark_pending_review is implemented
                if action != 'mark_pending_review':
                    raise NotImplementedError(
                        f"Phase 2-4 will implement {action} cascade action. "
                        f"Current policy for tenant {tenant_id} requires: {action}"
                    )

                # Apply mark_pending_review action to all rows
                for syn_id, old_syn_state in rows:
                    if old_syn_state is None:
                        logger.warning(
                            "Synthesis row %s has NULL synthesis_state; skipping cascade",
                            syn_id,
                        )
                        continue

                    # Transition to pending_review
                    result = transition_synthesis_state(
                        syn_id,
                        'pending_review',
                        conn,
                        reason=f"Source {source_memory_id} → {source_new_state}",
                    )
                    cascade_results.append({
                        'synthesis_id': syn_id,
                        'old_state': result['old_state'],
                        'new_state': result['new_state'],
                    })

            logger.info(
                "Cascaded source %s (%s) to %d synthesis rows",
                source_memory_id,
                source_new_state,
                len(cascade_results),
            )

            return cascade_results

    except NotImplementedError:
        raise
    except Exception as e:
        logger.error(
            "Failed to cascade source %s to synthesis: %s",
            source_memory_id,
            e,
        )
        raise RedactionCascadeError(f"Database error during cascade: {e}") from e


# ============================================================
# Synthesis state transitions
# ============================================================

def transition_synthesis_state(
    synthesis_id: str,
    new_state: str,
    conn,
    *,
    reason: str = '',
) -> Dict[str, Any]:
    """Transition a synthesis memory to a new synthesis state.

    Validates the transition, updates the database, and logs audit event.

    Args:
        synthesis_id: UUID of synthesis memory to transition
        new_state: Target synthesis_state value
        conn: psycopg connection (sync)
        reason: Optional human-readable reason for transition

    Returns:
        Dict with keys:
            - synthesis_id: UUID
            - old_state: Previous synthesis_state
            - new_state: New synthesis_state

    Raises:
        IllegalTransitionError: If transition is not allowed
        RedactionCascadeError: If database operation fails
        ValueError: If memory not found or not a synthesis row

    Examples:
        >>> result = transition_synthesis_state(syn_id, 'valid', conn, reason='Manual review approved')
    """
    try:
        with conn.cursor() as cur:
            # Fetch current state and verify it's a synthesis row
            cur.execute(
                """
                SELECT synthesis_state, tenant_id, memory_type
                FROM memory_service.memories
                WHERE id = %s
                """,
                (synthesis_id,),
            )
            row = cur.fetchone()

            if not row:
                raise ValueError(f"Memory {synthesis_id} not found")

            old_state, tenant_id, memory_type = row

            if memory_type != 'synthesis':
                raise ValueError(
                    f"Memory {synthesis_id} is not a synthesis row (type: {memory_type})"
                )

            if old_state is None:
                raise ValueError(
                    f"Synthesis memory {synthesis_id} has NULL synthesis_state"
                )

            # Validate transition
            validate_synthesis_transition(old_state, new_state)

            # Update state
            cur.execute(
                """
                UPDATE memory_service.memories
                SET synthesis_state = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (new_state, synthesis_id),
            )

            # Write audit event
            event_payload = {
                'old_state': old_state,
                'new_state': new_state,
                'reason': reason,
                'state_type': 'synthesis',
            }
            cur.execute(
                """
                INSERT INTO memory_service.synthesis_audit_events
                (tenant_id, target_memory_id, event_type, actor, event_payload)
                VALUES (%s, %s, 'state_transition', 'system', %s)
                """,
                (tenant_id, synthesis_id, json.dumps(event_payload)),
            )

            logger.info(
                "Transitioned synthesis memory %s: %s → %s (reason: %s)",
                synthesis_id,
                old_state,
                new_state,
                reason or 'none',
            )

            return {
                'synthesis_id': synthesis_id,
                'old_state': old_state,
                'new_state': new_state,
            }

    except IllegalTransitionError:
        raise
    except ValueError:
        raise
    except NotImplementedError:
        raise
    except Exception as e:
        logger.error("Failed to transition synthesis state for %s: %s", synthesis_id, e)
        raise RedactionCascadeError(f"Database error during state transition: {e}") from e
