# CP8 Phase 2 Task 8 — Autonomous Scope: VERBATIM-GUARANTEE.md

**Task:** Audit all four atom write paths and document the verbatim-preservation contract in `docs/VERBATIM-GUARANTEE.md`.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** T4 commit (jobs table).
**Estimated wall-clock:** 15–30 min for CC.
**Chain position:** Chain A, task 3 of 3 (T1 → T4 → **T8**).

---

## Goal

One sentence: Audit the four atom write paths to confirm they preserve verbatim text before any extraction runs, and document the resulting guarantee in a single user-facing markdown file.

This is a **paper audit + documentation task**. No code changes. The guarantee already holds (per the v3 scope: "this is verification, not implementation"); this task makes it explicit, citable, and provable.

---

## In scope

**Files to create:**
- `docs/VERBATIM-GUARANTEE.md` — NEW

**Files to read (do not modify):**
- `src/extraction.py` — primary write path with `raw_turn` preservation
- `api/main.py` — for `/memories/seed`, `/memories/extract`, and `/memories/{id}/source` route handlers
- `mcp-server/src/tools/memory_write.ts` (or equivalent) — MCP `memory_write` path
- Chrome extension source under `0latency-chrome-extension/` — extension write path
- `migrations/` — for the `raw_turn` storage shape and `parent_memory_ids` jsonb structure
- `docs/ENDPOINTS.md` — to align format and cross-link

**Database:** Read-only. May query `memory_service.memories` and `memory_service.raw_turns` to verify counts and shapes.

---

## Out of scope (DO NOT TOUCH)

- Any source code file (Python, TypeScript, JavaScript)
- Any migration file
- Marketing pages on `/var/www/0latency/` — surfacing the guarantee in marketing copy is Phase 5
- Any extension-side code
- Any MCP tool description rewrite — that lives in `docs/MCP-TOOLS.md`, which is a separate manual review pass
- The nightly contract test (T11 — separate scope, ships in Chain B)

---

## Document contract

`docs/VERBATIM-GUARANTEE.md` must contain these sections, in this order:

### 1. Summary (1 paragraph)

State the guarantee plainly: "Every atom written to 0Latency is preserved verbatim. The raw text of any memory remains recallable byte-for-byte via `GET /memories/{id}/source` indefinitely."

### 2. The four write paths (table + per-path detail)

| # | Path | Entry point | Where verbatim is stored | Cite (file:line) |
|---|---|---|---|---|
| 1 | Chrome extension capture | extension `observer.js` → `POST /memories/extract` | `memory_service.raw_turns` row inserted before extraction; `parent_memory_ids` populated on each extracted atom | extraction.py:L<N> |
| 2 | MCP `memory_write` (seed API) | `mcp-server/.../memory_write.ts` → `POST /memories/seed` | `memory_service.memories` row with `memory_type` matching input; if input is a turn, raw text is stored as the row body | api/main.py:L<N> |
| 3 | REST `/memories/seed` | direct API caller → `api/main.py` | Same as path 2, just no MCP wrapper | api/main.py:L<N> |
| 4 | REST `/memories/extract` | direct API caller → `extract_memories()` | Same as path 1, raw_turn row first then extracted atoms with parent links | extraction.py:L<N> |

For each path, a brief sub-section (≤5 sentences) describing:
- What the entry point accepts as input
- Where in the code the raw text is committed to the DB (exact `INSERT` location)
- What the resulting row's `memory_type` is (`raw_turn` for extraction paths, the user-supplied type for seed paths)
- Whether `parent_memory_ids` is populated to link extracted atoms back to the raw turn

### 3. The retrieval contract

State that `GET /memories/{id}/source` (CP8 P2 T9, shipped 2026-05-03) returns:
- For `raw_turn` and seed-typed memories: the original text directly.
- For derived memories (atoms with `parent_memory_ids`, syntheses, checkpoints): the chain of resolution back to the raw text.
- For tenant-isolated requests: 404 if the requested memory belongs to another tenant.

Cross-link to `docs/ENDPOINTS.md`'s `/memories/{id}/source` section.

### 4. Confirmed properties (with verification commands)

