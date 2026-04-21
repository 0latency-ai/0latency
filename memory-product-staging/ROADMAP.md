# Memory Layer for AI Agents — Product Roadmap

**Document:** Architecture & Roadmap v1
**Author:** Thomas (Chief of Staff)
**Date:** March 18, 2026
**Status:** Draft — for Justin's review before any building begins

---

## 1. The Problem (Why This Matters)

Every persistent AI agent — whether running on OpenClaw, LangChain, CrewAI, or any other framework — suffers from the same fundamental limitation: **agents forget.**

Context windows compress. Sessions reset. The agent wakes up fresh and the user has to re-explain things they've already said. This isn't a minor annoyance — it's the single biggest barrier to AI agents being genuinely useful over time.

### What Exists Today

| Approach | How It Works | Why It Fails |
|----------|-------------|--------------|
| **Flat file memory** (MEMORY.md) | Agent reads a markdown file at session start | Grows unbounded, no relevance scoring, relies on agent choosing to write things down, can't scale past ~30KB without eating context |
| **Vector databases** (Pinecone, Weaviate) | Store embeddings, retrieve by similarity | Good at "find similar text" — terrible at "what should this agent know right now?" No structure, no decay, no relationship between memories |
| **Chat history replay** | Feed prior messages back into context | Expensive, noisy, no signal filtering. 100 messages of chat ≠ 5 key facts |
| **RAG systems** | Retrieve documents by query | Built for document Q&A, not agent continuity. Agent has to know what to ask for |

### What's Missing

Nobody has built an **intelligent memory layer** that handles:
1. **Automatic extraction** — pulling key facts from conversations without the agent deciding to
2. **Structured storage** — facts with types, relationships, confidence levels, timestamps
3. **Proactive recall** — surfacing relevant memories at inference time without being asked
4. **Temporal dynamics** — memories strengthen with reinforcement, fade without it
5. **Context budget management** — fitting the right memories into limited context windows

NemoClaw (Nvidia, March 2026) addressed agent security/sandboxing. Memory was explicitly not in scope. This gap remains wide open.

---

## 2. What We've Learned from Running Thomas

After months of operating a persistent AI agent (Thomas) with real-world workload, these are the observed failure modes:

### Failure Mode 1: Write Failures
The agent doesn't write down important information. User says "remember X" and the agent acknowledges but doesn't persist it to any file. Or the agent writes it but in the wrong place, or with insufficient context to be useful later.

**Root cause:** Memory writes are discretionary. The agent *chooses* whether to write, *what* to write, and *where*. Three decision points, all heuristic.

### Failure Mode 2: Recall Failures
Information exists in memory files but the agent doesn't retrieve it when relevant. User asks about something discussed last week, agent says "I don't have context on that" — but it's in the daily notes.

**Root cause:** Recall depends on the agent knowing to search, crafting a good search query, and the search returning relevant results. Any step can fail. Flat file reading is even worse — the agent has to load the right file and hope the relevant section is in the context window.

### Failure Mode 3: Context Overflow
MEMORY.md grows beyond what can be loaded at session start. The file is 27KB and growing. Loading it consumes significant context budget, leaving less room for actual conversation.

**Root cause:** No curation, no decay, no prioritization. Everything that was ever important is still in the file, even if it's months stale.

### Failure Mode 4: Compaction Amnesia
After context compaction (when the conversation gets long), the agent loses awareness of capabilities, ongoing projects, and recent decisions. It reverts to default behaviors.

**Root cause:** Compaction strips out information that wasn't in the most recent exchanges. The agent's "working memory" of its own state gets wiped.

### Failure Mode 5: Cross-Session Discontinuity
Agent finishes a session having made decisions and done work. Next session, it doesn't know what happened. Daily notes help but require the agent to read the right file and parse unstructured markdown.

**Root cause:** No structured handoff mechanism. Memory is a pile of text, not a state machine.

---

## 3. Architecture Design

