# Example 1: Simple Chatbot with Memory

Build a chatbot that remembers user preferences and past conversations.

**What you'll build:** A command-line chatbot that:
- Remembers your name, preferences, and past topics
- Recalls relevant context for each new message
- Gets smarter over time

**Time:** ~15 minutes  
**Difficulty:** Beginner

---

## The Problem

Standard chatbots forget everything:

```python
# Without memory
user: "My name is Alex"
bot: "Nice to meet you, Alex!"

# 5 minutes later...
user: "What's my name?"
bot: "I don't know your name."  # 😞
```

Let's fix that.

---

## Full Working Code

Copy-paste this into `chatbot.py`:

```python
#!/usr/bin/env python3
"""
Simple chatbot with 0Latency memory.
Remembers everything. Never forgets.
"""

import os
from zerolatency import Memory

# Initialize memory client
AGENT_ID = "chatbot_v1"
mem = Memory(os.getenv("ZEROLATENCY_API_KEY"))

def chat(user_message: str) -> str:
    """
    Send a message and get a response with full memory context.
    """
    
    # Step 1: Recall relevant memories
    recall_result = mem.recall(
        agent_id=AGENT_ID,
        conversation_context=user_message,
        budget_tokens=2000  # Adjust based on your LLM's context window
    )
    
    context_block = recall_result["context_block"]
    
    # Step 2: Build the prompt with memory context
    prompt = f"""You are a helpful assistant with memory.

{context_block}

User: {user_message}
Assistant:"""
    
    # Step 3: Get LLM response (using OpenAI as example)
    # You can use Claude, Gemini, or any LLM here
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    bot_message = response.choices[0].message.content
    
    # Step 4: Store the conversation turn for future recall
    mem.add(
        agent_id=AGENT_ID,
        human_message=user_message,
        agent_message=bot_message
    )
    
    return bot_message

def main():
    """Interactive chat loop."""
    print("🤖 Chatbot with Memory")
    print("=" * 50)
    print("Type 'quit' to exit\n")
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ["quit", "exit", "q"]:
            print("\n👋 Goodbye! I'll remember this conversation.")
            break
        
        if not user_input:
            continue
        
        try:
            bot_response = chat(user_input)
            print(f"Bot: {bot_response}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    main()
```

---

## Setup

### 1. Install dependencies

```bash
pip install zerolatency openai
```

### 2. Set environment variables

```bash
export ZEROLATENCY_API_KEY="zl_live_your_key_here"
export OPENAI_API_KEY="sk-your-openai-key"
```

### 3. Run it

```bash
python chatbot.py
```

---

## Example Conversation

```
🤖 Chatbot with Memory
==================================================
Type 'quit' to exit

You: Hi, my name is Alex and I'm a software engineer
Bot: Nice to meet you, Alex! Software engineering is a great field. What kind of projects are you working on?

You: I'm building a personal finance app in Python
Bot: That sounds interesting! A personal finance app is a practical project. Are you using any specific frameworks or libraries for it?

You: Yes, Flask for the backend and React for the frontend
Bot: Great choices! Flask is lightweight and easy to work with for APIs, and React gives you a lot of flexibility on the frontend. How's the development going?

You: quit

👋 Goodbye! I'll remember this conversation.
```

### Now restart the chatbot and continue:

```
You: What's my name?
Bot: Your name is Alex.

You: What am I building?
Bot: You're building a personal finance app using Flask for the backend and React for the frontend.

You: What language am I using?
Bot: You're using Python for the backend (with Flask) and JavaScript/React for the frontend.
```

**It remembers everything.** 🧠

---

## How It Works

### Step 1: Recall Relevant Memories

```python
recall_result = mem.recall(
    agent_id=AGENT_ID,
    conversation_context=user_message,
    budget_tokens=2000
)
```

When the user asks "What's my name?", 0Latency:
1. Searches all stored memories for this agent
2. Finds "User's name is Alex" (high semantic similarity)
3. Scores by similarity, recency, importance, access frequency
4. Returns the most relevant memories within the token budget

### Step 2: Include Context in LLM Prompt

```python
context_block = recall_result["context_block"]

prompt = f"""You are a helpful assistant with memory.

{context_block}

User: {user_message}
Assistant:"""
```

The context block looks like this:

```
### Relevant Context
- User's name: Alex
- Occupation: Software engineer
- Current project: Personal finance app
- Tech stack: Flask (backend), React (frontend), Python

[4 memories used, 127 tokens]
```

This gets injected into your LLM prompt automatically.

### Step 3: Store the New Conversation

```python
mem.add(
    agent_id=AGENT_ID,
    human_message=user_message,
    agent_message=bot_message
)
```

Every conversation turn gets stored. 0Latency:
- Extracts structured memories (facts, preferences, decisions, etc.)
- Updates existing memories if they're reinforced or contradicted
- Indexes everything for fast recall

---

## Key Concepts

### Agent ID

```python
AGENT_ID = "chatbot_v1"
```

This identifies *which agent* the memories belong to. Use different IDs for:
- Different users (multi-tenant chatbot)
- Different agents (customer support vs. sales bot)
- Different environments (dev vs. prod)

