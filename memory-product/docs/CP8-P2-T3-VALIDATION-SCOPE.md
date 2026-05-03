# CP8 Phase 2 Task 3 — Autonomous Scope: Source-Quote Validation

**Task:** Build `synthesis/validation.py` — verify the synthesis writer's LLM output cites only IDs from the provided source set; reject hallucinations before the row is written.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** T2 commit (writer).
**Estimated wall-clock:** 10–20 min for CC.
**Chain position:** Chain B, task 2 of 4 (T2 → **T3** → T5+T6 → T11-fix).

---

## Goal

One sentence: Provide the validator that T2's writer plugs in via its `validate_callback` parameter — input is `(synthesis_text, candidate_source_ids)`, output is a `ValidationResult` with the cited IDs partitioned into legitimate and hallucinated sets.

This is the hallucination check from CP8 v3 Phase 2 Task 4. Synthesis writes are atomic: validation runs **before** the DB write, and a failed validation logs to audit and rejects the row.

---

## In scope

**Files to create:**
- `src/synthesis/validation.py` — NEW
- `tests/synthesis/test_validation.py` — NEW

**Files to modify:**
- `src/synthesis/writer.py` — wire `validate_synthesis_citations` as the default `validate_callback` when caller passes `None`. **Single-line change** to default arg or import-and-call site.

**Files to read (do not modify):**
- `src/synthesis/writer.py` — to align on the `ValidationResult` dataclass shape (already defined in T2)

**Database:** Read-only. Validator does not touch the DB; the writer handles the audit-on-failure write.

---

## Out of scope (DO NOT TOUCH)

- Any migration file
- Any module other than `validation.py` and the one-line writer wire-up
- Audit event writes — caller (T2 writer) handles
- LLM calls — validator is pure regex + set logic
- Source-text similarity scoring — Phase 5 (calibration); this is ID-set validation only

---

## Function contract

```python
import re
import uuid
from dataclasses import dataclass
from typing import Optional

UUID_CITE_PATTERN = re.compile(
    r'\[src:([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]',
    re.IGNORECASE
)

@dataclass
class ValidationResult:
    valid: bool
    cited_ids_in_source_set: list[uuid.UUID]
    cited_ids_NOT_in_source_set: list[uuid.UUID]
    failure_reason: Optional[str]

def validate_synthesis_citations(
    synthesis_text: str,
    candidate_source_ids: list[uuid.UUID],
    structured_cited_ids: Optional[list[uuid.UUID]] = None,
    require_at_least_one_citation: bool = True,
) -> ValidationResult:
    """
    Validate that all IDs cited in the synthesis are members of the candidate set.

    The synthesis prompt asks the LLM to:
      (a) cite IDs inline like [src:<uuid>]
      (b) ALSO return them in a structured `cited_atom_ids` JSON field

    This validator checks BOTH. The union of (a) and (b) must be a subset
    of `candidate_source_ids`. Inline-only OR structured-only citations are
    fine; either is acceptable. Hallucinations in either fail the validation.

    Args:
        synthesis_text: the LLM's prose output (may contain inline [src:UUID] citations)
        candidate_source_ids: the cluster's atom IDs the LLM was given
        structured_cited_ids: parsed from the LLM's JSON response field; may be None
        require_at_least_one_citation: if True, zero citations fails validation

    Returns:
        ValidationResult with all citation IDs partitioned.
    """
```

**Algorithm:**

1. Extract inline citations: `inline_ids = set(UUID(m.group(1)) for m in UUID_CITE_PATTERN.finditer(synthesis_text))`
2. Combine with structured citations: `all_cited = inline_ids | set(structured_cited_ids or [])`
3. Convert candidate set: `candidate_set = set(candidate_source_ids)`
4. Partition: `legit = all_cited & candidate_set`, `hallucinated = all_cited - candidate_set`
5. Apply rules:
   - If `len(all_cited) == 0` and `require_at_least_one_citation`: `valid=False, failure_reason='no_citations'`
   - If `len(hallucinated) > 0`: `valid=False, failure_reason='hallucinated_ids'`
   - Otherwise: `valid=True, failure_reason=None`
6. Return `ValidationResult(valid, sorted(legit), sorted(hallucinated), failure_reason)`

