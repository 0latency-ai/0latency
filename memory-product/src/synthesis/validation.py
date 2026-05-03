"""
CP8 Phase 2 Task 3 — Source-Quote Validation

Validates that synthesis text citations reference only IDs from the candidate set.

Why both inline and structured citations:
- Resilience to LLM format drift (if prompt changes, validator still catches both)
- Defense in depth: even if JSON parsing fails, inline citations can be validated

Why duplicates are deduped:
- Set semantics ensure citation counts don't affect legitimacy check
- LLM may cite same atom multiple times in different contexts

Why malformed UUIDs are silently skipped:
- Regex only matches well-formed UUID4 patterns; partial UUIDs don't match
- Not a failure mode — if LLM outputs gibberish, it won't match the pattern

Relationship to T2 writer:
- Validator is pure, side-effect-free
- Writer handles audit-on-failure writes
- Validator just partitions cited IDs into legit vs hallucinated sets
"""

import re
import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """Result from source-quote validation callback (T3 implements)."""
    valid: bool
    cited_ids_in_source_set: list[uuid.UUID]
    cited_ids_NOT_in_source_set: list[uuid.UUID]  # hallucinations
    failure_reason: Optional[str]


# Regex to match inline citations: [src:UUID]
UUID_CITE_PATTERN = re.compile(
    r'\[src:([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]',
    re.IGNORECASE
)


def validate_synthesis_citations(
    synthesis_text: str,
    candidate_source_ids: list[uuid.UUID],
    structured_cited_ids: Optional[list] = None,
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
    # Step 1: Extract inline citations
    inline_matches = UUID_CITE_PATTERN.finditer(synthesis_text)
    inline_ids = set()

    for match in inline_matches:
        try:
            uid = uuid.UUID(match.group(1))
            inline_ids.add(uid)
        except ValueError:
            # Malformed UUID (shouldn't happen if regex is correct, but defensive)
            continue

    # Step 2: Combine with structured citations
    structured_ids = set()

    if structured_cited_ids:
        for item in structured_cited_ids:
            try:
                # Coerce to UUID - handle both string and UUID object inputs
                if isinstance(item, uuid.UUID):
                    structured_ids.add(item)
                else:
                    uid = uuid.UUID(str(item))
                    structured_ids.add(uid)
            except (ValueError, TypeError, AttributeError):
                # Malformed UUID in structured list - skip it
                # (logged as warning in production; silently skipped in validator)
                continue

    all_cited = inline_ids | structured_ids

    # Step 3: Convert candidate set (handle both UUIDs and strings)
    candidate_set = set()
    for item in candidate_source_ids:
        if isinstance(item, uuid.UUID):
            candidate_set.add(item)
        else:
            try:
                candidate_set.add(uuid.UUID(str(item)))
            except (ValueError, TypeError):
                # Skip malformed UUIDs
                continue

    # Step 4: Partition
    legit = all_cited & candidate_set
    hallucinated = all_cited - candidate_set

    # Step 5: Apply validation rules
    if len(all_cited) == 0 and require_at_least_one_citation:
        return ValidationResult(
            valid=False,
            cited_ids_in_source_set=[],
            cited_ids_NOT_in_source_set=[],
            failure_reason="no_citations",
        )

    if len(hallucinated) > 0:
        return ValidationResult(
            valid=False,
            cited_ids_in_source_set=sorted(legit),
            cited_ids_NOT_in_source_set=sorted(hallucinated),
            failure_reason="hallucinated_ids",
        )

    # Step 6: Success
    return ValidationResult(
        valid=True,
        cited_ids_in_source_set=sorted(legit),
        cited_ids_NOT_in_source_set=[],
        failure_reason=None,
    )
