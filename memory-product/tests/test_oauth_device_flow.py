"""
OAuth Device Authorization Flow Tests
Tests migration 032 + /oauth/device/code + /oauth/device/token + /oauth/device/approve

Run: python3 -m pytest tests/test_oauth_device_flow.py -v
"""

import pytest
import requests
import os
import time
from datetime import datetime, timezone, timedelta

BASE = os.environ.get("ZL_TEST_URL", "https://api.0latency.ai")

# Will be fetched from DB in conftest
TEST_API_KEY = None


def setup_module():
    """Get a valid API key from the database."""
    global TEST_API_KEY
    import psycopg2
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")
    
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT api_key_live FROM memory_service.tenants WHERE active=true AND api_key_live LIKE 'zl_live_%' LIMIT 1")
    row = cur.fetchone()
    conn.close()
    
    if not row:
        pytest.skip("No active tenant with valid API key found")
    
    TEST_API_KEY = row[0]


def test_migration_032_table_exists():
    """Verify migration 032 created oauth_device_codes table."""
    import psycopg2
    
    db_url = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Check table exists
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'memory_service' AND table_name = 'oauth_device_codes'
    """)
    assert cur.fetchone() is not None, "Table oauth_device_codes should exist"
    
    # Check indexes exist
    cur.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'oauth_device_codes' AND schemaname = 'memory_service'
    """)
    indexes = [row[0] for row in cur.fetchall()]
    assert 'oauth_device_codes_pkey' in indexes, "Primary key index should exist"
    assert 'oauth_device_codes_user_code_key' in indexes, "Unique index on user_code should exist"
    assert 'idx_oauth_device_user_code' in indexes, "Explicit index on user_code should exist"
    
    conn.close()


def test_device_code_generation():
    """Test POST /oauth/device/code generates device and user codes."""
    r = requests.post(f"{BASE}/oauth/device/code", json={}, timeout=10)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    
    data = r.json()
    assert 'device_code' in data
    assert 'user_code' in data
    assert 'verification_uri' in data
    assert 'expires_in' in data
    assert 'interval' in data
    
    # Validate format
    assert len(data['device_code']) == 36, "device_code should be a UUID (36 chars with dashes)"
    assert len(data['user_code']) == 9, "user_code should be 9 chars (ABCD-EFGH)"
    assert data['user_code'][4] == '-', "user_code should have dash at position 4"
    assert data['verification_uri'] == "https://0latency.ai/auth/device"
    assert data['expires_in'] == 600
    assert data['interval'] == 5


def test_device_token_unapproved():
    """Test POST /oauth/device/token returns authorization_pending for unapproved code."""
    # Generate a code first
    r = requests.post(f"{BASE}/oauth/device/code", json={}, timeout=10)
    assert r.status_code == 200
    device_code = r.json()['device_code']
    
    # Poll immediately (should be pending)
    r = requests.post(f"{BASE}/oauth/device/token", json={"device_code": device_code}, timeout=10)
    assert r.status_code == 400
    assert r.json()['detail']['error'] == 'authorization_pending'


def test_device_token_invalid_grant():
    """Test POST /oauth/device/token returns invalid_grant for unknown code."""
    r = requests.post(f"{BASE}/oauth/device/token", json={"device_code": "invalid-code-12345"}, timeout=10)
    assert r.status_code == 400
    assert r.json()['detail']['error'] == 'invalid_grant'


def test_device_approval_invalid_code():
    """Test POST /oauth/device/approve rejects invalid user_code."""
    r = requests.post(
        f"{BASE}/oauth/device/approve",
        headers={"X-API-Key": TEST_API_KEY},
        json={"user_code": "INVALID-CODE"},
        timeout=10
    )
    assert r.status_code == 400
    assert r.json()['detail']['error'] == 'invalid_code'


