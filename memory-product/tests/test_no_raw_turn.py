"""
Unit test: extract_memories() never produces memory_type='raw_turn'
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/memory-product/src')

from extraction import extract_memories

def test_no_raw_turn_in_extraction():
    """Verify extract_memories() NEVER produces memory_type='raw_turn'."""
    
    # Test case 1: Normal conversation
    human = "My name is Alice and I work as a software engineer at Acme Corp."
    agent = "Got it! I'll remember that you're Alice, a software engineer at Acme Corp."
    
    memories, raw_turn_id = extract_memories(
        human_message=human,
        agent_message=agent,
        agent_id="test-agent",
        session_key="test-session",
        turn_id="turn-001",
        tenant_id="test-tenant-123",
    )
    
    # Verify: should be a list, not a tuple
    assert isinstance(memories, list), f"Expected list, got {type(memories)}"
    
    # Verify: no memory has memory_type='raw_turn'
    raw_turn_count = sum(1 for m in memories if m.get("memory_type") == "raw_turn")
    assert raw_turn_count == 0, f"Found {raw_turn_count} raw_turn memories (expected 0)"
    
    print(f"✓ Test case 1: Extracted {len(memories)} memories, 0 raw_turn")
    for mem in memories:
        print(f"  - [{mem['memory_type']}] {mem['headline']}")
    
    # Test case 2: Complex multi-fact turn
    human2 = "I graduated from MIT in 2015 with a degree in Computer Science. I'm currently working on a machine learning project called DeepVision."
    agent2 = "Thanks for sharing! I'll remember your MIT CS degree from 2015 and your DeepVision ML project."
    
    memories2 = extract_memories(
        human_message=human2,
        agent_message=agent2,
        agent_id="test-agent",
        session_key="test-session",
        turn_id="turn-002",
        tenant_id="test-tenant-123",
    )
    
    assert isinstance(memories2, list), f"Expected list, got {type(memories2)}"
    raw_turn_count2 = sum(1 for m in memories2 if m.get("memory_type") == "raw_turn")
    assert raw_turn_count2 == 0, f"Found {raw_turn_count2} raw_turn memories (expected 0)"
    
    print(f"✓ Test case 2: Extracted {len(memories2)} memories, 0 raw_turn")
    for mem in memories2:
        print(f"  - [{mem['memory_type']}] {mem['headline']}")
    
    print("\n✅ PASS: extract_memories() produces no raw_turn memories")
    return True

if __name__ == "__main__":
    try:
        test_no_raw_turn_in_extraction()
    except AssertionError as e:
        print(f"\n❌ FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
