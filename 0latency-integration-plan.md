# 0Latency Integration Layer - Build Plan

## Objective
Make 0Latency dead-simple to integrate: Python SDK, agent framework plugins, and clear documentation so users can add memory to their agents in <5 minutes.

## Requirements
**Inputs:**
- Working API at https://api.0latency.ai (endpoints: /extract, /recall, /health)
- Enterprise tier features (entity extraction, graph relationships, sentiment)
- API key authentication (X-API-Key header)

**Outputs:**
1. Python SDK (`pip install zerolatency`)
2. LangChain integration (`from langchain.memory import ZeroLatencyMemory`)
3. CrewAI integration (memory tool)
4. OpenClaw AgentSkill (already done - just needs polish)
5. Integration docs with copy-paste examples
6. Quick-start guide (5-minute setup)

**Constraints:**
- Must be production-ready (error handling, retry logic, rate limiting)
- Clear documentation (no "figure it out yourself")
- Examples for every major framework
- Keep it simple (Stripe-level DX)

## Dependencies
- Python 3.8+ (SDK)
- `requests` library (HTTP calls)
- Optional: `langchain`, `crewai` for framework integrations
- Existing 0latency.ai docs site structure
- PyPI account for publishing (need to verify if we have this)

## Architecture

### 1. Python SDK (`zerolatency`)
**Core client class:**
```python
from zerolatency import ZeroLatency

client = ZeroLatency(api_key="zl_live_...", agent_id="my-agent")

# Store conversation turn
result = client.store(
    human_message="What's Palmer's role?",
    agent_message="Palmer is Head of Engineering at ZeroClick"
)

# Recall memories
memories = client.recall("Palmer ZeroClick")

# Query graph
graph = client.graph()
```

**Features:**
- Automatic retry (3 attempts with backoff)
- Rate limit handling (respect 429 responses)
- Async support (`client.store_async()`)
- Batch operations (`client.store_batch([...])`)
- Error types (AuthError, RateLimitError, APIError)

### 2. LangChain Integration
**Memory class:**
```python
from langchain.memory import ZeroLatencyMemory
from langchain.chains import ConversationChain

memory = ZeroLatencyMemory(
    api_key="zl_live_...",
    agent_id="my-agent"
)

chain = ConversationChain(memory=memory)
```

Auto-stores on every turn, auto-recalls on relevant queries.

### 3. CrewAI Integration
**Memory tool:**
```python
from crewai import Agent, Task
from zerolatency.integrations.crewai import memory_tool

agent = Agent(
    role="Research Assistant",
    tools=[memory_tool(api_key="...", agent_id="...")],
    memory=True
)
```

### 4. Documentation Structure
```
docs/
├── quickstart.md          (5-minute setup)
├── python-sdk.md          (full SDK reference)
├── integrations/
│   ├── langchain.md
│   ├── crewai.md
│   ├── openclaw.md
│   ├── claude-desktop.md
│   └── autogen.md
├── examples/
│   ├── chatbot.py
│   ├── research-agent.py
│   └── multi-agent-system.py
└── api-reference.md       (existing)
```

## Risk Assessment
1. **PyPI publishing** - Do we have account? Need to set up if not.
2. **Framework version compatibility** - LangChain/CrewAI APIs change frequently
3. **Rate limiting** - Need to test under load (10K/min limit)
4. **Error handling** - API failures need graceful degradation
5. **Documentation drift** - Keep examples up-to-date with API changes

## Execution Steps

### Phase 1: Python SDK (Core) - 2 hours
1. Create package structure (`zerolatency/`)
2. Implement `ZeroLatency` client class
3. Add retry/rate-limit logic
4. Write unit tests
5. Add type hints + docstrings
6. Test against live API

### Phase 2: Framework Integrations - 3 hours
1. LangChain memory class (1h)
2. CrewAI tool wrapper (1h)
3. Test integrations with sample agents (1h)

### Phase 3: Documentation - 2 hours
1. Write quickstart guide
2. Full SDK reference
3. Integration guides (LangChain, CrewAI, OpenClaw)
4. Copy-paste examples
5. Troubleshooting section

### Phase 4: Publishing - 1 hour
1. Set up PyPI account (if needed)
2. Publish `zerolatency` package
3. Deploy docs to 0latency.ai/docs/
4. Create GitHub repo (python-sdk)
5. Add to main site nav

### Phase 5: Polish OpenClaw Skill - 30 min
1. Update SKILL.md with SDK usage
2. Deprecate shell scripts (keep as fallback)
3. Test auto-storage in conversation flow

## Verification
**Success criteria:**
- [ ] `pip install zerolatency` works
- [ ] LangChain example runs in <5 lines of code
- [ ] CrewAI integration works with sample agent
- [ ] Documentation loads on 0latency.ai/docs/
- [ ] Quickstart guide: user can integrate in <5 minutes
- [ ] All examples tested and working

## Token/Time Estimate
- **Coding:** ~6-8 hours (SDK + integrations)
- **Documentation:** ~2-3 hours
- **Testing:** ~1-2 hours
- **Total:** 9-13 hours of work
- **Token estimate:** ~50K tokens if done inline

**Recommendation:** Spawn coding agent (Claude Code) for SDK + integrations, keep main session for docs/coordination.

## Open Questions
1. Do we have PyPI publishing credentials?
2. Should we support AutoGen/other frameworks in v1?
3. Do we want GitHub org or personal account for SDK repo?
4. Should SDK include CLI tool (`zl store "..."`) for quick testing?
