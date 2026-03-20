#!/usr/bin/env python3
"""
Debug the recall function step by step to find where it fails.
"""

import os
import sys
import traceback

# Add src to path and set environment
sys.path.append('/root/.openclaw/workspace/memory-product/src')
os.environ["GOOGLE_API_KEY"] = "AIzaSyAvFCk21Sz4G3AbKm9USob55DqJnpJBVmI"

def test_recall_step_by_step():
    from recall import (
        _embed_text, 
        _retrieve_candidates, 
        _load_agent_config,
        _build_always_include,
        recall
    )
    
    agent_id = "thomas"
    query = "memory product decisions"
    
    print(f"Testing recall for: '{query}'")
    
    # Step 1: Test embedding
    print("\n1. Testing embedding generation...")
    try:
        embedding = _embed_text(query)
        print(f"✅ Generated embedding with {len(embedding)} dimensions")
    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        traceback.print_exc()
        return
    
    # Step 2: Test config loading
    print("\n2. Testing config loading...")
    try:
        config = _load_agent_config(agent_id)
        print(f"✅ Loaded config: {config}")
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        traceback.print_exc()
        return
    
    # Step 3: Test always-include
    print("\n3. Testing always-include block...")
    try:
        always_block, always_tokens = _build_always_include(agent_id)
        print(f"✅ Always-include built: {always_tokens} tokens")
        print(f"Preview: {always_block[:200]}...")
    except Exception as e:
        print(f"❌ Always-include failed: {e}")
        traceback.print_exc()
        return
    
    # Step 4: Test candidate retrieval
    print("\n4. Testing candidate retrieval...")
    try:
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        candidates = _retrieve_candidates(agent_id, embedding_str, query)
        print(f"✅ Retrieved {len(candidates)} candidates")
        if candidates:
            print("Top candidates:")
            for i, c in enumerate(candidates[:3]):
                print(f"  {i+1}. {c['headline']} (sim: {c.get('similarity', 'N/A')})")
        else:
            print("❌ No candidates retrieved!")
    except Exception as e:
        print(f"❌ Candidate retrieval failed: {e}")
        traceback.print_exc()
        return
    
    # Step 5: Test full recall
    print("\n5. Testing full recall function...")
    try:
        result = recall(agent_id, query, budget_tokens=2000)
        print(f"✅ Full recall completed")
        print(f"   Memories used: {result['memories_used']}")
        print(f"   Tokens used: {result['tokens_used']}")
        print(f"   Budget remaining: {result['budget_remaining']}")
        
        if result['memories_used'] == 0:
            print("❌ ZERO RESULTS - Need to debug scoring/filtering")
        
        if result['recall_details']:
            print("   Top details:")
            for detail in result['recall_details'][:3]:
                print(f"     - {detail['headline']} (score: {detail['composite']})")
                
    except Exception as e:
        print(f"❌ Full recall failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_recall_step_by_step()