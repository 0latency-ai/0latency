"""
For every Alembic revision newer than 0001_baseline, verify that
upgrade() followed by downgrade() returns the schema to the pre-upgrade state.

Runs against staging. Requires staging to be at the prior revision before
each test (we reset staging to baseline at the start of the suite).
"""
import os
import subprocess
import hashlib
import pytest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STAGING_URL = os.environ.get("STAGING_DATABASE_URL")


def _run(cmd, **kwargs):
    """Run a shell command, raising on non-zero. Returns stdout."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=str(REPO_ROOT), **kwargs
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\nstderr: {result.stderr}")
    return result.stdout


def _schema_hash(db_url):
    """Hash the schema (table defs + constraints + indexes) for comparison. Excludes alembic_version."""
    sql = """
    SELECT string_agg(definition, En ORDER BY definition) FROM (
      SELECT table_name || 
