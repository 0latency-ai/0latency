#\!/usr/bin/env python3
"""
Integration test for tenant role seeding.
Verifies that create_tenant() atomically creates tenant + 5 default roles.
"""

import sys
import os
import uuid

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_create_tenant_seeds_roles():
    """Test that create_tenant() creates tenant with 5 default roles."""
    from src.storage_multitenant import create_tenant, _db_execute_rows
    
    # Create a test tenant
    test_name = f"test-role-seeding-{str(uuid.uuid4())[:8]}"
    
    print(f"Creating tenant: {test_name}")
    tenant_info = create_tenant(name=test_name, plan='free')
    
    tenant_id = tenant_info['tenant_id']
    print(f"  ✓ Tenant created: {tenant_id}")
    
    # Verify tenant has 5 roles
    rows = _db_execute_rows("""
        SELECT role_name, description
        FROM memory_service.tenant_roles
        WHERE tenant_id = %s::UUID
        ORDER BY role_name
    """, (tenant_id,), tenant_id="00000000-0000-0000-0000-000000000000")
    
    role_names = [row[0] for row in rows]
    
    expected_roles = ['engineering', 'legal', 'product', 'public', 'revenue']
    
    assert len(rows) == 5, f"Expected 5 roles, got {len(rows)}"
    assert role_names == expected_roles, f"Role mismatch: {role_names} vs {expected_roles}"
    
    print(f"  ✓ Tenant has 5 default roles: {role_names}")
    
    # Verify role descriptions are correct
    descriptions = {row[0]: row[1] for row in rows}
    assert 'Public role - visible to all consumers within this tenant' in descriptions['public']
    assert 'Engineering team role' in descriptions['engineering']
    assert 'Product team role' in descriptions['product']
    assert 'Revenue team role' in descriptions['revenue']
    assert 'Legal team role' in descriptions['legal']
    
    print(f"  ✓ Role descriptions match migration 013")
    
    # Cleanup: mark tenant as inactive
    _db_execute_rows("""
        UPDATE memory_service.tenants 
        SET active = false, name = name || ' (test-deleted)'
        WHERE id = %s::UUID
    """, (tenant_id,), tenant_id="00000000-0000-0000-0000-000000000000", fetch_results=False)
    
    print(f"  ✓ Test tenant marked inactive")
    
    return True


if __name__ == '__main__':
    # Load .env with proper quote stripping
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Strip surrounding quotes if present
                    value = value.strip('"')
                    os.environ[key] = value
    
    try:
        test_create_tenant_seeds_roles()
        print("\n✓ TEST PASSED: create_tenant() correctly seeds 5 default roles")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
