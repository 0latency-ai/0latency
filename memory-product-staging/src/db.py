"""
Shared database module for utility scripts.
Uses psycopg2 with parameterized queries — NO subprocess psql, NO f-string SQL.
"""
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from config import get_db_conn


@contextmanager
def get_conn():
    """Get a database connection (context manager, auto-closes)."""
    conn = psycopg2.connect(get_db_conn())
    try:
        yield conn
    finally:
        conn.close()


def execute(query: str, params: tuple = None) -> list[dict]:
    """Execute a query and return results as list of dicts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            conn.commit()
            return []


def execute_one(query: str, params: tuple = None) -> dict | None:
    """Execute a query and return first result as dict, or None."""
    rows = execute(query, params)
    return rows[0] if rows else None


def execute_scalar(query: str, params: tuple = None):
    """Execute a query and return the first column of the first row."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if row:
                conn.commit()
                return row[0]
            conn.commit()
            return None


def execute_modify(query: str, params: tuple = None) -> int:
    """Execute an INSERT/UPDATE/DELETE and return rowcount."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            count = cur.rowcount
            conn.commit()
            return count
