#!/usr/bin/env python3
"""
Test script for the multi-tenant memory API
Creates a test tenant and tests the endpoints
"""

import hashlib
import secrets
import os
import sys

# Add src/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from storage_multitenant import create_tenant, get_tenant_by_api_key, _db_execute


def create_test_tenant():
    """Create a test tenant directly in the database."""
    # Generate a test API key
    api_key = f"zl_live_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Insert tenant directly (bypass RLS issues)
    try:
        import subprocess
        
        DB_CONN = os.environ.get("MEMORY_DB_CONN", "")
        
        query = f"""
        INSERT INTO memory_service.tenants (name, api_key_hash, plan, memory_limit, rate_limit_rpm, active)
        VALUES ('Test Company', '{api_key_hash}', 'pro', 50000, 100, true)
        RETURNING id, name, created_at;
        """
        
        result = subprocess.run(
            ["psql", DB_CONN, "-t", "-A", "-F", "|||", "-c", query],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "PGPASSWORD": os.environ.get("MEMORY_DB_PASSWORD", "")}
        )
        
        if result.returncode != 0:
            print(f"Error creating tenant: {result.stderr}")
            return None
        
        lines = result.stdout.strip().split("\n")
        if lines and lines[0]:
            parts = lines[0].split("|||")
            if len(parts) >= 3:
                return {
                    "tenant_id": parts[0],
                    "name": parts[1], 
                    "api_key": api_key,
                    "api_key_hash": api_key_hash,
                    "created_at": parts[2]
                }
    except Exception as e:
        print(f"Exception creating tenant: {e}")
        return None


def test_tenant_lookup(api_key_hash):
    """Test looking up tenant by API key hash."""
    tenant = get_tenant_by_api_key(api_key_hash)
    print(f"Tenant lookup result: {tenant}")
    return tenant


def main():
    print("=== Creating Test Tenant ===")
    tenant_info = create_test_tenant()
    
    if not tenant_info:
        print("Failed to create test tenant")
        return 1
    
    print(f"Created tenant:")
    print(f"  ID: {tenant_info['tenant_id']}")
    print(f"  Name: {tenant_info['name']}")
    print(f"  API Key: {tenant_info['api_key']}")
    print(f"  Created: {tenant_info['created_at']}")
    
    print("\n=== Testing Tenant Lookup ===")
    tenant = test_tenant_lookup(tenant_info['api_key_hash'])
    
    if tenant:
        print("✅ Tenant lookup successful")
        print(f"  Plan: {tenant['plan']}")
        print(f"  Memory limit: {tenant['memory_limit']}")
        print(f"  Rate limit: {tenant['rate_limit_rpm']} RPM")
    else:
        print("❌ Tenant lookup failed")
        return 1
    
    print(f"\n=== API Testing Instructions ===")
    print(f"Use this API key to test the endpoints:")
    print(f"curl -H 'X-API-Key: {tenant_info['api_key']}' http://localhost:8420/tenant-info")
    
    return 0


if __name__ == "__main__":
    exit(main())