### Token Budget

```python
budget_tokens=2000
```

How much context to include. Recommendations:
- **GPT-3.5/GPT-4:** 2000-4000 tokens
- **Claude 3:** 4000-8000 tokens
- **Gemini Pro:** 4000-6000 tokens
- **Llama 3 70B:** 2000-4000 tokens

0Latency **never exceeds** your budget. It packs the best memories into the available space.

### Context Block Format

The `context_block` is human-readable markdown. It includes:
- **Relevant Context:** Scored and ranked memories
- **Metadata:** How many memories, how many tokens used

You can customize the format if needed (see [Advanced Usage](../advanced/custom-context.md)).

---

## Improving the Chatbot

### Add User-Specific Agent IDs

```python
# Multi-user chatbot
def chat(user_id: str, user_message: str) -> str:
    agent_id = f"chatbot_{user_id}"
    
    recall_result = mem.recall(
        agent_id=agent_id,
        conversation_context=user_message,
        budget_tokens=2000
    )
    # ... rest of the code
```

Now each user has their own memory space.

### Add Session Context

```python
# Include session key for conversation grouping
mem.add(
    agent_id=AGENT_ID,
    human_message=user_message,
    agent_message=bot_message,
    session_key=f"session_{datetime.now().strftime('%Y%m%d')}"
)
```

Useful for grouping conversations by day, topic, or session.

### Add Sentiment Awareness

```python
# Filter memories by sentiment
from zerolatency import Memory

mem = Memory(api_key)

# Get positive memories for motivation
positive_memories = mem.list_memories(
    agent_id=AGENT_ID,
    sentiment="positive",
    limit=10
)
```

Great for wellness bots, therapy assistants, or customer support.

### Add Memory Search

```python
# Search memories by keyword
results = mem.search_memories(
    agent_id=AGENT_ID,
    query="Python",
    limit=10
)

for memory in results:
    print(f"- {memory['headline']}")
```

Useful for:
- "Show me all conversations about Python"
- "What did I say about the budget?"
- "Find mentions of Sarah"

---

## Handling Edge Cases

### What if there are no memories?

```python
recall_result = mem.recall(
    agent_id=AGENT_ID,
    conversation_context=user_message,
    budget_tokens=2000
)

if recall_result["memories_used"] == 0:
    context_block = "### Relevant Context\n(No prior context available)\n"
else:
    context_block = recall_result["context_block"]
```

The first conversation always has no context. That's fine.

### What if the API is down?

```python
try:
    recall_result = mem.recall(
        agent_id=AGENT_ID,
        conversation_context=user_message,
        budget_tokens=2000
    )
except Exception as e:
    print(f"⚠️ Memory recall failed: {e}")
    # Fall back to no memory context
    context_block = ""
```

Graceful degradation: your bot still works, just without memory.

### What about rate limits?

Free tier: **20 requests/min**  
Pro tier: **100 requests/min**

For high-traffic bots:
1. Cache recall results for repeated queries
2. Use async extraction (`mem.add_async()`) to avoid blocking
3. Upgrade to Pro ($19/mo) or Scale ($99/mo)

---

## Next Steps

You've built a chatbot with memory! Here's what to try next:

### 📘 More Examples
- [Customer Support Agent](./customer-support.md) — Handle support tickets with context
- [Claude Code Integration](./claude-code.md) — Add memory to Claude via MCP

### 🔧 Enhancements
- Add voice input/output (Whisper + ElevenLabs)
- Build a web UI (Flask + React)
- Deploy to production (Heroku, Railway, fly.io)
- Add multi-language support
- Implement conversation export

### 📖 Deep Dives
- [Memory Types](../memory-types.md) — Understanding what gets extracted
- [Scoring & Ranking](../scoring.md) — How recall prioritizes memories
- [Graph API](../graph-api.md) — Navigate memory relationships

---

## Full Code (Alternative: Claude)

Prefer Claude over OpenAI? Here's the same chatbot using Anthropic:

```python
#!/usr/bin/env python3
import os
from zerolatency import Memory
import anthropic

AGENT_ID = "chatbot_v1"
mem = Memory(os.getenv("ZEROLATENCY_API_KEY"))
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def chat(user_message: str) -> str:
    # Recall memories
    recall_result = mem.recall(
        agent_id=AGENT_ID,
        conversation_context=user_message,
        budget_tokens=4000  # Claude has bigger context window
    )
    
    context_block = recall_result["context_block"]
    
    # Build prompt
    prompt = f"""You are a helpful assistant with memory.

{context_block}

User: {user_message}"""
    
    # Get Claude response
    message = claude.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    
    bot_message = message.content[0].text
    
    # Store conversation
    mem.add(
        agent_id=AGENT_ID,
        human_message=user_message,
        agent_message=bot_message
    )
    
    return bot_message

# Same main() function as before
```

---

## Questions?

- 💬 [Discord Community](https://discord.gg/0latency)
- 📧 Email: support@0latency.ai
- 🐛 [Report a Bug](https://github.com/jghiglia2380/0Latency/issues)

---

**Your chatbot now has a memory.** What will you build next?

