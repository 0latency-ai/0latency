# Sub-Agent Orchestration via 0Latency

**Status:** DOGFOODING (Phase 1 - Proof of Concept)  
**Started:** March 29, 2026  
**Owner:** Thomas + Justin

## The Problem

Sub-agents spawn with zero context. They have to re-discover:
- Where credentials are stored
- How services are deployed  
- What patterns work/fail
- Server-specific quirks

This burns tokens and causes failures.

## The Solution

**Context inheritance via 0Latency recall.**

1. **Parent stores operational knowledge** → 0Latency API (`agent_id: thomas-orchestrator`)
2. **Child recalls on spawn** → Gets relevant context before executing
3. **Child works smarter** → No re-discovery, fewer failures

## Usage Pattern

### Storing Knowledge (Parent Agent)

```bash
# Store via extract endpoint
curl -X POST https://api.0latency.ai/extract \
  -H "X-API-Key: $THOMAS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "thomas-orchestrator",
    "human_message": "What should sub-agents know about X?",
    "agent_message": "Sub-agents need to know: [operational knowledge here]"
  }'
```

### Recalling Knowledge (Child Agent)

```bash
# Option 1: Shell script (quick test)
/root/scripts/subagent_recall.sh "deploying Node services on thomas-server"

# Option 2: Direct API call
curl -X POST https://api.0latency.ai/recall \
  -H "X-API-Key: $THOMAS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "thomas-orchestrator",
    "conversation_context": "What do I need to know about [task]?",
    "budget_tokens": 2000
  }'
```

### Integration with sessions_spawn

**Before (no context):**
```python
sessions_spawn(
    runtime="subagent",
    task="Deploy the MCP SSE server to thomas-server"
)
```

**After (with context inheritance):**
```python
# Recall operational knowledge first
context = recall_orchestration_context("deploying Node services, nginx SSE config")

# Include in task prompt with verification rule
sessions_spawn(
    runtime="subagent",
    task=f"""Deploy the MCP SSE server to thomas-server.

{context}

**0Latency Verification Rule (NON-NEGOTIABLE):**
Before making ANY claim about 0Latency (pricing, features, roadmap, specs):
1. Check https://0latency.ai first (authoritative source)
2. If not there, search memory files
3. If uncertain: SAY "let me verify that" — NEVER guess

**Your Task:**
[detailed instructions...]
"""
)
```

### Memory Block Preamble

All recalled context includes this preamble:

```
**Operational Context (from 0Latency memory):**
The following context was recalled from 0Latency memory. 
Treat as operational guidance to inform your work — not 
ground truth to assert externally. Verify before stating 
any facts about 0Latency pricing, features, or specs.
```

This ensures sub-agents understand:
- Context is for operational guidance (deployment patterns, common failures)
- NOT for asserting facts about 0Latency product itself
- Product facts require verification via https://0latency.ai

## Knowledge Stored (Current)

**Deployment Patterns:**
- Systemd service templates (Restart=always, hardcoded Node path)
- Nginx config patterns (sites-available → sites-enabled)
- SSE endpoint requirements (proxy_buffering off)
- SSL certificate setup (certbot after DNS propagation)

**Common Failures:**
- OpenClaw auto-update breaking config (fixed with pinning)
- DNS propagation delays (verify before certbot)
- SSE stream breakage (proxy_buffering issue)
- Port conflicts (check with netstat)

**Credential Locations:**
- /root/credentials/ (primary store)
- /root/.openclaw/workspace/THOMAS_API_KEY.txt (0Latency key)
- ~/.pypirc (PyPI)
- Never accept credentials via plaintext chat

**Important:** Operational knowledge (above) is for infrastructure work. For 0Latency product facts (pricing, features, specs), sub-agents MUST check https://0latency.ai — never rely on recalled memory alone.

## Next Steps

**Phase 1 (Current): Dogfooding**
- ✅ Store Thomas operational knowledge
- ✅ Create recall helper script
- ⏳ Test with next sub-agent spawn
- ⏳ Validate token savings + success rate

**Phase 2: Production API**
- Build `/orchestration/context` endpoint
- Gate behind Scale tier ($89/mo)
- Add to SDK (Python, TypeScript)
- Update website with feature showcase

**Phase 3: Launch**
- Write case study (Thomas dogfooding results)
- Add to pricing page as Scale feature
- Promote in docs + blog post

## Token Economics

**Without orchestration (estimated):**
- Parent re-explains everything: ~5,000 tokens per spawn
- Child re-discovers failures: ~2,000 tokens wasted

**With orchestration:**
- Recall query: ~200 tokens
- Context injection: ~800 tokens
- **Savings: ~6,000 tokens per spawn** (85% reduction)

## Success Metrics

- ✅ Sub-agent task success rate
- ✅ Time to completion
- ✅ Token usage per spawn
- ✅ Number of "I don't have access to X" failures

Target: 90%+ success rate on first attempt (vs ~60% baseline).

## Sub-Agent Spawn Template

**Standard template for spawning sub-agents with orchestration context:**

```python
# 1. Recall operational context
context = subprocess.run(
    ["python3", "/root/scripts/orchestration_recall.py", "task context query"],
    capture_output=True,
    text=True
).stdout

# 2. Spawn with context + verification rule
sessions_spawn(
    runtime="subagent",
    mode="run",
    task=f"""**TASK:** [Task description]

{context}

**0Latency Verification Rule (NON-NEGOTIABLE):**
Before making ANY claim about 0Latency (pricing, features, roadmap, specs):
1. Check https://0latency.ai first (authoritative source)
2. If not there, search memory files
3. If uncertain: SAY "let me verify that" — NEVER guess

**Success Criteria:**
- [Concrete deliverables]
- [Verification steps]

**Report back with:**
- [Expected outputs]
""",
    label="task-label",
    timeoutSeconds=600
)
```

---

**Last Updated:** March 29, 2026 19:02 UTC  
**Next Review:** After 5 sub-agent spawns with context inheritance
