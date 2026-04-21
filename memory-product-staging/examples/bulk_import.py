#!/usr/bin/env python3
"""
Bulk Import Example for 0Latency

Shows how to import existing notes, documents, or knowledge bases into 0Latency.
Useful for seeding agent memory with historical data or domain knowledge.
"""

import os
import json
from pathlib import Path
from typing import List
from zero_latency import ZeroLatencyClient, ZeroLatencyError


def read_text_file(file_path: str) -> str:
    """Read text content from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""


def split_into_chunks(text: str, chunk_size: int = 500) -> List[str]:
    """
    Split text into smaller chunks for better memory granularity.
    """
    # Simple sentence-aware splitting
    sentences = text.replace('\n', ' ').split('. ')
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < chunk_size:
            current_chunk += sentence + ". "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def import_text_file(client: ZeroLatencyClient, agent_id: str, file_path: str):
    """
    Import a text file into 0Latency memory.
    """
    print(f"\n📄 Importing {file_path}...")
    
    content = read_text_file(file_path)
    if not content:
        return 0
    
    # Split into chunks
    chunks = split_into_chunks(content, chunk_size=500)
    
    # Seed in batches (0Latency handles batching well)
    batch_size = 50
    total_imported = 0
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        try:
            result = client.seed(agent_id=agent_id, facts=batch)
            total_imported += len(batch)
            print(f"  ✓ Imported batch {i//batch_size + 1} ({len(batch)} facts)")
        except ZeroLatencyError as e:
            print(f"  ✗ Error importing batch: {e}")
    
    return total_imported


def import_json_file(client: ZeroLatencyClient, agent_id: str, file_path: str):
    """
    Import structured data from JSON file.
    Expects format: {"facts": [...]} or [{...}, {...}]
    """
    print(f"\n📋 Importing {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        facts = []
        if isinstance(data, dict) and 'facts' in data:
            facts = data['facts']
        elif isinstance(data, list):
            # Convert objects to strings
            facts = [json.dumps(item) if isinstance(item, dict) else str(item) for item in data]
        else:
            print("  ✗ Unsupported JSON format")
            return 0
        
        # Seed facts
        if facts:
            result = client.seed(agent_id=agent_id, facts=facts)
            print(f"  ✓ Imported {len(facts)} facts")
            return len(facts)
        
    except Exception as e:
        print(f"  ✗ Error importing JSON: {e}")
    
    return 0


def import_directory(client: ZeroLatencyClient, agent_id: str, directory: str):
    """
    Recursively import all supported files from a directory.
    """
    print(f"\n📁 Importing from directory: {directory}")
    
    supported_extensions = {'.txt', '.md', '.json'}
    total_files = 0
    total_facts = 0
    
    for path in Path(directory).rglob('*'):
        if path.is_file() and path.suffix.lower() in supported_extensions:
            total_files += 1
            
            if path.suffix.lower() == '.json':
                facts = import_json_file(client, agent_id, str(path))
            else:
                facts = import_text_file(client, agent_id, str(path))
            
            total_facts += facts
    
    return total_files, total_facts


def main():
    # Setup
    api_key = os.getenv("ZERO_LATENCY_API_KEY", "your_api_key_here")
    agent_id = "bulk-import-demo"
    
    print("🧠 0Latency Bulk Import Tool")
    print("="*60)
    
    # Initialize client
    client = ZeroLatencyClient(api_key=api_key)
    
    try:
        # Example 1: Import a list of facts
        print("\n📝 Example 1: Importing a fact list")
        facts = [
            "Python is a high-level programming language",
            "Machine learning is a subset of artificial intelligence",
            "Neural networks are inspired by biological neurons",
            "Deep learning uses multiple layers in neural networks",
            "Natural language processing enables computers to understand text"
        ]
        
        result = client.seed(agent_id=agent_id, facts=facts)
        print(f"✓ Imported {len(facts)} facts")
        
        # Example 2: Import from a text file (create demo file)
        print("\n📄 Example 2: Importing from text file")
        demo_file = "/tmp/demo_knowledge.txt"
        with open(demo_file, 'w') as f:
            f.write("""
            The OpenAI API provides access to powerful language models.
            GPT-4 is the latest model with improved reasoning capabilities.
            API keys should be kept secure and never committed to version control.
            Rate limits vary based on your subscription tier.
            """)
        
        imported = import_text_file(client, agent_id, demo_file)
        print(f"✓ Total facts imported from file: {imported}")
        
        # Example 3: Import from JSON
        print("\n📋 Example 3: Importing from JSON file")
        demo_json = "/tmp/demo_data.json"
        with open(demo_json, 'w') as f:
            json.dump({
                "facts": [
                    "REST APIs use HTTP methods like GET, POST, PUT, DELETE",
                    "JSON is a lightweight data interchange format",
                    "Authentication tokens should expire after a set time",
                    "Webhooks allow real-time event notifications"
                ]
            }, f)
        
        imported = import_json_file(client, agent_id, demo_json)
        
        # Show memory statistics
        print("\n" + "="*60)
        print("Import Summary")
        print("="*60)
        
        all_memories = client.list_memories(agent_id=agent_id, limit=100)
        print(f"Total memories in system: {len(all_memories)}")
        
        # Get entities
        entities = client.get_entities(agent_id=agent_id, limit=50)
        print(f"Extracted entities: {len(entities)}")
        if entities:
            print("\nTop entities:")
            for entity in entities[:10]:
                print(f"  - {entity.get('name')} ({entity.get('type')})")
        
        # Test recall
        print("\n🔍 Testing recall after import...")
        memories = client.recall(
            agent_id=agent_id,
            query="What is machine learning?",
            limit=3
        )
        print(f"Found {len(memories)} relevant memories:")
        for mem in memories:
            content = mem.get('content', mem.get('fact', 'N/A'))
            confidence = mem.get('confidence', 0)
            print(f"  - {content[:100]}... (confidence: {confidence:.2f})")
        
        print("\n✅ Bulk import complete!")
        print("\n💡 Usage tips:")
        print("   - Break large documents into semantic chunks")
        print("   - Use descriptive, self-contained facts")
        print("   - Run consolidation after large imports")
        print("   - Batch imports in groups of 50-100 for best performance")
        
    except ZeroLatencyError as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    finally:
        client.close()
        # Cleanup demo files
        for f in ["/tmp/demo_knowledge.txt", "/tmp/demo_data.json"]:
            if os.path.exists(f):
                os.remove(f)
    
    return 0


if __name__ == "__main__":
    exit(main())
