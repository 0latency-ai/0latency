# 0Latency Integration Examples

Working examples showing how to integrate 0Latency memory with popular agent frameworks.

## 🚀 Quick Start

All examples require a 0Latency API key:

```bash
export ZERO_LATENCY_API_KEY="your_api_key_here"
```

Most also need an OpenAI API key for the LLM:

```bash
export OPENAI_API_KEY="your_openai_key_here"
```

## 📚 Examples

### 1. Basic Example (`basic_example.py`)

**Requirements:** None (just the SDK)

```bash
pip install zero-latency
python basic_example.py
```

Simple script demonstrating:
- Extracting memories from conversations
- Recalling relevant memories
- Searching by keyword
- Seeding bulk facts
- Viewing entities and sentiment

**Perfect for:** Understanding core API concepts

---

### 2. LangChain Integration (`langchain_example.py`)

**Requirements:** LangChain, OpenAI

```bash
pip install zero-latency langchain langchain-openai
python langchain_example.py
```

Shows:
- Custom LangChain memory class using 0Latency
- Automatic context loading before each turn
- Persistent memory across sessions
- Integration with LangChain agents and tools

**Perfect for:** LangChain users wanting long-term memory

---

### 3. CrewAI Integration (`crewai_example.py`)

**Requirements:** CrewAI, LangChain, OpenAI

```bash
pip install zero-latency crewai langchain-openai
python crewai_example.py
```

Shows:
- Memory-enhanced CrewAI agents
- Context recall before task execution
- Storing research and outputs
- Multi-agent memory coordination

**Perfect for:** CrewAI users building research/writing workflows

---

### 4. AutoGen Integration (`autogen_example.py`)

**Requirements:** AutoGen (pyautogen)

```bash
pip install zero-latency pyautogen
python autogen_example.py
```

Shows:
- Custom AssistantAgent with memory
- Automatic memory recall during conversations
- Storing conversation history
- Multi-turn context preservation

**Perfect for:** AutoGen users building conversational agents

---

### 5. Bulk Import (`bulk_import.py`)

**Requirements:** None (just the SDK)

```bash
pip install zero-latency
python bulk_import.py
```

Shows:
- Importing text files and JSON
- Chunking large documents
- Batch seeding for performance
- Post-import consolidation

**Perfect for:** Seeding agents with knowledge bases, docs, or historical data

---

## 🎯 Which Example Should I Use?

| If you're using... | Start with... |
|---|---|
| LangChain agents | `langchain_example.py` |
| CrewAI teams | `crewai_example.py` |
| Microsoft AutoGen | `autogen_example.py` |
| Custom Python agent | `basic_example.py` |
| Importing existing data | `bulk_import.py` |
| Just learning 0Latency | `basic_example.py` |

## 🔑 Getting an API Key

1. Sign up at [0latency.ai](https://0latency.ai)
2. Create a new API key in your dashboard
3. Set as environment variable or pass to SDK

## 📖 Documentation

Full API documentation: [docs.0latency.ai](https://docs.0latency.ai)

## 💡 Tips

- **Start simple**: Run `basic_example.py` first to understand core concepts
- **Agent IDs**: Use descriptive agent IDs like "customer-support-bot" or "research-assistant"
- **Recall limits**: Start with `limit=5` for recall, adjust based on context window
- **Consolidation**: Run consolidation after bulk imports or every ~1000 memories
- **Error handling**: All examples include proper error handling - copy the patterns

## 🐛 Troubleshooting

**"Authentication failed"**
- Check your API key is correct
- Ensure it's set as environment variable or passed to client

**"Module not found"**
- Install the required dependencies for that example
- Use a virtual environment to avoid conflicts

**"No memories found"**
- Agent IDs are case-sensitive
- Make sure you're using the same agent_id for extract and recall
- Check memories were successfully stored using `list_memories()`

**Rate limit errors**
- Batch operations when possible
- Add delays between rapid API calls
- Contact support if you need higher limits

## 🤝 Contributing

Found a bug or have an improvement? Open an issue or PR at:
https://github.com/0latency/python-sdk

## 📧 Support

Questions? Email justin@0latency.ai