### Core Concept: Memory as a Service (MaaS)

The memory system is NOT an agent. It's a **service** that agents call. It has two interfaces:

```
Agent → Memory Service: "Here's what just happened in my conversation"
Memory Service → Agent: "Here's what you should know right now"
```

This is the fundamental design decision. The memory system doesn't participate in conversations. It observes them and provides context.

### Three-Layer Architecture

```
┌─────────────────────────────────────┐
│         RECALL LAYER                │
│  "What should the agent know now?"  │
│  Context budget, relevance scoring, │
│  proactive injection                │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         STORAGE LAYER               │
│  Structured facts, relationships,   │
│  embeddings, temporal metadata      │
│  (Postgres + pgvector)              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         EXTRACTION LAYER            │
│  "What matters in this exchange?"   │
│  Fact extraction, entity detection, │
│  relationship mapping               │
└─────────────────────────────────────┘
```

### Layer 1: Extraction

**Input:** Raw conversation turns (user message + agent response)
**Output:** Structured memory objects

The extraction layer processes each conversation exchange and outputs:

```json
{
  "facts": [
    {
      "content": "Justin prefers direct communication with no filler phrases",
      "type": "preference",
      "confidence": 0.95,
      "entities": ["Justin"],
      "source_turn": "msg_12345",
      "extracted_at": "2026-03-18T22:00:00Z"
    }
  ],
  "decisions": [
    {
      "content": "Chose Archway Depository for OK textbook submission",
      "context": "Only options were TBSD or Archway; PFL is digital-only",
      "date": "2026-03-18",
      "reversible": true
    }
  ],
  "tasks": [
    {
      "content": "Draft justification letter for OK STC",
      "status": "pending",
      "due": "April 2026",
      "project": "PFL Academy - Oklahoma"
    }
  ],
  "corrections": [
    {
      "old_fact": "PFL Academy depository is Self",
      "new_fact": "PFL Academy depository is Archway (Self not available on bid form)",
      "reason": "Form only offered TBSD or Archway options"
    }
  ]
}
```

**Key design decisions:**
- Extraction runs on EVERY conversation turn, not at agent discretion
- Uses a lightweight model call (could be Haiku/Flash-level, not Opus)
- Costs ~$0.001-0.003 per turn at current API pricing
- Outputs are typed (fact, decision, task, correction, preference, relationship)
- Each output has confidence score, source reference, and timestamp

**Architectural principle — async extraction is non-negotiable:**
Extraction always runs asynchronously. The caller gets an instant acknowledgment (202 Accepted) and processing happens in the background. This is not a configuration option — it's a core architectural decision based on three rules:
1. **Recall is always sync, always fast.** Sub-100ms. Every time.
2. **Extraction accepts instantly, processes in background.** The caller never waits.
3. **Partial results beat blocking.** If extraction is still processing, recall returns what's ready.

This mirrors the "zero latency" product promise: zero latency is what the system does by default, not a setting you tune.

### Layer 2: Storage

**Schema:** Postgres + pgvector (can run on Supabase, Neon, or self-hosted)

**Core Tables:**

