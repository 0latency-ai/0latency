# Zero Latency Memory 🧠

**Structured agent memory with zero-latency recall. Survives compaction.**

Zero Latency Memory provides instant, intelligent memory storage and recall for AI agents. Unlike traditional databases or flat files, it understands context, handles contradictions, and surfaces the most relevant memories automatically.

## The Problem

After context compaction, vanilla OpenClaw agents lose their memory:
- 📉 Forget previous decisions and facts
- 🔄 Need to be re-taught the same information
- ❌ Mix up details across conversations  
- 💸 Waste tokens re-establishing context

## The Solution

Zero Latency Memory automatically extracts, stores, and recalls structured memories:

- **🚀 Zero Latency**: Relevant context injected instantly on session start
- **🧠 Smart Extraction**: Auto-categorizes facts, preferences, decisions, tasks, relationships
- **🔍 Semantic Recall**: Vector similarity + importance scoring finds what matters
- **🛡️ Enterprise Ready**: Multi-tenant, authenticated API with rate limiting
- **✅ Self-Correcting**: Automatically handles contradictions and updates

## Quick Demo

```python
import requests

# 1. Extract memories from conversation
response = requests.post("https://164.90.156.169/api/extract", 
    headers={"X-API-Key": "zl_live_your_key"},
    json={
        "agent_id": "assistant_v1", 
        "human_message": "I live in San Francisco and work at OpenAI",
        "agent_message": "Thanks! I'll remember you're in SF and work at OpenAI."
    })
# → Stores 2 structured memories: location + workplace

# 2. Recall relevant context
response = requests.post("https://164.90.156.169/api/recall",
    headers={"X-API-Key": "zl_live_your_key"},
    json={
        "agent_id": "assistant_v1",
        "conversation_context": "User asking about coffee shops nearby"
    })
# → Returns: "User lives in San Francisco, works at OpenAI"
```

## Features

### 🔄 Automatic Memory Extraction

Every conversation turn is automatically processed to extract:

- **Facts**: Location, job, age, relationships
- **Preferences**: Favorite food, music, tools, styles  
- **Decisions**: Choices made, plans agreed upon
- **Tasks**: Action items, TODOs, reminders
- **Corrections**: Updates that supersede previous facts
- **Identity**: Core traits that never decay

### 🎯 Intelligent Recall

Memories are recalled using composite scoring:

- **Semantic Similarity** (40%): How related to current conversation?
- **Recency** (35%): How recently created or accessed?
- **Importance** (15%): How critical is this memory?
- **Access Frequency** (10%): How often is it referenced?

### 🏢 Production Ready

- **Multi-Tenant Architecture**: Secure isolation between users/organizations
- **API Authentication**: SHA-256 hashed API keys with rate limiting
- **Usage Tracking**: Monitor API calls, tokens, response times
- **Rate Limits**: Free (20/min), Pro (100/min), Enterprise (500/min)
- **Memory Limits**: Free (1K), Pro (50K), Enterprise (500K memories)

### 🧠 Advanced Memory Features

- **Contradiction Detection**: Automatically flags conflicting information
- **Cross-Agent Sharing**: Corrections propagate across agents in same tenant
- **Memory Decay**: Unused memories naturally fade over time
- **Reinforcement Learning**: Frequently accessed memories gain importance
- **Dynamic Budgeting**: Adapts recall context size based on conversation complexity

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Conversation   │───▶│  Memory Engine   │───▶│   Structured    │
│     Turn        │    │    Extraction    │    │    Storage      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Agent Context   │◀───│  Smart Recall    │◀───│   Vector DB     │
│  (RECALL.md)    │    │   Algorithm      │    │ (Postgres+PG)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Installation

### Option 1: OpenClaw Skill (Recommended)

```bash
# Install the memory-engine skill
openclaw skills install memory-engine

# Configure your API key  
export MEMORY_API_KEY="zl_live_your_key_here"

# Test the setup
cd skills/memory-engine/scripts
python3 api_health.py
```

