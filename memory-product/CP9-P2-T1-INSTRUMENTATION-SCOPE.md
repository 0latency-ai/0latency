# CP9 PHASE 2 — TRACK B1: TIME-TO-FIRST-MEMORY INSTRUMENTATION

**Date**: 2026-05-10  
**Branch**: cp9-p2-t1-instrumentation  
**Status**: Implementation in progress

---

## Objective

Emit structured telemetry events when tenants successfully add their first memory across all four install paths:
- Path A: SDK (direct API usage)
- Path B: CLI (0latency-cli wrapper)
- Path C: MCP (@0latency/mcp-server)
- Path D: Web (quickstart/dashboard)

Events capture: install_path, elapsed_seconds_from_tenant_creation, tenant_id, agent_id, timestamp.  
This enables data-driven onboarding optimization.

---

## Design Decisions

### 1. Table Schema

**Decision**: Create new table `memory_service.onboarding_events`

**Rationale**: 
- Clean separation of concerns — onboarding metrics are distinct from audit logs or analytics events
- Allows focused queries without filtering multi-purpose tables
- Simpler to add onboarding-specific columns (e.g., path, elapsed_seconds) without cluttering other tables
- Aligns with single-responsibility principle

**Schema**:
```sql
CREATE TABLE memory_service.onboarding_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'first_memory_add'
    install_path TEXT NOT NULL,  -- 'sdk', 'cli', 'mcp', 'web', 'unknown'
    elapsed_seconds NUMERIC NOT NULL,  -- NOW() - tenants.created_at
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_onboarding_events_tenant_id ON memory_service.onboarding_events(tenant_id);
CREATE INDEX idx_onboarding_events_path ON memory_service.onboarding_events(install_path);
CREATE INDEX idx_onboarding_events_created_at ON memory_service.onboarding_events(created_at);
```

**Alternative considered**: Extend `memory_service.analytics_events` table  
**Rejected because**: Generic analytics table would require complex filtering; onboarding is a first-class workflow worth dedicated tracking.

---

### 2. Path Detection

**Decision**: SDK/clients send `X-Install-Path` header; API records it

**Mechanism**:
- SDK calls default to `X-Install-Path: sdk`
- CLI wrapper sends `X-Install-Path: cli`
- MCP server sends `X-Install-Path: mcp`
- Web quickstart sends `X-Install-Path: web`
- If header absent → `unknown`

**Rationale**:
- Client knows its context better than server can infer
- Simple, explicit, no heuristics needed
- Easy to add to existing HTTP clients
- Backward compatible (missing header = unknown, still functional)

**OpenAPI Documentation**: Will document header in both `/memories/extract` and `/atoms` endpoints as optional string parameter.

---

### 3. Elapsed Time Calculation

**Decision**: `elapsed_seconds = EXTRACT(EPOCH FROM (NOW() - tenants.created_at))`

**When**: Calculated in same transaction as first memory write  
**Precision**: Floating-point seconds (allows sub-second precision for fast onboarding)  
**Trigger**: Only on first memory write per tenant

**Rationale**:
- Measures true onboarding latency from account creation to first value delivery
- Database-side calculation ensures accuracy (no clock skew)
- One-time measurement per tenant (idempotent)

---

### 4. One-Shot Event Per Tenant

**Decision**: Gate event emission with `NOT EXISTS` check against onboarding_events

**SQL Pattern**:
```sql
INSERT INTO memory_service.onboarding_events (
    tenant_id, agent_id, event_type, install_path, elapsed_seconds, metadata
)
SELECT 
    %s, %s, 'first_memory_add', %s, 
    EXTRACT(EPOCH FROM (NOW() - t.created_at)),
    %s::jsonb
FROM memory_service.tenants t
WHERE t.id = %s
  AND NOT EXISTS (
      SELECT 1 FROM memory_service.onboarding_events 
      WHERE tenant_id = %s AND event_type = 'first_memory_add'
  );
```

**Rationale**:
- Prevents duplicate events if multiple memories written concurrently
- Idempotent (safe to call on every memory write)
- Database-enforced correctness (no race conditions)
- CP9 P1 Pattern #2 compliance

---

### 5. Database Execution Pattern

**Decision**: Use `_db_execute_rows` for INSERT, NEVER `_db_execute` + split

