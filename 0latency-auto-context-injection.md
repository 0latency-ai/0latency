# 0Latency Auto-Context Injection - Product Feature Spec

## The Problem (Thomas's Problem = Every User's Problem)

**Current behavior:**
1. Agent has protocols/rules stored in memory
2. Agent can recall them when explicitly asked
3. Agent DOESN'T proactively recall before making mistakes
4. User has to "jog the agent's memory" after the mistake

**Example from today (March 27, 2026):**
- Thomas asked "Do we have PyPI credentials?" 
- The protocol "Check filesystem before asking" was stored in MEMORY.md
- Thomas COULD have recalled it, but didn't
- Justin had to correct → "Why didn't you check first?"
- THEN Thomas found the answer in 5 seconds

**This breaks the "It Just Works" promise.**

## The Solution: Smart Auto-Context Injection

**Concept:**
The MCP server / API should **detect patterns and auto-inject relevant memories BEFORE the agent acts.**

**Trigger-based recall:**
```
Agent thinking: "I should ask if we have X..."
↓
MCP detects question pattern
↓
Auto-injects: "Protocol: Check filesystem/env/memory before asking"
↓
Agent checks first, finds answer
↓
No question needed — problem solved
```

## Implementation Approaches

### Approach 1: MCP Server Pattern Detection (Recommended)

**How it works:**
1. MCP server monitors outbound messages from the agent
2. Detects patterns: questions, claims, actions
3. Runs recall query BEFORE sending message
4. Injects relevant context into agent's working memory
5. Agent sees context, adjusts behavior

**Example patterns:**
- "Do we have..." → Auto-inject: Check credentials/filesystem protocols
- "I think the API is..." → Auto-inject: Recent API test results
- "Let me build..." → Auto-inject: Related prior work, dependencies
- "The user prefers..." → Auto-inject: Verified preferences

**Technical:**
```javascript
// In MCP server, intercept outbound messages
server.onMessageSend(async (message) => {
  const triggers = detectPatterns(message.content);
  
  if (triggers.length > 0) {
    const context = await Promise.all(
      triggers.map(t => client.recall(t.query, { limit: 3 }))
    );
    
    // Inject context BEFORE message sends
    injectContext(message, context.flat());
  }
});
```

### Approach 2: Agent-Side Auto-Recall Hook

**How it works:**
1. Agent's tool-use layer has a pre-flight hook
2. Before calling message/send, auto-runs recall queries
3. Relevant memories injected into context
4. Agent adjusts behavior based on injected context

**OpenClaw integration:**
```javascript
// In OpenClaw agent runtime
beforeToolCall('message', async (params) => {
  if (params.action === 'send') {
    const memories = await zerolatency.recall({
      query: params.message,
      limit: 5,
      filter: { priority: 'high', type: 'protocol' }
    });
    
    if (memories.length > 0) {
      injectSystemMessage(`Relevant protocols:\n${formatMemories(memories)}`);
    }
  }
});
```

### Approach 3: API-Side Smart Suggestions

**How it works:**
1. API has a new endpoint: `/suggest-context`
2. Agent sends "about to do X" query
3. API returns relevant memories + confidence scores
4. Agent reviews before proceeding

**API endpoint:**
```
POST /suggest-context
{
  "agent_id": "thomas",
  "intent": "ask_about_credentials",
  "context": "User asked about PyPI publishing"
}

Response:
{
  "suggestions": [
    {
      "memory": "Protocol: Check ~/.pypirc before asking about credentials",
      "confidence": 0.95,
      "reason": "High-priority protocol, directly relevant"
    },
    {
      "memory": "PyPI credentials stored in ~/.pypirc (March 23, 2026)",
      "confidence": 0.88,
      "reason": "Factual match for 'PyPI credentials'"
    }
  ]
}
```

## Priority Features

### 1. Protocol Storage & Tagging
**Store operating rules as high-priority memories:**
```python
client.seed(
    agent_id="thomas",
    memories=[
        {
            "content": "PROTOCOL: Before asking 'Do we have X?', check filesystem, env vars, memory files, installed tools",
            "priority": "critical",
            "type": "protocol",
            "triggers": ["question_about_availability", "asking_user"]
        }
    ]
)
```

### 2. Pattern Detection Library
**Common agent anti-patterns to catch:**
- Asking questions answerable from memory/filesystem
- Making claims without verification
- Repeating work already done
- Suggesting features already built

### 3. Auto-Injection Config
**Per-agent configuration:**
```json
{
  "auto_inject": {
    "enabled": true,
    "triggers": ["question", "claim", "task_start"],
    "priority_threshold": 0.7,
    "max_injections_per_turn": 3
  }
}
```

## User Experience

### Before (Current):
```
Agent: "Do we have PyPI credentials?"
User: "Why are you asking? Check first!"
Agent: *checks* "Oh, found them in ~/.pypirc"
```

### After (Auto-Injection):
```
Agent: *about to ask question*
MCP: *injects "Check filesystem first" protocol*
Agent: *checks ~/.pypirc, finds credentials*
Agent: "Found PyPI credentials in ~/.pypirc. Publishing now."
```

**User sees:** Agent that "just knows" instead of asking obvious questions.

## Technical Requirements

### MCP Server Changes
1. Message interception hook
2. Pattern detection engine
3. Auto-recall on pattern match
4. Context injection mechanism

### API Enhancements
1. `/suggest-context` endpoint
2. Priority/trigger metadata on memories
3. Pattern matching service
4. Confidence scoring for relevance

### SDK Updates
1. `auto_inject=True` parameter on client init
2. Pattern detector registry
3. Pre-flight hooks for common operations

## Success Metrics

**For Thomas (immediate):**
- Zero "why didn't you check first?" corrections from Justin
- 100% protocol compliance without explicit reminders
- Sub-5-second response time on questions about infrastructure

**For all users (product):**
- 80% reduction in "agent asked obvious question" complaints
- 90% protocol adherence without user intervention
- Agent feels "naturally smart" vs "needs training"

## Implementation Plan

### Phase 1: Thomas Dogfooding (1 day)
1. Extract all NON-NEGOTIABLE rules from AGENTS.md/MEMORY.md
2. Store as high-priority protocol memories in 0Latency
3. Add session startup hook: recall all protocols
4. Add pre-message hook: check for relevant protocols
5. Test for 48 hours, measure corrections from Justin

### Phase 2: MCP Server Integration (3 days)
1. Build pattern detector (question/claim/action patterns)
2. Add message interception layer
3. Wire up auto-recall on pattern match
4. Test with Claude Desktop + Cursor users

### Phase 3: API Enhancement (1 week)
1. Build `/suggest-context` endpoint
2. Add priority/trigger metadata schema
3. Pattern matching service
4. Confidence scoring algorithm

### Phase 4: SDK Rollout (3 days)
1. Update Python SDK with `auto_inject` parameter
2. Documentation + examples
3. LangChain/CrewAI integration updates
4. Publish new versions

## Rollout Strategy

**Week 1:** Thomas proves it works (dogfooding)
**Week 2:** Ship MCP server update (opt-in flag)
**Week 3:** Gather feedback, iterate
**Week 4:** Default-on for new users
**Month 2:** API enhancement for non-MCP users

## Why This Matters

**This is the difference between:**
- "A memory API you have to remember to use" (current)
- "Memory that just works" (vision)

**Every agent has this problem.** They CAN recall, they just DON'T until corrected.

**Auto-context injection = the feature that makes 0Latency feel like magic.**

---

**Next steps:** Build it for Thomas first, prove it works, ship it as product feature.
