"""Anthropic client with 0Latency memory integration"""

import json
import threading
from typing import Any, Dict, List, Optional
import requests
from anthropic import Anthropic


class AnthropicWithMemory:
    """Drop-in replacement for Anthropic client with automatic memory storage and recall"""
    
    def __init__(
        self,
        api_key: str,
        zl_api_key: str,
        agent_id: str,
        zl_base_url: str = "https://api.0latency.ai",
        recall_enabled: bool = True,
        store_enabled: bool = True,
        budget_tokens: int = 4000,
    ):
        """
        Initialize Anthropic client with memory capabilities.
        
        Args:
            api_key: Anthropic API key
            zl_api_key: 0Latency API key
            agent_id: Unique identifier for this agent
            zl_base_url: 0Latency API base URL (default: https://api.0latency.ai)
            recall_enabled: Whether to recall memories before each request (default: True)
            store_enabled: Whether to store conversations as memories (default: True)
            budget_tokens: Max tokens for memory context (default: 4000)
        """
        self.client = Anthropic(api_key=api_key)
        self.zl_api_key = zl_api_key
        self.agent_id = agent_id
        self.zl_base_url = zl_base_url.rstrip("/")
        self.recall_enabled = recall_enabled
        self.store_enabled = store_enabled
        self.budget_tokens = budget_tokens
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for 0Latency API calls"""
        return {
            "X-API-Key": self.zl_api_key,
            "Content-Type": "application/json",
        }
    
    def _recall_memories(self, conversation_context: str) -> Optional[str]:
        """
        Recall relevant memories for the given context.
        
        Args:
            conversation_context: The conversation context to find relevant memories for
            
        Returns:
            Memory context string or None if recall fails/disabled
        """
        if not self.recall_enabled:
            return None
            
        try:
            response = requests.post(
                f"{self.zl_base_url}/recall",
                headers=self._get_headers(),
                json={
                    "agent_id": self.agent_id,
                    "conversation_context": conversation_context,
                    "budget_tokens": self.budget_tokens,
                },
                timeout=5,
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("context_block", "")
            else:
                print(f"[ZeroLatency] Recall failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[ZeroLatency] Recall error: {e}")
            return None
    
    def _store_memory(self, human_message: str, assistant_message: str):
        """
        Store conversation turn as memory (non-blocking).
        
        Args:
            human_message: The user's message
            assistant_message: The assistant's response
        """
        if not self.store_enabled:
            return
            
        def _store_async():
            try:
                # Extract text content from messages
                facts = []
                
                # Add user message as fact
                if human_message:
                    facts.append({
                        "text": f"User said: {human_message}",
                        "category": "conversation",
                        "importance": 0.6,
                    })
                
                # Add assistant message as fact
                if assistant_message:
                    facts.append({
                        "text": f"Assistant said: {assistant_message}",
                        "category": "conversation",
                        "importance": 0.5,
                    })
                
                if facts:
                    requests.post(
                        f"{self.zl_base_url}/memories/seed",
                        headers=self._get_headers(),
                        json={
                            "agent_id": self.agent_id,
                            "facts": facts,
                        },
                        timeout=10,
                    )
                    
            except Exception as e:
                print(f"[ZeroLatency] Store error: {e}")
        
        # Run storage in background thread
        thread = threading.Thread(target=_store_async, daemon=True)
        thread.start()
    
    def _extract_text_from_messages(self, messages: List[Dict[str, Any]]) -> str:
        """Extract text content from message list for context"""
        texts = []
        for msg in messages[-3:]:  # Last 3 messages for context
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str):
                texts.append(f"{role}: {content}")
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(f"{role}: {item.get('text', '')}")
        return "\n".join(texts)
    
    def _extract_assistant_text(self, response) -> str:
        """Extract text from assistant response"""
        try:
            if hasattr(response, "content") and response.content:
                texts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        texts.append(block.text)
                return " ".join(texts)
        except Exception:
            pass
        return ""
    
    class Messages:
        """Messages API with memory integration"""
        
        def __init__(self, wrapper):
            self.wrapper = wrapper
            
        def create(self, model: str, messages: List[Dict[str, Any]], **kwargs):
            """
            Create a message with automatic memory recall and storage.
            
            This is a drop-in replacement for anthropic.messages.create()
            """
            # Step 1: Recall relevant memories
            conversation_context = self.wrapper._extract_text_from_messages(messages)
            memory_context = self.wrapper._recall_memories(conversation_context)
            
            # Step 2: Inject memories as system context
            if memory_context:
                system_content = kwargs.get("system", "")
                if system_content:
                    system_content = f"{memory_context}\n\n{system_content}"
                else:
                    system_content = memory_context
                kwargs["system"] = system_content
            
            # Step 3: Call the actual Anthropic API
            response = self.wrapper.client.messages.create(
                model=model,
                messages=messages,
                **kwargs
            )
            
            # Step 4: Store conversation turn (non-blocking)
            user_message = ""
            if messages and messages[-1].get("role") == "user":
                content = messages[-1].get("content", "")
                if isinstance(content, str):
                    user_message = content
                elif isinstance(content, list):
                    user_message = " ".join([
                        item.get("text", "") 
                        for item in content 
                        if isinstance(item, dict) and item.get("type") == "text"
                    ])
            
            assistant_message = self.wrapper._extract_assistant_text(response)
            self.wrapper._store_memory(user_message, assistant_message)
            
            # Step 5: Return response unmodified
            return response
    
    @property
    def messages(self):
        """Access to messages API"""
        return self.Messages(self)
