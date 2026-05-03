"""
CP8 Phase 2 Task 3 — Source-Quote Validation Tests

Eight unit tests covering citation validation logic:
1. Inline citations all legit
2. Structured citations all legit
3. Inline with hallucination
4. Structured with hallucination
5. No citations required fails
6. No citations not required passes
7. Deduplication of repeated citations
8. Malformed UUID in structured list skipped
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uuid
from src.synthesis.validation import validate_synthesis_citations


def test_inline_citations_all_legit():
    """Test 1: All inline citations are in the candidate set."""
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    id3 = uuid.uuid4()

    candidate_ids = [id1, id2, id3]
    synthesis_text = f"Based on evidence [src:{id1}] and [src:{id2}], we conclude that [src:{id3}] supports this."

    result = validate_synthesis_citations(
        synthesis_text=synthesis_text,
        candidate_source_ids=candidate_ids,
    )

    assert result.valid is True
    assert len(result.cited_ids_in_source_set) == 3
    assert set(result.cited_ids_in_source_set) == {id1, id2, id3}
    assert len(result.cited_ids_NOT_in_source_set) == 0
    assert result.failure_reason is None


def test_structured_citations_all_legit():
    """Test 2: All structured citations are in the candidate set, no inline."""
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()

    candidate_ids = [id1, id2]
    synthesis_text = "This synthesis has no inline citations."
    structured = [id1, id2]

    result = validate_synthesis_citations(
        synthesis_text=synthesis_text,
        candidate_source_ids=candidate_ids,
        structured_cited_ids=structured,
    )

    assert result.valid is True
    assert len(result.cited_ids_in_source_set) == 2
    assert set(result.cited_ids_in_source_set) == {id1, id2}
    assert len(result.cited_ids_NOT_in_source_set) == 0


def test_inline_with_one_hallucination():
    """Test 3: Two legit + one not in candidates."""
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    id_hallucinated = uuid.uuid4()

    candidate_ids = [id1, id2]
    synthesis_text = f"Evidence [src:{id1}] and [src:{id2}], but also [src:{id_hallucinated}] which is fake."

    result = validate_synthesis_citations(
        synthesis_text=synthesis_text,
        candidate_source_ids=candidate_ids,
    )

    assert result.valid is False
    assert result.failure_reason == "hallucinated_ids"
    assert len(result.cited_ids_in_source_set) == 2
    assert set(result.cited_ids_in_source_set) == {id1, id2}
    assert len(result.cited_ids_NOT_in_source_set) == 1
    assert result.cited_ids_NOT_in_source_set[0] == id_hallucinated


def test_structured_with_one_hallucination():
    """Test 4: Hallucination via structured list."""
    id1 = uuid.uuid4()
    id_hallucinated = uuid.uuid4()

    candidate_ids = [id1]
    synthesis_text = "No inline citations."
    structured = [id1, id_hallucinated]

    result = validate_synthesis_citations(
        synthesis_text=synthesis_text,
        candidate_source_ids=candidate_ids,
        structured_cited_ids=structured,
    )

    assert result.valid is False
    assert result.failure_reason == "hallucinated_ids"
    assert len(result.cited_ids_NOT_in_source_set) == 1
    assert id_hallucinated in result.cited_ids_NOT_in_source_set


def test_no_citations_required_fails():
    """Test 5: Empty citations with require_at_least_one=True fails."""
    candidate_ids = [uuid.uuid4()]
    synthesis_text = "No citations at all."

    result = validate_synthesis_citations(
        synthesis_text=synthesis_text,
        candidate_source_ids=candidate_ids,
        structured_cited_ids=None,
        require_at_least_one_citation=True,
    )

    assert result.valid is False
    assert result.failure_reason == "no_citations"
    assert len(result.cited_ids_in_source_set) == 0
    assert len(result.cited_ids_NOT_in_source_set) == 0


def test_no_citations_not_required_passes():
    """Test 6: Empty citations with require_at_least_one=False passes."""
    candidate_ids = [uuid.uuid4()]
    synthesis_text = "No citations at all."

    result = validate_synthesis_citations(
        synthesis_text=synthesis_text,
        candidate_source_ids=candidate_ids,
        structured_cited_ids=None,
        require_at_least_one_citation=False,
    )

    assert result.valid is True
    assert result.failure_reason is None
    assert len(result.cited_ids_in_source_set) == 0


def test_dedupes_repeated_citations():
    """Test 7: Same UUID cited 5 times inline should dedupe to 1."""
    id1 = uuid.uuid4()
    candidate_ids = [id1]

    # Cite the same ID 5 times
    synthesis_text = f"[src:{id1}] and [src:{id1}] and [src:{id1}] and [src:{id1}] and [src:{id1}]"

    result = validate_synthesis_citations(
        synthesis_text=synthesis_text,
        candidate_source_ids=candidate_ids,
    )

    assert result.valid is True
    assert len(result.cited_ids_in_source_set) == 1
    assert result.cited_ids_in_source_set[0] == id1


def test_malformed_uuid_in_structured_skipped():
    """Test 8: Structured list with malformed UUID should skip the bad one."""
    id1 = uuid.uuid4()
    candidate_ids = [id1]

    synthesis_text = "No inline citations."
    structured = ["not-a-uuid", id1]  # One bad, one good

    result = validate_synthesis_citations(
        synthesis_text=synthesis_text,
        candidate_source_ids=candidate_ids,
        structured_cited_ids=structured,
    )

    # Should process only the valid UUID
    assert result.valid is True
    assert len(result.cited_ids_in_source_set) == 1
    assert result.cited_ids_in_source_set[0] == id1
