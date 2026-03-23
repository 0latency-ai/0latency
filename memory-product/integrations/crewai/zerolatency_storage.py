"""CrewAI memory storage backend for 0Latency.

Provides `ZeroLatencyStorage`, a CrewAI-compatible storage backend that
persists crew memories to the 0Latency API for cross-session recall.

Usage::

    from zerolatency_storage import ZeroLatencyStorage

    storage = ZeroLatencyStorage(api_key="zl_live_...")
    storage.save("user_prefs", "User prefers concise answers")
    results = storage.search("What does the user prefer?")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from zerolatency import Memory


class ZeroLatencyStorage:
    """CrewAI-compatible storage backend powered by 0Latency.

    This class implements the storage interface expected by CrewAI's memory
    system, routing all memory operations through the 0Latency API for
    persistent, cross-session recall with sub-100ms latency.

    Compatible with CrewAI's ``ShortTermMemory``, ``LongTermMemory``,
    and ``EntityMemory`` when used as a custom storage backend.

    Args:
        api_key: Your 0Latency API key.
        agent_id: Optional agent identifier for scoping memories.
        type: Memory type label (e.g. "short_term", "long_term", "entity").
        base_url: Override the API base URL.
    """

    def __init__(
        self,
        api_key: str,
        agent_id: Optional[str] = None,
        type: str = "general",
        base_url: Optional[str] = None,
    ) -> None:
        self.type = type
        self.agent_id = agent_id
        self._client = Memory(
            api_key=api_key,
            base_url=base_url,
        )

    def save(
        self,
        key: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save a memory to 0Latency.

        Args:
            key: A descriptive key or identifier for the memory.
            value: The text content to store.
            metadata: Optional additional metadata to attach.
        """
        meta = {
            "source": "crewai",
            "memory_type": self.type,
            "key": key,
        }
        if metadata:
            meta.update(metadata)

        self._client.add(
            content=value,
            agent_id=self.agent_id,
            metadata=meta,
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search for relevant memories.

        Args:
            query: Natural-language search query.
            limit: Maximum number of results to return.
            score_threshold: Minimum relevance score (0.0–1.0).

        Returns:
            List of memory dicts with ``content``, ``relevance``, and ``metadata``.
        """
        result = self._client.recall(
            query=query,
            agent_id=self.agent_id,
            limit=limit,
        )

        memories = result.get("memories", [])

        if score_threshold > 0:
            memories = [
                m for m in memories
                if m.get("relevance", 0) >= score_threshold
            ]

        return [
            {
                "context": m.get("content", ""),
                "score": m.get("relevance", 0.0),
                "metadata": m.get("metadata", {}),
            }
            for m in memories
        ]

    def reset(self) -> None:
        """Reset is a no-op for 0Latency.

        0Latency manages memory lifecycle automatically with temporal
        decay and reinforcement. To delete specific memories, use the
        0Latency API directly.
        """
        pass


class ZeroLatencyShortTermStorage(ZeroLatencyStorage):
    """Short-term memory storage for CrewAI.

    Pre-configured with ``type="short_term"`` for use with
    ``crewai.memory.ShortTermMemory``.
    """

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        super().__init__(api_key=api_key, type="short_term", **kwargs)


class ZeroLatencyLongTermStorage(ZeroLatencyStorage):
    """Long-term memory storage for CrewAI.

    Pre-configured with ``type="long_term"`` for use with
    ``crewai.memory.LongTermMemory``.
    """

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        super().__init__(api_key=api_key, type="long_term", **kwargs)


class ZeroLatencyEntityStorage(ZeroLatencyStorage):
    """Entity memory storage for CrewAI.

    Pre-configured with ``type="entity"`` for use with
    ``crewai.memory.EntityMemory``.
    """

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        super().__init__(api_key=api_key, type="entity", **kwargs)
