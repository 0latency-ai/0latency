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
    SELECT string_agg(definition, E'\n' ORDER BY ord) FROM (
      SELECT 1 as ord, table_name || ' ' || column_name || ' ' || data_type as definition
        FROM information_schema.columns
        WHERE table_schema = 'memory_service' AND table_name != 'alembic_version'
      UNION ALL
      SELECT 2, conname || ' ' || pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid::regclass::text LIKE 'memory_service.%'
          AND conrelid::regclass::text NOT LIKE '%alembic_version%'
      UNION ALL
      SELECT 3, indexname || ' ' || indexdef
        FROM pg_indexes
        WHERE schemaname = 'memory_service' AND tablename != 'alembic_version'
    ) sub;
    """
    out = subprocess.run(
        ["psql", db_url, "-tA", "-c", sql],
        capture_output=True, text=True, check=True
    ).stdout
    return hashlib.sha256(out.encode()).hexdigest()


def _list_revisions():
    """Return revisions newer than baseline, oldest-first."""
    out = _run("alembic history -r 0001_baseline:head | grep -E '^[a-z0-9_]+ ->' || true")
    revs = []
    for line in out.strip().splitlines():
        if "->" in line and "(head)" not in line:
            # Format: "<rev> -> <next>, <message>"
            after = line.split("->")[1].strip().split(",")[0].strip()
            revs.append(after)
    # Reverse to get oldest-first
    return list(reversed(revs))


def _get_prod_revision():
    """Get the current revision from production database."""
    prod_url = os.environ.get("DATABASE_URL")
    out = subprocess.run(
        ["psql", prod_url, "-tA", "-c", "SELECT version_num FROM memory_service.alembic_version"],
        capture_output=True, text=True, check=True
    ).stdout.strip()
    return out if out else "head"


@pytest.fixture(scope="module")
def staging_at_baseline():
    """Reset staging to baseline state once per module."""
    if not STAGING_URL:
        pytest.skip("STAGING_DATABASE_URL not set")
    _run("bash scripts/staging_reset.sh")
    # staging_reset copies prod schema, so stamp at prod revision then downgrade to baseline
    prod_rev = _get_prod_revision()
    _run(f"alembic -x env=staging stamp {prod_rev}")
    _run("alembic -x env=staging downgrade 0001_baseline")
    yield


@pytest.mark.parametrize("rev", _list_revisions() or ["__no_revisions__"])
def test_revision_round_trip(staging_at_baseline, rev):
    """upgrade(rev) then downgrade(-1) must leave schema unchanged."""
    if rev == "__no_revisions__":
        pytest.skip("No revisions newer than baseline yet")

    # Capture pre-upgrade schema hash
    before = _schema_hash(STAGING_URL)

    # Upgrade to this revision
    _run(f"alembic -x env=staging upgrade {rev}")

    # Downgrade back
    _run("alembic -x env=staging downgrade -1")

    # Capture post-downgrade schema hash
    after = _schema_hash(STAGING_URL)

    assert before == after, f"Revision {rev} downgrade did not restore schema. Before: {before[:12]}, After: {after[:12]}"

    # Re-upgrade so we're at the correct state for the next test
    _run(f"alembic -x env=staging upgrade {rev}")
