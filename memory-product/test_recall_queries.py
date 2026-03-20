#!/usr/bin/env python3
"""
Test script to debug recall quality issues.
Tests specific queries that SHOULD return results but might be returning 0.
"""

import os
import sys
import json

# Add src to path
sys.path.append('/root/.openclaw/workspace/memory-product/src')

# Set up environment
os.environ["GOOGLE_API_KEY"] = "AIzaSyAvFCk21Sz4G3AbKm9USob55DqJnpJBVmI"

from recall import recall

test_queries = [
    "memory product decisions",
    "pricing", 
    "pre-launch checklist",
    "Phase B API",
    "zero latency",
    "memory architecture",
    "thomas server",
    "product roadmap",
]

agent_id = "thomas"

def test_recall_query(query):
    print(f"\n{'='*60}")
    print(f"Testing query: '{query}'")
    print('='*60)
    
    try:
        result = recall(agent_id, query, budget_tokens=2000)
        
        print(f"Memories used: {result['memories_used']}")
        print(f"Tokens used: {result['tokens_used']}")
        print(f"Budget remaining: {result['budget_remaining']}")
        
        if result['memories_used'] == 0:
            print("❌ ZERO RESULTS - This is the problem!")
        else:
            print("✅ Got results")
        
        if result['recall_details']:
            print("\nTop results:")
            for i, detail in enumerate(result['recall_details'][:3]):
                print(f"  {i+1}. [{detail['type']}] {detail['tier']} (score={detail['composite']:.3f}) {detail['headline']}")
        else:
            print("No recall details returned")
            
        return result['memories_used']
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    print("Testing recall queries against Thomas's memories...")
    print(f"Agent ID: {agent_id}")
    
    zero_results_count = 0
    for query in test_queries:
        result_count = test_recall_query(query)
        if result_count == 0:
            zero_results_count += 1
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: {zero_results_count}/{len(test_queries)} queries returned ZERO results")
    if zero_results_count > 0:
        print("This confirms the recall quality issue.")
    print('='*60)