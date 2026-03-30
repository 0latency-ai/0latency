"""
Example: Using 0Latency with OpenAI GPT-4
"""
from zerolatency import ZeroLatency
from openai import OpenAI

# Initialize clients
memory = ZeroLatency(api_key="your_0latency_key")
openai = OpenAI(api_key="your_openai_key")

agent_id = "my-assistant"

# Store a memory
memory.store(agent_id, "User is a Python developer building a web scraper")

# Recall relevant context
context = memory.recall(agent_id, "What do I know about this user's technical background?")

# Use in your GPT-4 call
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": f"User context: {context}"},
        {"role": "user", "content": "Can you help me debug this code?"}
    ]
)

print(response.choices[0].message.content)

# Store the interaction
memory.store(agent_id, f"Helped user debug code. Topic: {response.choices[0].message.content[:100]}")
