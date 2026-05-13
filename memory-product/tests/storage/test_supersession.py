"""
F3a Gate G3: Unit tests for contradiction supersession fix.

Tests verify:
  (a) _handle_correction uses contradicts_id when present in metadata
  (b) _handle_correction falls back to embedding search without contradicts_id
  (c) _supersede_memory sets superseded_at and superseded_by correctly
"""
from unittest.mock import patch, MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_memory(headline, context="", memory_type="correction", contradicts_id=None):
    """Create a memory dict matching the format used in storage_multitenant.py."""
    meta = {}
    if contradicts_id:
        meta["contradicts_id"] = contradicts_id
    return {
        "headline": headline,
        "context": context,
        "memory_type": memory_type,
        "metadata": meta,
    }


# ---------------------------------------------------------------------------
# (a) _handle_correction uses contradicts_id when available
# ---------------------------------------------------------------------------

class TestHandleCorrectionWithContradicts:
    """When metadata contains contradicts_id, _handle_correction should
    directly target that memory instead of doing an embedding search."""

    @patch("storage_multitenant._supersede_memory")
    @patch("storage_multitenant._db_execute_rows")
    def test_uses_contradicts_id_directly(self, mock_db, mock_supersede):
        """Should query by exact ID, not by embedding similarity."""
        from storage_multitenant import _handle_correction

        old_id = "old-memory-uuid"
        correction_id = "new-correction-uuid"
        tenant_id = "test-tenant"

        memory = _make_memory(
            headline="Rachel moved to suburbs",
            contradicts_id=old_id,
        )

        # DB returns the old memory
        mock_db.return_value = [(old_id, "Rachel lives in Chicago")]

        _handle_correction(memory, correction_id, tenant_id)

        # Verify it queried by exact ID, not by embedding
        db_call_sql = mock_db.call_args[0][0]
        assert "id = %s" in db_call_sql
        assert "embedding" not in db_call_sql.lower()
        assert "<=> " not in db_call_sql

        # Verify supersede was called with the correct memory
        mock_supersede.assert_called_once()
        args = mock_supersede.call_args[0]
        assert args[0] == old_id  # old_id
        assert args[1] == "Rachel lives in Chicago"  # old_headline
        assert args[2] == correction_id

    @patch("storage_multitenant._supersede_memory")
    @patch("storage_multitenant._db_execute_rows")
    def test_no_supersede_if_already_superseded(self, mock_db, mock_supersede):
        """If the contradicted memory is already superseded, no action taken."""
        from storage_multitenant import _handle_correction

        memory = _make_memory(
            headline="Rachel moved to suburbs",
            contradicts_id="already-superseded-uuid",
        )

        # DB returns empty (memory already superseded or not found)
        mock_db.return_value = []

        _handle_correction(memory, "new-correction", "test-tenant")

        mock_supersede.assert_not_called()


# ---------------------------------------------------------------------------
# (b) Fallback to embedding search without contradicts_id
# ---------------------------------------------------------------------------

class TestHandleCorrectionFallback:
    """When metadata does NOT contain contradicts_id, _handle_correction
    should fall back to embedding-based search."""

    @patch("storage_multitenant._supersede_memory")
    @patch("storage_multitenant._db_execute_rows")
    @patch("storage_multitenant._embed_text")
    def test_falls_back_to_embedding_search(self, mock_embed, mock_db, mock_supersede):
        """Without contradicts_id, should do embedding similarity search."""
        from storage_multitenant import _handle_correction

        memory = _make_memory(
            headline="Rachel moved to suburbs",
            # No contradicts_id in metadata
        )

        mock_embed.return_value = [0.1] * 384  # Fake embedding
        mock_db.return_value = [
            ("old-uuid", "Rachel lives in Chicago", "user-agent"),
        ]

        _handle_correction(memory, "correction-id", "test-tenant")

        # Verify it used embedding search (has <=> operator)
        db_call_sql = mock_db.call_args[0][0]
        assert "<=>" in db_call_sql

        mock_supersede.assert_called_once()

    @patch("storage_multitenant._supersede_memory")
    @patch("storage_multitenant._db_execute_rows")
    @patch("storage_multitenant._embed_text")
    def test_no_supersede_if_no_similar_found(self, mock_embed, mock_db, mock_supersede):
        """If embedding search returns nothing, no supersession."""
        from storage_multitenant import _handle_correction

        memory = _make_memory(headline="Some correction")
        mock_embed.return_value = [0.1] * 384
        mock_db.return_value = []  # No similar memories found

        _handle_correction(memory, "correction-id", "test-tenant")

        mock_supersede.assert_not_called()


# ---------------------------------------------------------------------------
# (c) _supersede_memory behavior
# ---------------------------------------------------------------------------

class TestSupersedeMemory:
    """Verify _supersede_memory sets the correct fields."""

    @patch("storage_multitenant._db_execute_rows")
    def test_sets_superseded_fields(self, mock_db):
        """Should UPDATE with superseded_at=now() and superseded_by=correction_id."""
        from storage_multitenant import _supersede_memory

        mock_db.return_value = None
        memory = {"headline": "New fact about Rachel"}

        _supersede_memory(
            old_id="old-uuid",
            old_headline="Rachel lives in Chicago",
            correction_id="correction-uuid",
            memory=memory,
            tenant_id="test-tenant",
        )

        # Verify the UPDATE query
        db_call_sql = mock_db.call_args[0][0]
        assert "superseded_at" in db_call_sql
        assert "superseded_by" in db_call_sql
        assert "now()" in db_call_sql.lower() or "NOW()" in db_call_sql

        # Verify parameters include correction_id and old_id
        db_call_params = mock_db.call_args[0][1]
        assert "correction-uuid" in db_call_params
        assert "old-uuid" in db_call_params

    @patch("storage_multitenant._db_execute_rows")
    def test_only_supersedes_unsuperseded(self, mock_db):
        """UPDATE should include WHERE superseded_at IS NULL guard."""
        from storage_multitenant import _supersede_memory

        mock_db.return_value = None
        memory = {"headline": "New fact"}

        _supersede_memory("old-uuid", "Old fact", "correction-uuid", memory, "test-tenant")

        db_call_sql = mock_db.call_args[0][0]
        assert "superseded_at IS NULL" in db_call_sql
