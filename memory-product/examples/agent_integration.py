"""agent_integration.py — Wire 0Latency memory into an OpenAI / LangChain agent loop.

Shows two patterns:
  1. Direct OpenAI function-calling with memory context
  2. LangChain tool integration

pip install zerolatency openai
"""

import os

from zerolatency import Memory

API_KEY = os.environ["ZEROLATENCY_API_KEY"]

memory = Memory(API_KEY)


# ──────────────────────────────────────────────────────────────────────────────
# Pattern 1: OpenAI function-calling with memory-augmented system prompt
# ──────────────────────────────────────────────────────────────────────────────

def chat_with_memory(user_message: str) -> str:
    """Send a message to OpenAI with relevant memories injected."""
    import openai

    client = openai.OpenAI()

    # Recall relevant memories for this query
    recall_results = memory.recall(user_message, limit=5)
    memories = recall_results.get("memories", [])

    # Build memory context block
    if memories:
        memory_block = "\n".join(f"- {m['content']}" for m in memories)
        memory_context = f"\n\n## Relevant memories about this user:\n{memory_block}"
    else:
        memory_context = ""

    # Chat completion with memory context
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": f"You are a helpful assistant with persistent memory.{memory_context}",
            },
            {"role": "user", "content": user_message},
        ],
    )

    assistant_reply = response.choices[0].message.content

    # Store the conversation exchange for future recall
    memory.extract([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_reply},
    ])

    return assistant_reply


# ──────────────────────────────────────────────────────────────────────────────
# Pattern 2: LangChain tool integration
# ──────────────────────────────────────────────────────────────────────────────

def build_langchain_tools():
    """Create LangChain tools backed by 0Latency memory."""
    from langchain_core.tools import tool

    @tool
    def remember(content: str) -> str:
        """Store a fact or preference about the user for later recall."""
        result = memory.add(content)
        return f"Stored memory: {content} (id: {result.get('id', 'unknown')})"

    @tool
    def recall_memory(query: str) -> str:
        """Search stored memories for information relevant to a query."""
        results = memory.recall(query, limit=5)
        memories = results.get("memories", [])
        if not memories:
            return "No relevant memories found."
        return "\n".join(f"- {m['content']}" for m in memories)

    return [remember, recall_memory]


# ──────────────────────────────────────────────────────────────────────────────
# Demo
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Store some context first
    print("📝 Storing initial memories...")
    memory.add("User's name is Jordan. They prefer concise answers.")
    memory.add("User is building a customer support chatbot.")
    memory.add("User's tech stack: Python, FastAPI, PostgreSQL, Redis.")

    # Pattern 1: Direct OpenAI integration
    print("\n💬 Pattern 1: OpenAI with memory context")
    print("   (Requires OPENAI_API_KEY env var)")
    try:
        reply = chat_with_memory("What tech stack should I use for the queue system?")
        print(f"   Assistant: {reply[:200]}...")
    except Exception as e:
        print(f"   Skipped (set OPENAI_API_KEY to test): {e}")

    # Pattern 2: LangChain tools
    print("\n🔧 Pattern 2: LangChain tools")
    print("   (Requires langchain-core)")
    try:
        tools = build_langchain_tools()
        for t in tools:
            print(f"   Tool: {t.name} — {t.description}")
    except ImportError:
        print("   Skipped (pip install langchain-core to test)")

    print("\n✅ See source code for full integration patterns.")
