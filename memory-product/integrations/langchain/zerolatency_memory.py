"""LangChain memory integration for 0Latency.

Provides `ZeroLatencyMemory`, a LangChain-compatible memory class that
persists conversation context to the 0Latency memory API for cross-session
recall with sub-100ms latency.

Usage::

    from zerolatency_memory import ZeroLatencyMemory

    memory = ZeroLatencyMemory(api_key="zl_live_...")
    memory.save_context(
        {"input": "My name is Alice"},
        {"output": "Nice to meet you, Alice!"},
    )
    memory.load_memory_variables({"input": "What's my name?"})
    # → {"history": "User prefers to be called Alice."}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.memory import BaseMemory
from pydantic import Field, PrivateAttr
from zerolatency import Memory


class ZeroLatencyMemory(BaseMemory):
    """LangChain memory backed by the 0Latency persistent memory API.

    This memory class stores conversation turns via 0Latency's ``add()``
    method and retrieves relevant context via ``recall()`` at query time.
    Memories persist across sessions, so your agent never forgets.

    Args:
        api_key: Your 0Latency API key (starts with ``zl_live_`` or ``zl_test_``).
        agent_id: Optional agent identifier for scoping memories.
        memory_key: Key used in the returned dict from ``load_memory_variables``.
        input_key: Key for the human input in ``save_context``.
        output_key: Key for the AI output in ``save_context``.
        recall_limit: Maximum number of memories to retrieve per query.
        base_url: Override the API base URL (default: ``https://api.0latency.ai``).
        return_memories_as_list: If True, return memories as a list of strings
            instead of a single concatenated string.
    """

    api_key: str
    agent_id: Optional[str] = None
    memory_key: str = "history"
    input_key: Optional[str] = None
    output_key: Optional[str] = None
    recall_limit: int = 10
    base_url: Optional[str] = None
    return_memories_as_list: bool = False

    _client: Memory = PrivateAttr()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = Memory(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    # -- BaseMemory interface ------------------------------------------------

    @property
    def memory_variables(self) -> List[str]:
        """Return the list of keys this memory provides."""
        return [self.memory_key]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Recall relevant memories for the given inputs.

        Sends the human input as a query to 0Latency's recall endpoint and
        returns matching memories formatted for the prompt.

        Args:
            inputs: Dictionary containing at least the human input.

        Returns:
            Dictionary with ``memory_key`` mapped to recalled context.
        """
        query = self._get_input_value(inputs)
        if not query:
            return {self.memory_key: [] if self.return_memories_as_list else ""}

        result = self._client.recall(
            query=query,
            agent_id=self.agent_id,
            limit=self.recall_limit,
        )

        memories = result.get("memories", [])
        contents = [m.get("content", "") for m in memories if m.get("content")]

        if self.return_memories_as_list:
            return {self.memory_key: contents}

        return {self.memory_key: "\n".join(contents)}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save a conversation turn to 0Latency.

        Combines the human input and AI output into a single memory entry
        and stores it via the 0Latency API.

        Args:
            inputs: The human inputs (e.g. ``{"input": "Hello"}``).
            outputs: The AI outputs (e.g. ``{"output": "Hi there!"}``).
        """
        input_val = self._get_input_value(inputs)
        output_val = self._get_output_value(outputs)

        content = f"Human: {input_val}\nAI: {output_val}"
        self._client.add(
            content=content,
            agent_id=self.agent_id,
            metadata={"source": "langchain"},
        )

    def clear(self) -> None:
        """Clear is a no-op for 0Latency.

        0Latency manages memory lifecycle (decay, reinforcement) automatically.
        To delete specific memories, use the 0Latency API directly.
        """
        pass

    # -- helpers -------------------------------------------------------------

    def _get_input_value(self, inputs: Dict[str, Any]) -> str:
        """Extract the human input value from the inputs dict."""
        if self.input_key:
            return str(inputs.get(self.input_key, ""))
        # Auto-detect: skip memory_key, use first remaining key
        candidates = {k: v for k, v in inputs.items() if k != self.memory_key}
        if len(candidates) == 1:
            return str(next(iter(candidates.values())))
        if "input" in candidates:
            return str(candidates["input"])
        if "human_input" in candidates:
            return str(candidates["human_input"])
        # Fall back to first value
        return str(next(iter(candidates.values()), ""))

    def _get_output_value(self, outputs: Dict[str, str]) -> str:
        """Extract the AI output value from the outputs dict."""
        if self.output_key:
            return str(outputs.get(self.output_key, ""))
        if len(outputs) == 1:
            return str(next(iter(outputs.values())))
        if "output" in outputs:
            return str(outputs["output"])
        if "response" in outputs:
            return str(outputs["response"])
        return str(next(iter(outputs.values()), ""))
