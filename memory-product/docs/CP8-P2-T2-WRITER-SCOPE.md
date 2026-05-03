# CP8 Phase 2 Task 2 — Autonomous Scope: Synthesis Writer (with T7 audit & rate-limit-aware writes)

**Task:** Build `synthesis/writer.py` — the synchronous single-agent synthesis writer that runs against a cluster, calls Haiku, validates, and writes one synthesis row plus its audit trail.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** Chain A's last commit (T8). Imports T1's `find_clusters` and T4's `synthesis_jobs`.
**Estimated wall-clock:** 30–60 min for CC.
**Chain position:** Chain B, task 1 of 4 (**T2** → T3 → T5+T6 → T11-fix).

**Note:** This scope folds in T7 ("audit-and-rate-limit-aware writes") because T7 is implicit in the writer's behavior — the writer either calls `tier_gates.check_synthesis_quota` and `audit.write` or it doesn't. There is no separate T7 task.

---

## Goal

One sentence: Given a cluster of atom IDs and a tenant context, produce one synthesis memory row in `memory_service.memories` with full provenance, an audit log entry, and rate-limit accounting — synchronously, no async wrapper.

T2 is the smallest end-to-end path that proves a real synthesis row can be written under the cost ceiling, with all of the Phase 1 plumbing actually wired up.

---

## In scope

**Files to create:**
- `src/synthesis/writer.py` — NEW
- `src/synthesis/prompts/single_agent_v1.txt` — NEW (the synthesis prompt template)
- `tests/synthesis/test_writer.py` — NEW

**Files to read (do not modify):**
- `src/synthesis/clustering.py` — for `Cluster` dataclass and `find_clusters` signature
- `src/synthesis/policy.py` — for policy DSL access
- `src/synthesis/state_machine.py` — for redaction state enum (writer always writes `active`)
- `src/tier_gates.py` — for `check_synthesis_quota` and rate-limit increment functions (already wired per audit)
- `src/storage_multitenant.py` — for `_db_execute_rows` and tenant connection helpers
- `src/extraction.py` — to confirm Anthropic client construction pattern (Haiku model name, env var for key)

**Database:** Writes one row to `memory_service.memories` per synthesis. Writes one row to `memory_service.synthesis_audit_events` per synthesis. Updates `memory_service.synthesis_rate_limits` counters. No migrations.

---

## Out of scope (DO NOT TOUCH)

- Any migration file
- `src/synthesis/clustering.py`, `jobs.py`, `policy.py`, `redaction.py`, `state_machine.py` — read-only
- `tier_gates.py` — read-only; do NOT modify rate-limit logic, only call existing functions
- `src/extraction.py` — do NOT modify the extraction path
- `recall.py` — synthesis-aware recall is Phase 4, not here
- Multi-agent consensus — that's Phase 3
- Webhook firing on synthesis_written events — Phase 5
- The `memory_synthesize` MCP tool — Phase 4
- Any change to `mcp-server/` or extension repos
- **Source-quote validation** — that's T3; this writer accepts a `validate_callback` parameter and calls it, but T3 implements the actual validator
- **Manual trigger endpoint `POST /synthesis/run`** — that's T5
- **Cron schedule** — that's T6
- **Async job wrapping** — sync-first is the design; T4's jobs module exists but the writer doesn't wrap itself in a job; the caller (T5/T6) does

---

## Function contract

```python
def synthesize_cluster(
    cluster: Cluster,
    tenant_id: str,
    agent_id: str,
    role_tag: str = "public",
    prompt_version: str = "single_agent_v1",
    llm_model: Optional[str] = None,  # default: per-tier from tier_gates
    validate_callback: Optional[Callable[[str, list[uuid.UUID]], ValidationResult]] = None,
    dry_run: bool = False,
) -> SynthesisResult:
    """
    Run one synthesis attempt against a single cluster.

    Sequence (atomic for accounting; writes are individually transactional):
      1. Pre-flight: tier_gates.check_synthesis_quota(tenant_id) — abort + audit if blocked
      2. Pre-flight: load atoms, separate pinned from regular, fail if cluster is empty
      3. LLM call: format prompt, call Haiku/Sonnet per tier, capture token counts
      4. Parse + schema-validate response
      5. Source-quote validation via validate_callback (T3 plugs in here)
      6. If dry_run: return SynthesisResult with would_write=True, no DB writes
      7. Write synthesis row (memory_type='synthesis')
      8. Write audit event (event_type='synthesis_written')
      9. Increment rate-limit counters
     10. Return SynthesisResult
    """
```

Where:

