# Stage 02 Evidence - Hierarchical descent: expand=evidence

**Commit SHA:** 61574c2

**Outcome:** SHIPPED

## Files Touched
- api/main.py - Added expand parameter to RecallRequest, RecallResponse includes optional recall_details
- src/recall.py - Added expand parameter threading, implemented evidence expansion logic for synthesis memories

## Changes
1. RecallRequest now accepts optional `expand` query parameter (comma-separated: "evidence", "cluster")
2. RecallResponse includes `recall_details` field when expand is used (null otherwise)
3. recall_fixed implements evidence expansion: when expand="evidence", synthesis memories include `evidence` array containing their parent/source memories
4. Evidence fetched in single batched SQL query (not N+1)

## Verification Commands

### 1. Parse checks
```bash
python3 -c "import ast; ast.parse(open('api/main.py').read())"
python3 -c "import ast; ast.parse(open('src/recall.py').read())"
```

### 2. Service restart
```bash
systemctl restart memory-api
sleep 60
curl -s http://localhost:8420/health
```

### 3. Functional tests
```bash
# Without expand - recall_details should be null
curl -s .../recall -d '{"conversation_context": "test", "agent_id": "..."}' | jq '.recall_details'

# With expand - recall_details should be array
curl -s .../recall -d '{"conversation_context": "test", "agent_id": "...", "expand": "evidence"}' | jq '.recall_details | type'
```

## Verification Output (last 20 lines)

```
# Test without expand
null

# Test with expand
"array"
```

## Health Check
```json
{"status":"ok","version":"0.1.0","timestamp":"2026-05-05T00:13:33.755100+00:00","memories_total":9113,"db_pool":{"pool_min":1,"pool_max":5},"redis":"connected"}
```

## Error Log Check
No errors found (grep exit code 1 = no matches)

## Summary
- expand parameter successfully added to /recall endpoint
- recall_details included in response when expand is set
- Evidence expansion logic implemented for synthesis memories
- Batched query prevents N+1 problem
- Clean response shape: null when expand not used, detailed array when used
