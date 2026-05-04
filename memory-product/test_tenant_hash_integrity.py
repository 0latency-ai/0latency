#!/usr/bin/env python3
"""
Integration test: Verify api_key_hash matches sha256(api_key_live) for all tenants

This test prevents hash drift by auditing the database after any tenant key operations.
Run in CI after any migrations or tenant-related changes.

Background: Hash drift affected 27/110 tenants (24.5%) on 2026-05-03 due to buggy
rotate_api_key endpoint that only updated api_key_hash without updating api_key_live.

Expected: This test should ALWAYS pass after 2026-05-04 once the trigger is deployed.
If it fails, a code path is bypassing the trigger or the trigger is not deployed.
"""

import os
import sys
import hashlib
import psycopg2
from urllib.parse import urlparse


def test_tenant_hash_integrity():
    """Verify all tenants have api_key_hash = sha256(api_key_live)"""
    
    # Get database connection
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("⚠️  DATABASE_URL not set - skipping integration test")
        return True  # Don't fail CI if DB not available
    
    result = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
    
    cur = conn.cursor()
    
    # Get all tenants with live keys
    cur.execute("""
        SELECT id, name, api_key_live, api_key_hash 
        FROM memory_service.tenants 
        WHERE api_key_live IS NOT NULL
        ORDER BY created_at
    """)
    
    tenants = cur.fetchall()
    
    if not tenants:
        print("✓ No tenants with API keys found (empty database)")
        cur.close()
        conn.close()
        return True
    
    drifted = []
    checked = 0
    
    for tenant_id, name, api_key_live, stored_hash in tenants:
        checked += 1
        correct_hash = hashlib.sha256(api_key_live.encode()).hexdigest()
        
        if correct_hash != stored_hash:
            last4 = api_key_live[-4:] if api_key_live else "????"
            drifted.append({
                'id': tenant_id,
                'name': name,
                'last4': last4
            })
    
    cur.close()
    conn.close()
    
    # Report results
    if drifted:
        print(f"\n❌ HASH DRIFT DETECTED - {len(drifted)}/{checked} tenants affected:")
        for t in drifted:
            print(f"   - {t['name']} ({t['id']}) key ending ...{t['last4']}")
        print(f"\nFAILURE: Hash drift indicates a code path is not updating api_key_hash")
        print(f"         when writing api_key_live, or the trigger is not deployed.")
        print(f"\nAction required:")
        print(f"1. Check if migration 024_tenant_key_hash_trigger.sql is deployed")
        print(f"2. Audit recent code changes to api_key_live write paths")
        print(f"3. Run: python3 audit_tenant_hashes.py  # to repair drift")
        return False
    else:
        print(f"✓ Hash integrity verified - all {checked} tenants have matching hashes")
        return True


if __name__ == "__main__":
    success = test_tenant_hash_integrity()
    sys.exit(0 if success else 1)
