"""
Extraction Layer Test Suite
Tests against real conversation patterns from Thomas sessions.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from extraction import extract_memories

# Set API key
# GOOGLE_API_KEY must be set in environment before running tests


def test_preference_extraction():
    """Test: Does it catch user preferences/communication rules?"""
    print("=" * 60)
    print("TEST 1: Preference Extraction")
    print("=" * 60)
    
    human = """I know you have Graph API. You know you have Graph API. There's no need to announce it - 
    you need to simply know that you can do it and then do it. Ok? We set up all the access many weeks ago - 
    it's at the heart of what makes you valuable."""
    
    agent = """Noted. Won't happen again."""
    
    memories = extract_memories(human, agent, agent_id="thomas", session_key="test", turn_id="pref-001")
    
    print(f"Extracted {len(memories)} memories:")
    for m in memories:
        print(f"  [{m['memory_type'].upper()}] {m['headline']}")
        print(f"    Importance: {m['importance']}")
    
    # Should extract a preference about not announcing capabilities
    pref_found = any(m['memory_type'] == 'preference' for m in memories)
    print(f"\n  ✅ Preference detected: {pref_found}")
    return memories


def test_decision_extraction():
    """Test: Does it catch decisions with context?"""
    print("\n" + "=" * 60)
    print("TEST 2: Decision Extraction")
    print("=" * 60)
    
    human = """nope - forgot these two fields. What do I put?"""
    
    agent = """Cycle Year: 2026. Depository: Since PFL Academy is digital-only, go with Archway Depository. 
    They handle digital/smaller publishers. You can set up an account with them after submission if needed — 
    the Intent to Bid just needs a selection now."""
    
    memories = extract_memories(human, agent, agent_id="thomas", session_key="test", turn_id="dec-001")
    
    print(f"Extracted {len(memories)} memories:")
    for m in memories:
        print(f"  [{m['memory_type'].upper()}] {m['headline']}")
        print(f"    Importance: {m['importance']}")
    
    decision_found = any(m['memory_type'] == 'decision' for m in memories)
    print(f"\n  ✅ Decision detected: {decision_found}")
    return memories


def test_correction_extraction():
    """Test: Does it catch corrections to prior facts?"""
    print("\n" + "=" * 60)
    print("TEST 3: Correction Extraction")
    print("=" * 60)
    
    human = """No - I know it's there - that's the registration page that I used and I'm showing that to you 
    as what I selected. As you can see here, the only options they offer are either TBSD or ARCH"""
    
    agent = """Got it — my mistake. Self was only on registration, not on this form. Since PFL Academy is 
    digital-only, go with Archway Depository."""
    
    existing = "Justin selected 'Self' for depository during publisher registration"
    
    memories = extract_memories(human, agent, agent_id="thomas", session_key="test", turn_id="cor-001",
                               existing_context=existing)
    
    print(f"Extracted {len(memories)} memories:")
    for m in memories:
        print(f"  [{m['memory_type'].upper()}] {m['headline']}")
        print(f"    Importance: {m['importance']}")
        if m['memory_type'] == 'correction':
            print(f"    Full: {m['full_content'][:200]}")
    
    correction_found = any(m['memory_type'] == 'correction' for m in memories)
    print(f"\n  ✅ Correction detected: {correction_found}")
    return memories


def test_task_extraction():
    """Test: Does it catch tasks/action items?"""
    print("\n" + "=" * 60)
    print("TEST 4: Task Extraction")
    print("=" * 60)
    
    human = """put that on my list of todo's - in the meantime I have to get through some things that have 
    come up in the past several days."""
    
    agent = """Logged it. Go handle your stuff — I'm here when you need me."""
    
    memories = extract_memories(human, agent, agent_id="thomas", session_key="test", turn_id="task-001")
    
    print(f"Extracted {len(memories)} memories:")
    for m in memories:
        print(f"  [{m['memory_type'].upper()}] {m['headline']}")
        print(f"    Importance: {m['importance']}")
    
    task_found = any(m['memory_type'] == 'task' for m in memories)
    print(f"\n  ✅ Task detected: {task_found}")
    return memories


def test_complex_business_extraction():
    """Test: Does it handle dense business information?"""
    print("\n" + "=" * 60)
    print("TEST 5: Complex Business Information")
    print("=" * 60)
    
    human = """Spanish Transcreation — What Was Built
    All 192 scripts across 4 seasons were originally composed in Spanish using a v5 methodology — not 
    translated or transadapted from English. A full back-translation audit across all 192 scripts scored 
    3.81/4.0 on an original composition scale. All scripts are committed to git. S3-CH05 was the final 
    piece, finalized today."""
    
    agent = """Updated. That's a massive milestone — 192 scripts natively composed in Spanish with a 3.81/4.0 
    audit score, plus the full daytime UI built and deployed. Explore went from future product to needs LMS 
    hookup and one day of Sebastian's time."""
    
    memories = extract_memories(human, agent, agent_id="thomas", session_key="test", turn_id="biz-001")
    
    print(f"Extracted {len(memories)} memories:")
    for m in memories:
        print(f"  [{m['memory_type'].upper()}] {m['headline']}")
        print(f"    Importance: {m['importance']}")
        print(f"    Entities: {m['entities']}")
        print(f"    Project: {m['project']}")
    
    return memories


def test_no_extraction_needed():
    """Test: Does it correctly return empty for trivial exchanges?"""
    print("\n" + "=" * 60)
    print("TEST 6: No Extraction (Trivial Exchange)")
    print("=" * 60)
    
    human = "yes"
    agent = "Sent."
    
    memories = extract_memories(human, agent, agent_id="thomas", session_key="test", turn_id="triv-001")
    
    print(f"Extracted {len(memories)} memories (should be 0): {len(memories)}")
    print(f"  ✅ Correctly skipped: {len(memories) == 0}")
    return memories


if __name__ == "__main__":
    print("EXTRACTION LAYER TEST SUITE")
    print("Running against Gemini Flash 2.0\n")
    
    all_results = {}
    
    all_results["preference"] = test_preference_extraction()
    all_results["decision"] = test_decision_extraction()
    all_results["correction"] = test_correction_extraction()
    all_results["task"] = test_task_extraction()
    all_results["complex"] = test_complex_business_extraction()
    all_results["trivial"] = test_no_extraction_needed()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_memories = sum(len(v) for v in all_results.values())
    print(f"Total memories extracted across all tests: {total_memories}")
    
    types = {}
    for memories in all_results.values():
        for m in memories:
            t = m['memory_type']
            types[t] = types.get(t, 0) + 1
    
    print(f"By type: {json.dumps(types, indent=2)}")
    
    # Save results
    with open("/root/.openclaw/workspace/memory-product/src/test_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nFull results saved to test_results.json")
