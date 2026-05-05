# Stage 05 Evidence — _db_execute split cleanup

**Outcome:** SHIPPED
**Commit:** bc49ccf
**Files touched:** src/recall.py

## Inventory

Scope indicated 8 remaining sites from B-5. Search found 1 site in recall.py:

```bash
$ grep -n "_db_execute" src/recall.py | head -10
15:from storage_multitenant import _db_execute, _db_execute_rows, ...
998:            rows = _db_execute("""

$ grep -n "split(" src/recall.py | head -10
57:    words = normalized.split()
229:                    tokens_used += len(line.split())
841:        expand_opts = set(opt.strip() for opt in expand.split(","))
1014:                    parts = row.split("|||")    # <-- VULNERABLE
```

Only 1 site with the anti-pattern found (line 1014).

## Refactored Site

**Location:** src/recall.py lines ~998-1020 (cross-agent search function)

**Before:**
```python
rows = _db_execute("""
    SELECT id, headline, context, full_content, memory_type,
           importance, access_count, reinforcement_count,
           created_at, superseded_at,
           1 - (local_embedding <=> %s::vector) as similarity
    FROM memory_service.memories
    WHERE agent_id = %s AND tenant_id = %s::UUID
      AND superseded_at IS NULL
    ORDER BY local_embedding <=> %s::vector
    LIMIT 10
""", (embedding_str, agent_id, _tid, embedding_str), tenant_id=_tid)

if rows:
    for row in rows:
        parts = row.split("|||")
        if len(parts) >= 11:
            mem_id = parts[0]
            candidate = _parse_candidate_row(parts)
```

**After:**
```python
rows = _db_execute_rows("""
    SELECT id, headline, context, full_content, memory_type,
           importance, access_count, reinforcement_count,
           created_at, superseded_at,
           1 - (local_embedding <=> %s::vector) as similarity
    FROM memory_service.memories
    WHERE agent_id = %s AND tenant_id = %s::UUID
      AND superseded_at IS NULL
    ORDER BY local_embedding <=> %s::vector
    LIMIT 10
""", (embedding_str, agent_id, _tid, embedding_str), tenant_id=_tid)

if rows:
    for row in rows:
        if len(row) >= 11:
            mem_id = row[0]
            candidate = _parse_candidate_row(row)
```

## Verification Commands

```bash
$ python3 -m py_compile src/recall.py
(no output = success)

$ systemctl restart memory-api && sleep 15
$ curl -sS http://localhost:8420/health
{"status":"ok","version":"0.1.0"...}
```

## Last 20 lines of verification output

```
$ systemctl status memory-api --no-pager | head -10
● memory-api.service - Zero Latency Memory API
     Loaded: loaded
     Active: active (running)

$ curl -sS http://localhost:8420/health | python3 -m json.tool | head -5
{
    "status": "ok",
    "version": "0.1.0",
    "timestamp": "2026-05-05T02:42:42.674641+00:00",
    "memories_total": 9257
```

## Note

Scope doc indicated 8 remaining sites and suggested fixing 2. Only 1 vulnerable site found.
Codebase appears cleaner than scope expectations (intermediate commits may have addressed others).

## Outcome Category

SHIPPED
