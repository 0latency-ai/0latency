"""
Zero Latency Memory SDK — Python Client

Usage:
    from zerolatency import ZeroLatencyClient
    
    client = ZeroLatencyClient(api_key="zl_live_...")
    
    # Extract memories from a conversation turn
    result = client.extract(
        agent_id="my-agent",
        human_message="My name is Justin and I run PFL Academy",
        agent_message="Nice to meet you, Justin!"
    )
    
    # Recall relevant memories
    context = client.recall(
        agent_id="my-agent",
        conversation_context="Tell me about the user's business"
    )
    
    # List memories
    memories = client.list_memories(agent_id="my-agent")
    
    # Search memories
    results = client.search(agent_id="my-agent", query="business")
    
    # Batch extract
    results = client.batch_extract([
        {"agent_id": "my-agent", "human_message": "...", "agent_message": "..."},
        {"agent_id": "my-agent", "human_message": "...", "agent_message": "..."},
    ])
    
    # Graph: get entity subgraph
    graph = client.get_entity_graph(agent_id="my-agent", entity="Justin")
    
    # Memory history
    history = client.get_memory_history(memory_id="...")
"""

import json
import time
from typing import Optional, Union
import requests


class ZeroLatencyError(Exception):
    """Base exception for Zero Latency SDK."""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(ZeroLatencyError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ZeroLatencyClient:
    """Python SDK for Zero Latency Memory API."""
    
    def __init__(self, api_key: str, base_url: str = "https://164.90.156.169/api",
                 timeout: int = 30, max_retries: int = 3):
        """
        Initialize the client.
        
        Args:
            api_key: Your Zero Latency API key (zl_live_...)
            base_url: API base URL
            timeout: Request timeout in seconds
            max_retries: Max retries on transient failures
        """
        if not api_key.startswith("zl_live_"):
            raise ValueError("API key must start with 'zl_live_'")
        
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        })
    
    def _request(self, method: str, path: str, json_data: dict = None,
                 params: dict = None) -> dict:
        """Make an API request with retry logic."""
        url = f"{self.base_url}{path}"
        
        for attempt in range(self.max_retries):
            try:
                resp = self._session.request(
                    method, url, json=json_data, params=params,
                    timeout=self.timeout, verify=False  # Self-signed cert
                )
                
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    if attempt < self.max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after}s",
                        retry_after=retry_after
                    )
                
                if resp.status_code >= 400:
                    error_detail = resp.json().get("detail", resp.text) if resp.text else "Unknown error"
                    raise ZeroLatencyError(
                        f"API error ({resp.status_code}): {error_detail}",
                        status_code=resp.status_code,
                        response=resp.json() if resp.text else None
                    )
                
                return resp.json()
                
            except requests.exceptions.ConnectionError:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ZeroLatencyError("Connection failed after retries")
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                    continue
                raise ZeroLatencyError("Request timed out")
        
        raise ZeroLatencyError("Max retries exceeded")
    
    # --- Core Memory Operations ---
    
    def extract(self, agent_id: str, human_message: str, agent_message: str,
                session_key: str = None, turn_id: str = None) -> dict:
        """Extract memories from a conversation turn."""
        return self._request("POST", "/extract", {
            "agent_id": agent_id,
            "human_message": human_message,
            "agent_message": agent_message,
            "session_key": session_key,
            "turn_id": turn_id,
        })
    
    def recall(self, agent_id: str, conversation_context: str,
               budget_tokens: int = 4000) -> dict:
        """Recall relevant memories for a conversation."""
        return self._request("POST", "/recall", {
            "agent_id": agent_id,
            "conversation_context": conversation_context,
            "budget_tokens": budget_tokens,
        })
    
    def list_memories(self, agent_id: str, limit: int = 50, offset: int = 0,
                      memory_type: str = None) -> list[dict]:
        """List memories with pagination."""
        params = {"agent_id": agent_id, "limit": limit, "offset": offset}
        if memory_type:
            params["memory_type"] = memory_type
        return self._request("GET", "/memories", params=params)
    
    def search(self, agent_id: str, query: str, limit: int = 20) -> list[dict]:
        """Search memories by keyword."""
        return self._request("GET", "/memories/search", params={
            "agent_id": agent_id, "q": query, "limit": limit
        })
    
    def delete_memory(self, memory_id: str) -> dict:
        """Delete a specific memory."""
        return self._request("DELETE", f"/memories/{memory_id}")
    
    def export_memories(self, agent_id: str) -> dict:
        """Export all memories for an agent."""
        return self._request("GET", "/memories/export", params={"agent_id": agent_id})
    
    # --- Batch Operations ---
    
    def batch_extract(self, turns: list[dict]) -> dict:
        """
        Extract memories from multiple turns in one request.
        
        Args:
            turns: List of dicts with agent_id, human_message, agent_message
        """
        return self._request("POST", "/extract/batch", {"turns": turns})
    
    def batch_delete(self, memory_ids: list[str]) -> dict:
        """Delete multiple memories in one request."""
        return self._request("POST", "/memories/batch-delete", {"memory_ids": memory_ids})
    
    def batch_search(self, agent_id: str, queries: list[str], limit_per_query: int = 10) -> dict:
        """Search with multiple queries in one request."""
        return self._request("POST", "/memories/batch-search", {
            "agent_id": agent_id,
            "queries": queries,
            "limit_per_query": limit_per_query,
        })
    
    # --- Graph Memory ---
    
    def get_entity_graph(self, agent_id: str, entity: str, depth: int = 2) -> dict:
        """Get the knowledge graph around an entity."""
        return self._request("GET", "/graph/entity", params={
            "agent_id": agent_id, "entity": entity, "depth": depth
        })
    
    def list_entities(self, agent_id: str, entity_type: str = None,
                      limit: int = 50) -> list[dict]:
        """List known entities."""
        params = {"agent_id": agent_id, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type
        return self._request("GET", "/graph/entities", params=params)
    
    def get_entity_memories(self, agent_id: str, entity: str,
                            limit: int = 20) -> list[dict]:
        """Get all memories for an entity."""
        return self._request("GET", "/graph/entity/memories", params={
            "agent_id": agent_id, "entity": entity, "limit": limit
        })
    
    def find_path(self, agent_id: str, source: str, target: str,
                  max_depth: int = 4) -> list[str]:
        """Find path between two entities."""
        return self._request("GET", "/graph/path", params={
            "agent_id": agent_id, "source": source, "target": target,
            "max_depth": max_depth
        })
    
    # --- Memory History ---
    
    def get_memory_history(self, memory_id: str) -> dict:
        """Get version history for a memory."""
        return self._request("GET", f"/memories/{memory_id}/history")
    
    # --- Webhooks ---
    
    def create_webhook(self, url: str, events: list[str],
                       secret: str = None) -> dict:
        """Register a webhook."""
        return self._request("POST", "/webhooks", {
            "url": url, "events": events, "secret": secret
        })
    
    def list_webhooks(self) -> list[dict]:
        """List all webhooks."""
        return self._request("GET", "/webhooks")
    
    def delete_webhook(self, webhook_id: str) -> dict:
        """Delete a webhook."""
        return self._request("DELETE", f"/webhooks/{webhook_id}")
    
    # --- Custom Criteria ---
    
    def create_criteria(self, agent_id: str, name: str, weight: float = 0.5,
                        description: str = None) -> dict:
        """Create a custom recall criteria."""
        return self._request("POST", "/criteria", {
            "agent_id": agent_id, "name": name, "weight": weight,
            "description": description,
        })
    
    def list_criteria(self, agent_id: str) -> list[dict]:
        """List criteria for an agent."""
        return self._request("GET", "/criteria", params={"agent_id": agent_id})
    
    # --- Schemas ---
    
    def create_schema(self, name: str, schema: dict,
                      extraction_prompt: str = None) -> dict:
        """Create a custom extraction schema."""
        return self._request("POST", "/schemas", {
            "name": name, "schema": schema, "extraction_prompt": extraction_prompt
        })
    
    def list_schemas(self) -> list[dict]:
        """List all schemas."""
        return self._request("GET", "/schemas")
    
    # --- Org Memory ---
    
    def store_org_memory(self, headline: str, context: str = None,
                         memory_type: str = "fact", importance: float = 0.5) -> dict:
        """Store a memory at the organization level."""
        return self._request("POST", "/org/memories", {
            "headline": headline, "context": context,
            "memory_type": memory_type, "importance": importance,
        })
    
    def recall_org_memories(self, query: str, limit: int = 10) -> list[dict]:
        """Recall org-level memories."""
        return self._request("GET", "/org/memories/recall", params={
            "q": query, "limit": limit
        })
    
    def promote_to_org(self, memory_id: str) -> dict:
        """Promote an agent memory to org level."""
        return self._request("POST", f"/memories/{memory_id}/promote")
    
    # --- Utility ---
    
    def health(self) -> dict:
        """Check API health (no auth required)."""
        resp = requests.get(f"{self.base_url}/health", timeout=5, verify=False)
        return resp.json()
    
    def tenant_info(self) -> dict:
        """Get current tenant info."""
        return self._request("GET", "/tenant-info")
    
    def usage(self, days: int = 7) -> dict:
        """Get API usage stats."""
        return self._request("GET", "/usage", params={"days": days})