```python
@dataclass
class SynthesisResult:
    success: bool
    synthesis_id: Optional[uuid.UUID]
    audit_event_id: Optional[uuid.UUID]
    cluster_size: int
    source_memory_ids: list[uuid.UUID]      # what the LLM cited (evidence chain)
    parent_memory_ids: list[uuid.UUID]      # full cluster (cluster edge)
    tokens_used: int
    llm_model: str
    rejected_reason: Optional[str]          # rate_limited | validation_failed | empty_cluster | llm_error
    dry_run: bool
```

```python
@dataclass
class ValidationResult:
    valid: bool
    cited_ids_in_source_set: list[uuid.UUID]
    cited_ids_NOT_in_source_set: list[uuid.UUID]   # hallucinations
    failure_reason: Optional[str]
```

**Rate-limit handling (T7 fold-in):**

- Step 1 calls `tier_gates.check_synthesis_quota(tenant_id, tier=None)` — let `tier_gates` resolve the tier.
- If quota exceeded: insert `synthesis_audit_events(event_type='rate_limit_blocked', target_memory_id=NULL, actor=agent_id, event_payload={'cluster_size': N, 'reason': 'quota_exceeded'})`. Return `SynthesisResult(success=False, rejected_reason='rate_limited')`. **Do not** call the LLM.
- Step 9 calls the existing `tier_gates` increment function (per the audit, the UPDATE statements are in `tier_gates.py:219` and `:230`).

**Audit event payload (T7 fold-in):**

```json
{
  "cluster_id": "<deterministic-hash-of-cluster-ids>",
  "cluster_size": 7,
  "prompt_version": "single_agent_v1",
  "llm_model": "claude-haiku-4-5-20251001",
  "tokens_used": 1842,
  "input_tokens": 1620,
  "output_tokens": 222,
  "source_memory_ids_cited": ["uuid1", "uuid2", ...],
  "validation_passed": true
}
```

**LLM model selection:**

- `tier_gates.get_synthesis_model(tier)` returns `"haiku"` for Scale/Pro, `"sonnet"` for Enterprise.
- Map to actual Anthropic model strings: `"haiku"` → `"claude-haiku-4-5-20251001"`, `"sonnet"` → `"claude-sonnet-4-6"`.
- Free tier never reaches step 3 — quota check kicks at step 1.

**Prompt template** (`src/synthesis/prompts/single_agent_v1.txt`):

```
You are synthesizing related memories into a single higher-level summary memory.

You will receive {cluster_size} atom memories. Your job:
1. Identify the common theme.
2. Write a 2–4 sentence synthesis that captures it.
3. Cite the atom IDs you draw from. Cite each ID like [src:<uuid>].

Rules:
- Cite ONLY IDs from the provided set. Inventing IDs invalidates the synthesis.
- Quote sparingly. Paraphrase preferred.
- The synthesis is itself a memory; future agents will recall it. Write it crisply.
- Return ONLY a JSON object with shape:
  {
    "headline": "<8 words max>",
    "synthesis": "<2-4 sentences>",
    "cited_atom_ids": ["<uuid>", "<uuid>", ...]
  }

Atom set:
{atoms_block}
```

The `{atoms_block}` is rendered as `[<id>] <headline>: <full_content>` per atom, separated by blank lines.

**Synthesis row INSERT shape:**

```sql
INSERT INTO memory_service.memories (
    tenant_id, agent_id, memory_type,
    headline, context, full_content,
    source_memory_ids, role_tag, redaction_state, confidence_score,
    synthesis_prompt_version, synthesis_version,
    is_pinned, embedding,
    metadata
) VALUES (
    %s, %s, 'synthesis',
    %s, %s, %s,                                    -- headline, context (cluster signature), full_content
    %s::uuid[],                                    -- source_memory_ids (evidence chain only)
    %s,                                            -- role_tag
    'active',                                      -- redaction_state
    %s,                                            -- confidence_score
    %s, %s,                                        -- prompt_version, synthesis_version (1)
    FALSE,                                         -- is_pinned
    %s::vector,                                    -- embedding (compute via existing helper)
    jsonb_build_object('parent_memory_ids', %s)    -- cluster edge in metadata jsonb
) RETURNING id;
```

**Decision 1 reminder:** `source_memory_ids` (top-level uuid[]) is the **evidence chain** — only IDs the LLM cited. `parent_memory_ids` (inside `metadata` jsonb) is the **cluster edge** — every atom in the cluster. They are deliberately different.

