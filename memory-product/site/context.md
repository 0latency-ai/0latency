# 0Latency - AI Agent Memory API

## What is 0Latency?

0Latency is a specialized API service that provides **long-term memory storage and semantic recall** for AI agents. It solves the context window limitation problem by extracting, storing, and intelligently recalling memories from conversations.

**Core Problem:** AI agents lose context when conversations exceed their token limits or when sessions restart.

**Solution:** 0Latency extracts structured memories from conversation turns, stores them with semantic embeddings, and recalls relevant memories when needed.

## How It Works

### 1. Memory Extraction

Send conversation turns to the API. 0Latency extracts:
- **Facts** (user preferences, statements, decisions)
- **Entities** (people, places, concepts)
- **Relationships** (connections between entities)
- **Context** (temporal, emotional, situational metadata)

### 2. Semantic Storage

Memories are stored with:
- Vector embeddings for semantic search
- Entity graphs for relationship queries
- Version history for updates
- Importance scoring for prioritization

### 3. Intelligent Recall

When you need context, 0Latency:
- Performs semantic search across memories
- Ranks by relevance, recency, and importance
- Returns a formatted context block within your token budget
- Supports dynamic budget allocation

## Key Features

- **Async Processing** - Extract accepts instantly (202), processes in background
- **Tenant Isolation** - Each API key gets isolated memory storage
- **Knowledge Graphs** - Query entity relationships and paths
- **Custom Schemas** - Define domain-specific extraction patterns
- **Webhooks** - Real-time notifications for memory events
- **Organization Memory** - Share memories across multiple agents
- **Batch Operations** - Process multiple extractions or searches in one request
- **Version History** - Track memory changes over time
- **Rate Limiting** - Plan-based RPM limits (Free: 60, Pro: 300, Enterprise: custom)

## API Endpoints Summary

### Core Operations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/extract` | POST | Synchronous memory extraction (blocks until complete) |
| `/memories/extract` | POST | **Async extraction** (recommended) - accepts instantly |
| `/recall` | POST | Recall relevant memories for conversation context |
| `/memories` | GET | List memories for an agent (paginated) |
| `/memories/search` | GET | Keyword search across memories |
| `/memories/{id}` | PUT/DELETE | Update or delete a specific memory |

### Knowledge Graph

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/graph/entity` | GET | Get knowledge graph around an entity |
| `/graph/entities` | GET | List all known entities for an agent |
| `/graph/entity/memories` | GET | Get memories associated with an entity |
| `/graph/path` | GET | Find shortest path between two entities |

### Advanced Features

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/extract/batch` | POST | Extract from multiple conversation turns |
| `/memories/batch-search` | POST | Search with multiple queries at once |
| `/memories/batch-delete` | POST | Delete multiple memories |
| `/memories/export` | GET | Export all memories for an agent (JSON) |
| `/org/memories` | GET/POST | Shared organization-level memories |
| `/webhooks` | GET/POST | Manage webhook subscriptions |
| `/schemas` | GET/POST | Custom extraction schemas |
| `/criteria` | GET/POST | Custom recall scoring criteria |

### Health & Info

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check (no auth required) |
| `/tenant-info` | GET | Current tenant information |
| `/usage` | GET | API usage statistics |

## Authentication

All API requests (except `/health`) require an API key:

```
X-API-Key: your_api_key_here
```

