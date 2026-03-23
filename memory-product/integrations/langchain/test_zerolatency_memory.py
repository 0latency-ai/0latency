"""Tests for ZeroLatencyMemory LangChain integration."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from zerolatency_memory import ZeroLatencyMemory


class TestZeroLatencyMemory(unittest.TestCase):
    """Unit tests for ZeroLatencyMemory."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        with patch("zerolatency_memory.Memory") as MockMemory:
            self.mock_client = MagicMock()
            MockMemory.return_value = self.mock_client
            self.memory = ZeroLatencyMemory(api_key="zl_test_fake_key")

    def test_memory_variables(self) -> None:
        """memory_variables returns the configured key."""
        self.assertEqual(self.memory.memory_variables, ["history"])

    def test_memory_variables_custom_key(self) -> None:
        """memory_variables respects custom memory_key."""
        with patch("zerolatency_memory.Memory"):
            mem = ZeroLatencyMemory(api_key="zl_test_x", memory_key="context")
        self.assertEqual(mem.memory_variables, ["context"])

    def test_save_context(self) -> None:
        """save_context calls client.add with formatted content."""
        self.memory.save_context(
            {"input": "My name is Alice"},
            {"output": "Nice to meet you, Alice!"},
        )
        self.mock_client.add.assert_called_once_with(
            content="Human: My name is Alice\nAI: Nice to meet you, Alice!",
            agent_id=None,
            metadata={"source": "langchain"},
        )

    def test_save_context_with_agent_id(self) -> None:
        """save_context passes agent_id when configured."""
        with patch("zerolatency_memory.Memory") as MockMemory:
            mock = MagicMock()
            MockMemory.return_value = mock
            mem = ZeroLatencyMemory(api_key="zl_test_x", agent_id="agent-1")
        mem.save_context({"input": "hi"}, {"output": "hello"})
        mock.add.assert_called_once_with(
            content="Human: hi\nAI: hello",
            agent_id="agent-1",
            metadata={"source": "langchain"},
        )

    def test_load_memory_variables(self) -> None:
        """load_memory_variables returns recalled content as string."""
        self.mock_client.recall.return_value = {
            "memories": [
                {"content": "User prefers Python", "relevance": 0.95},
                {"content": "User hates mornings", "relevance": 0.82},
            ]
        }
        result = self.memory.load_memory_variables({"input": "schedule a meeting"})
        self.assertEqual(
            result,
            {"history": "User prefers Python\nUser hates mornings"},
        )
        self.mock_client.recall.assert_called_once_with(
            query="schedule a meeting",
            agent_id=None,
            limit=10,
        )

    def test_load_memory_variables_as_list(self) -> None:
        """load_memory_variables returns list when configured."""
        with patch("zerolatency_memory.Memory") as MockMemory:
            mock = MagicMock()
            MockMemory.return_value = mock
            mem = ZeroLatencyMemory(
                api_key="zl_test_x", return_memories_as_list=True
            )
        mock.recall.return_value = {
            "memories": [
                {"content": "Fact A"},
                {"content": "Fact B"},
            ]
        }
        result = mem.load_memory_variables({"input": "tell me"})
        self.assertEqual(result, {"history": ["Fact A", "Fact B"]})

    def test_load_memory_variables_empty(self) -> None:
        """load_memory_variables handles empty input gracefully."""
        result = self.memory.load_memory_variables({})
        self.assertEqual(result, {"history": ""})

    def test_load_memory_no_results(self) -> None:
        """load_memory_variables handles no recall results."""
        self.mock_client.recall.return_value = {"memories": []}
        result = self.memory.load_memory_variables({"input": "something"})
        self.assertEqual(result, {"history": ""})

    def test_clear_is_noop(self) -> None:
        """clear() does not raise and does not call the API."""
        self.memory.clear()  # Should not raise

    def test_input_key_extraction(self) -> None:
        """_get_input_value auto-detects input key."""
        self.assertEqual(
            self.memory._get_input_value({"input": "hello"}), "hello"
        )
        self.assertEqual(
            self.memory._get_input_value({"human_input": "hi"}), "hi"
        )
        self.assertEqual(
            self.memory._get_input_value({"question": "what?"}), "what?"
        )

    def test_explicit_input_key(self) -> None:
        """Explicit input_key overrides auto-detection."""
        with patch("zerolatency_memory.Memory"):
            mem = ZeroLatencyMemory(api_key="zl_test_x", input_key="query")
        self.assertEqual(
            mem._get_input_value({"query": "find it", "other": "ignore"}),
            "find it",
        )


if __name__ == "__main__":
    unittest.main()