**Confidence score (initial heuristic):** `len(cited_ids) / len(cluster.memory_ids)` — what fraction of the cluster the LLM actually drew from. Phase 5 replaces this with calibration.

---

## Steps

### Step 1 — Confirm `tier_gates` API surface

```bash
cd /root/.openclaw/workspace/memory-product
grep -n "^def \|def check_synthesis_quota\|def increment_\|def get_synthesis_model" src/tier_gates.py
```

**Gate G2:** functions `check_synthesis_quota`, an increment-counter function, and a model-selector function are all present. If any is missing, **halt** — Phase 1 was incomplete and writing the writer would shadow that.

### Step 2 — Write `src/synthesis/prompts/single_agent_v1.txt`

Per template above. No code, just the prompt.

### Step 3 — Implement `src/synthesis/writer.py`

Per function contract. Module docstring documents:
- Synchronous design (T4's jobs module is a wrapper, not the writer's concern)
- Source-quote validation via callback (T3 plugs in)
- The `dry_run` flag for T5's preview-impact use case
- Rate-limit pre-flight + post-flight increment pattern
- Decision 1 (`source_memory_ids` vs `parent_memory_ids` semantics)

Use `_db_execute_rows`. Use the existing Anthropic client construction from `extraction.py` (do not invent a new pattern).

For embedding generation, use whatever helper `extraction.py` uses for atom embeddings. If the helper isn't a clean function, **halt** and write to BLOCKED.

### Step 4 — Implement `tests/synthesis/test_writer.py`

Nine tests:
1. `test_synthesize_cluster_writes_one_row` — happy path; verify row exists, has correct memory_type, populated source_memory_ids, populated parent_memory_ids in metadata
2. `test_synthesis_audit_event_written` — verify one `synthesis_written` row in synthesis_audit_events with correct payload shape
3. `test_rate_limit_increment_called` — fixture tenant; check counters before and after; assert delta
4. `test_quota_exceeded_blocks_writes` — fixture tenant with quota at zero; verify no row written, audit event has `rate_limit_blocked` type, return value has `rejected_reason='rate_limited'`
5. `test_dry_run_writes_nothing` — same cluster, dry_run=True; verify zero rows added across memories, audit, rate_limits
6. `test_validation_failure_blocks_write` — pass a callback that returns `valid=False`; verify no synthesis row, audit captures failure reason
7. `test_empty_cluster_returns_failure` — pass a Cluster with empty memory_ids; verify clean failure, no LLM call attempted
8. `test_source_memory_ids_subset_of_parent` — happy path again; explicitly assert `source_memory_ids ⊆ parent_memory_ids`
9. `test_pinned_atom_in_cluster_handled` — cluster contains 1 pinned atom; verify pinned atom is loaded into prompt as pinned context (not removed) but not written into source_memory_ids unless cited

Mark all `@pytest.mark.integration`. Use real DB. Mock the Anthropic call where possible to avoid burning prod credits during tests — set up a fixture that returns canned JSON for the Haiku response.

### Step 5 — Test gate (G3)

```bash
pytest tests/synthesis/test_writer.py -v --tb=short 2>&1 | tee /tmp/t2-test-output.txt
grep -q "passed" /tmp/t2-test-output.txt && ! grep -q "failed" /tmp/t2-test-output.txt && echo 'T2 GATE PASS'
```

**HALT** on any test failure.

### Step 6 — Smoke test on real cluster

```bash
python3 -c "
from src.synthesis.clustering import find_clusters
from src.synthesis.writer import synthesize_cluster
clusters = find_clusters(
    tenant_id='44c3080d-c196-407d-a606-4ea9f62ba0fc',
    agent_id='user-justin',
)
if not clusters:
    print('NO CLUSTERS — halt')
    exit(1)
result = synthesize_cluster(
    cluster=clusters[0],
    tenant_id='44c3080d-c196-407d-a606-4ea9f62ba0fc',
    agent_id='user-justin',
    dry_run=True,
)
print(f'dry_run result: success={result.success} cluster_size={result.cluster_size}')
print(f'  source_memory_ids: {len(result.source_memory_ids)} cited')
print(f'  tokens_used: {result.tokens_used}')
"
```

**Gate G2:** dry-run smoke succeeds; `tokens_used > 0`; `len(source_memory_ids) > 0`. If any of these fail, halt — the writer cannot produce honest receipts for the commit.

### Step 7 — Smoke test, write-mode, ONE real synthesis