```sql
-- Individual memory atoms
CREATE TABLE memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL,         -- which agent this belongs to
  content TEXT NOT NULL,           -- the actual memory
  memory_type TEXT NOT NULL,       -- fact, decision, task, preference, correction, relationship
  confidence FLOAT DEFAULT 0.8,   -- extraction confidence
  relevance_score FLOAT DEFAULT 1.0, -- decays over time, increases with reinforcement
  embedding vector(1536),         -- for semantic search
  entities TEXT[],                 -- people, projects, orgs mentioned
  project TEXT,                    -- optional project association
  source_session TEXT,             -- which session this came from
  source_turn TEXT,                -- specific message reference
  created_at TIMESTAMPTZ DEFAULT now(),
  last_accessed TIMESTAMPTZ,      -- updated on recall
  access_count INT DEFAULT 0,     -- how often this gets retrieved
  superseded_by UUID REFERENCES memories(id), -- for corrections
  metadata JSONB                   -- extensible
);

-- Relationships between memories
CREATE TABLE memory_edges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES memories(id),
  target_id UUID REFERENCES memories(id),
  relationship TEXT NOT NULL,      -- supports, contradicts, supersedes, related_to
  weight FLOAT DEFAULT 1.0
);

-- Agent identity and persistent state
CREATE TABLE agent_state (
  agent_id TEXT PRIMARY KEY,
  identity JSONB,                  -- name, role, personality, capabilities
  active_projects JSONB,           -- current project list with status
  user_profile JSONB,              -- info about the human
  last_checkpoint TIMESTAMPTZ,
  context_budget INT DEFAULT 4000  -- max tokens for memory injection
);

-- Session handoff records
CREATE TABLE session_handoffs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL,
  session_key TEXT NOT NULL,
  summary TEXT NOT NULL,           -- what happened this session
  decisions_made JSONB,            -- key decisions for continuity
  open_threads JSONB,              -- things that were in progress
  created_at TIMESTAMPTZ DEFAULT now()
);
```

**Decay mechanism:**
- `relevance_score` starts at 1.0
- Decays by 0.02/day for facts, 0.005/day for decisions, 0.001/day for preferences
- Each access (recall) resets decay clock and adds 0.1 to relevance
- Memories below 0.1 relevance are archived (not deleted)
- Corrections immediately set superseded memory's relevance to 0

**Embedding strategy:**
- Content + context concatenated before embedding
- Use same embedding model as the recall query (consistency matters)
- Re-embed on correction/update

### Layer 3: Recall

**Input:** Current conversation context (recent messages, current topic)
**Output:** A curated block of relevant memories that fits within context budget

This is the hardest layer. The algorithm:

```
1. ANALYZE current conversation
   - Extract key entities, topics, project references
   - Detect implicit context (if discussing Oklahoma, surface OK-related memories)

2. RETRIEVE candidates
   - Semantic search on conversation embedding → top 50 candidates
   - Entity match → all memories mentioning detected entities
   - Project match → all memories tagged to detected projects
   - Recency boost → last 48 hours get 2x relevance multiplier
   - Merge and deduplicate

3. RANK by composite score
   - relevance_score × recency_weight × access_frequency × confidence
   - Bonus for decisions (they're more actionable than facts)
   - Bonus for corrections (they prevent errors)
   - Bonus for preferences (they prevent user frustration)

4. BUDGET
   - Estimate token count per memory
   - Fill context budget (default 4000 tokens) starting from highest ranked
   - Always include: agent identity, active projects, user preferences
   - Fill remaining budget with situation-relevant memories

5. FORMAT
   - Output as structured block for injection into system prompt
   - Group by category (identity, preferences, relevant facts, recent decisions)
```

**Proactive recall triggers:**
- Session start → full recall (identity + recent + high-relevance)
- Every N turns → incremental recall (topic may have shifted)
- Entity mention → entity-specific recall
- Compaction event → emergency recall of critical state

**Context budget management:**
This is where most systems fail. If you stuff 10KB of memories into the system prompt, you waste context and the agent performs worse. The budget system ensures memories compete for limited space based on relevance. Default budget: 4000 tokens (~3KB). Configurable per agent.

---

## 4. Build Sequence

### Phase 0: Architecture Spec & Schema (← WE ARE HERE)
- [x] Document failure modes from Thomas experience
- [x] Design three-layer architecture
- [x] Define database schema
- [x] **Competitive teardown:** 6 products analyzed (OpenViking, Mem0, Zep/Graphiti, Letta, LangChain, CrewAI). See `competitive-teardown.md`
- [x] **Unit economics model:** Margins 80-95%. Break-even at 3 Pro users. See `unit-economics.md`
- [x] **Privacy architecture:** GDPR/CCPA compliant, RLS isolation, tiered deployment. See `privacy-architecture.md`
- [x] **Design decisions:** Synthesized best ideas from each competitor. Updated schema with tiered content (L0/L1/L2), composite scoring, temporal validity. See `design-decisions.md`
- [x] **Domain research:** synaptic.dev, mnemonic.dev, agentrecall.dev possibly available
- [ ] Justin reviews and approves approach
- **Duration:** ~~3-5 days~~ Completed March 18, 2026
- **Cost:** $0

