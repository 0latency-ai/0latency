#!/usr/bin/env python3
"""
Health check for Memory Engine API-based setup
"""

import os
import sys
import requests
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_tenant_info():
    """Get current tenant information."""
    api_key = os.environ.get("MEMORY_API_KEY")
    api_url = os.environ.get("MEMORY_API_URL", "https://164.90.156.169")
    
    if not api_key:
        print("❌ MEMORY_API_KEY not set")
        print("   Export your API key: export MEMORY_API_KEY='zl_live_...'")
        return None
    
    if not api_key.startswith("zl_live_") or len(api_key) != 40:
        print("❌ Invalid API key format")
        print("   API keys must be: zl_live_<32-characters>")
        return None
    
    try:
        response = requests.get(
            f"{api_url}/api/tenant-info",
            headers={"X-API-Key": api_key},
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"❌ API connection failed: {e}")
        print(f"   Check API_URL: {api_url}")
        return None

def test_api_endpoints():
    """Test key API endpoints."""
    api_key = os.environ.get("MEMORY_API_KEY")
    api_url = os.environ.get("MEMORY_API_URL", "https://164.90.156.169")
    
    if not api_key:
        return False
    
    # Test health endpoint
    try:
        response = requests.get(f"{api_url}/health", verify=False, timeout=5)
        response.raise_for_status()
        print("✅ Health endpoint responding")
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
        return False
    
    # Test memory listing
    try:
        response = requests.get(
            f"{api_url}/api/memories",
            headers={"X-API-Key": api_key},
            params={"agent_id": "test_agent", "limit": 1},
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        memories = response.json()
        print(f"✅ Memory API responding ({len(memories)} test memories)")
    except Exception as e:
        print(f"❌ Memory API failed: {e}")
        return False
    
    return True

def main():
    print("🧠 Memory Engine Health Check")
    print("=" * 50)
    
    # Check environment
    api_key = os.environ.get("MEMORY_API_KEY")
    api_url = os.environ.get("MEMORY_API_URL", "https://164.90.156.169")
    
    print(f"API URL: {api_url}")
    print(f"API Key: {'*' * 32 if api_key else 'NOT SET'}")
    print()
    
    # Get tenant info
    tenant = get_tenant_info()
    if not tenant:
        print("\n💡 Setup Instructions:")
        print("1. Get API key from your administrator")
        print("2. export MEMORY_API_KEY='zl_live_your_key_here'")
        print("3. Run this script again")
        return 1
    
    print("📊 Tenant Information:")
    print(f"   Name: {tenant['name']}")
    print(f"   Plan: {tenant['plan']}")
    print(f"   Memory Limit: {tenant['memory_limit']:,}")
    print(f"   Rate Limit: {tenant['rate_limit_rpm']}/min")
    print(f"   API Calls: {tenant['api_calls_count']:,}")
    print()
    
    # Test API endpoints
    print("🔧 API Tests:")
    if test_api_endpoints():
        print("✅ All systems operational")
        return 0
    else:
        print("❌ Some systems failing")
        return 1

if __name__ == "__main__":
    sys.exit(main())