Get your API key from the [dashboard](https://0latency.ai/dashboard.html) after signing up.

## Code Examples

### Python - Basic Extract & Recall

```python
import requests

API_BASE = "https://api.0latency.ai"
API_KEY = "your_api_key_here"
HEADERS = {"X-API-Key": API_KEY}

# Extract memory from a conversation turn
def extract_memory(agent_id, human_msg, agent_msg):
    response = requests.post(
        f"{API_BASE}/memories/extract",
        headers=HEADERS,
        json={
            "agent_id": agent_id,
            "content": f"Human: {human_msg}\nAssistant: {agent_msg}",
            "session_key": "session_123"
        }
    )
    return response.json()  # Returns {"job_id": "..."}

# Recall relevant memories
def recall_memories(agent_id, context, budget_tokens=4000):
    response = requests.post(
        f"{API_BASE}/recall",
        headers=HEADERS,
        json={
            "agent_id": agent_id,
            "conversation_context": context,
            "budget_tokens": budget_tokens
        }
    )
    result = response.json()
    return result["context_block"]  # Ready to inject into your prompt

# Usage
extract_memory("agent_1", "I love Thai food", "Great! I'll remember that.")
context = recall_memories("agent_1", "Where should we eat tonight?")
print(context)
```

### JavaScript/Node.js - Async Extract & Recall

```javascript
const axios = require('axios');

const API_BASE = 'https://api.0latency.ai';
const API_KEY = 'your_api_key_here';
const headers = { 'X-API-Key': API_KEY };

// Async extract (recommended)
async function extractMemory(agentId, humanMsg, agentMsg) {
  const response = await axios.post(
    `${API_BASE}/memories/extract`,
    {
      agent_id: agentId,
      content: `Human: ${humanMsg}\nAssistant: ${agentMsg}`,
      session_key: 'session_123'
    },
    { headers }
  );
  return response.data; // { job_id: "..." }
}

// Recall memories
async function recallMemories(agentId, context, budgetTokens = 4000) {
  const response = await axios.post(
    `${API_BASE}/recall`,
    {
      agent_id: agentId,
      conversation_context: context,
      budget_tokens: budgetTokens
    },
    { headers }
  );
  return response.data.context_block;
}

// Usage
(async () => {
  await extractMemory('agent_1', 'I prefer dark mode', 'Noted!');
  const context = await recallMemories('agent_1', 'What are my preferences?');
  console.log(context);
})();
```

### cURL - Quick Test

```bash
# Extract memory
curl -X POST https://api.0latency.ai/memories/extract \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test_agent",
    "content": "Human: I live in San Francisco\nAssistant: Great! I will remember that.",
    "session_key": "session_001"
  }'

# Recall memories
curl -X POST https://api.0latency.ai/recall \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test_agent",
    "conversation_context": "Where does the user live?",
    "budget_tokens": 2000
  }'
```

## Use Cases

### 1. **Personal AI Assistants**
Maintain long-term context about user preferences, habits, and history across sessions.

```python
# Before each response, inject recalled context
context = recall_memories(user_id, current_conversation)
prompt = f"{context}\n\n{current_conversation}\n\nAssistant:"
```

### 2. **Customer Support Bots**
Remember customer issues, preferences, and interaction history.

```python
# Extract from every support conversation
extract_memory(f"customer_{id}", customer_msg, agent_response)

# Recall when customer returns
history = recall_memories(f"customer_{id}", "What issues has this customer reported?")
```

### 3. **Multi-Agent Systems**
Share knowledge across specialized agents via organization memories.

```python
# Agent A stores insight
requests.post(f"{API_BASE}/org/memories", headers=HEADERS, json={
    "headline": "User prefers JSON responses over XML",
    "memory_type": "preference"
})

# Agent B recalls org-level knowledge
org_context = requests.get(
    f"{API_BASE}/org/memories/recall?q=response format preferences",
    headers=HEADERS
).json()
```

### 4. **Knowledge Bases**
Build queryable knowledge graphs from conversations.

```python
# Query entity relationships
graph = requests.get(
    f"{API_BASE}/graph/entity?agent_id=docs_agent&entity=API authentication&depth=2",
    headers=HEADERS
).json()
```

### 5. **Coding Agents**
Maintain project context, architecture decisions, and user coding style preferences.

```python
# Extract coding decisions
extract_memory("coding_agent", 
    "Use TypeScript for this project", 
    "Got it! I'll use TypeScript.")

# Recall before generating code
context = recall_memories("coding_agent", "Generate a new API endpoint")
```

## Integration Patterns

### Pattern 1: Extract-on-Response
Extract after every agent response:
```python
response = generate_response(user_message)
extract_memory(agent_id, user_message, response)  # Fire and forget
return response
```

### Pattern 2: Recall-Before-Prompt
Inject context before generating response:
```python
context = recall_memories(agent_id, conversation_history)
prompt = f"{context}\n\n{conversation_history}"
response = llm.complete(prompt)
```

### Pattern 3: Hybrid (Recommended)
Combine both for continuous learning:
```python
# 1. Recall relevant context
context = recall_memories(agent_id, user_message, budget_tokens=3000)

# 2. Generate response with context
prompt = f"{context}\n\nUser: {user_message}\nAssistant:"
response = llm.complete(prompt)

# 3. Extract memory from this turn (async, non-blocking)
extract_memory(agent_id, user_message, response)

return response
```

## Best Practices

1. **Use Async Extraction** - Prefer `/memories/extract` over `/extract` to avoid blocking your response pipeline
2. **Set Appropriate Budgets** - Start with 3000-4000 tokens for recall budget, adjust based on your model's context window
3. **Use Session Keys** - Group related conversation turns with consistent `session_key` values
4. **Agent ID Naming** - Use descriptive, hierarchical IDs: `user_{id}`, `customer_{id}`, `agent_{specialty}`
5. **Memory Types** - Leverage memory_type field: `fact`, `preference`, `decision`, `event`, `insight`
6. **Batch When Possible** - Use batch endpoints when processing multiple items
7. **Monitor Usage** - Check `/usage` endpoint regularly to track API consumption
8. **Export Regularly** - Use `/memories/export` for backups and data portability

## Rate Limits & Pricing

| Plan | Rate Limit | Memory Limit | Price |
|------|-----------|--------------|-------|
| Free | 60 RPM | 1,000 memories | $0/month |
| Pro | 300 RPM | 100,000 memories | $29/month |
| Scale | 1,000 RPM | 1M memories | $99/month |
| Enterprise | Custom | Unlimited | Contact sales |

## OpenAPI Specification

Full OpenAPI 3.0 spec available at: [https://0latency.ai/api-docs.json](https://0latency.ai/api-docs.json)

## Resources

- **Documentation**: [https://0latency.ai/docs/](https://0latency.ai/docs/)
- **Quick Start**: [https://0latency.ai/docs/quick-start.html](https://0latency.ai/docs/quick-start.html)
- **API Reference**: [https://0latency.ai/docs/api-reference.html](https://0latency.ai/docs/api-reference.html)
- **Examples**: [https://0latency.ai/docs/examples/](https://0latency.ai/docs/examples/)
- **Dashboard**: [https://0latency.ai/dashboard.html](https://0latency.ai/dashboard.html)
- **Support**: [https://0latency.ai/support.html](https://0latency.ai/support.html)

## Support

- **Email**: justin@0latency.ai
- **Documentation Issues**: Open an issue or contact support
- **Feature Requests**: support@0latency.ai

---

**Last Updated**: 2026-03-26
**API Version**: 0.1.0
**Base URL**: https://api.0latency.ai
