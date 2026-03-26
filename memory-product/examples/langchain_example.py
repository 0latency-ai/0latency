#!/usr/bin/env python3
"""
LangChain + 0Latency Integration Example

Shows how to integrate 0Latency memory with LangChain agents.
"""

import os
from typing import Any, Dict, List
from zero_latency import ZeroLatencyClient

# LangChain imports
try:
    from langchain.memory import BaseMemory
    from langchain.schema import BaseMessage, HumanMessage, AIMessage
    from langchain_openai import ChatOpenAI
    from langchain.agents import AgentExecutor, create_openai_functions_agent
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.tools import tool
except ImportError:
    print("❌ This example requires LangChain. Install with:")
    print("   pip install langchain langchain-openai")
    exit(1)


class ZeroLatencyMemory(BaseMemory):
    """
    Custom LangChain memory class that uses 0Latency for storage and recall.
    """
    
    client: ZeroLatencyClient
    agent_id: str
    memory_key: str = "chat_history"
    return_messages: bool = True
    
    def __init__(self, api_key: str, agent_id: str, **kwargs):
        super().__init__(**kwargs)
        self.client = ZeroLatencyClient(api_key=api_key)
        self.agent_id = agent_id
    
    @property
    def memory_variables(self) -> List[str]:
        """Return memory variables."""
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load memory variables - recall relevant memories based on current input.
        """
        # Get the current query from inputs
        query = inputs.get("input", "")
        
        if not query:
            return {self.memory_key: []}
        
        # Recall relevant memories from 0Latency
        try:
            memories = self.client.recall(
                agent_id=self.agent_id,
                query=query,
                limit=5
            )
            
            # Convert memories to LangChain message format
            memory_messages = []
            for mem in memories:
                content = mem.get('content', mem.get('fact', ''))
                # Add as system-like message showing context
                memory_messages.append(
                    AIMessage(content=f"[Memory: {content}]")
                )
            
            return {self.memory_key: memory_messages}
        
        except Exception as e:
            print(f"Warning: Could not load memories: {e}")
            return {self.memory_key: []}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """
        Save conversation context to 0Latency.
        """
        human_message = inputs.get("input", "")
        ai_message = outputs.get("output", "")
        
        if human_message and ai_message:
            try:
                # Extract and store memories
                self.client.extract(
                    agent_id=self.agent_id,
                    human_message=human_message,
                    agent_message=ai_message
                )
            except Exception as e:
                print(f"Warning: Could not save context: {e}")
    
    def clear(self) -> None:
        """Clear memory (optional - 0Latency persists across sessions)."""
        pass


def main():
    # Setup
    api_key = os.getenv("ZERO_LATENCY_API_KEY", "your_zero_latency_key")
    openai_key = os.getenv("OPENAI_API_KEY", "your_openai_key")
    agent_id = "langchain-demo-agent"
    
    # Initialize 0Latency memory
    print("🧠 Initializing 0Latency memory for LangChain...")
    memory = ZeroLatencyMemory(api_key=api_key, agent_id=agent_id)
    
    # Create LLM
    llm = ChatOpenAI(
        api_key=openai_key,
        model="gpt-4",
        temperature=0.7
    )
    
    # Define a simple tool
    @tool
    def get_weather(location: str) -> str:
        """Get the current weather for a location."""
        return f"The weather in {location} is sunny and 72°F."
    
    tools = [get_weather]
    
    # Create prompt with memory placeholder
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant with long-term memory."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Create agent
    agent = create_openai_functions_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True)
    
    # Example conversations
    print("\n" + "="*60)
    print("First conversation - teaching the agent about user preferences")
    print("="*60)
    
    result1 = agent_executor.invoke({
        "input": "My name is Bob and I live in Seattle. I love coffee and hiking."
    })
    print(f"\n🤖 Agent: {result1['output']}")
    
    print("\n" + "="*60)
    print("Second conversation - agent recalls previous information")
    print("="*60)
    
    result2 = agent_executor.invoke({
        "input": "What's my favorite activity?"
    })
    print(f"\n🤖 Agent: {result2['output']}")
    
    print("\n" + "="*60)
    print("Third conversation - checking weather with context")
    print("="*60)
    
    result3 = agent_executor.invoke({
        "input": "What's the weather like where I live?"
    })
    print(f"\n🤖 Agent: {result3['output']}")
    
    print("\n✅ LangChain + 0Latency integration complete!")
    print("\n💡 The agent now has persistent memory across sessions.")
    print("   Restart this script and it will remember Bob from Seattle!")


if __name__ == "__main__":
    main()
