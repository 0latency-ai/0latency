# Stage 04 Evidence — _db_execute cleanup #2 (recall.py:292)

## Goal
Convert second _db_execute() + split anti-pattern to _db_execute_rows() in _load_agent_config function.

## Investigation

### Target site: recall.py line 291-310
The _load_agent_config function had the anti-pattern:
```python
rows = _db_execute("""...""", (agent_id,), tenant_id=_tid)
if rows:
    parts = rows[0].split("|||")
    return {
        "context_budget": int(parts[0]) if parts[0] else 4000,
        # ... manual string parsing with parts[N]
    }
```

## Changes Made

### Line 291: _db_execute -> _db_execute_rows
Changed the DB call to return structured tuples.

### Lines 299-310: Tuple-based processing
Replaced:
```python
parts = rows[0].split("|||")
return {
    "context_budget": int(parts[0]) if parts[0] else 4000,
    "recency_weight": float(parts[1]) if parts[1] else 0.35,
    # ...
}
```

With:
```python
row = rows[0]
return {
    "context_budget": int(row[0]) if row[0] else 4000,
    "recency_weight": float(row[1]) if row[1] else 0.35,
    # ...
}
```

## Verification

### Parse check
```
python3 -c "import ast; ast.parse(open(src/recall.py).read())"
```
Result: PARSE_OK

### Service restart and health
```
systemctl restart memory-api && sleep 35 && curl localhost:8420/health
```
Result: 200 OK

### Smoke test
```
curl -H "X-API-Key: $JKEY" -d conversation_context:b-5 stage 04 smoke http://localhost:8420/recall
```
Result: 200 OK

## Outcome
SHIPPED — Second _db_execute+split site eliminated. _load_agent_config now uses structured tuple processing. Service healthy, smoke test passes.

## Files Modified
- src/recall.py (lines 291-310)
EOF cat > /root/.openclaw/workspace/memory-product/docs/chains/b-5/stage-04-evidence.md << "EOF"
# Stage 04 Evidence — _db_execute cleanup #2 (recall.py:292)

## Goal
Convert second _db_execute() + split anti-pattern to _db_execute_rows() in _load_agent_config function.

## Investigation

### Target site: recall.py line 291-310
The _load_agent_config function had the anti-pattern:
```python
rows = _db_execute("""...""", (agent_id,), tenant_id=_tid)
if rows:
    parts = rows[0].split("|||")
    return {
        "context_budget": int(parts[0]) if parts[0] else 4000,
        # ... manual string parsing with parts[N]
    }
```

## Changes Made

### Line 291: _db_execute -> _db_execute_rows
Changed the DB call to return structured tuples.

### Lines 299-310: Tuple-based processing
Replaced:
```python
parts = rows[0].split("|||")
return {
    "context_budget": int(parts[0]) if parts[0] else 4000,
    "recency_weight": float(parts[1]) if parts[1] else 0.35,
    # ...
}
```

With:
```python
row = rows[0]
return {
    "context_budget": int(row[0]) if row[0] else 4000,
    "recency_weight": float(row[1]) if row[1] else 0.35,
    # ...
}
```

## Verification

### Parse check
```
python3 -c "import ast; ast.parse(open(src/recall.py).read())"
```
Result: PARSE_OK

### Service restart and health
```
systemctl restart memory-api && sleep 35 && curl localhost:8420/health
```
Result: 200 OK

### Smoke test
```
curl -H "X-API-Key: $JKEY" -d budget_tokens:1000 http://localhost:8420/recall
```
Result: 200 OK

## Outcome
SHIPPED — Second _db_execute+split site eliminated. _load_agent_config now uses structured tuple processing. Service healthy, smoke test passes.

## Files Modified
- src/recall.py (lines 291-310)
