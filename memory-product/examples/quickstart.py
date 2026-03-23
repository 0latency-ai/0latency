"""quickstart.py — Basic add + recall with 0Latency.

pip install zerolatency
"""

import os

from zerolatency import Memory

API_KEY = os.environ["ZEROLATENCY_API_KEY"]

memory = Memory(API_KEY)

# Store some memories
memory.add("User prefers dark mode across all applications.")
memory.add("User's name is Alice and she works at Acme Corp.")
memory.add("User is building a RAG pipeline with LangChain.", metadata={"project": "rag-v2"})

print("✅ Memories stored.\n")

# Recall relevant memories
results = memory.recall("What does the user prefer for UI?")
print("🔍 Recall: 'What does the user prefer for UI?'")
for mem in results.get("memories", []):
    print(f"  - {mem['content']}  (score: {mem.get('score', 'N/A')})")

print()

# Scoped recall by agent
memory.add("Deployment target is AWS us-east-1.", agent_id="ops-agent")
results = memory.recall("Where do we deploy?", agent_id="ops-agent")
print("🔍 Scoped recall (ops-agent): 'Where do we deploy?'")
for mem in results.get("memories", []):
    print(f"  - {mem['content']}")
