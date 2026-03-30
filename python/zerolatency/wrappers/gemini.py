"""Google Gemini client with 0Latency memory integration"""

import json
import threading
from typing import Any, Dict, List, Optional
import requests
import google.generativeai as genai


class GeminiWithMemory:
    """Drop-in replacement for Gemini client with automatic memory storage and recall"""
    
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
        Initialize Gemini client with memory capabilities.
        
        Args:
            api_key: Google AI API key
            zl_api_key: 0Latency API key
            agent_id: Unique identifier for this agent
            zl_base_url: 0Latency API base URL (default: https://api.0latency.ai)
            recall_enabled: Whether to recall memories before each request (default: True)
            store_enabled: Whether to store conversations as memories (default: True)
            budget_tokens: Max tokens for memory context (default: 4000)
        """
        genai.configure(api_key=api_key)
        self.api_key = api_key
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
    
    def GenerativeModel(self, model_name: str, **kwargs):
        """
        Create a generative model with memory integration.
        
        This is a drop-in replacement for genai.GenerativeModel()
        """
        return self._ModelWrapper(
            model_name=model_name,
            wrapper=self,
            **kwargs
        )
    
    class _ModelWrapper:
        """Wrapper for GenerativeModel with memory integration"""
        
        def __init__(self, model_name: str, wrapper, **kwargs):
            self.wrapper = wrapper
            self.model = genai.GenerativeModel(model_name, **kwargs)
            
        def generate_content(self, contents, **kwargs):
            """
            Generate content with automatic memory recall and storage.
            
            This is a drop-in replacement for model.generate_content()
            """
            # Step 1: Extract conversation context
            if isinstance(contents, str):
                conversation_context = contents
                user_message = contents
            elif isinstance(contents, list):
                conversation_context = " ".join([
                    str(item) for item in contents[-3:]
                ])
                user_message = str(contents[-1]) if contents else ""
            else:
                conversation_context = str(contents)
                user_message = conversation_context
            
            # Step 2: Recall relevant memories
            memory_context = self.wrapper._recall_memories(conversation_context)
            
            # Step 3: Inject memories into prompt
            modified_contents = contents
            if memory_context:
                if isinstance(contents, str):
                    modified_contents = f"{memory_context}\n\n{contents}"
                elif isinstance(contents, list):
                    # Prepend memory context to the list
                    modified_contents = [memory_context] + contents
            
            # Step 4: Call the actual Gemini API
            response = self.model.generate_content(modified_contents, **kwargs)
            
            # Step 5: Store conversation turn (non-blocking)
            assistant_message = ""
            if hasattr(response, "text"):
                assistant_message = response.text
            
            self.wrapper._store_memory(user_message, assistant_message)
            
            # Step 6: Return response unmodified
            return response
        
        def start_chat(self, **kwargs):
            """Start a chat session with memory integration"""
            return self._ChatWrapper(
                chat=self.model.start_chat(**kwargs),
                wrapper=self.wrapper
            )
        
        class _ChatWrapper:
            """Wrapper for chat sessions with memory integration"""
            
            def __init__(self, chat, wrapper):
                self.chat = chat
                self.wrapper = wrapper
                
            def send_message(self, message, **kwargs):
                """Send message with memory recall and storage"""
                # Recall memories
                memory_context = self.wrapper._recall_memories(str(message))
                
                # Inject memories
                modified_message = message
                if memory_context:
                    if isinstance(message, str):
                        modified_message = f"{memory_context}\n\n{message}"
                
                # Call actual API
                response = self.chat.send_message(modified_message, **kwargs)
                
                # Store conversation
                user_msg = str(message)
                assistant_msg = response.text if hasattr(response, "text") else ""
                self.wrapper._store_memory(user_msg, assistant_msg)
                
                return response