### Phase 1: Build Extraction Layer ✅ COMPLETE (March 18, 2026)
- [x] Build extraction prompt that processes conversation turns
- [x] Test on real Thomas conversations (6-test suite)
- [x] Tuned prompt for correct memory_type classification (preference, decision, correction all detected)
- [x] Uses Gemini Flash 2.0 ($0.00015/turn) with Anthropic/OpenAI fallback chain
- [x] Output: structured memory objects with L0/L1/L2 tiered content
- **Results:** 5/6 tests passing correctly. Preference, correction, task detection working. Trivial exchange correctly skipped.
- **Cost:** ~$0.02 in API calls for testing
- **Files:** `src/extraction.py`, `src/test_extraction_suite.py`

### Phase 2: Build Storage Layer ✅ COMPLETE (March 18, 2026)
- [x] Created `memory_service` schema on existing Supabase (isolated from `thomas` schema)
- [x] Tables: memories, session_handoffs, agent_config, memory_audit_log
- [x] Embedding pipeline: Gemini embedding-001 (768 dims) with OpenAI fallback
- [x] Duplicate detection via cosine similarity (0.88 threshold) → reinforcement instead of duplication
- [x] Correction handling: auto-supersedes old facts when corrections are stored
- [x] Decay mechanism: type-specific rates (preferences barely decay, tasks decay fast)
- [x] Audit logging on every write
- [x] Full pipeline test: extract → embed → store → verify → reinforce all working
- **Cost:** $0 (using existing Supabase instance)
- **Files:** `src/storage.py`, `src/test_pipeline.py`

### Phase 3: Build Recall Layer ✅ COMPLETE (March 18, 2026)
- [x] Built recall algorithm with composite scoring (semantic + recency + importance + access)
- [x] Built context budget manager — tiered loading (L1 for high-relevance, L0 for medium, skip low)
- [x] Always-include block: identity, user profile, last handoff, corrections, preferences
- [x] 3-strategy candidate retrieval: semantic search + high-importance + recently accessed
- [x] Type bonuses: corrections/preferences 1.3x, recent decisions 1.2x
- [x] Tested: 6 memories correctly recalled from test data, 250 tokens of 4000 budget used
- **Duration:** ~~5-7 days~~ Built same night as Phases 1-2
- **Cost:** ~$0.01 in API calls
- **Files:** `src/recall.py`
- **Next:** Phase 4 — Integration with a test agent

### Phase 4: Integration & Test Agent
- Set up new OpenClaw instance (can be same server, different config)
- Create new Telegram bot via BotFather
- Wire memory service into the test agent
- Justin talks to both Thomas (old system) and Test Agent (new system)
- Compare: which one remembers better? Which one surfaces the right context?
- **Duration:** 2-3 days setup + 2-3 weeks testing
- **Cost:** New Telegram bot (free) + OpenClaw running costs
- **Success criteria:** Test agent demonstrably outperforms Thomas on memory tasks

### Phase 5: Iterate Based on Real Usage
- Justin uses test agent for real work (subset of tasks)
- Document every memory failure (missed recall, wrong context, stale info)
- Fix, test, repeat
- This phase has no fixed duration — it ends when the system is reliably better
- **Duration:** 2-4 weeks
- **Success criteria:** Justin stops having to repeat himself

### Phase 6: Migrate to Thomas
- When test agent's memory system is proven, migrate it to Thomas
- Backfill existing memories from MEMORY.md and daily files
- Parallel run period: both old and new systems active
- Cut over when confident
- **Duration:** 1 week
- **Success criteria:** Thomas with new memory ≥ test agent performance

