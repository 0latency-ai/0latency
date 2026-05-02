# CP8 Phase 2 Task 9 — Autonomous Scope

**Task:** Add `GET /memories/{id}/source` endpoint.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** `ab5553b` (Track 1 — verbatim raw_turn preservation).
**Estimated wall-clock:** 60-120 min for CC.

---

## Goal

One sentence: Given any memory ID, return the original verbatim text — directly for raw_turn or atom memories, via parent_memory_ids chain for derived memories (checkpoints, syntheses).

This is the user-facing proof point that 0Latency does not summarize away facts. It's also the substrate for the nightly contract test (Task 11) and the CLI verb (Task 10).

---

## In scope

**Files to modify:**
- `api/main.py` — add the new route handler
- `tests/test_source_endpoint.py` — NEW file, integration tests

**Files to read (do not modify):**
- `src/extraction.py` — to confirm raw_turn write contract
- `src/storage_multitenant.py` — to find the existing memory-fetch helpers
- `docs/ENDPOINTS.md` — to know the format for documenting the new endpoint

**Database:** Read-only. Uses existing `memory_service.memories` and `memory_service.raw_turns` tables. No migrations.

---

## Out of scope (DO NOT TOUCH)

- Any migration file (`migrations/*.sql`)
- `extract_memories()` or any extraction logic
- Recall path (`/recall`, `/memories/recall`)
- Synthesis writer (Task 8a, separate Track)
- The CLI (Task 10 — separate scope doc)
- The nightly contract test (Task 11 — separate scope doc)
- Any file in `src/storage_*.py` (read-only)
- `docs/ENDPOINTS.md` updates (manual review pass post-task)
- Any change to authentication/authorization layer

---

## Endpoint contract

```
GET /memories/{memory_id}/source
Headers: X-API-Key: <tenant_api_key>

Response 200:
{
  "memory_id": "<uuid>",
  "memory_type": "raw_turn" | "fact" | "preference" | "synthesis" | ...,
  "source_type": "verbatim" | "derived",
  "source_text": "<original raw text>",  // present when source_type=verbatim
  "source_chain": [                      // present when source_type=derived
    {
      "memory_id": "<uuid>",
      "memory_type": "raw_turn",
      "source_text": "<verbatim text>"
    },
    ...
  ],
  "trace": {
    "raw_turn_ids": ["<uuid>", ...],     // resolved parent raw_turns
    "depth": <int>                       // chain traversal depth
  }
}

Response 404: memory_id not found OR not owned by tenant
Response 401: missing/invalid X-API-Key
Response 422: memory_id not a valid UUID
```

**Resolution rules:**
1. If `memory_type == "raw_turn"`: return `source_type=verbatim`, `source_text` = the row's `full_content`. `source_chain` omitted. `trace.raw_turn_ids = [memory_id]`, `depth=0`.
2. If `memory_type` ∈ {"fact", "preference", "correction", "identity", ...} (atom-level types): treat as `source_type=derived`. Read `metadata.parent_memory_ids` (jsonb array). For each parent UUID, fetch the row. If parent is `raw_turn`, include in `source_chain` with its `full_content`. If parent is anything else, recurse (max depth 5). `trace.raw_turn_ids` collects all raw_turn UUIDs found at any depth.
3. If `memory_type == "synthesis"` or `memory_type == "session_checkpoint"`: same recursive logic; chain may be deeper.
4. If `metadata.parent_memory_ids` missing/empty: return `source_type=derived` with empty `source_chain` and `trace.depth=0`. This is legacy data pre-Track 1.
5. **Tenant isolation:** every fetched row must have `tenant_id = <calling tenant>`. Cross-tenant returns 404, never 403.

**Recursion safety:**
- Hard depth cap: 5. If exceeded, return what's collected so far with `trace.depth=5` and a `trace.truncated=true` flag.
- Cycle detection: maintain a visited-set of memory_ids; skip already-visited.

---

## Inputs at start

