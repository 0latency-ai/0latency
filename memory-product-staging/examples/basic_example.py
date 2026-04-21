#!/usr/bin/env python3
"""
Basic 0Latency Example

A simple script showing how to store and recall memories using 0Latency.
Just set your API key and run!
"""

import os
from zero_latency import ZeroLatencyClient, ZeroLatencyError

def main():
    # Get API key from environment or hardcode for testing
    api_key = os.getenv("ZERO_LATENCY_API_KEY", "your_api_key_here")
    
    # Initialize client
    print("🧠 Initializing 0Latency client...")
    client = ZeroLatencyClient(api_key=api_key)
    
    # Use a unique agent ID for this example
    agent_id = "basic-example-agent"
    
    try:
        # 1. Extract memories from a conversation
        print("\n📝 Extracting memories from conversation...")
        conversation = {
            "human": "My name is Alice and I work as a data scientist in San Francisco. I love Python and hiking.",
            "agent": "Nice to meet you, Alice! Data science is a fascinating field, and San Francisco is a great place for hiking."
        }
        
        extract_result = client.extract(
            agent_id=agent_id,
            human_message=conversation["human"],
            agent_message=conversation["agent"]
        )
        print(f"✓ Extracted {len(extract_result.get('memories', []))} memories")
        
        # 2. Store another conversation turn
        print("\n📝 Storing another conversation...")
        client.extract(
            agent_id=agent_id,
            human_message="I'm working on a machine learning project using scikit-learn and TensorFlow.",
            agent_message="That's great! Those are powerful tools for ML projects."
        )
        
        # 3. Seed some additional facts
        print("\n🌱 Seeding additional facts...")
        facts = [
            "User prefers morning hikes on weekends",
            "User's favorite Python library is pandas",
            "User attended PyData conference last year"
        ]
        seed_result = client.seed(agent_id=agent_id, facts=facts)
        print(f"✓ Seeded {len(facts)} facts")
        
        # 4. Recall relevant memories
        print("\n🔍 Recalling memories about Python...")
        memories = client.recall(
            agent_id=agent_id,
            query="What programming languages and tools does the user use?",
            limit=5
        )
        
        print(f"\nFound {len(memories)} relevant memories:")
        for i, memory in enumerate(memories, 1):
            content = memory.get('content', memory.get('fact', 'N/A'))
            confidence = memory.get('confidence', 0)
            print(f"  {i}. {content[:100]}... (confidence: {confidence:.2f})")
        
        # 5. Search for specific keywords
        print("\n🔎 Searching for 'hiking'...")
        search_results = client.search(
            agent_id=agent_id,
            q="hiking",
            limit=10
        )
        print(f"Found {len(search_results)} memories mentioning hiking")
        
        # 6. Get all memories
        print("\n📚 Listing all memories...")
        all_memories = client.list_memories(agent_id=agent_id, limit=50)
        print(f"Total memories stored: {len(all_memories)}")
        
        # 7. Get entities
        print("\n👤 Extracting entities...")
        entities = client.get_entities(agent_id=agent_id, limit=20)
        if entities:
            print(f"Found {len(entities)} entities:")
            for entity in entities[:5]:  # Show first 5
                print(f"  - {entity.get('name')} ({entity.get('type')})")
        
        # 8. Get sentiment summary
        print("\n😊 Getting sentiment summary...")
        sentiment = client.get_sentiment_summary(agent_id=agent_id)
        print(f"Sentiment breakdown: {sentiment}")
        
        print("\n✅ Example complete!")
        
    except ZeroLatencyError as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    finally:
        # Clean up
        client.close()
    
    return 0


if __name__ == "__main__":
    exit(main())
