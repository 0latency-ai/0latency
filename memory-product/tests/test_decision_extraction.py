"""Test decision memory extraction with decision_text and rationale fields."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock the extraction model to return controlled responses
import src.extraction as extraction

original_call_model = extraction._call_model

def mock_call_model_decision(prompt):
    """Mock that returns a decision with required fields."""
    return """[
  {
    "headline": "Use Option B: Fix extraction over removing constraint",
    "context": "Decision to fix extraction.py to populate decision_text/rationale instead of removing check_decision_required_fields constraint",
    "full_content": "Team decided to implement Option B (fix extraction layer) rather than Option A (remove constraint). This preserves data quality while fixing the root cause. Constraint is structurally correct and should remain.",
    "memory_type": "decision",
    "decision_text": "Fix extraction.py to populate decision_text and rationale columns for decision-type memories",
    "rationale": "Option B addresses the root cause while maintaining data quality. Removing the constraint (Option A) would allow bad data. The constraint is correct; extraction was incomplete.",
    "importance": 0.9,
    "confidence": 1.0,
    "entities": ["extraction.py", "check_decision_required_fields"],
    "project": "memory-product",
    "categories": ["architecture", "decision"],
    "scope": "/memory-product/phase6",
    "temporal_type": "current"
  }
]"""

def mock_call_model_missing_fields(prompt):
    """Mock that returns a decision WITHOUT required fields."""
    return """[
  {
    "headline": "Approved deployment to production",
    "context": "User approved the deployment plan",
    "full_content": "User reviewed and approved production deployment",
    "memory_type": "decision",
    "importance": 0.8,
    "confidence": 1.0,
    "entities": ["production"],
    "categories": ["deployment"],
    "scope": "/",
    "temporal_type": "event"
  }
]"""

def test_decision_with_fields():
    """Test that decision memories with decision_text/rationale are extracted correctly."""
    extraction._call_model = mock_call_model_decision
    
    memories, _ = extraction.extract_memories(
        human_message="Should we fix extraction or remove the constraint?",
        agent_message="Option B is better - fix extraction to populate the fields properly.",
        agent_id="test-agent",
        session_key="test-session",
        turn_id="turn-001"
    )
    
    assert len(memories) == 1
    mem = memories[0]
    assert mem["memory_type"] == "decision"
    assert mem["decision_text"] is not None
    assert mem["rationale"] is not None
    assert "Fix extraction.py" in mem["decision_text"]
    assert "root cause" in mem["rationale"]
    print("✓ Decision with required fields: PASS")

def test_decision_missing_fields_downgrade():
    """Test that decision memories without decision_text/rationale are downgraded to fact."""
    extraction._call_model = mock_call_model_missing_fields
    
    memories, _ = extraction.extract_memories(
        human_message="Can we deploy?",
        agent_message="Yes, go ahead with production deployment.",
        agent_id="test-agent",
        session_key="test-session",
        turn_id="turn-002"
    )
    
    assert len(memories) == 1
    mem = memories[0]
    # Should be downgraded to fact
    assert mem["memory_type"] == "fact"
    assert mem["decision_text"] is None
    assert mem["rationale"] is None
    print("✓ Decision missing fields downgraded to fact: PASS")

if __name__ == "__main__":
    try:
        test_decision_with_fields()
        test_decision_missing_fields_downgrade()
        print("\n✓ All decision extraction tests passed")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    finally:
        # Restore original function
        extraction._call_model = original_call_model
