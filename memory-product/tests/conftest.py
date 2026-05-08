"""
Pytest configuration for test namespace isolation.

ISSUE: api.main adds src/ to sys.path, making "synthesis" a top-level package.
When pytest collects tests/synthesis/*.py after api.main is imported, it gets
confused between tests.synthesis and the src/synthesis package.

FIX: Ensure tests/ directory is properly namespaced by adding an __init__.py
and this conftest.py. The presence of conftest.py at tests/ root tells pytest
to treat this as a proper test package hierarchy.
"""

import pytest
import psycopg2
import os

try:
    from pgvector.psycopg2 import register_vector
except ImportError:
    register_vector = None


@pytest.fixture(scope="function")
def db_conn():
    """Get database connection from environment with transaction management."""
    db_url = os.environ.get("MEMORY_DB_CONN") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("MEMORY_DB_CONN or DATABASE_URL not set; skipping DB integration tests")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False  # Ensure transactions
    
    if register_vector is not None:
        register_vector(conn)
    
    # Start with clean slate
    conn.rollback()
    
    yield conn
    
    # Rollback any uncommitted changes
    try:
        conn.rollback()
    except:
        pass
    
    conn.close()