Each property is stated, then accompanied by the SQL or curl command that verifies it. Use real fixture data where possible.

Properties to verify:
- **P1 — Every extraction creates a `raw_turn` row first.** Verify with: SQL count of `raw_turn` rows in last 7d ≥ count of `extract` API calls (allowing for some skew).
- **P2 — Every extracted atom has `parent_memory_ids` containing at least one `raw_turn` ID.** Verify with: SQL count of atoms in last 7d with empty `metadata.parent_memory_ids` is zero (or near-zero with documented exceptions for legacy data).
- **P3 — `raw_turns` are never updated or deleted by the extraction path.** Verify by: stating the absence of UPDATE/DELETE statements on `raw_turns` in `src/extraction.py` (grep result included).
- **P4 — Seed-API rows are stored verbatim with no extraction step.** Verify with: write a seed memory with a sentinel string, recall by ID, confirm exact match.
- **P5 — `GET /memories/{id}/source` returns identical text to what was written.** Verify with: end-to-end curl against fixture.

### 5. Known caveats and exclusions

Be explicit about what the guarantee does NOT cover:
- **Pre-2026-04-25 atoms** may have been written before the `raw_turn` preservation contract was formalized. Some legacy atoms have no `parent_memory_ids`. These show `source_type=derived` with empty `source_chain` from the source endpoint. (Cross-reference handoff 2026-04-29 for the migration history.)
- **Synthesis rows** (when they exist post-T2) preserve the *evidence chain* via `source_memory_ids` and the *cluster edge* via `parent_memory_ids` — both lead back to atoms or raw_turns, but are computed, not stored verbatim. Synthesis content itself is LLM-generated and not subject to byte-for-byte preservation; the underlying atoms are.
- **Embedding** is not part of the verbatim guarantee. Embeddings are derived numeric representations and may be re-computed if model versions change.
- **Redacted memories** (`redaction_state='redacted'`) are excluded from recall but the underlying `raw_turn` row is preserved. The cascade is on synthesis rows, not atoms.

### 6. Future work (link to T11)

State that the nightly contract test (CP8 P2 T11, shipped 2026-05-03 with hollow-pass bug) will verify the guarantee continuously once the hollow-pass fix lands. Link to the T11 scope doc once it exists.

### 7. References

- `docs/CHECKPOINT-8-SCOPE-v3.md` — the scope where this guarantee was promoted to a verified property
- `docs/ENDPOINTS.md` — `GET /memories/{id}/source` and `POST /memories/seed`
- `src/extraction.py` — primary `raw_turn` write path
- Handoff `2026-04-29` — the verbatim raw_turn migration history

---

## Steps

### Step 1 — Locate every write path's commit point

```bash
cd /root/.openclaw/workspace/memory-product
grep -n "INSERT INTO memory_service.memories" src/extraction.py
grep -n "INSERT INTO memory_service.raw_turns" src/extraction.py
grep -n "INSERT INTO memory_service.memories" api/main.py | head -20
```

**Gate G2:** at least 4 distinct commit-point line numbers found across these files. Record them — they fill the citation column in the document's table.

### Step 2 — Verify P1 against prod

```bash
psql "$DATABASE_URL" -c "
SELECT
  (SELECT COUNT(*) FROM memory_service.raw_turns
   WHERE created_at > NOW() - INTERVAL '7 days') AS raw_turns_7d,
  (SELECT COUNT(*) FROM memory_service.memories
   WHERE memory_type IN ('fact','preference','instruction','event','correction','identity')
     AND created_at > NOW() - INTERVAL '7 days') AS atoms_7d;
"
```

**Gate G2:** raw_turns_7d > 0, ratio is reasonable (atoms ≥ raw_turns, since each raw_turn typically yields multiple atoms). Record both values for the document.

### Step 3 — Verify P2 against prod

```bash
psql "$DATABASE_URL" -c "
SELECT COUNT(*) AS atoms_missing_parents
FROM memory_service.memories
WHERE memory_type IN ('fact','preference','instruction','event','correction','identity')
  AND created_at > NOW() - INTERVAL '7 days'
  AND (metadata->'parent_memory_ids' IS NULL
       OR jsonb_array_length(metadata->'parent_memory_ids') = 0);
"
```

