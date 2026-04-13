# Best Practices for 0Latency Memory API

## Section 1: Agent ID Management

### Set agent_id Once at Setup, Never Change It

**Why:** Changing an agent's `agent_id` creates an orphaned memory namespace. All previous memories remain under the old `agent_id` and are inaccessible to the new one.

**Example of what NOT to do:**
```python
# Week 1
client.extract(agent_id="my-agent", content="...")

# Week 2 - decides to rename
client.extract(agent_id="my-agent-v2", content="...")
```

Result: You now have two separate namespaces that cannot recall each other's memories.

**Correct approach:**
```python
# At initialization
AGENT_ID = "my-agent"

# Use consistently everywhere
client.extract(agent_id=AGENT_ID, content="...")
client.recall(agent_id=AGENT_ID, context="...")
client.search(agent_id=AGENT_ID, query="...")
```

### Use list_agents to Audit Namespaces Periodically

**Check for fragmentation:**
```bash
curl "https://api.0latency.ai/list_agents" \
  -H "X-API-Key: your_api_key"
```

**Signs of fragmentation:**
- Multiple similar agent_ids: `thomas`, `thomas-test`, `thomas-chief-of-staff`
- Test namespaces left behind: `test-agent`, `debug-agent`
- Typo variants: `my_agent` vs `my-agent`

**Fix:** Use the namespace consolidation script to merge related namespaces:
```python
# See: scripts/migrate_namespaces.py
python3 migrate_namespaces.py \
  --source thomas-test,thomas-debug \
  --target thomas
```

### One Canonical Namespace Per Agent

**Recommended naming conventions:**
- **Personal agents:** Use the person's name: `justin`, `alice`, `bob`
- **Specialized agents:** Use role: `writer`, `researcher`, `analyst`
- **Team agents:** Use team name: `marketing`, `engineering`, `support`
- **Service agents:** Use service name: `chatbot`, `assistant`, `advisor`

**Avoid:**
- Versioning in agent_id: ~~`my-agent-v2`~~ (use metadata instead)
- Timestamps: ~~`agent-2026-03-31`~~ (memories are timestamped internally)
- Test suffixes: ~~`agent-test`~~ (use separate dev tenant instead)

---

## Section 2: Tiered Memory Architecture

### Agent-Specific Memories

**What:** Memories stored with a specific `agent_id` that contain specialist knowledge unique to that agent.

**Examples:**
- Writer agent: style preferences, common phrases, writing rules
- Researcher agent: research methodology, source credibility assessments
- Sales agent: customer interaction patterns, objection handling strategies

**Storage:**
```python
client.extract(
    agent_id="writer",
    content="User prefers Oxford commas and active voice"
)
```

**Recall:**
```python
result = client.recall(
    agent_id="writer",
    conversation_context="Draft an email to the team"
)
# Returns writer-specific memories only
```

### Shared Namespace (Cross-Cutting Facts)

**What:** Memories that are relevant across multiple agents. Facts that any agent should know.

**Examples:**
- Company information: "0Latency API endpoint is api.0latency.ai"
- User preferences: "Justin's timezone is US Pacific"
- Project context: "Current project is memory-product launch"

**Recommended pattern:**
1. Use a dedicated agent_id for shared facts: `shared` or `wall-e`
2. Promote important facts from agent-specific to shared namespace
3. Use Wall-E (or equivalent) to curate shared memories

**Storage:**
```python
# Agent discovers important fact
client.extract(
    agent_id="researcher",
    content="Company HQ is in San Francisco"
)

# Later, promote to shared namespace
client.extract(
    agent_id="shared",
    content="Company HQ is in San Francisco"
)
```

**Recall from multiple namespaces:**
```python
# Not yet supported natively - coming soon
# For now, make separate recall calls and merge
agent_memories = client.recall(agent_id="writer", ...)
shared_memories = client.recall(agent_id="shared", ...)
```

### Chrome Extension Namespace Routing

**Default behavior:** Chrome extension writes captures to agent_id `"justin"` (configurable).

**Change in extension settings:**
1. Click extension icon in browser
2. Go to Settings
3. Update "Agent ID" field
4. Click Save

**Routing strategies:**

**Option A: Personal namespace (default)**
```
agent_id: "justin"
```
All browser captures → justin's personal memory

**Option B: Project-specific**
```
agent_id: "pfl-academy-research"
```
All browser captures → project namespace

**Option C: Shared team namespace**
```
agent_id: "team-engineering"
```
All browser captures → team shared memory

**Best practice:** Use personal namespace by default, create project-specific agents when working on isolated projects.

---

## Section 3: Monitoring and Observability

### Canary Monitoring

**What:** Automated health check that runs every 30 minutes via cron.

**What it checks:**
- `/health` endpoint availability
- `/recall` endpoint functionality
- Embedding API status
- Database connectivity

**Where to find logs:**
```bash
tail -50 /root/logs/canary_$(date +%Y-%m-%d).log
```

**Alert destinations:**
- Telegram bot: Thomas (@Thomas_clawdbot)
- Chat ID: Justin Ghiglia

**What triggers alerts:**
- API returns non-200 status
- `/recall` returns 0 memories despite data existing
- Response is malformed or unparseable

**How to disable (if needed):**
```bash
crontab -e
# Comment out: */30 * * * * /root/scripts/memory_canary.sh
```

### /health Endpoint with Embedding Status

**Endpoint:** `GET https://api.0latency.ai/health`

