#!/usr/bin/env python3
"""
AutoGen + 0Latency Integration Example

Shows how to integrate 0Latency memory with Microsoft AutoGen agents.
"""

import os
from typing import Dict, List, Any
from zero_latency import ZeroLatencyClient

try:
    import autogen
    from autogen import AssistantAgent, UserProxyAgent, ConversableAgent
except ImportError:
    print("❌ This example requires AutoGen. Install with:")
    print("   pip install pyautogen")
    exit(1)


class MemoryEnhancedAssistant(AssistantAgent):
    """
    AutoGen AssistantAgent with 0Latency memory integration.
    """
    
    def __init__(
        self,
        name: str,
        zl_client: ZeroLatencyClient,
        agent_id: str,
        *args,
        **kwargs
    ):
        super().__init__(name, *args, **kwargs)
        self.zl_client = zl_client
        self.agent_id = agent_id
        self._conversation_history = []
    
    def generate_reply(
        self,
        messages: List[Dict],
        sender: ConversableAgent,
        config=None
    ) -> str:
        """
        Override reply generation to include memory recall.
        """
        # Get the last message
        if messages:
            last_message = messages[-1].get("content", "")
            
            # Recall relevant memories
            try:
                memories = self.zl_client.recall(
                    agent_id=self.agent_id,
                    query=last_message,
                    limit=3
                )
                
                # Add memory context to system message if we have memories
                if memories:
                    memory_context = "\n\nRelevant context from past conversations:\n"
                    for mem in memories:
                        content = mem.get('content', mem.get('fact', ''))
                        memory_context += f"- {content}\n"
                    
                    # Inject memory context into the conversation
                    enhanced_messages = messages.copy()
                    enhanced_messages.insert(-1, {
                        "role": "system",
                        "content": memory_context
                    })
                    
                    # Generate reply with enhanced context
                    reply = super().generate_reply(enhanced_messages, sender, config)
                else:
                    reply = super().generate_reply(messages, sender, config)
                
                # Store this interaction
                if len(messages) >= 2:
                    human_msg = messages[-1].get("content", "")
                    self.zl_client.extract(
                        agent_id=self.agent_id,
                        human_message=human_msg,
                        agent_message=reply
                    )
                
                return reply
                
            except Exception as e:
                print(f"Warning: Memory operation failed: {e}")
                return super().generate_reply(messages, sender, config)
        
        return super().generate_reply(messages, sender, config)


def main():
    # Setup
    zero_latency_key = os.getenv("ZERO_LATENCY_API_KEY", "your_zero_latency_key")
    openai_key = os.getenv("OPENAI_API_KEY", "your_openai_key")
    
    # AutoGen LLM config
    llm_config = {
        "model": "gpt-4",
        "api_key": openai_key,
        "temperature": 0.7,
    }
    
    # Initialize 0Latency
    print("🧠 Initializing 0Latency for AutoGen...")
    zl_client = ZeroLatencyClient(api_key=zero_latency_key)
    
    # Create memory-enhanced assistant
    assistant = MemoryEnhancedAssistant(
        name="MemoryAssistant",
        zl_client=zl_client,
        agent_id="autogen-assistant",
        system_message="""You are a helpful AI assistant with long-term memory.
        You can remember past conversations and use that context to provide better help.""",
        llm_config=llm_config,
    )
    
    # Create user proxy (simulates user)
    user_proxy = UserProxyAgent(
        name="User",
        human_input_mode="NEVER",  # Automated for demo
        max_consecutive_auto_reply=0,
        code_execution_config={"use_docker": False},
    )
    
    print("\n" + "="*60)
    print("Conversation 1: Teaching the assistant about user preferences")
    print("="*60)
    
    # First conversation - establish context
    user_proxy.initiate_chat(
        assistant,
        message="Hi! My name is Sarah. I'm a product manager at a tech startup in Austin, Texas. I love cycling and reading sci-fi novels."
    )
    
    print("\n" + "="*60)
    print("Conversation 2: The assistant recalls previous info")
    print("="*60)
    
    # Second conversation - test memory recall
    user_proxy.initiate_chat(
        assistant,
        message="What do you know about my hobbies?"
    )
    
    print("\n" + "="*60)
    print("Conversation 3: Context-aware recommendations")
    print("="*60)
    
    # Third conversation - use memory for recommendations
    user_proxy.initiate_chat(
        assistant,
        message="Can you recommend some weekend activities based on what you know about me?"
    )
    
    # Show memory statistics
    print("\n" + "="*60)
    print("Memory Statistics")
    print("="*60)
    
    memories = zl_client.list_memories("autogen-assistant", limit=50)
    print(f"Total memories stored: {len(memories)}")
    
    # Show some memories
    if memories:
        print("\nRecent memories:")
        for i, mem in enumerate(memories[:5], 1):
            content = mem.get('content', mem.get('fact', 'N/A'))
            print(f"{i}. {content[:100]}...")
    
    # Get entities
    entities = zl_client.get_entities("autogen-assistant", limit=20)
    if entities:
        print(f"\nExtracted entities: {len(entities)}")
        for entity in entities[:5]:
            print(f"  - {entity.get('name')} ({entity.get('type')})")
    
    # Consolidate memories
    print("\n🔄 Running memory consolidation...")
    consolidation = zl_client.consolidate("autogen-assistant", auto_merge=False)
    print(f"Consolidation result: {consolidation}")
    
    print("\n✅ AutoGen + 0Latency integration complete!")
    print("\n💡 The assistant now has persistent memory across sessions.")
    print("   It will remember Sarah from Austin when you run this again!")
    
    # Cleanup
    zl_client.close()


if __name__ == "__main__":
    main()
