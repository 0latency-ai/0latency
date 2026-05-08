"""
Pytest configuration for test namespace isolation.

ISSUE: api.main adds src/ to sys.path, making "synthesis" a top-level package.
When pytest collects tests/synthesis/*.py after api.main is imported, it gets
confused between tests.synthesis and the src/synthesis package.

FIX: Ensure tests/ directory is properly namespaced by adding an __init__.py
and this conftest.py. The presence of conftest.py at tests/ root tells pytest
to treat this as a proper test package hierarchy.
"""

# This file intentionally left minimal. Its mere existence tells pytest
# that tests/ is a package root separate from src/.

import pytest
import psycopg2
import os

try:
    from pgvector.psycopg2 import register_vector
except ImportError:
    register_vector = None


@pytest.fixture
def db_conn():
    """Get database connection from environment."""
    db_url = os.environ.get("MEMORY_DB_CONN") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("MEMORY_DB_CONN or DATABASE_URL not set; skipping DB integration tests")

    conn = psycopg2.connect(db_url)
    if register_vector is not None:
        register_vector(conn)
    yield conn
    conn.close()
