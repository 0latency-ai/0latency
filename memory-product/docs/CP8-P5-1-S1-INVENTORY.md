# CP8 P5.1 Stage 1 — Redaction Cascade Inventory

**Date:** 2026-05-05
**HEAD at audit:** e3b0ea7
**Author:** CC (autonomous)

## Summary

Redaction cascade is partially implemented. Core state transition functions exist in `src/synthesis/redaction.py` (415 lines, 3 public functions). Phase 1 implements `mark_pending_review` cascade action and `evidence_chain_only` depth; other actions/depths raise NotImplementedError. DB schema complete (4 columns landed via migrations 012 and 017). Recall filter correctly excludes redacted/pending_resynthesis. No HTTP endpoint exists. Audit events write to `synthesis_audit_events` with event_type='state_transition'. Test coverage exists (479-line test file). Validation cluster b28b7a99fd4791cb present with 21 synthesis rows and 8 source memories.

## DB shape

Query 1: Column metadata
```
column_name|data_type|is_nullable|column_default
redaction_state|text|YES|'active'::text
source_memory_ids|ARRAY|YES|
superseded_by|uuid|YES|
synthesis_version|integer|YES|1
(4 rows)
```

Query 2: Redaction state distribution
```
memory_type|redaction_state|count
correction|active|242
decision|active|777
fact|active|4671
fact|redacted|2
identity|active|601
pattern|active|3
preference|active|743
raw_turn|active|556
relationship|active|27
session_checkpoint|active|189
synthesis|active|48
task|active|1793
(12 rows)
```

Notable: 2 fact memories already in 'redacted' state (manual redaction occurred).

## redaction.py function inventory

| Function Name | Status | Behavior |
|---------------|--------|----------|
| `transition_source_state` | **Implemented** | Validates transition, updates redaction_state, logs audit event, triggers cascade for 'redacted'/'modified' states |
| `cascade_to_synthesis` | **Partial** | Finds dependent synthesis rows, applies policy. mark_pending_review+evidence_chain_only implemented. Other actions/depths raise NotImplementedError |
| `transition_synthesis_state` | **Implemented** | Validates transition, updates synthesis_state, logs audit event |
| `RedactionCascadeError` | Implemented | Exception class for cascade failures |

**File details:**
- Path: `src/synthesis/redaction.py`
- Size: 14K (415 lines)
- Last modified: 2026-04-28 21:00:26 (commit c366a00)
- Imports: policy.py, state_machine.py, json, logging, datetime, typing, uuid
- Phase 1 scope per header: mark_pending_review + evidence_chain_only only
- Phase 2-4 actions not implemented: resynthesize_without, invalidate, full_cluster depth

## Other module presence

### `src/synthesis/audit.py`
**Does NOT exist.** Audit functionality is embedded in other modules.

### `src/synthesis/writer.py`
- Exists: 26K
- Contains: `synthesize_cluster()` (main synthesis entry point), `_write_audit_event()` (writes to synthesis_audit_events)
- Audit event writer signature: `_write_audit_event(tenant_id, memory_id, event_type, actor, payload) -> UUID`
- Event types written: 'synthesis_written', 'rate_limit_blocked', 'synthesis_candidate_prepared'

### `src/synthesis/jobs.py`
- Exists: 13K
- Contains: job orchestration layer (create_job, start_job, complete_job, fail_job, cancel_job, get_job, list_jobs, claim_next_queued_job)
- Job state transitions defined via InvalidJobStateTransition exception

### `src/recall.py`
- Exists: 51K
- Redaction filter present (see Step 5)

### `api/main.py`
- Exists: 136K
- No redaction endpoint found (grep for 'redact|/redact|redaction' returned no results)

## Endpoint surface

**No redaction-related HTTP endpoints exist.**

Grep results:
- `api/main.py`: No matches for redact/redaction
- `src/recall.py`: Filter logic only (no endpoint)

**Finding:** Stage 2 must author a redaction endpoint (e.g., `POST /memories/{id}/redact`) to expose `transition_source_state()`.

## Recall filter verification

`src/recall.py:391` defines:
```python
_redaction_filter = "AND COALESCE(redaction_state, 'active') NOT IN ('redacted', 'pending_resynthesis')"
```

Filter applied in 3 CTEs:
1. Line 462: `vector_results` CTE (vector search via embedding distance)
2. Line 479: `importance_results` CTE (importance > 0.8)
3. Line 497: `text_results` CTE (full-text search via ts_query)

**Verification:** All recall paths correctly filter out redacted and pending_resynthesis memories. Phase 4 claim confirmed.

## Audit event vocabulary

| Event Type | Emitted By | Call Site |
|------------|-----------|-----------|
| `state_transition` | redaction.py | transition_source_state (line 122), transition_synthesis_state (line 387) |
| `synthesis_written` | writer.py | synthesize_cluster (line 622) |
| `rate_limit_blocked` | writer.py | synthesize_cluster (line 247) |
| `synthesis_candidate_prepared` | writer.py | synthesize_cluster (line 534, Phase 3 path) |

**State machine vocabulary** (from state_machine.py):
- Source states: 'active', 'redacted', 'modified', 'pending_resynthesis'
- Synthesis states: 'valid', 'pending_review', 'invalidated', 'resynthesized'
- Terminal states: 'redacted' (source), 'resynthesized' (synthesis)

