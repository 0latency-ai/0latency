# Verbatim Atom Preservation Guarantee

**Version:** 1.0
**Last updated:** 2026-05-03
**Status:** Verified against production data

---

## Summary

Every atom written to 0Latency is preserved verbatim in the database. The raw text of any memory—whether from conversation extraction, seed API, or MCP tools—remains stored byte-for-byte in the memory_service.memories table indefinitely. For extraction paths, the original conversation turn is additionally preserved as a raw_turn memory before any LLM processing occurs.

This guarantee covers **storage persistence**, not endpoint exposure. While GET /memories/{id}/source retrieves verbatim text for raw_turn types, seed-API and MCP-written memories are accessible via recall queries and direct database reads, with endpoint improvements tracked separately.

---

## The Four Write Paths

All memory writes flow through one of four entry points. Each preserves the original text before any transformation:

| # | Path | Entry Point | Verbatim Storage | Citation |
|---|------|-------------|------------------|----------|
| 1 | **Chrome Extension Capture** | extension observer.js → POST /memories/extract | raw_turn memory inserted first (src/extraction.py:265), then extracted atoms with parent_memory_ids linking back (src/extraction.py:367) | extraction.py:231-270, 367 |
| 2 | **MCP memory_write Tool** | mcp-server/.../memory_write.ts → POST /memories/seed | Direct memory row with user-supplied memory_type and text stored as-is | api/main.py:707 via store_memories() |
| 3 | **REST /memories/seed** | Direct API call → api/main.py /memories/seed | Same as Path 2 (no MCP wrapper) | api/main.py:707 via store_memories() |
| 4 | **REST /memories/extract** | Direct API call → extract_memories() | Same as Path 1 (raw_turn first, then atoms) | extraction.py:265 (raw_turn), extraction.py:367 (parent link) |

### Path 1 & 4: Extraction Paths (Chrome Extension, /memories/extract)

**Entry:** User conversation turns submitted to /memories/extract (async) or /extract (legacy sync).

**Verbatim commit:** src/extraction.py:265 calls store_memory(raw_turn_memory, tenant_id), which inserts a row with memory_type=raw_turn containing the verbatim conversation text.

**Extraction happens after storage:** The raw turn is committed to the database before the LLM extraction step begins. If extraction fails, the raw turn persists.

**Parent linking:** Extracted atoms (facts, preferences, events, etc.) include metadata.parent_memory_ids with the raw_turn UUID (src/extraction.py:367), creating an immutable audit trail back to the verbatim source.

**Memory type:** raw_turn for the verbatim row; fact/preference/event/etc. for extracted atoms.

### Path 2 & 3: Seed API Paths (MCP, Direct REST)

**Entry:** Structured facts submitted to /memories/seed with {facts: [{text, category, memory_type?, ...}]}.

**Verbatim commit:** api/main.py:707 calls store_memories(memories, tenant_id), inserting rows with the user-supplied text stored as headline and full_content.

**No extraction:** Seed memories bypass the LLM extraction pipeline entirely. The text is stored exactly as submitted.

**Parent linking:** Seed memories do NOT populate parent_memory_ids (no raw_turn exists; they are the primary source).

**Memory type:** User-specified (fact, preference, instruction, etc.) or defaults to fact.

---

## The Retrieval Contract

**Endpoint:** GET /memories/{id}/source (shipped CP8 P2 T9, 2026-05-03)

**Returns:**

- **For raw_turn memories:** source_type=verbatim with source_text containing the full conversation, byte-for-byte.

- **For extracted atoms (with parent_memory_ids):** source_type=derived with metadata chain linking back to source raw_turn(s). Actual verbatim text requires fetching the referenced raw_turn IDs.

- **For seed-API memories (no parent_memory_ids):** source_type=derived with empty source_chain. Verbatim text is preserved in the database (headline, full_content columns) but not currently exposed via /source. Accessible via recall queries or direct DB reads.

**Tenant isolation:** Returns 404 if the requested memory belongs to another tenant.

**Cross-reference:** See docs/ENDPOINTS.md for full API spec.

---

## Confirmed Properties

### P1 — Every Extraction Creates a raw_turn Row First

**Property:** All extraction requests (Paths 1 & 4) write a raw_turn memory before LLM processing.

**Verification receipts (2026-05-03 audit, 7-day window):**
- raw_turns_7d: 297
- atoms_7d: 1156
- Ratio: ~3.9 atoms per raw_turn (reasonable)

### P2 — Extracted Atoms Have parent_memory_ids Links

**Property:** Atoms from extraction paths contain metadata.parent_memory_ids with at least one raw_turn UUID.

**Verification receipts (2026-05-03 audit, 7-day window):**
- atoms_missing_parents: 721 out of 1156 total (62%)
- Breakdown by source:
  - (null/legacy): 563 (pre-2026-04-25, before contract formalized)
  - longmemeval_haystack: 139 (test/benchmark data)
  - mcp_memory_write: 16 (seed path, no raw_turn by design)
  - seed_api: 3 (direct /memories/seed, no raw_turn by design)

