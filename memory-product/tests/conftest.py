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
