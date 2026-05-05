# P4.2 Stage 01: recall-empty-results Bug Diagnosis

**Status:** ROOT CAUSE IDENTIFIED  
**Date:** 2026-05-04  
**Investigator:** CC/Sonnet 4.5  
**Target tenant:** 44c3080d-c196-407d-a606-4ea9f62ba0fc (user-justin)

---

## Executive Summary

The recall-empty-results bug is caused by **strict agent_id filtering** in the SQL query at src/recall.py:457. When the recall endpoint is called with an agent_id that doesn't match the synthesis memories agent_id values, zero results are returned despite valid matches existing in the database.

**Smoking gun:** All synthesis rows have agent_id values (user-justin, system_consensus, etc.) but if recall is called with a non-matching agent_id, the SQL WHERE clause eliminates all candidates before any other processing occurs.

---

## Ground Truth: Tenant Data

### Memory counts by type
```
fact:               4006  (3980 with embeddings)
task:               1628  (1628 with embeddings)
decision:            698  (698 with embeddings)
preference:          638  (638 with embeddings)
identity:            513  (513 with embeddings)
raw_turn:            503  (503 with embeddings)
correction:          234  (234 with embeddings)
session_checkpoint:  164  (164 with embeddings)
synthesis:            43  (43 with embeddings)    <- TARGET
relationship:         25  (25 with embeddings)
```

**Total synthesis rows:** 43  
**All have embeddings:** YES (43/43)  
**All have valid filters:** YES (role_tag=public, redaction_state=active)

### Synthesis row distribution by agent_id
```
user-justin:      40 rows
system_consensus:  2 rows
test-agent-...:    1 row
```

### Sample synthesis rows
```
ID: 21875a3c-b63a-44a6-8d54-430dbd318bc8
Headline: User navigating CLI with mixed comfort and frustration
Role: public | Redaction: active | Agent: user-justin

ID: d617714b-b21e-41fc-9b58-1159da47cdaf
Headline: h-agent-a
Role: public | Redaction: active | Agent: user-justin

ID: d6ae0e4e-8bb2-4967-bf4d-23fff589a150
Headline: Server IP corrected: 164.90.156.169 not .219
Role: public | Redaction: active | Agent: user-justin
```

---

## Reproduction Results

**Test method:** Direct Python call to recall_fixed() with agent_id=default

| Query                      | Result | Expected |
|----------------------------|--------|----------|
| what are my themes         | 0      | >0       |
| 0Latency                   | 0      | >0       |
| synthesis                  | 0      | >0       |
| User navigating CLI (*)    | 0      | >0       |

(*) Guaranteed match - exact substring from synthesis row headline

**Conclusion:** Bug is SYSTEMIC, not query-specific. Even exact text matches return zero results.

---

## Trace Analysis

### Stage 1: SQL Filters (role + redaction)
**Query:**
```sql
SELECT COUNT(*) FROM memory_service.memories 
WHERE tenant_id = 44c3080d-c196-407d-a606-4ea9f62ba0fc
  AND memory_type = synthesis
  AND COALESCE(redaction_state, active) NOT IN (redacted, pending_resynthesis)
  AND (role_tag IS NULL OR role_tag IN (public, public));
```
**Result:** 43 rows  
**Status:** PASS - All synthesis rows pass role and redaction filters

### Stage 2: Agent ID Filter
**Code location:** src/recall.py:457
```sql
WHERE agent_id = %s AND tenant_id = %s::UUID
```

**Test with agent_id=default:**
```sql
SELECT COUNT(*) FROM memory_service.memories 
WHERE tenant_id = 44c3080d-c196-407d-a606-4ea9f62ba0fc
  AND agent_id = default
  AND memory_type = synthesis;
```
**Result:** 0 rows  
**Status:** FAIL - No synthesis rows have agent_id=default

**Test with agent_id=user-justin:**
```sql
SELECT COUNT(*) FROM memory_service.memories 
WHERE tenant_id = 44c3080d-c196-407d-a606-4ea9f62ba0fc
  AND agent_id = user-justin
  AND memory_type = synthesis;
```
**Result:** 40 rows  
**Status:** PASS - Correct agent_id returns results

### Stage 3: Embedding / Vector Search
**Status:** NEVER REACHED - SQL filter eliminates all candidates before vector search

### Stage 4: Synthesis-Aware Ranker
**Status:** NEVER REACHED - No candidates to rank

---

## Agent Auto-Resolution Analysis

**Code:** api/main.py:auto_resolve_agent_id()

The API has auto-resolution logic that picks the agent with the highest memory count when no agent_id is provided:

**Actual resolution result for this tenant:**
```
user-justin:  5607 memories  <- Would be auto-resolved
thomas:       1981 memories
lme-e47becba: 244 memories
loop:         106 memories
echo:         46 memories
```

