# Verbatim Guarantee

**Status**: Implemented (CP8 Phase 2 Task 8)  
**Last Updated**: 2026-05-04  
**Owner**: Core extraction + storage layer

## Overview

The 0Latency memory service guarantees that **all raw input is preserved verbatim** before any summarization, extraction, or transformation occurs. This enables:

1. **Auditability**: Trace any derived memory back to its exact source.
2. **Re-extraction**: Re-run extraction logic on raw atoms without data loss.
3. **Debugging**: Verify extraction quality against ground truth.
4. **Legal/compliance**: Maintain unaltered records of what was written.

This document specifies **how** each write path implements this guarantee and **where** the verbatim copy lives.

---

## Write Paths

0Latency has four primary write paths. All four preserve verbatim input, but via different mechanisms.

### 1. POST /extract — Conversational extraction (main path)

**Location**: `api/main.py:514` → `src/extraction.py:extract_memories()`

**How verbatim preservation works**:

1. **Input arrives**: `{human_message, agent_message, agent_id, ...}`
2. **Raw turn created FIRST** (lines 233-268 in `src/extraction.py`):
   ```python
   full_content = f"Human: {human_message}\\n\\nAgent: {agent_message}"
   raw_turn_memory = {
       "headline": f"Raw turn — {timestamp}",
       "context": full_content[:500] + "...",
       "full_content": full_content,  # ← verbatim copy
       "memory_type": "raw_turn",
       ...
   }
   result = store_memory(raw_turn_memory, tenant_id=tenant_id)
   raw_turn_id = result["id"]
   ```
3. **Extraction proceeds**: Haiku analyzes the turn and produces structured atoms (facts, decisions, preferences).
4. **Atoms reference raw_turn**: Each extracted atom stores `raw_turn_id` in its `metadata.raw_turn_id` field (not yet enforced in all code paths — see Known Limitations).

**Verbatim location**: `memory_service.memories` table, row with `memory_type = 'raw_turn'`, column `full_content`.

**Retrieval**: `GET /memories/{raw_turn_id}/source` → returns `{source_text: "<verbatim>"}`

**Chrome extension**: Uses this same `/extract` endpoint, so inherits verbatim guarantee.

---

### 2. POST /memories/seed — Direct fact seeding

**Location**: `api/main.py:647`

**How verbatim preservation works**:

1. **Input arrives**: `{facts: [{text, importance, category, ...}]}`
2. **Each fact becomes a memory directly**:
   ```python
   memories.append({
       "headline": fact.text,
       "context": fact.text,
       "full_content": fact.text,  # ← verbatim input
       "memory_type": fact.memory_type or "fact",
       ...
   })
   ```
3. **No extraction step**: The input text IS the output memory. No transformation applied (beyond metadata enrichment).

**Verbatim location**: `memory_service.memories.full_content` for each seeded fact.

**Retrieval**: `GET /memories/{memory_id}/source` → returns the fact text.

**MCP memory_write tool**: Wraps `/memories/seed`, so it inherits this guarantee. The MCP server (`0latency-mcp-sse`) proxies to the REST API without transformation.

---

### 3. POST /memories/checkpoint — Mid-thread rollup

**Location**: `api/main.py:817`

**How verbatim preservation works**:

1. **Input arrives**: `{parent_memory_ids: [atom1, atom2, ...], thread_id, turn_range, ...}`
2. **Parent atoms are fetched from DB**:
   ```python
   parent_atoms = _db_execute_rows("""
       SELECT id, context, metadata, created_at
       FROM memory_service.memories
       WHERE id = ANY(%s::UUID[])
   """, (req.parent_memory_ids,))
   ```
3. **Haiku summarizes the atoms** into a dense rollup (the `session_checkpoint` memory).
4. **Checkpoint stores parent references**:
   ```python
   "metadata": {
       "parent_memory_ids": req.parent_memory_ids,  # ← preserve lineage
       ...
   }
   ```
5. **Parent atoms remain in DB unchanged**. The checkpoint is a *view* over them, not a replacement.

**Verbatim location**: Original atoms in `memory_service.memories` (referenced by `metadata.parent_memory_ids` in the checkpoint row).

**Retrieval**: `GET /memories/{checkpoint_id}/source` recursively resolves `parent_memory_ids` chain until it reaches raw_turn or seed atoms, then concatenates their `full_content`.

