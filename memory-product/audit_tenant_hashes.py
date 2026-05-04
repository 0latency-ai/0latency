#!/usr/bin/env python3
import os
import psycopg2
import hashlib
from urllib.parse import urlparse

# Database connection from .env
DATABASE_URL = os.environ['DATABASE_URL']

# Parse connection details
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

drifted = []
checked = 0

print(f"Auditing {len(tenants)} tenants for hash drift...")
print()

for tenant_id, name, api_key_live, stored_hash in tenants:
    checked += 1
    
    # Compute correct hash
    correct_hash = hashlib.sha256(api_key_live.encode()).hexdigest()
    
    if correct_hash != stored_hash:
        last4 = api_key_live[-4:] if api_key_live else "????"
        print(f"❌ DRIFT DETECTED:")
        print(f"   Tenant ID: {tenant_id}")
        print(f"   Name: {name}")
        print(f"   Key suffix: ...{last4}")
        print(f"   Stored hash: {stored_hash[:16]}...")
        print(f"   Correct hash: {correct_hash[:16]}...")
        print()
        
        drifted.append({
            'id': tenant_id,
            'name': name,
            'last4': last4,
            'correct_hash': correct_hash
        })

print(f"✓ Checked {checked} tenants")
print(f"✗ Found {len(drifted)} with hash drift")
print()

# Repair drifted tenants
if drifted:
    print("Repairing drifted tenants...")
    repaired = 0
    failed = 0
    
    for t in drifted:
        try:
            cur.execute(
                "UPDATE memory_service.tenants SET api_key_hash = %s WHERE id = %s",
                (t['correct_hash'], t['id'])
            )
            conn.commit()
            print(f"✓ Repaired {t['name']} ({t['id']}) key ...{t['last4']}")
            repaired += 1
        except Exception as e:
            print(f"✗ Failed to repair {t['name']}: {e}")
            failed += 1
            conn.rollback()
    
    print()
    print(f"Summary: {repaired} repaired, {failed} failed")
else:
    print("✓ No drift detected - all hashes are correct")

cur.close()
conn.close()