**Edge cases:**
- Malformed UUIDs in regex matches: `re.IGNORECASE` plus full UUID4 pattern catches well-formed only; partial/malformed UUIDs are silently skipped (they don't match the regex).
- Duplicate citations: deduped by set conversion.
- Mixed-case UUIDs: normalized to lowercase canonical form via `uuid.UUID()`.
- `structured_cited_ids` containing strings instead of UUID objects: validator must coerce via `uuid.UUID(str(x))` and skip strings that fail to parse (logged to a warning, not a failure — the LLM may have returned a partially-valid list).

---

## Steps

### Step 1 — Read T2 writer for callback signature alignment

```bash
cd /root/.openclaw/workspace/memory-product
grep -n "validate_callback\|ValidationResult" src/synthesis/writer.py | head -10
```

**Gate G2:** confirms `ValidationResult` dataclass exists in writer; signature matches the contract above. If shape diverges, halt — T2 needs adjustment first.

### Step 2 — Implement `src/synthesis/validation.py`

Per function contract. Module docstring documents:
- Why both inline and structured citations are accepted (resilience to LLM format drift)
- Why duplicates are deduped (set semantics)
- Why malformed UUIDs are silently skipped (regex doesn't match them; not a failure mode)
- The relationship to T2's writer — validator is pure, side-effect-free

The `ValidationResult` dataclass is defined in `writer.py` per T2; validation.py **imports** it from writer to avoid duplication. (If T2 placed it elsewhere or didn't define it, adjust the import.)

### Step 3 — Wire as default callback in writer

Single-line change to `src/synthesis/writer.py`:

```python
# Before:
def synthesize_cluster(..., validate_callback: Optional[Callable[[str, list[uuid.UUID]], ValidationResult]] = None, ...):

# After (add at module top):
from src.synthesis.validation import validate_synthesis_citations

# In function body, replace:
#   if validate_callback is not None:
#       result = validate_callback(synthesis_text, candidate_ids)
# with:
#   validator = validate_callback or validate_synthesis_citations
#   result = validator(synthesis_text, candidate_ids, structured_cited_ids=parsed_response.get("cited_atom_ids"))
```

This is the **only** code change to `writer.py`. If the writer's existing structure makes this a multi-line refactor, halt — scope says one-line wiring.

### Step 4 — Implement `tests/synthesis/test_validation.py`

Eight tests (pure unit tests; no DB, no LLM):

1. `test_inline_citations_all_legit` — synthesis with 3 `[src:UUID]` citations all in candidate set; valid=True
2. `test_structured_citations_all_legit` — empty inline, structured list of 2 IDs both in candidate set; valid=True
3. `test_inline_with_one_hallucination` — 2 legit + 1 not-in-candidates; valid=False, failure_reason='hallucinated_ids', hallucinated list has 1 element
4. `test_structured_with_one_hallucination` — same but via structured list; valid=False
5. `test_no_citations_required_fails` — empty synthesis text, empty structured list, require_at_least_one=True; valid=False, failure_reason='no_citations'
6. `test_no_citations_not_required_passes` — same as 5 but require=False; valid=True
7. `test_dedupes_repeated_citations` — same UUID cited 5× inline; cited_ids_in_source_set has length 1
8. `test_malformed_uuid_in_structured_skipped` — structured list contains `["not-a-uuid", <real_uuid>]`; validator skips the bad one, processes the real one without raising

These are pure unit tests — mark `@pytest.mark.unit` if that marker exists, otherwise no marker.

### Step 5 — Test gate (G3)

```bash
pytest tests/synthesis/test_validation.py -v --tb=short 2>&1 | tee /tmp/t3-test-output.txt
grep -q "passed" /tmp/t3-test-output.txt && ! grep -q "failed" /tmp/t3-test-output.txt && echo 'T3 UNIT GATE PASS'
```

### Step 6 — Re-run T2 writer tests with default validator now wired

```bash
pytest tests/synthesis/test_writer.py -v --tb=short 2>&1 | tee /tmp/t3-writer-regression.txt
grep -q "passed" /tmp/t3-writer-regression.txt && ! grep -q "failed" /tmp/t3-writer-regression.txt && echo 'T3 WRITER REGRESSION PASS'
```

**Gate G3:** all T2 writer tests still pass with the new default validator wired in. **HALT** if any T2 test now fails — the wiring broke something.

### Step 7 — Smoke test: synthesize one real cluster, observe validator engagement

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
    dry_run=True,  # don't actually write; just exercise the validator
)
print(f'success={result.success} cited={len(result.source_memory_ids)} '
      f'rejected_reason={result.rejected_reason}')
"
```

**Gate G2:** prints `success=True`. If `success=False` with `rejected_reason='validation_failed'`, the validator is too strict for the real LLM output — halt and dump the synthesis text + cited IDs into a debug note.

### Step 8 — Commit

```bash
git add src/synthesis/validation.py src/synthesis/writer.py tests/synthesis/test_validation.py
git status  # GATE: 3 files staged (validation.py NEW, writer.py 1-line change, test_validation.py NEW)
git diff --cached --stat
```

Commit message:

```
CP8 Phase 2 T3: source-quote validation (hallucination check)

Validator extracts cited atom IDs from synthesis text (inline [src:UUID]
plus structured cited_atom_ids JSON field), partitions into legit and
hallucinated sets, returns ValidationResult.

Wired into writer as default validate_callback; behavior:
- All cited IDs in candidate set + at least one citation → valid
- Any cited ID NOT in candidate set → invalid (hallucinated_ids)
- Zero citations + require_at_least_one=True → invalid (no_citations)

Resilient to:
- Mixed inline + structured citations
- Duplicate citations (deduped)
- Mixed-case UUIDs (normalized)
- Malformed UUIDs in structured list (skipped, not raised)

Side-effect-free; pure regex + set logic. Audit-on-failure handled by
the writer (T2), not the validator.

Verification receipts:
[CC fills in: validation tests pass, writer regression pass, smoke result]

Files: src/synthesis/validation.py (NEW),
       src/synthesis/writer.py (1-line: import + default callback wiring),
       tests/synthesis/test_validation.py (NEW, 8 unit tests)
```

```bash
git commit -F /tmp/cp8-p2-t3-commit-msg.txt
git log -1 --stat
git push origin master
```

**Final gate:** push exit 0.

---

## Halt conditions (specific to this task)

1. **`ValidationResult` not defined in writer.** Halt — T2 didn't ship the dataclass; validation.py has nowhere to import from.
2. **Wiring change requires more than one logical change to writer.py.** Halt — scope violated.
3. **T2 writer regression tests fail after wiring.** Halt — revert and investigate.
4. **Smoke test in step 7 fails with `validation_failed` against real Haiku output.** Halt — validator strictness is incompatible with the prompt's actual output. Likely a prompt template or regex mismatch.

---

## Definition of done

1. `src/synthesis/validation.py` exists with `validate_synthesis_citations` and the regex.
2. `writer.py` uses validator as default when caller passes `None`.
3. 8 unit tests pass.
4. T2 writer integration tests still all pass.
5. Smoke run on real cluster shows `success=True` (validator does not falsely reject real LLM output).
6. Single commit pushed.
7. No `CP8-P2-T3-BLOCKED.md`.

**No deploy needed.**