### Option 2: Direct API Integration

```bash
pip install requests
export MEMORY_API_KEY="zl_live_your_key_here"
# See docs/QUICKSTART.md for code examples
```

## Usage

### Basic Memory Operations

```python
from memory_api import MemoryAPI

memory = MemoryAPI("zl_live_your_key")

# Extract memories from conversation
result = memory.extract(
    agent_id="assistant_v1",
    human_message="I'm planning a trip to Japan in March",
    agent_message="That sounds exciting! Spring is a beautiful time to visit Japan."
)

# Recall relevant context for new conversation
context = memory.recall(
    agent_id="assistant_v1", 
    conversation_context="User asking about travel recommendations"
)
print(context["context_block"])
# → "User planning trip to Japan in March. Interested in travel."

# List all memories
memories = memory.list_memories(agent_id="assistant_v1", limit=20)
for mem in memories:
    print(f"[{mem['memory_type']}] {mem['headline']}")
```

### OpenClaw Integration

With the skill installed, memories are automatically extracted from every conversation:

```bash
# Check memory health
python3 scripts/api_health.py

# List recent memories  
python3 scripts/list_memories.py thomas --limit 10

# Test full pipeline
python3 scripts/test_api.py
```

On session start, your agent automatically reads:
- `memory/RECALL.md` — Relevant memories for current context
- `memory/HANDOFF.md` — Session state from last conversation

## API Reference

### Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/api/extract` | POST | Extract memories from conversation |
| `/api/recall` | POST | Recall relevant memories |
| `/api/memories` | GET | List memories for agent |
| `/api/tenant-info` | GET | Get account information |
| `/docs` | GET | Interactive API documentation |

### Memory Types

- **`fact`**: General factual information
- **`preference`**: Personal likes/dislikes  
- **`decision`**: Choices and plans made
- **`task`**: Action items and TODOs
- **`correction`**: Updates to previous facts
- **`relationship`**: Information about people
- **`identity`**: Core traits (never decay)

See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for complete documentation.

## Pricing

| Plan | Requests/Min | Memory Limit | Price |
|------|-------------|--------------|--------|
| **Free** | 20 | 1,000 memories | $0 |
| **Pro** | 100 | 50,000 memories | $49/month |
| **Enterprise** | 500 | 500,000 memories | Contact us |

## Self-Hosted Deployment

Zero Latency Memory can be deployed on your own infrastructure:

- **Database**: PostgreSQL 14+ with pgvector extension
- **Backend**: FastAPI + Uvicorn + Nginx 
- **SSL**: Self-signed or Let's Encrypt certificates
- **Authentication**: API key management with admin endpoints

See [PHASE_B_BUILD.md](PHASE_B_BUILD.md) for deployment instructions.

## Examples & Use Cases

### 🎓 Educational Tutoring Agent

```python
# Student mentions struggling with calculus
memory.extract("tutor_agent", 
    "I'm having trouble with derivatives in calculus",
    "Let's work on derivatives step by step")

# Later session automatically recalls:
# "Student struggling with calculus derivatives, needs step-by-step help"
```

### 💼 Business Assistant

```python
# Extract project decisions and deadlines
memory.extract("biz_agent",
    "We decided to launch the new feature next quarter, Q2 2026", 
    "I've noted the Q2 2026 launch timeline for the new feature")

# Auto-recalls during planning meetings:
# "New feature launch planned for Q2 2026"
```

### 🏥 Healthcare Assistant

```python
# Remember patient preferences and medical history
memory.extract("health_agent",
    "I'm allergic to penicillin and prefer morning appointments",
    "Noted your penicillin allergy and morning appointment preference")

# Never forgets critical medical information
```

## Community

- **Documentation**: [docs/](docs/) 
- **Issues**: Report bugs and feature requests
- **Discussions**: Share use cases and integration tips
- **Contributions**: See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Get Started**: Request an API key and try the [Quickstart Guide](docs/QUICKSTART.md)

**Enterprise**: Contact us for custom deployments, higher limits, and dedicated support.