#!/usr/bin/env python3
"""
Simple test of recall function after fixing agent config.
"""

import os
import sys

# Add src to path and set environment
sys.path.append('/root/.openclaw/workspace/memory-product/src')
# GOOGLE_API_KEY must be set in environment

from recall import recall

test_queries = [
    "memory product decisions",
    "pricing", 
    "pre-launch checklist",
]

agent_id = "thomas"

for query in test_queries:
    print(f"\nTesting: '{query}'")
    try:
        result = recall(agent_id, query, budget_tokens=2000)
        print(f"✅ Memories: {result['memories_used']}, Tokens: {result['tokens_used']}")
        
        if result['recall_details']:
            print("Top results:")
            for detail in result['recall_details'][:3]:
                print(f"  - {detail['headline']} (score: {detail['composite']})")
        else:
            print("No recall details")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()