def test_full_happy_path():
    """Test complete OAuth flow: generate -> approve -> poll -> get token."""
    # Step 1: Generate device code
    r = requests.post(f"{BASE}/oauth/device/code", json={}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    device_code = data['device_code']
    user_code = data['user_code']
    
    # Step 2: Poll before approval (should be pending)
    r = requests.post(f"{BASE}/oauth/device/token", json={"device_code": device_code}, timeout=10)
    assert r.status_code == 400
    assert r.json()['detail']['error'] == 'authorization_pending'
    
    # Step 3: Approve via dashboard endpoint
    r = requests.post(
        f"{BASE}/oauth/device/approve",
        headers={"X-API-Key": TEST_API_KEY},
        json={"user_code": user_code},
        timeout=10
    )
    assert r.status_code == 200, f"Approval failed: {r.text}"
    assert r.json()['status'] == 'approved'
    
    # Step 4: Poll after approval (should return token)
    r = requests.post(f"{BASE}/oauth/device/token", json={"device_code": device_code}, timeout=10)
    assert r.status_code == 200, f"Token request failed: {r.text}"
    token_data = r.json()
    
    assert 'access_token' in token_data
    assert 'tenant_id' in token_data
    assert token_data['access_token'].startswith('zl_live_'), "access_token should be a valid API key"
    assert len(token_data['access_token']) == 40, "access_token should be 40 chars"
    
    # Step 5: Verify the token works (call /memories with it)
    r = requests.get(
        f"{BASE}/memories",
        headers={"X-API-Key": token_data['access_token']},
        params={"agent_id": "oauth-test"},
        timeout=10
    )
    assert r.status_code == 200, "Returned access_token should be valid"


def test_double_approval_fails():
    """Test that approving the same code twice fails."""
    # Generate code
    r = requests.post(f"{BASE}/oauth/device/code", json={}, timeout=10)
    assert r.status_code == 200
    user_code = r.json()['user_code']
    
    # Approve once
    r = requests.post(
        f"{BASE}/oauth/device/approve",
        headers={"X-API-Key": TEST_API_KEY},
        json={"user_code": user_code},
        timeout=10
    )
    assert r.status_code == 200
    
    # Try to approve again (should fail)
    r = requests.post(
        f"{BASE}/oauth/device/approve",
        headers={"X-API-Key": TEST_API_KEY},
        json={"user_code": user_code},
        timeout=10
    )
    assert r.status_code == 400
    assert r.json()['detail']['error'] == 'already_approved'


def test_expired_code():
    """Test that expired codes are rejected."""
    import psycopg2
    
    # Generate a code
    r = requests.post(f"{BASE}/oauth/device/code", json={}, timeout=10)
    assert r.status_code == 200
    device_code = r.json()['device_code']
    user_code = r.json()['user_code']
    
    # Manually expire it in the database
    db_url = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        UPDATE memory_service.oauth_device_codes
        SET expires_at = NOW() - INTERVAL '1 minute'
        WHERE device_code = %s
    """, (device_code,))
    conn.commit()
    conn.close()
    
    # Try to poll (should be expired)
    r = requests.post(f"{BASE}/oauth/device/token", json={"device_code": device_code}, timeout=10)
    assert r.status_code == 400
    assert r.json()['detail']['error'] == 'expired_token'
    
    # Try to approve (should also fail)
    r = requests.post(
        f"{BASE}/oauth/device/approve",
        headers={"X-API-Key": TEST_API_KEY},
        json={"user_code": user_code},
        timeout=10
    )
    assert r.status_code == 400
    assert r.json()['detail']['error'] == 'invalid_code'


if __name__ == "__main__":
    # Run tests manually
    import sys
    
    print("Setting up...")
    setup_module()
    
    tests = [
        ("Migration 032 table exists", test_migration_032_table_exists),
        ("Device code generation", test_device_code_generation),
        ("Device token unapproved", test_device_token_unapproved),
        ("Device token invalid grant", test_device_token_invalid_grant),
        ("Device approval invalid code", test_device_approval_invalid_code),
        ("Full happy path", test_full_happy_path),
        ("Double approval fails", test_double_approval_fails),
        ("Expired code rejected", test_expired_code),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            print(f"\n🧪 {name}")
            test_fn()
            print(f"  ✅ Passed")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ Failed: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    sys.exit(0 if failed == 0 else 1)
