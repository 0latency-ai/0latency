
## 2026-04-29: Track 6 — Clean up memory_type junk values and add CHECK constraint

**Context**: Migration 021 revealed 31 distinct memory_type values in production with no validation. Canonical types per extraction.py: fact, decision, preference, task, correction, relationship, identity, session_checkpoint, pattern, raw_turn (10 total).

**Actions**:
1. Created backup table:  (78 rows)
2. Re-labeled junk types to canonical equivalents:
   - fact ← fix, smoke-test, test, test_legacy_category, verification, diagnostic_probe, cp7b_followup, cp8_phase1_status, cp8_phase1_blocker, crash_workflow, event, documentation, git, project
   - task ← issue, project_milestone
   - preference ← rule, instruction
   - identity ← system, toolkit, skills, profile
3. Updated 78 rows via CASE expression in single transaction
4. Added CHECK constraint: `check_memory_type` enforcing 10 canonical types
5. Verified constraint blocks invalid inserts

**Result**: memory_type now restricted to: fact (3732), task (1578), decision (612), preference (556), identity (466), correction (228), session_checkpoint (115), relationship (25), pattern (3), raw_turn (0 until Track 1 ships).

**SQL executed**:
```sql
CREATE TABLE memory_service.memory_type_backup_20260429 AS
SELECT id, memory_type, headline, agent_id, tenant_id, created_at
FROM memory_service.memories
WHERE memory_type NOT IN ('fact','decision','preference','task','correction','relationship','identity','session_checkpoint','pattern','raw_turn');

BEGIN;
UPDATE memory_service.memories
SET memory_type = CASE memory_type
  WHEN 'fix' THEN 'fact'
  WHEN 'smoke-test' THEN 'fact'
  WHEN 'test' THEN 'fact'
  WHEN 'test_legacy_category' THEN 'fact'
  WHEN 'verification' THEN 'fact'
  WHEN 'diagnostic_probe' THEN 'fact'
  WHEN 'cp7b_followup' THEN 'fact'
  WHEN 'cp8_phase1_status' THEN 'fact'
  WHEN 'cp8_phase1_blocker' THEN 'fact'
  WHEN 'crash_workflow' THEN 'fact'
  WHEN 'event' THEN 'fact'
  WHEN 'documentation' THEN 'fact'
  WHEN 'git' THEN 'fact'
  WHEN 'project' THEN 'fact'
  WHEN 'issue' THEN 'task'
  WHEN 'project_milestone' THEN 'task'
  WHEN 'rule' THEN 'preference'
  WHEN 'instruction' THEN 'preference'
  WHEN 'system' THEN 'identity'
  WHEN 'toolkit' THEN 'identity'
  WHEN 'skills' THEN 'identity'
  WHEN 'profile' THEN 'identity'
END
WHERE memory_type NOT IN ('fact','decision','preference','task','correction','relationship','identity','session_checkpoint','pattern','raw_turn');
COMMIT;

ALTER TABLE memory_service.memories
ADD CONSTRAINT check_memory_type
CHECK (memory_type IN (
  'fact','decision','preference','task','correction','relationship','identity',
  'session_checkpoint','pattern','raw_turn'
));
```

**Backup location**:  table (78 rows preserved for rollback if needed).

## 2026-04-29: Track 6 — Clean up memory_type junk values and add CHECK constraint

**Context**: Migration 021 revealed 31 distinct memory_type values in production with no validation. Canonical types per extraction.py: fact, decision, preference, task, correction, relationship, identity, session_checkpoint, pattern, raw_turn (10 total).

**Actions**:
1. Created backup table: `memory_service.memory_type_backup_20260429` (78 rows)
2. Re-labeled junk types to canonical equivalents:
   - fact ← fix, smoke-test, test, test_legacy_category, verification, diagnostic_probe, cp7b_followup, cp8_phase1_status, cp8_phase1_blocker, crash_workflow, event, documentation, git, project
   - task ← issue, project_milestone
   - preference ← rule, instruction
   - identity ← system, toolkit, skills, profile
3. Updated 78 rows via CASE expression in single transaction
4. Added CHECK constraint: `check_memory_type` enforcing 10 canonical types
5. Verified constraint blocks invalid inserts

**Result**: memory_type now restricted to: fact (3732), task (1578), decision (612), preference (556), identity (466), correction (228), session_checkpoint (115), relationship (25), pattern (3), raw_turn (0 until Track 1 ships).

**SQL executed**:
```sql
CREATE TABLE memory_service.memory_type_backup_20260429 AS
SELECT id, memory_type, headline, agent_id, tenant_id, created_at
FROM memory_service.memories
WHERE memory_type NOT IN ('fact','decision','preference','task','correction','relationship','identity','session_checkpoint','pattern','raw_turn');

BEGIN;
UPDATE memory_service.memories
SET memory_type = CASE memory_type
  WHEN 'fix' THEN 'fact'
  WHEN 'smoke-test' THEN 'fact'
  WHEN 'test' THEN 'fact'
  WHEN 'test_legacy_category' THEN 'fact'
  WHEN 'verification' THEN 'fact'
  WHEN 'diagnostic_probe' THEN 'fact'
  WHEN 'cp7b_followup' THEN 'fact'
  WHEN 'cp8_phase1_status' THEN 'fact'
  WHEN 'cp8_phase1_blocker' THEN 'fact'
  WHEN 'crash_workflow' THEN 'fact'
  WHEN 'event' THEN 'fact'
  WHEN 'documentation' THEN 'fact'
  WHEN 'git' THEN 'fact'
  WHEN 'project' THEN 'fact'
  WHEN 'issue' THEN 'task'
  WHEN 'project_milestone' THEN 'task'
  WHEN 'rule' THEN 'preference'
  WHEN 'instruction' THEN 'preference'
  WHEN 'system' THEN 'identity'
  WHEN 'toolkit' THEN 'identity'
  WHEN 'skills' THEN 'identity'
  WHEN 'profile' THEN 'identity'
END
WHERE memory_type NOT IN ('fact','decision','preference','task','correction','relationship','identity','session_checkpoint','pattern','raw_turn');
COMMIT;

ALTER TABLE memory_service.memories
ADD CONSTRAINT check_memory_type
CHECK (memory_type IN (
  'fact','decision','preference','task','correction','relationship','identity',
  'session_checkpoint','pattern','raw_turn'
));
```

**Backup location**: `memory_service.memory_type_backup_20260429` table (78 rows preserved for rollback if needed).
