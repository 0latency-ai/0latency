# Redaction State Machine

This document describes the two state machines that govern memory redaction and synthesis validity in the 0Latency memory service.

## Overview

Two independent state machines control memory lifecycle:

1. **Source State** (`redaction_state`) — applies to ALL memories (atoms and synthesis)
2. **Synthesis State** (`synthesis_state`) — applies ONLY to synthesis rows

The database enforces valid current values via CHECK constraints. Python code in `src/synthesis/state_machine.py` and `src/synthesis/redaction.py` enforces legal TRANSITIONS between states.

## Source State Machine

### States

- **active**: Normal operational state
- **redacted**: Memory has been redacted (GDPR deletion, user request) — TERMINAL
- **modified**: Memory content has been edited/updated
- **pending_resynthesis**: Memory is queued for resynthesis (Phase 2-4 internal state)

### Transition Table

| From State            | Legal Next States                  | Notes                                    |
|-----------------------|------------------------------------|------------------------------------------|
| active                | redacted, modified                 | Public API transitions                   |
| modified              | active, redacted                   | Can revert or escalate                   |
| redacted              | *(none)*                           | **TERMINAL** — GDPR compliance           |
| pending_resynthesis   | active, redacted, modified         | Recovery transitions (Phase 2-4 internal)|

### Important Notes

- **redacted is terminal**: Once a memory is redacted, it cannot be un-redacted. This is a GDPR requirement.
- **pending_resynthesis is internal**: Public API cannot directly transition to `pending_resynthesis`. This state is set by internal Phase 2-4 synthesis processes. It can be recovered to other states.
- **Cascade triggers**: Transitioning to `redacted` or `modified` triggers cascade to dependent synthesis rows.

### State Diagram (ASCII)

```
       ┌─────────┐
       │ active  │────┐
       └─────────┘    │
            │         │
         modified  redacted
            │         │
            ▼         ▼
       ┌─────────┐   ┌──────────┐
       │modified │   │ redacted │ (TERMINAL)
       └─────────┘   └──────────┘
            │
        can revert
            │
            ▼
       ┌─────────┐
       │ active  │
       └─────────┘

    (pending_resynthesis can transition to any non-terminal state)
```

## Synthesis State Machine

### States

- **valid**: Synthesis is current and accurate
- **pending_review**: Synthesis needs manual review (source was redacted/modified)
- **invalidated**: Synthesis is known to be incorrect
- **resynthesized**: Synthesis has been regenerated — TERMINAL

### Transition Table

| From State      | Legal Next States                       | Notes                                |
|-----------------|-----------------------------------------|--------------------------------------|
| valid           | pending_review, invalidated, resynthesized | Normal flow or direct regeneration |
| pending_review  | valid, invalidated, resynthesized       | Manual approval or auto-regeneration|
| invalidated     | resynthesized                           | Only path is regeneration           |
| resynthesized   | *(none)*                                | **TERMINAL** — replaced by new row  |

### Important Notes

- **resynthesized is terminal**: When a synthesis row is regenerated, the old row is marked `resynthesized` and a new row is created. The old row is immutable.
- **invalidated can only go forward**: Once invalidated, the only legal transition is to `resynthesized`. This prevents data integrity issues.
- **pending_review allows recovery**: Humans can manually approve a flagged synthesis (→ valid) or reject it (→ invalidated).

### State Diagram (ASCII)

```
       ┌─────────┐
       │  valid  │────┐
       └─────────┘    │
            │         │
    pending_review invalidated
            │         │
            ▼         ▼
    ┌───────────────┐ ┌──────────────┐
    │pending_review │ │ invalidated  │
    └───────────────┘ └──────────────┘
            │                │
        can approve      only path
            │                │
            ▼                ▼
       ┌─────────┐    ┌────────────────┐
       │  valid  │    │ resynthesized  │ (TERMINAL)
       └─────────┘    └────────────────┘
```

## Cascade Behavior

When a source memory transitions to `redacted` or `modified`, all synthesis rows that reference it (via `source_memory_ids` array) are automatically updated based on the tenant's synthesis policy.

### Cascade Actions (from policy)

1. **mark_pending_review** (Phase 1 ✅) — Set synthesis state to `pending_review`, flag for human review
2. **resynthesize_without** (Phase 2-4 ⚠️) — Regenerate synthesis excluding the changed source
3. **invalidate** (Phase 2-4 ⚠️) — Mark synthesis as `invalidated`, queue for regeneration

### Cascade Depth (from policy)

1. **evidence_chain_only** (Phase 1 ✅) — Cascade only to direct synthesis consumers (one hop: atom → synthesis)
2. **full_cluster** (Phase 2-4 ⚠️) — Cascade through entire synthesis graph (multi-hop: atom → synthesis → higher-order synthesis)

### Default Policy

