#!/usr/bin/env python3
"""
Simple test of Google embedding API to isolate the issue.
"""

import os
import requests

# Test the embedding API
def test_embedding():
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    model_name = "gemini-embedding-001"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent"
    
    test_text = "memory product decisions"
    
    print(f"Testing embedding API with text: '{test_text}'")
    
    try:
        resp = requests.post(
            url,
            params={"key": api_key},
            json={
                "model": f"models/{model_name}",
                "content": {"parts": [{"text": test_text}]},
                "outputDimensionality": 768
            },
            timeout=15
        )
        
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"Error response: {resp.text}")
            return None
        
        data = resp.json()
        if "embedding" in data:
            embedding = data["embedding"]["values"]
            print(f"✅ Successfully got embedding with {len(embedding)} dimensions")
            print(f"First 5 values: {embedding[:5]}")
            return embedding
        else:
            print(f"❌ No embedding in response: {data}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

if __name__ == "__main__":
    test_embedding()