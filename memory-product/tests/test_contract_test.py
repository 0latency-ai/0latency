"""
Unit tests for scripts/contract_test.py
Tests helper functions without making network calls.
"""

import importlib.util
import tempfile
from pathlib import Path
import re


# Import contract_test module
spec = importlib.util.spec_from_file_location("contract_test", "scripts/contract_test.py")
contract_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract_test)


def test_generate_sentinel_format():
    """Sentinel matches expected pattern: 0latency-contract-{timestamp}-{8hex}"""
    sentinel = contract_test.generate_sentinel()
    pattern = r"^0latency-contract-\d{8}T\d{6}Z-[0-9a-f]{8}$"
    assert re.match(pattern, sentinel), f"Sentinel doesn't match pattern: {sentinel}"


def test_generate_sentinel_unique():
    """Two calls produce different sentinels."""
    sentinel1 = contract_test.generate_sentinel()
    sentinel2 = contract_test.generate_sentinel()
    assert sentinel1 != sentinel2, "Sentinels should be unique"


def test_load_env_parses_key_value():
    """load_env() parses a temp .env file correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("TEST_KEY=test_value\n# comment line\nANOTHER_KEY=another_value\n")
        
        # Change to temp dir
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            env_vars = contract_test.load_env()
            assert "TEST_KEY" in env_vars, "TEST_KEY not found in parsed env"
            assert env_vars["TEST_KEY"] == "test_value", f"Unexpected value: {env_vars[TEST_KEY]}"
            assert "ANOTHER_KEY" in env_vars, "ANOTHER_KEY not found"
            assert env_vars["ANOTHER_KEY"] == "another_value"
        finally:
            os.chdir(old_cwd)


def test_generate_sentinel_contains_timestamp():
    """Sentinel contains today's date substring."""
    from datetime import datetime, timezone
    sentinel = contract_test.generate_sentinel()
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert today_str in sentinel, f"Sentinel doesn't contain today's date: {sentinel}"
