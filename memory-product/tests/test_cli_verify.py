"""
Integration tests for cli/verify.py
Runs the CLI as a subprocess and checks exit codes and output.
"""

import os
import subprocess
import pytest

# Fixture UUID from test_source_endpoint.py
RAW_TURN_ID = "9deed596-57f4-47fe-b788-1c640f9f178b"
ZEROLATENCY_API_KEY = os.environ.get("ZEROLATENCY_API_KEY", "")


def run_verify(*args):
    """Run cli/verify.py with args and return CompletedProcess."""
    cmd = ["python3", "cli/verify.py"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


@pytest.mark.integration
def test_verify_raw_turn_exits_zero():
    """Verify with valid raw_turn UUID exits 0."""
    result = run_verify(RAW_TURN_ID)
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"


@pytest.mark.integration
def test_verify_raw_turn_output_contains_verbatim():
    """Verify output contains verbatim for raw_turn."""
    result = run_verify(RAW_TURN_ID)
    assert "verbatim" in result.stdout, f"Expected verbatim in output: {result.stdout}"


@pytest.mark.integration
def test_verify_nonexistent_exits_one():
    """Verify with nil UUID exits 1 (404)."""
    result = run_verify("00000000-0000-0000-0000-000000000000")
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stderr: {result.stderr}"


@pytest.mark.integration
def test_verify_bad_uuid_exits_three():
    """Verify with malformed UUID exits 3 (422)."""
    result = run_verify("not-a-uuid")
    assert result.returncode == 3, f"Expected exit 3, got {result.returncode}. stderr: {result.stderr}"


@pytest.mark.integration
def test_verify_bad_key_exits_two():
    """Verify with bad API key exits 2 (401)."""
    result = run_verify(RAW_TURN_ID, "--api-key", "zl_live_bad")
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}. stderr: {result.stderr}"