**Gate G2:** result is zero (or low single digits, all from legacy paths). Record the value. If it's a high number, halt and write to BLOCKED — guarantee may not be holding in practice.

### Step 4 — Verify P4/P5 end-to-end with sentinel

```bash
SENTINEL="VERBATIM-AUDIT-$(date +%s)-zwoeijfweofij"
curl -sS -X POST http://localhost:8420/memories/seed \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"user-justin\", \"memory_type\": \"fact\", \"content\": \"$SENTINEL\"}" \
  | tee /tmp/t8-seed-response.json
SEED_ID=$(jq -r '.id // .memory_id' /tmp/t8-seed-response.json)
echo "Seeded ID: $SEED_ID"
curl -sS http://localhost:8420/memories/$SEED_ID/source \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  | tee /tmp/t8-source-response.json
grep -q "$SENTINEL" /tmp/t8-source-response.json && echo "T8 SENTINEL PASS"
```

**Gate G1:** the sentinel string appears in the source response. If not, halt — verbatim contract is broken and the doc cannot honestly assert P5.

### Step 5 — Write `docs/VERBATIM-GUARANTEE.md`

Per the document contract above. Use the file/line numbers from Step 1 in the table. Use real numbers from Steps 2 and 3 in the verification commands' "expected output" annotations. Include the actual sentinel command from Step 4 as a runnable example.

Document length target: 400–800 lines. Long enough to be a thorough audit; short enough that a skeptical engineer can read it in 10 minutes.

### Step 6 — Cross-check the document

Re-read the file. Verify:
- All 4 paths in the table have non-placeholder file:line citations.
- All 5 properties have an associated verification command.
- The sentinel test command is copy-pasteable and uses real env vars.
- No claims about T11's hollow-pass status that conflict with the actual T11 commit message.

### Step 7 — Commit

```bash
git add docs/VERBATIM-GUARANTEE.md
git status  # GATE: exactly that 1 file staged
git diff --cached --stat
```

Commit message:

```
CP8 Phase 2 T8: docs/VERBATIM-GUARANTEE.md audit

Documents the verbatim atom preservation contract across all four
write paths: Chrome extension, MCP memory_write, REST /memories/seed,
REST /memories/extract.

Confirms guarantee holds via prod data:
- P1: raw_turns inserted before atoms (7d count: <N>)
- P2: atoms_missing_parents over 7d window: <N>
- P3: no UPDATE/DELETE on raw_turns in extraction.py
- P4/P5: sentinel-string round-trip via /memories/seed → /memories/{id}/source

Cross-links to /memories/{id}/source endpoint (T9) and the nightly
contract test (T11) once hollow-pass fix lands.

This closes the T8 leftover from CP8 Phase 2 verbatim slice.
No code changes; documentation-only.

Verification receipts:
[CC fills in: file:line citations from step 1, prod counts from steps 2-3,
 sentinel test result from step 4]

Files: docs/VERBATIM-GUARANTEE.md (NEW, ~N lines)
```

```bash
git commit -F /tmp/cp8-p2-t8-commit-msg.txt
git log -1 --stat
git push origin master
```

**Final gate:** `git push` exit code 0.

---

## Halt conditions (specific to this task)

1. **Step 1 finds fewer than 4 distinct insert points.** Codebase has changed; halt.
2. **Step 3 reveals high atom-without-parent count.** Guarantee is not holding; halt and document the gap. Do NOT write a doc claiming the property holds.
3. **Step 4 sentinel test fails.** Halt — verbatim contract broken; T9's endpoint regressed.
4. **`docs/VERBATIM-GUARANTEE.md` already exists** — Justin already wrote it manually. Halt, do not overwrite. Defer to manual review.

---

## Definition of done

1. `docs/VERBATIM-GUARANTEE.md` exists with all 7 sections from the contract.
2. All 5 properties have associated verification commands with real values.
3. All 4 write paths have file:line citations (no placeholders).
4. Sentinel round-trip test passed during the run.
5. Single commit on master pushed.
6. Commit message contains real receipts.
7. No `CP8-P2-T8-BLOCKED.md` exists.

**No deploy needed** — documentation only.
