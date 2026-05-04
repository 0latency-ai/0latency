"""Pin the contract of 401 messages from the auth layer.

These tests guard against accidental message regression — message text is
shipped in error responses and developers depend on it for diagnosis.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import hashlib
import secrets
import psycopg2
import pytest
import requests

API_BASE = os.environ.get("API_BASE", "http://localhost:8420")


def _live_key_for_justin():
    db_url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT api_key_live FROM memory_service.tenants WHERE id='44c3080d-c196-407d-a606-4ea9f62ba0fc'"
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _insert_revoked_key_for_test(tenant_id: str = "44c3080d-c196-407d-a606-4ea9f62ba0fc") -> str:
    """Insert a revoked api_keys row and return the literal key (for use in test)."""
    test_body = ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))
    test_key = f"zl_live_{test_body}"
    test_hash = hashlib.sha256(test_key.encode()).hexdigest()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO memory_service.api_keys (tenant_id, key_hash, status, created_at, revoked_at)
            VALUES (%s::uuid, %s, 'revoked', now() - interval '1 day', now() - interval '12 hours')
            ON CONFLICT (key_hash) DO UPDATE SET status='revoked'
            """,
            (tenant_id, test_hash),
        )
    finally:
        conn.close()
    return test_key


def _delete_test_revoked_key(test_key: str):
    test_hash = hashlib.sha256(test_key.encode()).hexdigest()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM memory_service.api_keys WHERE key_hash = %s", (test_hash,))
    finally:
        conn.close()


def test_missing_header():
    r = requests.get(f"{API_BASE}/tenant-info")
    assert r.status_code == 401
    assert "Missing X-API-Key header" in r.json()["detail"]


def test_invalid_format_too_short():
    r = requests.get(f"{API_BASE}/tenant-info", headers={"X-API-Key": "zl_live_short"})
    assert r.status_code == 401
    assert "format is invalid" in r.json()["detail"].lower()


def test_invalid_format_wrong_prefix():
    bogus = "zl_test_" + ("x" * 32)
    r = requests.get(f"{API_BASE}/tenant-info", headers={"X-API-Key": bogus})
    assert r.status_code == 401
    assert "format is invalid" in r.json()["detail"].lower()


def test_not_found():
    nonexistent = "zl_live_" + ("a" * 32)
    r = requests.get(f"{API_BASE}/tenant-info", headers={"X-API-Key": nonexistent})
    assert r.status_code == 401
    assert "not found" in r.json()["detail"].lower()
    assert "rotation" in r.json()["detail"].lower()


def test_revoked():
    test_key = _insert_revoked_key_for_test()
    try:
        r = requests.get(f"{API_BASE}/tenant-info", headers={"X-API-Key": test_key})
        assert r.status_code == 401
        assert "revoked" in r.json()["detail"].lower()
    finally:
        _delete_test_revoked_key(test_key)


def test_active_key_succeeds():
    live_key = _live_key_for_justin()
    assert live_key is not None, "Justin's tenant has no api_key_live — test setup broken"
    r = requests.get(f"{API_BASE}/tenant-info", headers={"X-API-Key": live_key})
    assert r.status_code == 200
