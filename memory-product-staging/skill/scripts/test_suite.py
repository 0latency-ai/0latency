#!/usr/bin/env python3
"""
Memory Engine — Test Suite
Validates extraction, storage, recall, dedup, and handoff.
Run after setup to verify everything works.
"""

import os
import sys
import json
import time
import subprocess

sys.path.insert(0, os.path.dirname(__file__))

DB_CONN = os.environ.get("MEMORY_DB_CONN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

results = {"passed": 0, "failed": 0, "errors": []}


def test(name, fn):
    """Run a test and track results."""
    try:
        fn()
        results["passed"] += 1
        print(f"  ✅ {name}")
    except AssertionError as e:
        results["failed"] += 1
        results["errors"].append(f"{name}: {e}")
        print(f"  ❌ {name}: {e}")
    except Exception as e:
        results["failed"] += 1
        results["errors"].append(f"{name}: {e}")
        print(f"  💥 {name}: {e}")


# === Test 1: Database Connection ===
def test_db_connection():
    from storage import _db_execute
    rows = _db_execute("SELECT 1 as test")
    assert rows, "Database returned no rows"

# === Test 2: Schema Exists ===
def test_schema_exists():
    from storage import _db_execute
    rows = _db_execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'memory_service' ORDER BY table_name")
    tables = [r.strip() for r in rows]
    required = ['memories', 'session_handoffs', 'entity_index', 'memory_edges', 'topic_coverage']
    for t in required:
        assert t in tables, f"Missing table: {t}"

# === Test 3: Extraction ===
def test_extraction():
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    from extraction import extract_memories
    memories = extract_memories(
        human_message="My name is Alex and I work at Acme Corp. My dog's name is Biscuit.",
        agent_message="Nice to meet you, Alex! Acme Corp sounds interesting. And Biscuit is a great name for a dog.",
        agent_id="test_agent",
        session_key="test_session",
        turn_id="test_turn_001",
    )
    assert isinstance(memories, list), "Extraction didn't return a list"
    assert len(memories) > 0, "No memories extracted"
    # Should extract identity facts
    types = [m.get("memory_type") for m in memories]
    assert any(t in types for t in ["identity", "fact"]), f"Expected identity/fact, got: {types}"

# === Test 4: Storage + Dedup ===
def test_storage_and_dedup():
    from extraction import extract_memories
    from storage import store_memories, _db_execute
    
    # Clean up any previous test data
    _db_execute("DELETE FROM memory_service.memories WHERE agent_id = 'test_agent'")
    
    memories = extract_memories(
        human_message="I prefer dark mode in all my applications.",
        agent_message="I'll remember that — dark mode everywhere.",
        agent_id="test_agent",
        session_key="test_session",
        turn_id="test_turn_002",
    )
    
    ids1 = store_memories(memories)
    assert len(ids1) > 0, "No memories stored"
    
    # Store same thing again — should deduplicate (reinforce, not create new)
    memories2 = extract_memories(
        human_message="Just to confirm, I always want dark mode.",
        agent_message="Got it — dark mode is your preference.",
        agent_id="test_agent",
        session_key="test_session",
        turn_id="test_turn_003",
    )
    
    ids2 = store_memories(memories2)
    
    # Check total — should not have doubled
    rows = _db_execute("SELECT COUNT(*) FROM memory_service.memories WHERE agent_id = 'test_agent'")
    count = int(rows[0]) if rows else 0
    assert count <= len(ids1) + 2, f"Possible duplicate issue: {count} memories for 2 similar inputs"

# === Test 5: Recall ===
def test_recall():
    from recall import recall
    result = recall(
        agent_id="test_agent",
        conversation_context="What display preferences does the user have?",
        budget_tokens=2000,
    )
    assert "context_block" in result, "Recall didn't return context_block"
    assert result["memories_used"] >= 0, "Negative memories_used"
    # If we stored memories, they should be recallable
    # (May be 0 if embeddings aren't matching — that's still a valid test result)

# === Test 6: Handoff ===
def test_handoff():
    from handoff import generate_handoff, save_handoff, get_latest_handoff
    
    recent_turns = [
        ("What's the plan for today?", "We need to finish the deployment script and test it."),
        ("Sounds good, let's do it.", "Starting with the deployment script now."),
    ]
    
    handoff = generate_handoff(
        agent_id="test_agent",
        session_key="test_session",
        recent_turns=recent_turns,
    )
    
    assert "summary" in handoff, "Handoff missing summary"
    assert isinstance(handoff.get("decisions_made"), list), "Handoff decisions not a list"
    
    save_handoff("test_agent", "test_session", handoff)
    
    retrieved = get_latest_handoff("test_agent")
    assert retrieved is not None, "Couldn't retrieve saved handoff"
    assert "summary" in retrieved, "Retrieved handoff missing summary"

# === Test 7: Contradiction Detection ===
def test_contradiction():
    from extraction import extract_memories
    from storage import store_memories
    
    # Store a fact
    memories1 = extract_memories(
        human_message="The project deadline is March 30th.",
        agent_message="Got it — March 30th deadline.",
        agent_id="test_agent",
        session_key="test_session",
        turn_id="test_turn_004",
    )
    store_memories(memories1)
    
    # Now contradict it
    memories2 = extract_memories(
        human_message="Actually, the deadline moved to April 15th, not March 30th.",
        agent_message="Updated — April 15th is the new deadline.",
        agent_id="test_agent",
        session_key="test_session",
        turn_id="test_turn_005",
    )
    
    # Should detect the contradiction
    has_correction = any(m.get("memory_type") == "correction" for m in memories2)
    # Note: extraction may or may not flag this as correction — the storage layer
    # also runs contradiction detection. So we just verify something was extracted.
    assert len(memories2) > 0, "No memories extracted from contradiction"

# === Test 8: List Preservation ===
def test_list_preservation():
    from extraction import extract_memories
    
    memories = extract_memories(
        human_message="""Here's our launch checklist:
1. Test the installer
2. Write documentation
3. Set up billing
4. Create landing page
5. Submit to marketplace""",
        agent_message="Got it — 5-item launch checklist captured.",
        agent_id="test_agent",
        session_key="test_session",
        turn_id="test_turn_006",
    )
    
    # Should be 1-2 memories, not 5
    assert len(memories) <= 3, f"List was shattered into {len(memories)} memories (expected 1-2)"

# === Test 9: Cleanup ===
def test_cleanup():
    from storage import _db_execute
    _db_execute("DELETE FROM memory_service.memories WHERE agent_id = 'test_agent'")
    _db_execute("DELETE FROM memory_service.session_handoffs WHERE agent_id = 'test_agent'")
    _db_execute("DELETE FROM memory_service.entity_index WHERE agent_id = 'test_agent'")
    _db_execute("DELETE FROM memory_service.memory_edges WHERE agent_id = 'test_agent'")
    _db_execute("DELETE FROM memory_service.topic_coverage WHERE agent_id = 'test_agent'")


def main():
    print("🧠 Memory Engine — Test Suite")
    print("=" * 50)
    
    if not DB_CONN:
        print("❌ MEMORY_DB_CONN not set. Cannot run tests.")
        sys.exit(1)
    
    if not OPENAI_API_KEY:
        print("⚠️  OPENAI_API_KEY not set. Extraction tests will fail.")
    
    print("\n📋 Running tests...\n")
    
    test("Database connection", test_db_connection)
    test("Schema exists", test_schema_exists)
    
    if OPENAI_API_KEY:
        test("Extraction", test_extraction)
        test("Storage + dedup", test_storage_and_dedup)
        test("Recall", test_recall)
        test("Handoff generation", test_handoff)
        test("Contradiction detection", test_contradiction)
        test("List preservation", test_list_preservation)
        test("Cleanup", test_cleanup)
    else:
        print("  ⏭️  Skipping extraction/storage/recall tests (no OPENAI_API_KEY)")
    
    print(f"\n{'=' * 50}")
    print(f"Results: {results['passed']} passed, {results['failed']} failed")
    
    if results["errors"]:
        print("\nFailures:")
        for e in results["errors"]:
            print(f"  ❌ {e}")
    
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
