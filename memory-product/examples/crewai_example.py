#!/usr/bin/env python3
"""
CrewAI + 0Latency Integration Example

Shows how to give CrewAI agents long-term memory using 0Latency.
"""

import os
from zero_latency import ZeroLatencyClient

try:
    from crewai import Agent, Task, Crew, Process
    from langchain_openai import ChatOpenAI
except ImportError:
    print("❌ This example requires CrewAI. Install with:")
    print("   pip install crewai langchain-openai")
    exit(1)


class MemoryEnhancedAgent:
    """
    Wrapper that adds 0Latency memory to a CrewAI agent.
    """
    
    def __init__(self, agent: Agent, zero_latency_client: ZeroLatencyClient, agent_id: str):
        self.agent = agent
        self.client = zero_latency_client
        self.agent_id = agent_id
    
    def recall_context(self, query: str) -> str:
        """
        Recall relevant memories for context.
        """
        try:
            memories = self.client.recall(
                agent_id=self.agent_id,
                query=query,
                limit=5
            )
            
            if not memories:
                return ""
            
            # Format memories as context
            context = "Relevant memories:\n"
            for mem in memories:
                content = mem.get('content', mem.get('fact', ''))
                context += f"- {content}\n"
            
            return context
        
        except Exception as e:
            print(f"Warning: Could not recall memories: {e}")
            return ""
    
    def store_interaction(self, task_description: str, result: str):
        """
        Store the task and result as memories.
        """
        try:
            self.client.extract(
                agent_id=self.agent_id,
                human_message=task_description,
                agent_message=result
            )
        except Exception as e:
            print(f"Warning: Could not store interaction: {e}")


def main():
    # Setup
    zero_latency_key = os.getenv("ZERO_LATENCY_API_KEY", "your_zero_latency_key")
    openai_key = os.getenv("OPENAI_API_KEY", "your_openai_key")
    
    # Initialize 0Latency
    print("🧠 Initializing 0Latency for CrewAI agents...")
    zl_client = ZeroLatencyClient(api_key=zero_latency_key)
    
    # Initialize LLM
    llm = ChatOpenAI(
        api_key=openai_key,
        model="gpt-4",
        temperature=0.7
    )
    
    # Create CrewAI agents with memory
    researcher_agent = Agent(
        role='Research Analyst',
        goal='Find and analyze information about topics',
        backstory='You are a detail-oriented researcher with excellent memory.',
        verbose=True,
        llm=llm
    )
    
    writer_agent = Agent(
        role='Content Writer',
        goal='Create engaging content based on research',
        backstory='You are a creative writer who remembers past work and preferences.',
        verbose=True,
        llm=llm
    )
    
    # Wrap agents with memory
    researcher_with_memory = MemoryEnhancedAgent(
        researcher_agent,
        zl_client,
        "crewai-researcher"
    )
    
    writer_with_memory = MemoryEnhancedAgent(
        writer_agent,
        zl_client,
        "crewai-writer"
    )
    
    # Example 1: Research task with memory
    print("\n" + "="*60)
    print("Task 1: Research with memory enhancement")
    print("="*60)
    
    research_query = "What are the benefits of AI in education?"
    
    # Recall previous context
    context = researcher_with_memory.recall_context(research_query)
    task_description = f"{context}\n\nNew query: {research_query}"
    
    research_task = Task(
        description=task_description,
        agent=researcher_agent,
        expected_output="A comprehensive analysis of AI benefits in education"
    )
    
    crew = Crew(
        agents=[researcher_agent],
        tasks=[research_task],
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    print(f"\n📊 Research Result: {result}")
    
    # Store the interaction
    researcher_with_memory.store_interaction(research_query, str(result))
    
    # Example 2: Writing task building on previous research
    print("\n" + "="*60)
    print("Task 2: Writing with memory of previous research")
    print("="*60)
    
    writing_query = "Write a short article about AI in education"
    
    # Recall previous research
    context = writer_with_memory.recall_context(writing_query)
    writing_description = f"{context}\n\nTask: {writing_query}"
    
    writing_task = Task(
        description=writing_description,
        agent=writer_agent,
        expected_output="An engaging 200-word article about AI in education"
    )
    
    crew2 = Crew(
        agents=[writer_agent],
        tasks=[writing_task],
        process=Process.sequential,
        verbose=True
    )
    
    article_result = crew2.kickoff()
    print(f"\n📝 Article: {article_result}")
    
    # Store the writing
    writer_with_memory.store_interaction(writing_query, str(article_result))
    
    # Show memory stats
    print("\n" + "="*60)
    print("Memory Statistics")
    print("="*60)
    
    researcher_memories = zl_client.list_memories("crewai-researcher", limit=50)
    writer_memories = zl_client.list_memories("crewai-writer", limit=50)
    
    print(f"Researcher memories: {len(researcher_memories)}")
    print(f"Writer memories: {len(writer_memories)}")
    
    # Get sentiment
    researcher_sentiment = zl_client.get_sentiment_summary("crewai-researcher")
    print(f"\nResearcher sentiment: {researcher_sentiment}")
    
    print("\n✅ CrewAI + 0Latency integration complete!")
    print("\n💡 Both agents now have persistent memory.")
    print("   They can recall previous research and writing for future tasks!")
    
    # Cleanup
    zl_client.close()


if __name__ == "__main__":
    main()
