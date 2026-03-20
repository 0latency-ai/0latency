#!/usr/bin/env python3
"""
Test the vector search directly against the database.
"""

import os
import subprocess
import requests

def get_embedding(text):
    """Get embedding for text using Google API."""
    api_key = "AIzaSyAvFCk21Sz4G3AbKm9USob55DqJnpJBVmI"
    model_name = "gemini-embedding-001"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent"
    
    resp = requests.post(
        url,
        params={"key": api_key},
        json={
            "model": f"models/{model_name}",
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": 768
        },
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]

def db_execute(query):
    """Execute a query against the database."""
    result = subprocess.run(
        ["psql", "postgresql://postgres.fuojxlabvhtmysbsixdn:jcYlwEhuHN9VcOuj@aws-1-us-east-1.pooler.supabase.com:5432/postgres", 
         "-t", "-A", "-F", "|||", "-c", query],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "PGPASSWORD": "jcYlwEhuHN9VcOuj"}
    )
    if result.returncode != 0:
        print(f"DB error: {result.stderr}")
        return []
    rows = [line for line in result.stdout.strip().split("\n") if line]
    return rows

def test_vector_search(query_text):
    print(f"\n=== Testing vector search for: '{query_text}' ===")
    
    # Get embedding for query
    print("Getting embedding...")
    try:
        embedding = get_embedding(query_text)
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        print(f"✅ Got embedding with {len(embedding)} dimensions")
    except Exception as e:
        print(f"❌ Failed to get embedding: {e}")
        return
    
    # Test vector search query
    vector_query = f"""
        SELECT id, headline, memory_type,
               1 - (embedding <=> '{embedding_str}'::extensions.vector) as similarity
        FROM memory_service.memories
        WHERE agent_id = 'thomas'
          AND superseded_at IS NULL
          AND embedding IS NOT NULL
        ORDER BY embedding <=> '{embedding_str}'::extensions.vector
        LIMIT 10
    """
    
    print("Running vector search...")
    try:
        rows = db_execute(vector_query)
        
        if not rows:
            print("❌ Vector search returned 0 results!")
        else:
            print(f"✅ Vector search returned {len(rows)} results")
            print("Top results:")
            for i, row in enumerate(rows[:5]):
                parts = row.split("|||")
                if len(parts) >= 4:
                    print(f"  {i+1}. [{parts[2]}] {parts[1]} (similarity: {parts[3]})")
    except Exception as e:
        print(f"❌ Vector search failed: {e}")

def test_keyword_search(query_text):
    print(f"\n=== Testing keyword search for: '{query_text}' ===")
    
    # Simple keyword search
    keyword_query = f"""
        SELECT id, headline, memory_type
        FROM memory_service.memories
        WHERE agent_id = 'thomas'
          AND superseded_at IS NULL
          AND (headline ILIKE '%{query_text}%' OR context ILIKE '%{query_text}%')
        ORDER BY importance DESC
        LIMIT 10
    """
    
    try:
        rows = db_execute(keyword_query)
        
        if not rows:
            print("❌ Keyword search returned 0 results!")
        else:
            print(f"✅ Keyword search returned {len(rows)} results")
            print("Top results:")
            for i, row in enumerate(rows[:5]):
                parts = row.split("|||")
                if len(parts) >= 3:
                    print(f"  {i+1}. [{parts[2]}] {parts[1]}")
    except Exception as e:
        print(f"❌ Keyword search failed: {e}")

if __name__ == "__main__":
    test_queries = [
        "memory product decisions",
        "pricing",
        "pre-launch checklist",
    ]
    
    for query in test_queries:
        test_vector_search(query)
        test_keyword_search(query)