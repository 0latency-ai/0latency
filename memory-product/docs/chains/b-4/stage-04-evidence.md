# Stage 04 Evidence - Audit-aware reads (Enterprise tier)

**Commit SHA:** N/A

**Outcome:** BLOCKED-NEEDS-HUMAN

## Blocking Reason
The synthesis_audit_events table exists, but the event_type check constraint does not include 'read'. Adding 'read' to the constraint requires:

```sql
ALTER TABLE memory_service.synthesis_audit_events 
DROP CONSTRAINT synthesis_audit_events_event_type_check;

ALTER TABLE memory_service.synthesis_audit_events 
ADD CONSTRAINT synthesis_audit_events_event_type_check 
CHECK (event_type = ANY (ARRAY[..., 'read'::text]));
```

This is a schema migration (Tier 2 operation per chain framework), which is outside the scope of this Tier 1 read-path chain.

## Current Constraint
```
CHECK (event_type = ANY (ARRAY['synthesis_written'::text, 'redacted'::text, 'resynthesized'::text, ...]))
```

Does NOT include 'read'.

## Required Migration
1. Add 'read' to event_type check constraint
2. Test audit event insertion with event_type='read'
3. Then implement audit-aware recall code

## Next Steps
- Mark this stage as BLOCKED-NEEDS-HUMAN
- Continue with Stages 05 and 06 (MCP tool work)
- Schema migration can be done in a separate Tier 2 chain
- After migration, implement audit logic in recall.py:
  - Check if tenant.plan == 'enterprise'
  - Count synthesis memories in result
  - Fire-and-forget INSERT into synthesis_audit_events
  - Verify latency unchanged for non-enterprise tiers