- HEAD commit: `__PENDING__`
- Working tree: in-scope files clean. Pre-existing untracked files (api/analytics.py.bak-tupleidx, api/main.py.backup, scripts/seed_*.py, smoke_test.py, memory-product-staging/) and submodule churn are PARKED and tolerated. Halt only if api/main.py or tests/test_source_endpoint.py is dirty at start.
- Existing fixtures: a known raw_turn ID `9deed596-57f4-47fe-b788-1c640f9f178b` exists for tenant `44c3080d-c196-407d-a606-4ea9f62ba0fc` (from tonight's smoke). An atom linked to it: `002e58b3-2e69-4a3d-9548-2a2a7fbc78dc`.

---

## Steps

### Step 1 — Pre-flight
```bash
cd /root/.openclaw/workspace/memory-product
git status --porcelain -- api/main.py tests/ # GATE: must print nothing (in-scope files only)
git log -1 --oneline               # confirm: __PENDING__ (Step 1 hardening on top of ab5553b Track 1)
ls /root/.openclaw/workspace/memory-product/CP*-BLOCKED.md 2>/dev/null  # GATE: must be empty (no halts pending)
```

**HALT** if `git status --porcelain -- api/main.py tests/` prints anything OR HEAD ≠ `__PENDING__` OR any blocked notes exist.

### Step 2 — Read context
```bash
sed -n '1,50p' src/extraction.py             # confirm raw_turn write shape
grep -n "metadata.*parent_memory_ids" src/extraction.py
grep -n "fetch_memory\|get_memory_by_id" src/storage_multitenant.py | head -10
grep -n "@app\.\(get\|post\).*\"/memories" api/main.py | head -10  # find existing /memories routes for style consistency
```

No gate. CC produces a 5-line written summary in its scratchpad of: where parent_memory_ids is written, what fetch helpers exist, what auth pattern existing /memories routes use.

### Step 3 — Add endpoint to `api/main.py`

Locate the end of the existing `/memories` route block. Add the new handler. Use existing patterns:
- Auth via the same `X-API-Key` dependency function the other `/memories` routes use.
- DB access via `_db_execute_rows(query, params, tenant_id=tenant["id"])`.
- Error handling: explicit 404 for not-found, 422 for malformed UUID.
- No new imports unless absolutely required; reuse existing.

Implementation must include:
- A helper function `_resolve_source_chain(memory_id, tenant_id, visited, depth)` that returns the chain.
- The route handler `get_memory_source(memory_id, tenant)` that calls the helper and shapes the response.

**Style:** match existing handlers. Type hints on function signatures. Logging at INFO level for successful fetches, WARNING for 404s.

### Step 4 — Compile check
```bash
cd /root/.openclaw/workspace/memory-product
python3 -c "import ast; ast.parse(open('api/main.py').read())"  # GATE: must exit 0
```

**HALT** on syntax error. Re-read the diff, attempt one fix, then halt if still broken.

### Step 5 — Restart and verify import

```bash
systemctl restart memory-api
sleep 30                           # cold start with sentence-transformers
systemctl is-active memory-api     # GATE: must print "active"
journalctl -u memory-api --since "1 minute ago" --no-pager | grep -E "ERROR|Traceback" | grep -v "analytics_events"  # GATE: empty (modulo known issue)
```

**HALT** on inactive OR any new error in journal.

### Step 6 — Functional gates (G1)

Source `.env` and bashrc first:

```bash
set -a && source .env && set +a
source ~/.bashrc
```

**Gate 6a — raw_turn fetch:**
```bash
curl -sS http://localhost:8420/memories/9deed596-57f4-47fe-b788-1c640f9f178b/source \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  | python3 -c "
import sys, json
r = json.load(sys.stdin)
assert r['memory_type'] == 'raw_turn', f'expected raw_turn, got {r[\"memory_type\"]}'
assert r['source_type'] == 'verbatim', f'expected verbatim, got {r[\"source_type\"]}'
assert 'track1-commit-final' in r['source_text'], f'source_text missing sentinel: {r[\"source_text\"][:100]}'
assert r['trace']['depth'] == 0, f'expected depth 0, got {r[\"trace\"][\"depth\"]}'
print('G6a PASS')
"
```

**Gate 6b — atom fetch with parent chain:**
```bash
curl -sS http://localhost:8420/memories/002e58b3-2e69-4a3d-9548-2a2a7fbc78dc/source \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  | python3 -c "
import sys, json
r = json.load(sys.stdin)
assert r['source_type'] == 'derived', f'expected derived, got {r[\"source_type\"]}'
assert len(r['source_chain']) >= 1, f'source_chain empty: {r}'
assert r['source_chain'][0]['memory_type'] == 'raw_turn'
assert len(r['trace']['raw_turn_ids']) >= 1
print('G6b PASS')
"
```

**Gate 6c — 404 on bad ID:**
```bash
curl -sS -o /dev/null -w "%{http_code}" \
  http://localhost:8420/memories/00000000-0000-0000-0000-000000000000/source \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  | grep -q '^404$' && echo 'G6c PASS'
```

**Gate 6d — 422 on malformed UUID:**
```bash
curl -sS -o /dev/null -w "%{http_code}" \
  http://localhost:8420/memories/not-a-uuid/source \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  | grep -qE '^(422|400)$' && echo 'G6d PASS'
```

**Gate 6e — 401 on missing key:**
```bash
curl -sS -o /dev/null -w "%{http_code}" \
  http://localhost:8420/memories/9deed596-57f4-47fe-b788-1c640f9f178b/source \
  | grep -qE '^(401|403|422)$' && echo 'G6e PASS'
```

**HALT** if any gate fails twice in a row.

### Step 7 — Write integration tests

Create `tests/test_source_endpoint.py` with 6 tests covering:
1. raw_turn fetch returns verbatim
2. atom with parent_memory_ids returns chain
3. atom with empty/missing parent_memory_ids returns empty chain (legacy data)
4. 404 on non-existent UUID
5. 422 on malformed UUID
6. 401 on missing X-API-Key
7. Tenant isolation: fetching another tenant's memory returns 404

Use pytest. Use `requests` against `http://localhost:8420`. Mark tests requiring fixtures with `@pytest.mark.integration`.

### Step 8 — Test gate (G3)

```bash
cd /root/.openclaw/workspace/memory-product
pytest tests/test_source_endpoint.py -v --tb=short 2>&1 | tee /tmp/test-output.txt
grep -q "passed" /tmp/test-output.txt && ! grep -q "failed" /tmp/test-output.txt && echo 'G8 PASS'
```

**HALT** on any test failure.

### Step 9 — Commit

```bash
cd /root/.openclaw/workspace/memory-product
git add api/main.py tests/test_source_endpoint.py
git status                         # GATE: only those 2 files staged
git diff --cached --stat
```

Commit message (write to `/tmp/cp9-commit-msg.txt` first):

```
CP8 Phase 2 Task 9: GET /memories/{id}/source endpoint

User-facing proof point that 0Latency does not summarize away facts.
Returns verbatim source text for raw_turn memories, parent-chain
resolution for atom and derived memories.

Endpoint contract:
- GET /memories/{memory_id}/source
- 200: {memory_id, memory_type, source_type, source_text|source_chain, trace}
- 404: not found or cross-tenant
- 422: malformed UUID
- 401: missing X-API-Key

Resolution rules:
- raw_turn → verbatim, source_text = full_content
- atom/derived → derived, source_chain = recursively-resolved parents
- Max depth 5, cycle detection via visited-set
- Tenant isolation enforced; cross-tenant returns 404

Verification receipts:
[CC fills in actual outputs from gates 6a-6e and test run]

Files: api/main.py (+N lines, 1 new route + 1 helper),
       tests/test_source_endpoint.py (NEW, 7 tests)
```

```bash
git commit -F /tmp/cp9-commit-msg.txt
git log -1 --stat
git push origin master
```

**Final gate:** `git push` exit code 0.

---

## Halt conditions (specific to this task)

In addition to the protocol's standard halts:

1. **Existing fixture data missing.** If gates 6a/6b can't find the seed UUIDs, halt — the test fixtures changed and the scope doc is stale.
2. **`metadata` jsonb structure unexpected.** If `parent_memory_ids` lives somewhere other than `metadata.parent_memory_ids`, halt and write the discovered shape into the BLOCKED note.
3. **Cycle detected in real data.** If a memory_id loops back to itself in the chain, halt and dump the cycle path.
4. **Production query > 500ms.** If recursive chain resolution is unexpectedly slow on real data, halt — needs index work, out of scope for this task.

---

## Halt note format

If halting, write `/root/.openclaw/workspace/memory-product/CP8-P2-T9-BLOCKED.md`:

```markdown
# CP8 Phase 2 Task 9 — BLOCKED

**Halted at step:** <step number>
**Trigger:** <which halt condition>
**HEAD at halt:** <git rev-parse HEAD>

## What CC tried
[Actual commands run and outputs]

## What went wrong
[Specific error, missing fixture, unexpected schema, etc.]

## State of repo
[git status output]

## Recommended next move
[CC's best guess at what should happen next]
```

Do NOT stage or commit any work-in-progress on halt.

---

## Definition of done

All of:

1. New route `GET /memories/{id}/source` exists in `api/main.py`.
2. All 5 gates in Step 6 PASS.
3. All 7 tests in `tests/test_source_endpoint.py` PASS.
4. Single commit on master pushed to remote.
5. Commit message contains real verification receipts (not placeholders).
6. No `CP8-P2-T9-BLOCKED.md` exists.
7. `journalctl -u memory-api --since "<run start>"` shows no new ERRORs (pre-existing analytics_events errors are tolerated).
