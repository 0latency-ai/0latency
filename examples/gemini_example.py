"""
Example: Using 0Latency with Google Gemini
"""
from zerolatency import ZeroLatency
import google.generativeai as genai

# Initialize clients
memory = ZeroLatency(api_key="your_0latency_key")
genai.configure(api_key="your_google_api_key")

agent_id = "my-assistant"
model = genai.GenerativeModel('gemini-pro')

# Store a memory
memory.store(agent_id, "User is interested in machine learning and neural networks")

# Recall relevant context
context = memory.recall(agent_id, "What are the user's interests?")

# Use in Gemini prompt
prompt = f"""
Based on what I know about you: {context}

How can I help you today?
"""

response = model.generate_content(prompt)
print(response.text)

# Store this interaction
memory.store(agent_id, f"Conversation about: {response.text[:100]}")
