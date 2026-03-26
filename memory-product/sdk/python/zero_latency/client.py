"""
0Latency Python SDK Client
"""
import requests
from typing import Dict, List, Optional, Any


class ZeroLatencyError(Exception):
    """Base exception for 0Latency SDK errors."""
    pass


class AuthenticationError(ZeroLatencyError):
    """Raised when API authentication fails (401)."""
    pass


class ForbiddenError(ZeroLatencyError):
    """Raised when access is forbidden (403)."""
    pass


class ValidationError(ZeroLatencyError):
    """Raised when request validation fails (422)."""
    pass


class ServerError(ZeroLatencyError):
    """Raised when server encounters an error (500)."""
    pass


class ZeroLatencyClient:
    """
    Client for interacting with the 0Latency memory API.
    
    Args:
        api_key: Your 0Latency API key
        base_url: API base URL (default: https://api.0latency.ai)
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.0latency.ai"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
    
    def _handle_response(self, response: requests.Response) -> Any:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise AuthenticationError(f"Authentication failed: {response.text}")
        elif response.status_code == 403:
            raise ForbiddenError(f"Access forbidden: {response.text}")
        elif response.status_code == 422:
            raise ValidationError(f"Validation error: {response.text}")
        elif response.status_code >= 500:
            raise ServerError(f"Server error: {response.text}")
        else:
            raise ZeroLatencyError(f"Unexpected error ({response.status_code}): {response.text}")
    
    def extract(self, agent_id: str, human_message: str, agent_message: str) -> Dict:
        """
        Extract and store memories from a conversation turn.
        
        Args:
            agent_id: Unique identifier for the agent
            human_message: The human's message in the conversation
            agent_message: The agent's response
            
        Returns:
            dict: Response containing extracted memories and metadata
        """
        response = self.session.post(
            f"{self.base_url}/v1/memory/extract",
            json={
                "agent_id": agent_id,
                "human_message": human_message,
                "agent_message": agent_message
            }
        )
        return self._handle_response(response)
    
    def recall(self, agent_id: str, query: str, limit: int = 10) -> List[Dict]:
        """
        Recall relevant memories for a query using semantic search.
        
        Args:
            agent_id: Unique identifier for the agent
            query: Search query to find relevant memories
            limit: Maximum number of memories to return (default: 10)
            
        Returns:
            list: List of relevant memory objects
        """
        response = self.session.post(
            f"{self.base_url}/v1/memory/recall",
            json={
                "agent_id": agent_id,
                "query": query,
                "limit": limit
            }
        )
        return self._handle_response(response)
    
    def search(self, agent_id: str, q: str, limit: int = 20) -> List[Dict]:
        """
        Search memories by text (keyword-based search).
        
        Args:
            agent_id: Unique identifier for the agent
            q: Search query string
            limit: Maximum number of results (default: 20)
            
        Returns:
            list: List of matching memory objects
        """
        response = self.session.get(
            f"{self.base_url}/v1/memory/search",
            params={
                "agent_id": agent_id,
                "q": q,
                "limit": limit
            }
        )
        return self._handle_response(response)
    
    def list_memories(self, agent_id: str, limit: int = 50) -> List[Dict]:
        """
        List all memories for an agent.
        
        Args:
            agent_id: Unique identifier for the agent
            limit: Maximum number of memories to return (default: 50)
            
        Returns:
            list: List of memory objects
        """
        response = self.session.get(
            f"{self.base_url}/v1/memory",
            params={
                "agent_id": agent_id,
                "limit": limit
            }
        )
        return self._handle_response(response)
    
    def seed(self, agent_id: str, facts: List[str]) -> Dict:
        """
        Seed multiple facts at once (bulk import).
        
        Args:
            agent_id: Unique identifier for the agent
            facts: List of fact strings to store
            
        Returns:
            dict: Response containing created memory IDs and metadata
        """
        response = self.session.post(
            f"{self.base_url}/v1/memory/seed",
            json={
                "agent_id": agent_id,
                "facts": facts
            }
        )
        return self._handle_response(response)
    
    def get_graph(self, agent_id: str, memory_id: str, depth: int = 2) -> Dict:
        """
        Get memory graph traversal from a specific memory.
        
        Args:
            agent_id: Unique identifier for the agent
            memory_id: Starting memory ID for graph traversal
            depth: How many relationship hops to traverse (default: 2)
            
        Returns:
            dict: Graph structure with nodes and edges
        """
        response = self.session.get(
            f"{self.base_url}/v1/memory/{memory_id}/graph",
            params={
                "agent_id": agent_id,
                "depth": depth
            }
        )
        return self._handle_response(response)
    
    def get_entities(self, agent_id: str, limit: int = 50) -> List[Dict]:
        """
        List extracted entities for an agent.
        
        Args:
            agent_id: Unique identifier for the agent
            limit: Maximum number of entities to return (default: 50)
            
        Returns:
            list: List of entity objects with metadata
        """
        response = self.session.get(
            f"{self.base_url}/v1/memory/entities",
            params={
                "agent_id": agent_id,
                "limit": limit
            }
        )
        return self._handle_response(response)
    
    def get_sentiment_summary(self, agent_id: str) -> Dict:
        """
        Get sentiment breakdown for an agent's memories.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            dict: Sentiment statistics and distribution
        """
        response = self.session.get(
            f"{self.base_url}/v1/memory/sentiment",
            params={"agent_id": agent_id}
        )
        return self._handle_response(response)
    
    def consolidate(self, agent_id: str, auto_merge: bool = False) -> Dict:
        """
        Run consolidation pass to merge and deduplicate memories.
        
        Args:
            agent_id: Unique identifier for the agent
            auto_merge: Whether to automatically merge similar memories (default: False)
            
        Returns:
            dict: Consolidation results and statistics
        """
        response = self.session.post(
            f"{self.base_url}/v1/memory/consolidate",
            json={
                "agent_id": agent_id,
                "auto_merge": auto_merge
            }
        )
        return self._handle_response(response)
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a specific memory.
        
        Args:
            memory_id: ID of the memory to delete
            
        Returns:
            bool: True if deletion was successful
        """
        response = self.session.delete(
            f"{self.base_url}/v1/memory/{memory_id}"
        )
        self._handle_response(response)
        return True
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