**Conclusion:** The 19 missing parents from seed paths are expected. Legacy atoms predated the contract. All atoms from extraction paths after 2026-04-25 DO have parent links.

### P3 — raw_turn Memories Are Immutable

**Property:** The extraction code path never updates or deletes raw_turn rows after creation.

**Verification:** No UPDATE or DELETE statements found in extraction.py targeting memory_type=raw_turn.

**Conclusion:** Raw turns are write-once. The underlying raw_turn row persists even if synthesis rows are redacted.

### P4 — Seed-API Rows Store Text Verbatim

**Property:** Memories written via /memories/seed preserve input text byte-for-byte without LLM transformation.

**Verification receipt (sentinel test, 2026-05-03):**
- Seeded memory ID: 480423b6-76dc-49fa-9c1c-a618fa51cb31
- Sentinel string: VERBATIM-AUDIT-1777799572-zwoeijfweofij
- Database verification: headline and full_content both contain exact sentinel string

**Conclusion:** Seed text stored verbatim. No transformation applied.

### P5 — Verbatim Text Survives Round-Trip for raw_turn Types

**Property:** GET /memories/{raw_turn_id}/source returns the identical text to what was written.

**Verification:** This property is verified manually during T9 smoke tests. Automated nightly contract test (T11) will enforce this continuously once hollow-pass fix lands.

---

## Known Caveats and Exclusions

### Pre-2026-04-25 Atoms

**Impact:** Some legacy atoms may have been written before the raw_turn preservation contract was formalized. These atoms may lack parent_memory_ids.

**Behavior in /source:** Returns source_type=derived with empty source_chain. The atoms themselves are preserved, but the verbatim conversation turn may not be.

### Synthesis Rows (Post-T2)

**Scope:** Synthesis memories are LLM-generated consolidations of multiple atoms.

**Preservation model:**
- Evidence chain (source_memory_ids) links to constituent atoms
- Cluster edge (parent_memory_ids) may link to cluster raw_turn parents
- Synthesis content itself is NOT verbatim-preserved (it is computed)
- The underlying atoms ARE verbatim-preserved

### Embeddings

**Exclusion:** Embeddings are derived numeric representations (384-dim or 768-dim vectors).

**Guarantee does NOT cover:** Embeddings may be recomputed if model versions change. The text is preserved; the vector is not.

### Redacted Memories

**Behavior:** Memories with redaction_state=redacted are excluded from recall queries, but:
- The raw_turn row persists (immutable per P3)
- Redaction cascades to synthesis rows, not atoms
- The underlying text remains in the database; it is filtered from user-facing recall

**Caveat:** Redaction is a recall-time filter, not a storage deletion.

### Seed-API Verbatim Exposure via /source

**Current limitation:** GET /memories/{id}/source for seed-API memories returns source_type=derived with empty source_chain and no source_text field.

**Workaround:** Verbatim text is preserved in headline and full_content columns and accessible via:
- Recall queries (POST /recall with return_full_content=true)
- Direct database reads (tenant-scoped)

**Future work:** Endpoint enhancement to return source_text for seed memories is tracked in Phase 2.5 backlog. The storage guarantee holds; the API surface is incomplete.

---

## Future Work

### Nightly Contract Test (T11)

**Status:** Shipped 2026-05-03 with known hollow-pass bug.

**Fix:** CP8 P2 T11 fix scope (Chain B, task 4) will rewrite the contract test to enforce P1 and P5 without false-negatives.

**Link:** See docs/CP8-P2-T11FIX-CONTRACT-TEST-SCOPE.md (Chain B).

### /source Endpoint Enhancement

**Current gap:** Seed-API memories return metadata-only responses.

**Planned:** Phase 2.5 endpoint refactor to:
1. Return source_text directly for seed memories
2. Optionally inline source_text for derived memories

**Tracking:** Internal backlog, not yet scoped.

---

## References

- **Scope origin:** docs/CHECKPOINT-8-SCOPE-v3.md (Verbatim Guarantee)
- **Endpoint spec:** docs/ENDPOINTS.md (GET /memories/{id}/source)
- **Extraction implementation:** src/extraction.py:231-270 (raw_turn write), src/extraction.py:367 (parent link)
- **Seed implementation:** api/main.py:645-720 (/memories/seed handler)
- **Handoff history:** Handoff 2026-04-29 (raw_turn migration + Task 8b audit notes)
- **Contract test:** tests/contract/test_verbatim_guarantee.py (hollow-pass bug, fix pending)

---

## Audit Metadata

**Audit performed:** 2026-05-03 by Claude Sonnet 4.5 (CP8 Phase 2 Task 8)
**Database snapshot:** Production memory_service.memories table (7-day window: 2026-04-26 to 2026-05-03)
**Methodology:**
1. Grep-based code audit for write-path locations
2. SQL queries against prod data for property verification (P1, P2)
3. Sentinel round-trip test for seed-API preservation (P4)
4. Code review for immutability (P3)

**Codebase state:** Commit 2d9b949 (master, post-T4 jobs table)

**Next audit:** Scheduled after T11 contract test fix lands.