Constraint enforcement via migrations:
- Migration 017 added CHECK constraints for both state machines
- synthesis_audit_events.event_type CHECK includes 'state_transition'

## Validation cluster status

Cluster `b28b7a99fd4791cb` on `user-justin` tenant:

**Synthesis rows:** 21 (all active, synthesis_state=NULL)
- IDs: 608d7237-1731-45cc-a178-3189b39a5c43, ea6e4716-5143-48c6-9150-fbbbaedf586a, e553ce52-df2e-4f4e-85a8-2ca945e76c6b, 237c19dc-e228-43a8-97af-63c7079a5c8b, 2674639e-eb10-4e30-afbe-cee6e22c4ace, 344ace8e-07ff-4269-84b2-2f0551952672, 587d6e27-fec8-42cd-9a84-d04bf3ee2194, 808d3871-b3d7-4ed8-a8ba-0cf9ac517f6d, 20d9d8de-0cfe-4241-b63d-b6f36cd673f1, 818b8ac0-cb9e-4a70-8cb9-194f1f384444, 001d2660-c1d7-4b81-8536-b7bc1ce578d0, 77ff281d-75c5-4961-9753-77a431fb9017, 88af5f82-28b5-47d9-8b3c-390a0b1fa80a, 0bd7202f-ae3d-424b-a743-49d3bd6a4b4b, e4f5363a-ab41-4bb9-b507-81c58bfaaec3, 9cbe65bd-301f-444e-9bf3-f814b4f6d5ca, 03470924-2ece-4024-b41b-b08edfe0872a, 4adb6017-e7f4-4093-97bf-3be73e124b63, 5a379aff-1620-486a-aa12-8a237888fdf8, 6c367c56-c738-4d05-bb07-ed0f3fa90787, 69044bdf-933b-4223-b20f-5d98ec613d64
- Created: 2026-05-03 to 2026-05-04

**Source memories:** 8 (all identity type, all active)
- IDs: 58772303-7644-418e-a39d-3d55ecd3b3ae, b8931bd5-4693-4da0-88be-f5802a3430bd, 9be1478c-adee-4a12-82e5-84bae5fbfaa8, aab371ed-8c18-48c6-98f2-07014b64cdb7, 8896ea6d-d747-460d-9c0c-5d3d3d7f2784, 598cd922-ad7e-4dde-af3b-bdf51394f3d2, 357f2074-2412-4849-9473-74328bd4b3df, 46eafc5e-2f31-46e7-b803-64fa20cb710d
- Created: 2026-04-16 to 2026-04-23

**Fixture status:** VALID. Cluster present, no superseded rows, all synthesis rows share same source_memory_ids.

## Migration history

| Migration | File | Columns Added |
|-----------|------|---------------|
| 007 | memory_consolidation.sql | `superseded_by` (uuid, nullable) |
| 012 | cp8_synthesis_schema.sql | `source_memory_ids` (uuid[], nullable), `synthesis_version` (int, default 1) |
| 017 | cp8_redaction_state_machine.sql | `synthesis_state` (text, nullable, CHECK constraint) + updated redaction_state CHECK to include 'modified' |

**Indexes created:**
- `idx_memories_source_memory_ids` (GIN, partial: WHERE source_memory_ids IS NOT NULL)
- `idx_memories_synthesis_state` (btree, partial: WHERE memory_type='synthesis')

## Test coverage

| Test File | Size | Purpose |
|-----------|------|---------|
| `tests/synthesis/test_redaction.py` | 17K (479 lines) | DB-integration tests for redaction cascade |
| `tests/synthesis/test_state_machine.py` | 9.4K | State transition validation tests |
| `tests/synthesis/test_writer.py` | 22K | Synthesis writer tests |
| `tests/synthesis/test_policy.py` | 4.1K | Policy loader tests |
| `tests/synthesis/test_jobs.py` | 11K | Job orchestration tests |

**Coverage gaps identified:**
- No end-to-end test for HTTP redaction endpoint (because endpoint doesn't exist)
- No test for full_cluster cascade depth (unimplemented)
- No test for resynthesize_without/invalidate actions (unimplemented)

## Open questions for Stage 2 author

1. **Redaction endpoint design:** Should `POST /memories/{id}/redact` accept only `reason` in body, or also `new_state` (to support both 'redacted' and 'modified' transitions)?

2. **Auth/authorization:** Should redaction be admin-only, or can users redact their own memories? Tenant-scoped only or cross-tenant for superadmin?

3. **Resynthesis trigger:** When source state transitions 'pending_resynthesis' → 'active', should synthesis jobs auto-spawn, or require manual trigger?

4. **Policy override:** Should redaction endpoint accept a `?force_action=invalidate` query param to override tenant policy for one-off operations?

5. **Batch redaction:** Should Stage 2 support `POST /memories/redact` (plural) with `memory_ids: []` body, or only single-memory redaction?

6. **Cascade blocking:** Should endpoint return 202 Accepted with job_id (async cascade), or 200 OK after cascade completes (sync)? Current redaction.py is sync — should it stay that way?

7. **synthesis_state NULL handling:** All 21 synthesis rows in validation cluster have synthesis_state=NULL. Is this expected (means 'valid' implicitly), or should migration backfill NULL → 'valid'?

8. **Audit event granularity:** Should cascade_to_synthesis emit one audit event per affected synthesis row, or one aggregate event with `affected_synthesis_ids: []`? Currently emits one per row.
