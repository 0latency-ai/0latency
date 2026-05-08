"""
CP8 P5.7 T4 - Regression test for _handle_correction _db_execute_rows migration.

Tests that _handle_correction correctly uses tuple unpacking instead of
split('|||') to prevent silent column-alignment failures.
"""
import pytest


def test_handle_correction_uses_rows_not_split():
    """Verify _handle_correction migrated to _db_execute_rows."""
    from src.storage_multitenant import _handle_correction
    import inspect
    
    source = inspect.getsource(_handle_correction)
    
    # Should NOT contain the vulnerable split pattern
    assert "split('|||')" not in source, "_handle_correction still uses vulnerable split pattern"
    assert 'split("|||")' not in source, "_handle_correction still uses vulnerable split pattern"
    
    # Should use _db_execute_rows, not _db_execute
    assert '_db_execute_rows' in source, "_handle_correction should use _db_execute_rows"
    
    # Should use tuple unpacking pattern
    assert 'for (old_id,' in source or 'for (' in source, "_handle_correction should use tuple unpacking"
    
    print("✓ _handle_correction correctly migrated to _db_execute_rows")


def test_split_pattern_not_in_migrated_function():
    """Ensure the migrated function doesn't accidentally use split."""
    from src.storage_multitenant import _handle_correction
    import inspect
    
    source = inspect.getsource(_handle_correction)
    lines = source.split('\n')
    
    for i, line in enumerate(lines):
        if 'parts = row.split' in line:
            pytest.fail(f"Found vulnerable split pattern at line {i+1}: {line.strip()}")
    
    print("✓ No split pattern found in _handle_correction")