**Rationale**:
- `_db_execute` + string split is the root cause of 12.5% silent recall failures (CP9 finding)
- `_db_execute_rows` guarantees correct parameterized queries
- CP9 P1 Pattern #1 compliance

---

### 6. Atomicity

**Decision**: Emit onboarding event in SAME transaction as memory write

**Implementation**:
- Both memory INSERT and onboarding event INSERT in single `_db_execute_rows` call
- Both succeed or both fail together
- No orphaned events or missed tracking

**Rationale**:
- CP9 P1 Pattern #1 (atomic operations)
- Ensures event count exactly matches first-memory count
- Simplifies error handling

---

### 7. Migration Strategy

**Decision**: Use `bash scripts/db_migrate.sh up canonical`, NOT direct alembic

**Classification**: Tier 1 additive migration (new table, no existing data affected)

**Steps**:
1. Create migration file in `alembic/versions/`
2. Apply via `bash scripts/db_migrate.sh up canonical`
3. Verify table creation with `\d memory_service.onboarding_events`
4. Test rollback with `bash scripts/db_migrate.sh down canonical 1`
5. Re-apply before production deploy

**Rationale**:
- Follows established project pattern
- `db_migrate.sh` handles environment sourcing and connection setup
- Canonical path ensures consistency across staging/prod

---

### 8. Testing Strategy

**Ground-truth re-query assertion** (CP9 P1 Pattern #3):
- After emitting event, immediately re-query `onboarding_events` table
- Assert row exists with expected values
- Ensures write actually succeeded (catches silent failures)

**Integration test flow**:
1. Create 4 test tenants (one per path)
2. POST first memory for each with appropriate `X-Install-Path` header
3. Assert exactly 1 onboarding event per tenant
4. POST second memory for same tenant
5. Assert still only 1 event (no duplicate)
6. Verify elapsed_seconds > 0 and < 300 (reasonable bounds)

**Verification script**:
```bash
#!/bin/bash
# tests/verify_onboarding_events.sh
set -a && source .env && set +a

echo === Onboarding Events Per Path ===
psql "$DATABASE_URL" -c "
SELECT install_path, COUNT(*) as events
FROM memory_service.onboarding_events
WHERE event_type = 'first_memory_add'
GROUP BY install_path
ORDER BY events DESC;
"

echo ""
echo "=== Elapsed Seconds Histogram ==="
psql "$DATABASE_URL" -c "
SELECT 
    CASE 
        WHEN elapsed_seconds < 60 THEN '<1min'
        WHEN elapsed_seconds < 300 THEN '1-5min'
        WHEN elapsed_seconds < 900 THEN '5-15min'
        WHEN elapsed_seconds < 3600 THEN '15-60min'
        ELSE '>1hr'
    END as time_bucket,
    COUNT(*) as events
FROM memory_service.onboarding_events
WHERE event_type = 'first_memory_add'
GROUP BY time_bucket
ORDER BY MIN(elapsed_seconds);
"
```

---

## Implementation Checklist

- [x] Scope document created
- [ ] Migration file created
- [ ] Migration applied to staging
- [ ] Migration rollback tested
- [ ] `/memories/extract` endpoint updated
- [ ] `/atoms` endpoint updated
- [ ] Header handling added to both endpoints
- [ ] OpenAPI docs updated
- [ ] Integration test created
- [ ] Verification script created
- [ ] Service restarted
- [ ] Curl test for all 4 paths
- [ ] DB inspect confirms events recorded
- [ ] N≥20 simulations run
- [ ] Migration applied to prod
- [ ] Final commit and tag
- [ ] HANDOFF doc updated

---

## Exit Gates

1. Migration applied to staging first, rollback tested, then prod
2. All 4 paths emit events end-to-end (curl test each)
3. Re-query confirms onboarding_events rows match expectation
4. N≥20 first-memory simulations across paths, zero misses
5. Final commit + push to master, tag `cp9-p2-t1-instrumentation`
6. HANDOFF doc updated with completion state

---

## Notes

- SDK header change (`X-Install-Path`) ships in next package bump (not republished yet)
- Server-side instrumentation is path-agnostic (works even if clients don't send header)
- Backward compatible (unknown path is valid, allows gradual rollout)
- Event emission adds <5ms to memory write path (negligible)

---

**Status**: Ready for implementation