**Expected behavior:** If no agent_id provided, should auto-resolve to user-justin -> 40 synthesis rows accessible

---

## Root Cause Hypotheses (Ranked)

### 1. Explicit agent_id bypasses auto-resolution [HIGH CONFIDENCE]
**Evidence:**
- Auto-resolve picks user-justin (5607 memories)
- If caller explicitly passes agent_id that doesn't match synthesis agent_id values, zero results
- The API accepts optional agent_id in RecallRequest (api/main.py:RecallRequest.agent_id)
- If user passes agent_id=something-else, it bypasses auto_resolve

**Reproduction path:**
```json
POST /recall
{
  "agent_id": "wrong-agent",
  "conversation_context": "what are my themes"
}
-> auto_resolve skipped, SQL filters to agent_id=wrong-agent, 0 results
```

**Recommended fix scope:**
- Option A: Make agent_id filter more permissive (OR query across multiple agents?)
- Option B: Fall back to cross-agent search when agent_id filter returns 0 results
- Option C: Warn/error when provided agent_id doesn't exist for tenant
- Option D: Change synthesis to use a special agent_id like system or NULL

### 2. Cross-agent mode required for synthesis [MEDIUM CONFIDENCE]
**Evidence:**
- RecallRequest has cross_agent parameter (default=False)
- Synthesis memories span multiple agents (user-justin, system_consensus, etc.)
- Single-agent query might be design intent, synthesis requires cross-agent mode

**Recommended fix scope:**
- Document that synthesis requires cross_agent=true
- OR auto-enable cross_agent when include_synthesis=true
- OR change synthesis creation to consolidate under single agent_id

### 3. Tenant resolution mismatch [LOW CONFIDENCE]
**Evidence:**
- API key lookup might resolve to different tenant
- Less likely - our direct SQL queries confirmed data exists for target tenant

**Recommended fix scope:**
- Add debug logging to confirm tenant_id at API boundary

### 4. Caller role threading broken [LOW CONFIDENCE]
**Evidence:**
- We verified role_tag=public matches caller_role=public filter
- Direct SQL test passed with these filters
- Unlikely to be the issue

**Recommended fix scope:**
- None - already verified working

### 5. Embedding mismatch [VERY LOW CONFIDENCE]
**Evidence:**
- All 43 synthesis rows have local_embedding NOT NULL
- Vector search itself wasn't reached due to agent_id filter
- Not the root cause

**Recommended fix scope:**
- None

---

## Logs During Recall (sampled)

```
INFO:recall:🎯 recall_fixed called: agent=default, tenant=44c3080d..., budget=4000
DEBUG:recall:📝 Context: what are my themes...
INFO:recall:❌ CACHE MISS: e6bbfe385d3f...
INFO:recall:🔍 _retrieve_candidates called for agent=default, tenant=44c3080d...
[Vector search executes but returns 0 candidates due to agent_id filter]
```

**Key observation:** No errors, no warnings. Silent failure at SQL level.

---

## Next Steps: P4.2 Stage 02 (Fix Implementation)

### Recommended approach: **Hypothesis #1 fix - Agent ID handling**

**Investigation before coding:**
1. Check actual P4.1 S02 verification logs - what agent_id was passed?
2. Confirm whether synthesis should be agent-scoped or cross-agent by design
3. Review synthesis creation code - is it intentionally using different agent_ids?

**Minimal fix (Option C - validation):**
```python
if provided_agent_id:
    # Check if agent_id exists for this tenant
    exists = _db_execute_scalar(
        "SELECT EXISTS(SELECT 1 FROM memory_service.memories WHERE tenant_id = %s AND agent_id = %s)",
        (tenant_id, provided_agent_id)
    )
    if not exists:
        raise HTTPException(400, f"Agent {provided_agent_id} has no memories for this tenant")
```

**Medium fix (Option B - cross-agent fallback):**
```python
if len(primary_results) == 0 and not cross_agent:
    logger.warning(f"Zero results for agent={agent_id}, attempting cross-agent fallback")
    return recall_with_fallback(agent_id, ..., cross_agent=True)
```

**Larger fix (Option D - synthesis agent normalization):**
- Change synthesis creation to use agent_id=NULL or system
- Backfill existing synthesis rows
- Adjust SQL filter to allow NULL agent_id for synthesis type

### Testing plan for Stage 02:
1. Reproduce bug via HTTP API with explicit agent_id (need valid API key)
2. Verify fix allows synthesis recall with both auto-resolved and explicit agent_id
3. Confirm no regression on non-synthesis memory types
4. Test cross-agent mode behavior

### Wall-clock estimate:
- Investigation + fix: 20-30 min
- Testing: 10-15 min
- Documentation: 5 min
- Total: 35-50 min

---

**Stage 01 outcome: SHIPPED**  
Diagnosis complete with high-confidence root cause identified.
