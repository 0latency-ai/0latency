"""OpenAI client with 0Latency memory integration"""

import json
import threading
from typing import Any, Dict, List, Optional
import requests
from openai import OpenAI


class OpenAIWithMemory:
    """Drop-in replacement for OpenAI client with automatic memory storage and recall"""
    
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
        Initialize OpenAI client with memory capabilities.
        
        Args:
            api_key: OpenAI API key
            zl_api_key: 0Latency API key
            agent_id: Unique identifier for this agent
            zl_base_url: 0Latency API base URL (default: https://api.0latency.ai)
            recall_enabled: Whether to recall memories before each request (default: True)
            store_enabled: Whether to store conversations as memories (default: True)
            budget_tokens: Max tokens for memory context (default: 4000)
        """
        self.client = OpenAI(api_key=api_key)
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
                facts = []
                
                if human_message:
                    facts.append({
                        "text": f"User said: {human_message}",
                        "category": "conversation",
                        "importance": 0.6,
                    })
                
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
        return "\n".join(texts)
    
    class Chat:
        """Chat API with memory integration"""
        
        def __init__(self, wrapper):
            self.wrapper = wrapper
            
        class Completions:
            """Completions API with memory integration"""
            
            def __init__(self, wrapper):
                self.wrapper = wrapper
                
            def create(self, model: str, messages: List[Dict[str, Any]], **kwargs):
                """
                Create a chat completion with automatic memory recall and storage.
                
                This is a drop-in replacement for openai.chat.completions.create()
                """
                # Step 1: Recall relevant memories
                conversation_context = self.wrapper._extract_text_from_messages(messages)
                memory_context = self.wrapper._recall_memories(conversation_context)
                
                # Step 2: Inject memories as system message
                modified_messages = messages.copy()
                if memory_context:
                    # Check if there's already a system message
                    has_system = any(msg.get("role") == "system" for msg in modified_messages)
                    
                    if has_system:
                        # Prepend to existing system message
                        for msg in modified_messages:
                            if msg.get("role") == "system":
                                msg["content"] = f"{memory_context}\n\n{msg['content']}"
                                break
                    else:
                        # Add new system message at the beginning
                        modified_messages.insert(0, {
                            "role": "system",
                            "content": memory_context
                        })
                
                # Step 3: Call the actual OpenAI API
                response = self.wrapper.client.chat.completions.create(
                    model=model,
                    messages=modified_messages,
                    **kwargs
                )
                
                # Step 4: Store conversation turn (non-blocking)
                user_message = ""
                if messages and messages[-1].get("role") == "user":
                    user_message = str(messages[-1].get("content", ""))
                
                assistant_message = ""
                if response.choices and response.choices[0].message:
                    assistant_message = response.choices[0].message.content or ""
                
                self.wrapper._store_memory(user_message, assistant_message)
                
                # Step 5: Return response unmodified
                return response
        
        @property
        def completions(self):
            """Access to completions API"""
            return self.Completions(self.wrapper)
    
    @property
    def chat(self):
        """Access to chat API"""
        return self.Chat(self)
