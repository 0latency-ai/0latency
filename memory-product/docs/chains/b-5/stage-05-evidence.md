# Stage 05 Evidence — _db_execute cleanup #3 + VERBATIM-GUARANTEE.md

## Part A: recall.py cleanups

### Goal
Convert two remaining _db_execute sites in _build_always_include function.

### Target sites

#### Site 1: Line 342-348 (session handoffs)
Simple conversion - changed rows[0] to rows[0][0] after switching to _db_execute_rows.

#### Site 2: Line 353-365 (corrections) - ANTI-PATTERN
This site had the split anti-pattern. Changed from parts = row.split("|||") to direct tuple access row[0], row[1].

## Part B: VERBATIM-GUARANTEE.md

### Goal
Author the long-pending verbatim-guarantee doc (T8 from CP8 Phase 1).

### Created document
Path: docs/VERBATIM-GUARANTEE.md

### Required sections (all present):
- What we promise
- How it is enforced (4-path coverage, verification slice, CLI tool, nightly contract test, hollow-pass guard)
- What is covered
- What is NOT covered (negative scope) — synthesis/embeddings/redacted/legacy excluded
- Public claim — explicit claim text
- Verification (operator snippet)
- Cron schedule

## Verification

### Parse check
Result: PARSE_OK

### Service health
Result: 200 OK

### Document verification
Result: DOC_GATE_PASS (all required sections present)

### Smoke test
Result: 200 OK

## Outcome
SHIPPED — Third and fourth _db_execute cleanups complete (8 remaining in codebase). VERBATIM-GUARANTEE.md authored with all required sections including negative-scope and public-claim sections that B-3.5 Stage 15 evidence flagged as missing.

## Files Modified
- src/recall.py (lines 342-348, 353-365)
- docs/VERBATIM-GUARANTEE.md (created)
