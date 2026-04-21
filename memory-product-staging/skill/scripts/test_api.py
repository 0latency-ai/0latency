#!/usr/bin/env python3
"""
Test the Memory Engine API with sample data
"""

import os
import sys
import json
import requests
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def test_extract_and_recall():
    """Test extracting memories and recalling them."""
    api_key = os.environ.get("MEMORY_API_KEY")
    api_url = os.environ.get("MEMORY_API_URL", "https://164.90.156.169")
    
    if not api_key:
        print("❌ MEMORY_API_KEY not set")
        return False
    
    headers = {"X-API-Key": api_key}
    
    print("🧠 Testing Memory Engine API")
    print("=" * 40)
    
    # Test extraction
    print("1. Testing memory extraction...")
    extract_data = {
        "agent_id": "test_agent",
        "human_message": "I live in Seattle and work as a software engineer at Microsoft. My favorite programming language is Python.",
        "agent_message": "Thanks for sharing! I'll remember that you're in Seattle, work at Microsoft as a software engineer, and prefer Python programming.",
        "session_key": "test_session_001",
        "turn_id": "001"
    }
    
    try:
        response = requests.post(
            f"{api_url}/api/extract",
            headers=headers,
            json=extract_data,
            verify=False,
            timeout=15
        )
        response.raise_for_status()
        extract_result = response.json()
        print(f"   ✅ Stored {extract_result['memories_stored']} memories")
        print(f"   Memory IDs: {extract_result['memory_ids'][:2]}...")
    except Exception as e:
        print(f"   ❌ Extract failed: {e}")
        return False
    
    # Test recall
    print("2. Testing memory recall...")
    recall_data = {
        "agent_id": "test_agent",
        "conversation_context": "User is asking about career and programming recommendations",
        "budget_tokens": 2000,
        "dynamic_budget": True
    }
    
    try:
        response = requests.post(
            f"{api_url}/api/recall",
            headers=headers,
            json=recall_data,
            verify=False,
            timeout=15
        )
        response.raise_for_status()
        recall_result = response.json()
        print(f"   ✅ Recalled {recall_result['memories_used']} memories")
        print(f"   Tokens used: {recall_result['tokens_used']}")
        print("   Context preview:")
        preview = recall_result['context_block'][:200].replace('\n', ' ')
        print(f"   {preview}...")
    except Exception as e:
        print(f"   ❌ Recall failed: {e}")
        return False
    
    # Test listing
    print("3. Testing memory listing...")
    try:
        response = requests.get(
            f"{api_url}/api/memories",
            headers=headers,
            params={"agent_id": "test_agent", "limit": 5},
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        memories = response.json()
        print(f"   ✅ Found {len(memories)} memories")
        for mem in memories[:3]:
            print(f"   - [{mem['memory_type']}] {mem['headline']}")
    except Exception as e:
        print(f"   ❌ List failed: {e}")
        return False
    
    print("\n🎉 All tests passed! Memory Engine is working correctly.")
    return True

def main():
    if not test_extract_and_recall():
        print("\n💡 Troubleshooting:")
        print("- Check MEMORY_API_KEY is set correctly")
        print("- Verify API endpoint is accessible")
        print("- Run api_health.py for detailed diagnostics")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())