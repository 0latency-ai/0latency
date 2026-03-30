"""
Example: Using 0Latency with Anthropic Claude
"""
from zerolatency import ZeroLatency
import anthropic

# Initialize clients
memory = ZeroLatency(api_key="your_0latency_key")
claude = anthropic.Anthropic(api_key="your_anthropic_key")

agent_id = "my-assistant"

# Store a memory
memory.store(agent_id, "User prefers concise responses without unnecessary preamble")

# Recall relevant context before making API call
context = memory.recall(agent_id, "How should I respond to this user?")

# Use recalled context in your prompt
response = claude.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": f"Context from previous conversations:\n{context}\n\nUser question: What's the weather like?"
    }]
)

print(response.content[0].text)

# Store this interaction for future recall
memory.store(agent_id, f"User asked about weather. Response: {response.content[0].text}")