```bash
python3 -c "
from src.synthesis.clustering import find_clusters
from src.synthesis.writer import synthesize_cluster
clusters = find_clusters(
    tenant_id='44c3080d-c196-407d-a606-4ea9f62ba0fc',
    agent_id='user-justin',
)
result = synthesize_cluster(
    cluster=clusters[0],
    tenant_id='44c3080d-c196-407d-a606-4ea9f62ba0fc',
    agent_id='user-justin',
    dry_run=False,
)
print(f'WROTE synthesis_id={result.synthesis_id}')
print(f'  audit_event_id={result.audit_event_id}')
print(f'  cluster_size={result.cluster_size} cited={len(result.source_memory_ids)}')
"
```

**Gate G2:** synthesis_id is a real UUID; audit_event_id is a real UUID. Then verify in DB:

```bash
psql "$DATABASE_URL" -c "
SELECT memory_type, role_tag, array_length(source_memory_ids, 1) AS evidence_count,
       jsonb_array_length(metadata->'parent_memory_ids') AS cluster_count,
       redaction_state, confidence_score
FROM memory_service.memories
WHERE id = '<synthesis_id from python>';
"
psql "$DATABASE_URL" -c "
SELECT event_type, actor, event_payload->>'cluster_size' AS cluster_size,
       event_payload->>'tokens_used' AS tokens
FROM memory_service.synthesis_audit_events
WHERE id = '<audit_event_id from python>';
"
```

Both queries must return a row with the expected shape. If either is empty, halt — write succeeded silently but accounting failed.

### Step 8 — Commit

```bash
git add src/synthesis/writer.py src/synthesis/prompts/single_agent_v1.txt tests/synthesis/test_writer.py
git status  # GATE: exactly those 3 files staged
```

Commit message:

```
CP8 Phase 2 T2+T7: synthesis writer (synchronous, single-agent)

End-to-end synthesis path: cluster → LLM → validate → write.
Writes one memory_type='synthesis' row per cluster with full provenance:
- source_memory_ids (uuid[]): evidence chain — only IDs the LLM cited
- metadata.parent_memory_ids: cluster edge — every atom in the cluster
- role_tag, confidence_score, synthesis_prompt_version populated

T7 ("audit-and-rate-limit-aware writes") folded in:
- tier_gates.check_synthesis_quota pre-flight; quota_exceeded short-circuits
  to rate_limit_blocked audit row, no LLM call
- synthesis_audit_events row written with full payload (cluster_id, prompt
  version, model, tokens, cited IDs)
- tier_gates rate-limit counters incremented post-write

Synchronous by design — T5's manual trigger and T6's cron wrap this in
T4's synthesis_jobs for async lifecycle.

Source-quote validation is delegated to a callback param; T3 supplies
the implementation.

Verification receipts:
[CC fills in: dry-run result from step 6, real synthesis_id + audit_event_id
 from step 7, DB row shapes]

Files: src/synthesis/writer.py (NEW),
       src/synthesis/prompts/single_agent_v1.txt (NEW),
       tests/synthesis/test_writer.py (NEW, 9 tests)
```

```bash
git commit -F /tmp/cp8-p2-t2-commit-msg.txt
git log -1 --stat
git push origin master
```

**Final gate:** `git push` exit code 0.

### Step 9 — Verify no regression

```bash
journalctl -u memory-api --since "10 minutes ago" --no-pager | grep -E "ERROR|CRITICAL" | grep -v "analytics_events"
```

**Gate G2:** clean modulo known noise.

---

## Halt conditions (specific to this task)

1. **`tier_gates` is missing functions** the writer needs to call. Halt — Phase 1 incomplete.
2. **Embedding helper in `extraction.py` not callable as a clean function.** Halt — refactor needed before writer can use it.
3. **Step 7 writes a row but no audit event** (or vice versa). Halt — accounting bug.
4. **Step 7 writes a synthesis with empty `source_memory_ids`** (LLM cited nothing). Halt — prompt is broken.
5. **Anthropic API returns non-200 in the smoke step.** Halt — credentials or rate-limited upstream.
6. **`source_memory_ids` is NOT a subset of `parent_memory_ids`** in step 7's DB read. Halt — Decision 1 violated.

---

## Definition of done

1. `src/synthesis/writer.py` and prompt file exist.
2. All 9 tests pass.
3. Smoke step 7 wrote one real synthesis row, one audit row, incremented one counter.
4. `source_memory_ids ⊆ parent_memory_ids` verified in DB.
5. Single commit on master pushed.
6. Real receipts in commit message.
7. No `CP8-P2-T2-BLOCKED.md`.
8. `journalctl` clean post-commit.

**No deploy needed** — writer not yet imported by `memory-api`. T5's endpoint imports it.