**Response format:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2026-03-31T23:02:39.601468+00:00",
  "memories_total": 2069,
  "db_pool": {
    "pool_min": 1,
    "pool_max": 5
  },
  "redis": "connected",
  "embedding": "ok"
}
```

**Key fields:**
- `status`: Overall health - `"ok"` or `"degraded"`
- `embedding`: Embedding API status - `"ok"`, `"failed: <error>"`, or `"degraded: <reason>"`
- `redis`: Cache status - `"connected"` or `"unavailable"`

**Status meanings:**
- `"ok"`: All systems operational
- `"degraded"`: One or more critical systems failing (check `embedding` field)

**Use in monitoring:**
```bash
# Check health periodically
curl -s https://api.0latency.ai/health | jq .status

# Alert if degraded
STATUS=$(curl -s https://api.0latency.ai/health | jq -r .status)
if [ "$STATUS" = "degraded" ]; then
  echo "Alert: API health degraded"
fi
```

### Zero-Recall Alert System

**What:** Tracks consecutive `/recall` requests returning `memories_used: 0` and alerts after 3 failures within 60 minutes.

**Why:** Indicates systemic issues with embedding API or vector index, not just a one-off query problem.

**Alert format:**
```
⚠️ RECALL FAILURE

Tenant 44c3080d... getting 0 memories on recall.

Consecutive failures: 3
Possible embedding or index issue.
```

**When it fires:**
- 3+ consecutive zero-recall responses
- All within 60-minute sliding window
- Per-tenant tracking (isolated counters)

**When it resets:**
- Automatically when next recall returns `memories_used > 0`
- Timestamp history cleared

**Rate limiting:**
- Only alerts once per hour per tenant (prevents spam)

**Investigation steps when alert fires:**
1. Check `/health` endpoint for embedding status
2. Verify agent has memories: `GET /memories?agent_id=...`
3. Check API logs: `journalctl -u zerolatency-api -n 100`
4. Test embedding API manually (see TROUBLESHOOTING.md)

---

## Section 4: API Usage Patterns

### Extraction: Store Once, Recall Often

**Anti-pattern:**
```python
# Storing redundant memories every request
for user_message in conversation:
    client.extract(content=user_message)  # Too frequent
```

**Best practice:**
```python
# Extract only when new information is learned
if contains_new_information(user_message):
    client.extract(content=user_message)
```

**Guidelines:**
- Extract facts, decisions, preferences, corrections
- Skip pleasantries and acknowledgments
- Dedupe automatically handled by API (>0.92 similarity)

### Recall: Budget-Aware Context Loading

**Token budgets:**
- **Small context:** 1000-2000 tokens (quick queries)
- **Standard context:** 4000 tokens (default, recommended)
- **Large context:** 8000-12000 tokens (complex reasoning)

**Example:**
```python
result = client.recall(
    agent_id="thomas",
    conversation_context="Current task: write deployment guide",
    budget_tokens=4000
)

# Use result['context_block'] as system message
system_prompt = f"{agent_identity}\n\n{result['context_block']}"
```

**Budget allocation:**
1. Always-include block (identity, profile, corrections): ~300-500 tokens
2. Relevant memories: Fills remaining budget
3. Tiered loading: High-scoring memories get full context, low-scoring get headlines only

### Search vs Recall

**Use /memories/search when:**
- You know exactly what you're looking for
- Exploring memory history
- Auditing stored facts
- Building custom memory browsers

**Use /recall when:**
- Preparing context for LLM agent
- Need automatic relevance scoring
- Want budget-aware memory loading
- Need temporal weighting (recent + important)

**Comparison:**
| Feature | /recall | /search |
|---------|---------|---------|
| Semantic similarity | ✅ | ✅ |
| Temporal decay | ✅ | ❌ |
| Importance weighting | ✅ | ❌ |
| Token budget | ✅ | ❌ |
| Tiered loading | ✅ | ❌ |
| Keyword fallback | ✅ | ⚠️ Limited |
| Raw results | ❌ | ✅ |

---

## Section 5: Security and API Keys

### Environment Variables, Never Hardcoded

**Wrong:**
```ini
# In systemd service file
Environment=GOOGLE_API_KEY=AIzaSyD...
Environment=OPENAI_API_KEY=sk-proj-...
```

**Correct:**
```ini
# In systemd service file
EnvironmentFile=/path/to/.env

# In .env file
GOOGLE_API_KEY=AIzaSyD...
OPENAI_API_KEY=sk-proj-...
```

**Benefits:**
- Easy key rotation without systemd reload
- Keys not visible in `systemctl status`
- Same `.env` file for dev and production
- Git-ignored by default

### API Key Rotation

**When to rotate:**
- On schedule: Every 90 days
- After compromise: Immediately
- Team member leaves: Within 24 hours
- Suspicious activity: Immediately

**How to rotate:**
1. Generate new key in dashboard
2. Update `.env` file with new key
3. Restart API: `systemctl restart zerolatency-api`
4. Test: `curl https://api.0latency.ai/health`
5. Revoke old key after 24-hour grace period

**Zero-downtime rotation:**
- Keep both old and new keys active for 24 hours
- Update all clients to new key
- Monitor usage of old key (should drop to zero)
- Revoke old key

### Rate Limiting

**Current limits:**
- **Free tier:** 20 RPM
- **Pro tier:** 100 RPM
- **Scale tier:** 500 RPM
- **Enterprise:** Custom

**Best practices:**
- Implement exponential backoff on 429 errors
- Cache recall results for identical queries (60s TTL)
- Batch extract operations when possible
- Use webhooks for async processing

**Example with retry:**
```python
import time

def extract_with_retry(client, content, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.extract(content=content)
        except RateLimitError:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                time.sleep(wait_time)
            else:
                raise
```
