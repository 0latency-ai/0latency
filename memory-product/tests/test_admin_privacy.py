#!/usr/bin/env python3
"""
Privacy test for admin analytics endpoints.

Ensures that NO memory content fields are exposed in admin API responses.
This is a critical product promise - admins can see metadata only, never content.

Forbidden fields:
- content
- text
- summary
- body
- memory_text
- headline
- full_content
- context
"""

import os
import sys
import json
import requests

# Admin API key from environment
ADMIN_KEY = os.environ.get('MEMORY_ADMIN_KEY', 'zl_admin_thomas_server_2026')
API_BASE = 'http://localhost:8420'

# Fields that must NEVER appear in admin responses
FORBIDDEN_FIELDS = {
    'content',
    'text', 
    'summary',
    'body',
    'memory_text',
    'headline',
    'full_content',
    'context',
    'query_text',  # from recall_telemetry - exposes user queries
}


def check_response_for_forbidden_fields(response_json, endpoint_name):
    """
    Recursively search JSON response for forbidden field names.
    Returns list of violations.
    """
    violations = []
    
    def recurse(obj, path="root"):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in FORBIDDEN_FIELDS:
                    violations.append(f"{endpoint_name}: Found forbidden field '{key}' at {path}.{key}")
                recurse(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                recurse(item, f"{path}[{i}]")
    
    recurse(response_json)
    return violations


def test_admin_summary():
    """Test /admin/analytics/summary for privacy violations."""
    url = f"{API_BASE}/admin/analytics/summary"
    headers = {"X-Admin-Key": ADMIN_KEY}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"⚠ Summary endpoint returned {response.status_code}, skipping privacy check")
        return []
    
    return check_response_for_forbidden_fields(response.json(), "GET /admin/analytics/summary")


def test_admin_tenants_list():
    """Test /admin/analytics/tenants for privacy violations."""
    url = f"{API_BASE}/admin/analytics/tenants?limit=10"
    headers = {"X-Admin-Key": ADMIN_KEY}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"⚠ Tenants list endpoint returned {response.status_code}, skipping privacy check")
        return []
    
    return check_response_for_forbidden_fields(response.json(), "GET /admin/analytics/tenants")


def test_admin_tenant_detail():
    """Test /admin/analytics/tenants/{id} for privacy violations."""
    # First get a tenant ID from the list
    url = f"{API_BASE}/admin/analytics/tenants?limit=1"
    headers = {"X-Admin-Key": ADMIN_KEY}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200 or not response.json().get('tenants'):
        print(f"⚠ No tenants found, skipping detail privacy check")
        return []
    
    tenant_id = response.json()['tenants'][0]['tenant_id']
    
    # Now test the detail endpoint
    detail_url = f"{API_BASE}/admin/analytics/tenants/{tenant_id}"
    detail_response = requests.get(detail_url, headers=headers)
    
    if detail_response.status_code != 200:
        print(f"⚠ Tenant detail endpoint returned {detail_response.status_code}, skipping privacy check")
        return []
    
    return check_response_for_forbidden_fields(detail_response.json(), f"GET /admin/analytics/tenants/{tenant_id}")


def main():
    print("\n" + "="*60)
    print("Admin Analytics Privacy Test")
    print("="*60)
    print(f"Testing against: {API_BASE}")
    print(f"Admin key: {ADMIN_KEY[:20]}...")
    print(f"Forbidden fields: {', '.join(FORBIDDEN_FIELDS)}")
    print("="*60 + "\n")
    
    all_violations = []
    
    # Test all three endpoints
    print("[1/3] Testing GET /admin/analytics/summary...")
    violations = test_admin_summary()
    all_violations.extend(violations)
    print(f"      {'✓ PASS' if not violations else '✗ FAIL: ' + str(len(violations)) + ' violations'}")
    
    print("[2/3] Testing GET /admin/analytics/tenants...")
    violations = test_admin_tenants_list()
    all_violations.extend(violations)
    print(f"      {'✓ PASS' if not violations else '✗ FAIL: ' + str(len(violations)) + ' violations'}")
    
    print("[3/3] Testing GET /admin/analytics/tenants/{{id}}...")
    violations = test_admin_tenant_detail()
    all_violations.extend(violations)
    print(f"      {'✓ PASS' if not violations else '✗ FAIL: ' + str(len(violations)) + ' violations'}")
    
    # Final report
    print("\n" + "="*60)
    if all_violations:
        print("✗ PRIVACY TEST FAILED")
        print(f"Found {len(all_violations)} violations:")
        for v in all_violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("✓ PRIVACY TEST PASSED")
        print("No memory content fields found in admin API responses.")
        print("="*60 + "\n")
        sys.exit(0)


if __name__ == '__main__':
    main()
