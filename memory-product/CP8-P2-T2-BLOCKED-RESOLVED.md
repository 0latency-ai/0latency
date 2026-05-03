# CP8 Phase 2 T2 — BLOCKED

**Date:** 2026-05-03
**Task:** Synthesis Writer implementation
**Blocked at:** Step 3 (implementation)

---

## Blocker

**Database schema missing 'synthesis' memory_type in CHECK constraint.**

### Evidence

Current CHECK constraint on `memory_service.memories.memory_type`:

```sql
CHECK ((memory_type = ANY (ARRAY[
  'fact'::text,
  'decision'::text,
  'preference'::text,
  'task'::text,
  'correction'::text,
  'relationship'::text,
  'identity'::text,
  'session_checkpoint'::text,
  'pattern'::text,
  'raw_turn'::text
])))
```

**Missing:** 'synthesis'

### Scope requirement

From CP8-P2-T2-WRITER-SCOPE.md line ~155:

```sql
INSERT INTO memory_service.memories (
    tenant_id, agent_id, memory_type,
    ...
) VALUES (
    %s, %s, 'synthesis',  -- <-- Requires 'synthesis' memory_type
    ...
)
```

### Impact

Cannot write synthesis rows with memory_type='synthesis' as specified in scope. Attempting to INSERT will fail with:

```
ERROR:  new row for relation "memories" violates check constraint "check_memory_type"
DETAIL:  Failing row contains (... memory_type = synthesis ...)
```

### Root cause

Migration 012_cp8_synthesis_schema.sql added synthesis-related columns (source_memory_ids, role_tag, redaction_state, etc.) but did NOT update the memory_type CHECK constraint to include 'synthesis'.

Migration 017_cp8_redaction_state_machine.sql references `WHERE memory_type = 'synthesis'` in an index definition (line 49) but does not add 'synthesis' to the allowed values.

### Required fix

Add migration 023 to update the CHECK constraint:

```sql
ALTER TABLE memory_service.memories
DROP CONSTRAINT IF EXISTS check_memory_type;

ALTER TABLE memory_service.memories
ADD CONSTRAINT check_memory_type
CHECK (memory_type IN (
    'fact',
    'decision',
    'preference',
    'task',
    'correction',
    'relationship',
    'identity',
    'session_checkpoint',
    'pattern',
    'raw_turn',
    'synthesis'  -- NEW
));
```

### Autonomy protocol

Per `docs/AUTONOMY-PROTOCOL.md`:
- Out of scope: "Any migration file"
- Halt condition: "Phase 1 incomplete" (similar to tier_gates missing functions)

**Decision:** HALT. Writing BLOCKED file. User review required.

---

## Verification performed

```bash
ssh root@164.90.156.169 'source /root/.openclaw/workspace/memory-product/.env && psql "$DATABASE_URL" -c "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = '\''check_memory_type'\'' AND conrelid = '\''memory_service.memories'\''::regclass"'
```

Result: Confirmed 'synthesis' is NOT in the allowed array.

---

## Next steps

1. User applies migration 023 to add 'synthesis' to memory_type CHECK constraint
2. User resumes CC with: "Migration 023 applied. Resume T2 from Step 3."
3. Writer implementation can proceed

---

**End of BLOCKED report**