Free/Pro/Scale tiers:
- `on_source_redacted`: `resynthesize_without` (Phase 2-4)
- `on_source_modified`: `mark_pending_review` (Phase 1 ✅)
- `cascade_depth`: `evidence_chain_only` (Phase 1 ✅)

## Phase 1 vs Phase 2-4 Implementation

### Implemented in Phase 1 ✅

- ✅ Both state machines with full transition validation
- ✅ `mark_pending_review` cascade action
- ✅ `evidence_chain_only` cascade depth
- ✅ Audit logging to `synthesis_audit_events`
- ✅ Policy-driven cascade behavior
- ✅ Database CHECK constraints

### Stubbed for Phase 2-4 ⚠️

- ⚠️ `resynthesize_without` cascade action → raises `NotImplementedError`
- ⚠️ `invalidate` cascade action → raises `NotImplementedError`
- ⚠️ `full_cluster` cascade depth → raises `NotImplementedError`
- ⚠️ Actual LLM-driven resynthesis pipeline
- ⚠️ Multi-hop synthesis graph traversal

Phase 1 focuses on **data integrity and audit trails**. Phase 2-4 will add **intelligent resynthesis** powered by LLMs.

## GDPR and Compliance Rationale

### Why `redacted` is Terminal

Under GDPR Article 17 (Right to Erasure), once personal data is deleted, it cannot be "un-deleted" or recovered. Making `redacted` a terminal state enforces this at the data model level.

### Why the Audit Log is Append-Only

GDPR Article 30 requires maintaining processing records. The `synthesis_audit_events` table uses a trigger to prevent UPDATE/DELETE operations, ensuring an immutable audit trail of all state changes, redactions, and resynthesis operations.

### Why Cascade Propagation Matters

If a user requests deletion of a memory that was used to create a synthesis, GDPR requires that the synthesis be flagged or regenerated to exclude the deleted data. The cascade mechanism automates this compliance requirement.

## API Usage Examples

### Redact a Source Memory

```python
from src.synthesis.redaction import transition_source_state

result = transition_source_state(
    memory_id='550e8400-e29b-41d4-a716-446655440000',
    new_state='redacted',
    conn=db_conn,
    reason='GDPR deletion request from user@example.com',
)

print(f"Cascaded to {len(result['cascade_summary'])} synthesis rows")
```

### Approve a Flagged Synthesis

```python
from src.synthesis.redaction import transition_synthesis_state

result = transition_synthesis_state(
    synthesis_id='550e8400-e29b-41d4-a716-446655440001',
    new_state='valid',
    conn=db_conn,
    reason='Manual review approved by engineer@0latency.ai',
)
```

### Validate a Transition (Pure Python, No DB)

```python
from src.synthesis.state_machine import validate_source_transition, IllegalTransitionError

try:
    validate_source_transition('active', 'pending_resynthesis')
except IllegalTransitionError as e:
    print(f"Not allowed: {e}")
    # Output: Illegal source state transition: active → pending_resynthesis
```

## Database Schema

### Columns Added

**memories table:**
- `redaction_state TEXT DEFAULT 'active'` — CHECK constraint: `('active', 'redacted', 'modified', 'pending_resynthesis')`
- `synthesis_state TEXT DEFAULT NULL` — CHECK constraint: `(NULL OR ('valid', 'pending_review', 'invalidated', 'resynthesized'))`

**Indexes:**
- `idx_memories_redaction_state` (btree) — for filtering redacted/modified memories
- `idx_memories_synthesis_state` (btree, partial WHERE memory_type='synthesis') — for filtering synthesis states
- `idx_memories_source_memory_ids` (GIN, partial WHERE source_memory_ids IS NOT NULL) — for cascade queries

### Audit Events Schema

**synthesis_audit_events table:**
- `event_type` includes `'state_transition'` (added in Migration 017)
- `event_payload` JSONB contains:
  ```json
  {
    "old_state": "valid",
    "new_state": "pending_review",
    "reason": "Source memory redacted",
    "state_type": "source" | "synthesis"
  }
  ```

## Testing

### Pure Python Tests

```bash
pytest tests/synthesis/test_state_machine.py -v
```

Tests all legal and illegal transitions for both state machines. No database required.

### DB Integration Tests

```bash
set -a && source .env && set +a && pytest tests/synthesis/test_redaction.py -v
```

Tests cascade behavior, policy integration, and audit logging. Requires `DATABASE_URL` env var.

## Migration History

- **Migration 012** (Task 1): Added `redaction_state` column and initial CHECK constraint
- **Migration 017** (Task 8): Added `synthesis_state` column, updated `redaction_state` CHECK constraint to include `modified` and `pending_resynthesis`, added `state_transition` to audit event types

## See Also

- `src/synthesis/state_machine.py` — Pure Python state transition validators
- `src/synthesis/redaction.py` — Service layer with cascade logic
- `src/synthesis/policy.py` — Tenant policy DSL parser
- `tests/synthesis/test_state_machine.py` — Unit tests
- `tests/synthesis/test_redaction.py` — Integration tests