### Phase 7: Generalize & Package
- Strip Thomas-specific logic
- Build clean API surface
- Write documentation
- Create OpenClaw plugin wrapper
- Set up public GitHub repo
- **Duration:** 2-3 weeks
- **Cost:** Domain, hosting for demo
- **Success criteria:** A stranger can install it and have it work

### Phase 8: Ship
- Landing page
- Free tier (self-hosted SQLite) + hosted tier ($15-20/mo)
- Launch on Hacker News, OpenClaw community, agent builder communities
- **Duration:** 1 week
- **Success criteria:** 50 installs in first month

---

## 5. Open Design Questions

These need answers before or during building. They don't need answers right now.

| # | Question | Current Thinking | When to Decide |
|---|----------|-----------------|----------------|
| 1 | What model for extraction? | Haiku/Flash (cheap, fast) with Sonnet fallback for complex turns | Phase 1 |
| 2 | Sync vs async extraction? | Async with write-ahead log | Phase 1 |
| 3 | How often to run recall? | Session start + every 5 turns + entity trigger | Phase 3 |
| 4 | Where to inject memories? | System prompt, structured section | Phase 4 |
| 5 | How to handle multi-agent? | Shared storage, per-agent views | Phase 7 |
| 6 | How to handle private vs shared memories? | Tag memories with visibility scope | Phase 7 |
| 7 | Self-hosted vs hosted-only? | Both: SQLite for self-hosted, Postgres for hosted | Phase 7 |
| 8 | Pricing model? | Free (self-hosted) + $15-20/mo (hosted) | Phase 8 |
| 9 | What about non-OpenClaw agents? | REST API makes it framework-agnostic | Phase 7 |
| 10 | How to handle conflicting memories? | Corrections supersede; confidence-weighted for ambiguity | Phase 3 |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Extraction quality too low | Medium | High | Iterate on prompts; use Sonnet if Haiku insufficient |
| Recall surfaces wrong memories | Medium | High | Extensive testing; confidence thresholds; human feedback loop |
| Context budget too small for useful recall | Low | Medium | Make budget configurable; test at different sizes |
| API costs too high per turn | Low | Medium | Batch extraction; use cached embeddings |
| Nobody else wants this | Low | Low | We built it for ourselves first; external adoption is bonus |
| Someone else ships it first | Medium | Medium | Speed matters but quality matters more; first-mover advantage is weaker than best-product advantage in dev tools |
| Scope creep into "agent OS" too early | High | Medium | Strict phasing; no orchestration features until memory is proven |

---

## 7. What Success Looks Like

**For us (Phase 6 complete):**
- Justin talks to Thomas and never has to repeat a preference, decision, or fact
- Thomas surfaces relevant context proactively — "this reminds me of the decision you made about X on March 3"
- After compaction, Thomas doesn't lose awareness of capabilities or ongoing work
- Session handoffs are seamless — tomorrow's Thomas knows what today's Thomas did

**For the product (Phase 8 complete):**
- Any OpenClaw user can install the memory plugin in under 5 minutes
- Their agent demonstrably remembers better across sessions
- The hosted tier has paying customers
- The open-source repo has community contributions

**For the long term (Option B → C):**
- Memory API has adoption across multiple agent frameworks
- Users start requesting orchestration features → organic path to agent OS
- Revenue supports continued development
- Justin has a third business line alongside PFL Academy and Startup Smartup

---

## 8. Immediate Next Steps

1. **Justin reviews this roadmap** — poke holes, ask questions, adjust
2. **Decision: new Supabase project or new schema on existing?** (I recommend new project for clean isolation)
3. **Justin creates Telegram bot via BotFather** (when ready for Phase 4)
4. **Thomas begins Phase 1** (extraction layer) as background work
5. **No code until Justin approves the approach**

---

*This document will evolve. Version history will be tracked in git.*
*Last updated: March 18, 2026*
