# 0Latency Examples

Basic usage examples showing how to integrate 0Latency with popular AI providers.

## Installation

```bash
pip install zerolatency
```

## Examples

### Anthropic Claude
[`anthropic_example.py`](./anthropic_example.py) - Store and recall context with Claude

### OpenAI GPT-4
[`openai_example.py`](./openai_example.py) - Persistent memory for GPT-4 conversations

### Google Gemini
[`gemini_example.py`](./gemini_example.py) - Use 0Latency with Gemini Pro

## Basic Pattern

All examples follow the same pattern:

1. **Initialize** both 0Latency and your AI provider
2. **Store** memories: `memory.store(agent_id, content)`
3. **Recall** context: `context = memory.recall(agent_id, query)`
4. **Use** recalled context in your AI prompts
5. **Store** the interaction for future recall

## Get Your API Key

Sign up at [0latency.ai](https://0latency.ai) to get your free API key.

## Documentation

- [Full API Docs](https://0latency.ai/docs)
- [Python SDK](../python/)
- [TypeScript SDK](../typescript/)
- [MCP Server](../mcp/)
