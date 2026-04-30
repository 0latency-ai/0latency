"""
End-to-end pipeline test: Extract → Store → Verify
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

# GOOGLE_API_KEY must be set in environment before running tests

from extraction import extract_memories
from storage import store_memories, get_memory_stats, _db_execute

AGENT_ID = "test-agent"


def clean_test_data():
    """Remove test agent data."""
    _db_execute("DELETE FROM memory_service.memory_audit_log WHERE agent_id = %s", (AGENT_ID,))
    _db_execute("DELETE FROM memory_service.memories WHERE agent_id = %s", (AGENT_ID,))
    print("🧹 Cleaned test data\n")


def test_full_pipeline():
    """Run 3 conversation turns through extract → store pipeline."""
    
    turns = [
        {
            "human": "I need you to explore what Nvidia just launched with NemoClaw to tell me how it's different than what we have here.",
            "agent": "NemoClaw is not a replacement for OpenClaw. It's an enterprise wrapper Nvidia announced at GTC. It addresses security and sandboxing. On the memory issue — they haven't solved it. Zero mention of memory persistence anywhere.",
            "turn_id": "turn-001"
        },
        {
            "human": "Is there any way that we could package what we've built and sell it as a product?",
            "agent": "Worth thinking about seriously. The memory layer is a wide open gap nobody is filling. Option B — a Memory API — is the sweet spot. Framework-agnostic, solves the universal problem. Estimated 40-80 hours to MVP.",
            "turn_id": "turn-002"
        },
        {
            "human": "I know you have Graph API. There's no need to announce it - just do it. We set up all the access weeks ago.",
            "agent": "Noted. Won't happen again.",
            "turn_id": "turn-003"
        }
    ]
    
    all_stored = []
    
    for i, turn in enumerate(turns):
        print(f"--- Turn {i+1} ---")
        print(f"  Human: {turn['human'][:80]}...")
        
        # Extract
        memories, raw_turn_id = extract_memories(
            human_message=turn['human'],
            agent_message=turn['agent'],
            agent_id=AGENT_ID,
            session_key="pipeline-test",
            turn_id=turn['turn_id'],
        )
        print(f"  Extracted: {len(memories)} memories")
        
        # Store
        if memories:
            ids = store_memories(memories)
            all_stored.extend(ids)
        
        print()
    
    # Verify
    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    
    stats = get_memory_stats(AGENT_ID)
    print(f"\nMemory Stats: {json.dumps(stats, indent=2)}")
    
    # Query all stored memories
    rows = _db_execute(f"""
        SELECT headline, memory_type, importance, relevance_score, 
               array_to_string(entities, ', ') as entities
        FROM memory_service.memories 
        WHERE agent_id = '{AGENT_ID}'
          AND superseded_at IS NULL
        ORDER BY importance DESC
    """)
    
    print(f"\nStored memories ({len(rows)}):")
    for row in rows:
        parts = row.split("|")
        print(f"  [{parts[1].upper()}] (imp={parts[2]}, rel={parts[3]}) {parts[0]}")
        if parts[4]:
            print(f"    Entities: {parts[4]}")
    
    # Test reinforcement — re-extract the same NemoClaw fact
    print(f"\n--- Reinforcement Test ---")
    memories2, raw_turn_id2 = extract_memories(
        human_message="Tell me again about NemoClaw",
        agent_message="NemoClaw is Nvidia's enterprise wrapper for OpenClaw announced at GTC. It handles security, not memory.",
        agent_id=AGENT_ID,
        session_key="pipeline-test",
        turn_id="turn-reinforce",
    )
    if memories2:
        store_memories(memories2)
    
    # Check if reinforcement worked
    rows2 = _db_execute(f"""
        SELECT headline, reinforcement_count, relevance_score
        FROM memory_service.memories
        WHERE agent_id = '{AGENT_ID}'
          AND headline ILIKE '%NemoClaw%'
          AND superseded_at IS NULL
        ORDER BY reinforcement_count DESC
        LIMIT 3
    """)
    print(f"\nNemoClaw memories after reinforcement:")
    for row in rows2:
        parts = row.split("|")
        print(f"  {parts[0]} — reinforced {parts[1]}x, relevance={parts[2]}")
    
    return all_stored


if __name__ == "__main__":
    clean_test_data()
    test_full_pipeline()
