#!/usr/bin/env python3
"""
List memories for an agent via Memory Engine API
"""

import os
import sys
import json
import argparse
import requests
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def list_memories(agent_id, memory_type=None, limit=50):
    """List memories for an agent."""
    api_key = os.environ.get("MEMORY_API_KEY")
    api_url = os.environ.get("MEMORY_API_URL", "https://164.90.156.169")
    
    if not api_key:
        print("❌ MEMORY_API_KEY not set")
        return False
    
    headers = {"X-API-Key": api_key}
    params = {"agent_id": agent_id, "limit": limit}
    if memory_type:
        params["memory_type"] = memory_type
    
    try:
        response = requests.get(
            f"{api_url}/api/memories",
            headers=headers,
            params=params,
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        memories = response.json()
        
        if not memories:
            print(f"No memories found for agent '{agent_id}'")
            if memory_type:
                print(f"(filtered by type: {memory_type})")
            return True
        
        print(f"📚 Found {len(memories)} memories for '{agent_id}'")
        if memory_type:
            print(f"   (filtered by type: {memory_type})")
        print("=" * 60)
        
        # Group by type for better display
        by_type = {}
        for mem in memories:
            mem_type = mem['memory_type']
            if mem_type not in by_type:
                by_type[mem_type] = []
            by_type[mem_type].append(mem)
        
        for mem_type, mems in sorted(by_type.items()):
            print(f"\n📝 {mem_type.upper()} ({len(mems)})")
            print("-" * 40)
            for mem in sorted(mems, key=lambda x: x['importance'], reverse=True):
                importance_stars = "★" * int(mem['importance'] * 5)
                print(f"   {importance_stars:<5} {mem['headline']}")
                print(f"         ID: {mem['id']}")
                print(f"         Created: {mem['created_at'][:19]}")
                print()
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="List memories for an agent")
    parser.add_argument("agent_id", nargs="?", default="thomas", 
                       help="Agent ID (default: thomas)")
    parser.add_argument("--type", dest="memory_type", 
                       choices=["fact", "preference", "decision", "task", "correction", "relationship", "identity"],
                       help="Filter by memory type")
    parser.add_argument("--limit", type=int, default=50,
                       help="Maximum number of memories to show (default: 50)")
    
    args = parser.parse_args()
    
    if not list_memories(args.agent_id, args.memory_type, args.limit):
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())