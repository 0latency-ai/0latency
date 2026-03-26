"""async_extraction.py — Extract memories from a conversation, poll for results.

The extract endpoint analyzes a conversation and automatically identifies
facts, preferences, and context worth remembering.

pip install zerolatency
"""

import os
import time

from zerolatency import Memory

API_KEY = os.environ["ZEROLATENCY_API_KEY"]

memory = Memory(API_KEY)

# A sample conversation to extract memories from
conversation = [
    {"role": "user", "content": "I just moved to San Francisco from Austin."},
    {"role": "assistant", "content": "Welcome to SF! Are you settling in okay?"},
    {"role": "user", "content": "Yeah, I found a place in the Mission. I work at Stripe now."},
    {"role": "assistant", "content": "Great neighborhood! How's the new role?"},
    {"role": "user", "content": "Love it. I'm on the payments infra team. We use Python and Go mostly."},
]

# Start async extraction
print("🧠 Starting memory extraction from conversation...")
job = memory.extract(conversation)
job_id = job["job_id"]
print(f"   Job ID: {job_id}")

# Poll until complete
while True:
    status = memory.extract_status(job_id)
    state = status.get("status", "unknown")
    print(f"   Status: {state}")

    if state == "completed":
        break
    if state == "failed":
        print(f"   ❌ Extraction failed: {status.get('error', 'unknown')}")
        exit(1)

    time.sleep(2)  # poll every 2 seconds

# Show extracted memories
print("\n✅ Extraction complete. Memories found:")
for mem in status.get("memories", []):
    print(f"  - {mem['content']}")

# Now recall against extracted memories
print("\n🔍 Recall: 'Where does the user work?'")
results = memory.recall("Where does the user work?")
for mem in results.get("memories", []):
    print(f"  - {mem['content']}  (score: {mem.get('score', 'N/A')})")