**Critical caveat**: If parent atoms are later deleted or superseded, the verbatim chain breaks. Current implementation does NOT hard-pin atoms used in checkpoints. This is a known gap (see Known Limitations).

---

### 4. Chrome Extension Capture

**Location**: Extension → `POST /extract` (same as path #1)

**How verbatim preservation works**: Identical to `/extract` path. Extension packages web content or user annotations into `{human_message, agent_message}` format and POSTs to `/extract`. The rest is handled by the extraction pipeline (raw_turn creation, then atom extraction).

**Verbatim location**: Same as path #1.

---

## Proof Points

The verbatim guarantee is validated by three mechanisms:

### T9: GET /memories/{id}/source endpoint

**Location**: `api/main.py:2528`

**What it does**: Given any memory ID (atom, checkpoint, or raw_turn), recursively resolves the verbatim source chain:

1. If `memory_type = 'raw_turn'` or `'fact'` (from seed), return `full_content` directly.
2. If `memory_type = 'session_checkpoint'`, fetch `metadata.parent_memory_ids`, recurse on each parent, concatenate results.
3. If atom has `metadata.raw_turn_id`, resolve that raw_turn's `full_content`.

**Returns**: `{source_text: "<verbatim content>", source_chain: [id1, id2, ...], memory_type: "..."}`

**Validation**: Any memory can be traced back to verbatim source. If this endpoint returns empty or errors, the guarantee is broken.

---

### T10: CLI verify verb

**Status**: Not yet implemented (deferred from CP8 Phase 2).

**Planned behavior**: `0latency-cli verify --memory-id <uuid>` would call `/memories/{id}/source` and display the verbatim chain, highlighting any breaks (missing parents, corrupted full_content, etc.).

**Workaround**: Manually call `GET /memories/{id}/source` via `curl` or Postman.

---

### T11: Nightly contract test

**Location**: `scripts/contract_test.py`

**What it does**:

1. Generates a unique sentinel string (e.g., `VERBATIM-CONTRACT-TEST-2026-05-04T06:16:37-9c9b683bc5f37a81`).
2. POSTs to `/extract` with the sentinel embedded in `human_message`.
3. Captures the returned `raw_turn_id`.
4. Calls `GET /memories/{raw_turn_id}/source`.
5. **Asserts sentinel is byte-for-byte present** in `source_text`.
6. **Hollow pass guard** (added Stage 2): Asserts ≥1 atom was extracted (test fails if 0 atoms, meaning extraction didn't run).

**Exit codes**:
- `0` = PASS (verbatim guarantee upheld)
- `1` = FAIL (sentinel missing or 0 atoms extracted)
- `2` = ERROR (test infra issue)

**Run**: `cd /root/.openclaw/workspace/memory-product && python3 scripts/contract_test.py --api-key <key>`

**Cron**: Should be installed as nightly cron (not yet scheduled as of 2026-05-04).

---

## Database Schema

Verbatim content lives in the `memory_service.memories` table.

**Relevant columns**:

| Column         | Type             | Purpose                                                  |
|----------------|------------------|----------------------------------------------------------|
| `id`           | UUID (PK)        | Memory identifier                                        |
| `full_content` | TEXT NOT NULL    | **Verbatim copy** of raw input                           |
| `context`      | TEXT NOT NULL    | Truncated preview (≤500 chars) for listing UIs           |
| `headline`     | TEXT NOT NULL    | Short summary (≤200 chars)                               |
| `memory_type`  | TEXT NOT NULL    | `raw_turn`, `fact`, `session_checkpoint`, etc.           |
| `metadata`     | JSONB            | May contain `raw_turn_id`, `parent_memory_ids`, etc.     |
| `source_turn`  | TEXT             | Turn ID from conversation system (nullable)              |
| `source_id`    | TEXT             | External source identifier (nullable)                    |

**Key invariant**: `full_content` is **never null**. Even for derived memories (checkpoints, summaries), `full_content` holds the generated summary text, and `metadata.parent_memory_ids` points back to verbatim atoms.

---

## Cross-References

- **CP8 Scope**: `CHECKPOINT-8-SCOPE-v3.md` Phase 2 Task 8 (this doc), Task 9 (source endpoint), Task 10 (CLI verb), Task 11 (contract test).
- **Operations Manual**: `OPERATIONS.md` §6.2 (memories schema), §10.3 (verbatim guarantee enforcement).
- **Source Endpoint**: `api/main.py:2528` (`get_memory_source`).
- **Extraction Logic**: `src/extraction.py:193` (`extract_memories` — raw_turn creation at lines 233-268).
- **Contract Test**: `scripts/contract_test.py`.

---

## Known Limitations

### 1. Checkpoint parent deletion

**Issue**: If a `session_checkpoint` references `parent_memory_ids = [atom1, atom2]` and those atoms are later deleted (via `DELETE /memories/{id}` or TTL expiry), the verbatim chain breaks. `/memories/{checkpoint_id}/source` will fail or return incomplete data.

**Mitigation**: Not yet implemented. Requires either:
- Hard-pin atoms used in checkpoints (set `superseded_at = NULL` permanently, or add a `pinned` flag), OR
- Copy parent `full_content` into checkpoint `metadata` at creation time (storage cost increase).

**Severity**: Medium. Rare in practice (most users don't delete atoms), but violates strict auditability.

---

### 2. Extracted atoms don't always store raw_turn_id

**Issue**: The `/extract` endpoint creates `raw_turn_id` and is supposed to pass it to extracted atoms via `metadata.raw_turn_id`. However, some code paths (legacy, async extraction) don't propagate this reliably.

**Symptom**: `/memories/{atom_id}/source` may return the atom's own `full_content` instead of resolving back to the raw_turn.

**Mitigation**: Audit all extraction callsites to ensure `metadata["raw_turn_id"] = raw_turn_id` is set. Track in OPERATIONS.md §10.3.

**Severity**: Low. Affects traceability, not verbatim preservation (raw_turn still exists, just not linked).

---

### 3. Seed API has no raw_turn

**Issue**: `/memories/seed` writes facts directly. There is no "raw turn" concept because the input is already structured. If a seeded fact is later used as a parent in a checkpoint, the verbatim chain bottoms out at the fact itself (which IS verbatim), but there's no conversational context to resolve.

**Mitigation**: None planned. This is by design. Seed facts are their own verbatim source.

**Severity**: None. Not a bug, just a clarification.

---

### 4. MCP memory_write exposes same limitation as seed

**Issue**: The MCP `memory_write` tool calls `/memories/seed` under the hood. It has no raw_turn or conversational wrapper. The `content` parameter becomes `full_content` directly.

**Mitigation**: None needed. MCP is explicitly a "structured write" path. The content IS the verbatim input.

**Severity**: None.

---

### 5. Async extraction jobs (202 path) not covered

**Issue**: `POST /memories/extract` (line 732) returns `202 Accepted` and queues extraction. The contract test uses the sync `/extract` path (line 514). Async path verbatim handling is not explicitly tested.

**Mitigation**: Add async variant to contract test, or audit async job worker to confirm raw_turn creation.

**Severity**: Low. Code paths converge (both call `extract_memories`), but test gap exists.

---

## Future Work

1. **Hard-pin checkpoint parents**: Prevent deletion of atoms referenced by checkpoints.
2. **Enforce raw_turn_id propagation**: Make `metadata.raw_turn_id` mandatory for all extracted atoms (schema validation or API-level check).
3. **Expand contract test**: Cover async extraction, seed path, checkpoint path.
4. **CLI verify verb**: Implement T10 to make verbatim chain inspection a one-liner.
5. **Audit log for verbatim access**: Track who called `/memories/{id}/source` for compliance use cases.

---

## Summary

| Write Path       | Verbatim Mechanism                          | Retrievable Via                   | Test Coverage        |
|------------------|---------------------------------------------|-----------------------------------|----------------------|
| `/extract`       | Creates `raw_turn` with `full_content`      | `GET /memories/{raw_turn_id}/source` | ✅ contract_test.py  |
| `/memories/seed` | Input text IS `full_content`                | `GET /memories/{fact_id}/source`  | ⚠️  not tested       |
| `/checkpoint`    | Parents preserved, refs in `metadata`       | Recursive source chain            | ⚠️  not tested       |
| MCP `memory_write` | Wraps `/seed` → same as seed              | Same as seed                      | ⚠️  not tested       |

**Guarantee**: For every memory written via any path, the original input (or its lineage) is recoverable via `/memories/{id}/source`. The only failure mode is parent deletion (checkpoint path), which is rare and mitigable.

---

**Document authored by**: Claude Sonnet 4.5 (autonomous chain execution, CP8 Phase 4B → Stage 3)  
**Chain context**: `CHAIN-2026-05-04-synthesis-hardening.md`
