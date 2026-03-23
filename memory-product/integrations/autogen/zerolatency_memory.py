"""AutoGen memory integration for 0Latency.

Provides `ZeroLatencyMemory` for use with AutoGen's Teachable agents and
memory-augmented conversation patterns. Gives agents persistent, cross-session
memory with sub-100ms recall.

Usage::

    from zerolatency_memory import ZeroLatencyMemory

    memory = ZeroLatencyMemory(api_key="zl_live_...")
    memory.add("User prefers Python for backend work")
    results = memory.query("What languages does the user know?")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from zerolatency import Memory


class ZeroLatencyMemory:
    """Persistent memory module for AutoGen agents via 0Latency.

    This class provides a memory interface compatible with AutoGen's
    teachability and memory augmentation patterns. It can be used to:

    - Store facts learned during conversations
    - Recall relevant context before generating responses
    - Build persistent agent knowledge across sessions

    Works with ``autogen.ConversableAgent``, ``autogen.AssistantAgent``,
    and the Teachability capability.

    Args:
        api_key: Your 0Latency API key.
        agent_id: Optional agent identifier for scoping memories.
        recall_threshold: Minimum relevance score for recall results (0.0–1.0).
        max_recall: Maximum number of memories to retrieve per query.
        base_url: Override the API base URL.
        auto_learn: If True, automatically extract and store facts from
            conversation messages.
    """

    def __init__(
        self,
        api_key: str,
        agent_id: Optional[str] = None,
        recall_threshold: float = 0.5,
        max_recall: int = 5,
        base_url: Optional[str] = None,
        auto_learn: bool = True,
    ) -> None:
        self.agent_id = agent_id
        self.recall_threshold = recall_threshold
        self.max_recall = max_recall
        self.auto_learn = auto_learn
        self._client = Memory(
            api_key=api_key,
            base_url=base_url,
        )

    # -- Core API ------------------------------------------------------------

    def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store a fact or piece of knowledge.

        Args:
            content: The text content to remember.
            metadata: Optional metadata to attach.

        Returns:
            API response confirming storage.
        """
        meta = {"source": "autogen"}
        if metadata:
            meta.update(metadata)

        return self._client.add(
            content=content,
            agent_id=self.agent_id,
            metadata=meta,
        )

    def query(
        self,
        question: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Recall relevant memories for a question or context.

        Args:
            question: Natural-language query to search memories.
            limit: Override the default max_recall for this query.

        Returns:
            List of relevant memory dicts with ``content`` and ``relevance``.
        """
        result = self._client.recall(
            query=question,
            agent_id=self.agent_id,
            limit=limit or self.max_recall,
        )

        memories = result.get("memories", [])
        return [
            m for m in memories
            if m.get("relevance", 0) >= self.recall_threshold
        ]

    def get_context(self, question: str) -> str:
        """Get formatted context string for injection into prompts.

        Args:
            question: The question or topic to recall context for.

        Returns:
            A formatted string of relevant memories, or empty string.
        """
        memories = self.query(question)
        if not memories:
            return ""

        lines = [f"- {m['content']}" for m in memories if m.get("content")]
        return "Relevant context from memory:\n" + "\n".join(lines)

    # -- Conversation Processing ---------------------------------------------

    def process_message(
        self,
        message: str,
        role: str = "user",
    ) -> None:
        """Process a conversation message for memory storage.

        If ``auto_learn`` is enabled, stores the message as a memory.
        Useful as a hook in AutoGen's message processing pipeline.

        Args:
            message: The message text.
            role: The role of the sender ("user", "assistant", etc.).
        """
        if not self.auto_learn:
            return

        self._client.add(
            content=f"[{role}] {message}",
            agent_id=self.agent_id,
            metadata={"source": "autogen", "role": role},
        )

    def process_conversation(
        self,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Extract memories from a full conversation via async extraction.

        Uses 0Latency's extraction endpoint to analyze a conversation
        and automatically identify and store relevant facts.

        Args:
            messages: List of message dicts with "role" and "content" keys.

        Returns:
            Extraction job info with ``job_id`` for status polling.
        """
        return self._client.extract(
            conversation=messages,
            agent_id=self.agent_id,
        )

    # -- AutoGen Integration Helpers -----------------------------------------

    def augment_system_message(
        self,
        system_message: str,
        context_query: str,
    ) -> str:
        """Augment a system message with recalled context.

        Retrieves relevant memories and appends them to the system message
        for context-aware responses.

        Args:
            system_message: The original system message.
            context_query: Query to recall relevant memories.

        Returns:
            The system message with appended memory context.
        """
        context = self.get_context(context_query)
        if not context:
            return system_message

        return f"{system_message}\n\n{context}"

    def create_teachable_hook(self):
        """Create a message hook function for use with AutoGen agents.

        Returns a callable that can be registered with
        ``agent.register_hook("process_last_received_message", hook)``.

        Returns:
            A hook function that augments messages with memory context.
        """
        memory = self

        def hook(message: str) -> str:
            context = memory.get_context(message)
            if context:
                return f"{context}\n\n{message}"
            return message

        return hook

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._client.close()

    def __enter__(self) -> ZeroLatencyMemory:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
