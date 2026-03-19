# Design Decisions — Informed by Competitive Teardown

**Date:** March 18, 2026
**Status:** Draft — synthesized from competitive analysis

---

## What We're Taking From Each Competitor

### From OpenViking: Tiered Context Loading
Their L0/L1/L2 approach is validated and works (35% → 52% task completion with fewer tokens). We adopt this:
- **L0 (Headline):** One-line fact. ~10-20 tokens. Always loadable.
- **L1 (Context):** Fact + context + source. ~50-100 tokens. Loaded when relevant.
- **L2 (Full):** Complete memory with all metadata, original text, relationships. ~200-500 tokens. Loaded on-demand.

**Our improvement over OpenViking:** Add temporal weighting to tier selection. Recent L1s get loaded more aggressively than old L1s. OpenViking treats all tiers equally regardless of age.

### From CrewAI: Composite Relevance Scoring
Their blended scoring is the right architecture:
```
composite_score = (semantic_weight × similarity) + (recency_weight × recency_score) + (importance_weight × importance)
```
- `semantic_weight`: default 0.4
- `recency_weight`: default 0.35
- `importance_weight`: default 0.25
- `recency_half_life_days`: configurable, default 14 days

**Our improvement over CrewAI:** Add `access_frequency` as a fourth signal. Memories that get recalled often are demonstrably important, regardless of what the LLM scored them at extraction time. Also add reinforcement — if the same fact is extracted again from a later conversation, its importance increases.

### From Zep/Graphiti: Temporal Fact Validity
Facts change. Zep's `valid_at` / `invalid_at` model is elegant:
- "Justin's depository selection is Self" → valid_at: March 15, invalid_at: March 18
- "Justin's depository selection is Archway" → valid_at: March 18, invalid_at: null

**Our implementation:** Add `valid_from` and `superseded_at` to the memories table. When a correction is extracted, the old memory gets `superseded_at` set and a `superseded_by` reference to the new memory. Old facts don't disappear — they become historical context.

### From Mem0: Simple API Surface
Their three-method API is why they have 50K stars:
- `memory.add(messages)` → extract and store
- `memory.search(query)` → retrieve relevant memories  
- `memory.get_all()` → dump everything

**Our API:** Same simplicity for the basic case, with power underneath:
- `memory.ingest(conversation_turn)` → extract and store (runs on every turn)
- `memory.recall(context, budget=4000)` → proactive, budget-aware retrieval
- `memory.list(filters)` → browse/manage
- `memory.forget(id)` → delete
- `memory.export()` → full data export

The key difference: `recall()` takes a token budget and returns a pre-formatted context block. Mem0's `search()` returns raw results and leaves formatting to the developer.

### From Letta: Session Handoff
Letta's full persistence of agent state across sessions is worth adopting:
- At session end (or compaction), write a structured handoff record
- At session start, load the most recent handoff + relevant memories
- Handoff includes: what happened, decisions made, open threads, current projects

**Our implementation:** The `session_handoffs` table in our schema. Extraction runs on session boundaries to capture state, not just facts.

---

## What We're NOT Doing (Yet)

| Feature | Why Not |
|---------|---------|
| Knowledge graph (Zep/Graphiti style) | Adds massive complexity. Facts with temporal metadata + embeddings cover 90% of use cases. Graph is Phase 7+ if needed. |
| Agent-managed memory (Letta style) | Unreliable — depends on LLM choosing to save things. System-managed extraction is more consistent. |
| Full agent platform (Letta style) | We're a library/service, not a platform. Framework-agnostic is our positioning. |
| Vision/multimodal memory (OpenViking) | V1 is text-only. Multimodal is Phase 7+. |
| Custom entity types (Zep) | Over-engineering for V1. Simple type field (fact/decision/preference/task/correction) covers the core use cases. |

---

## Updated Schema (Incorporating Learnings)

```sql
-- Core memory atoms with tiered content + temporal validity
CREATE TABLE memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL,
  
  -- Tiered content (OpenViking-inspired)
  headline TEXT NOT NULL,           -- L0: one-line summary (~10-20 tokens)
  context TEXT NOT NULL,            -- L1: fact + context + source (~50-100 tokens)
  full_content TEXT NOT NULL,       -- L2: complete memory with all detail (~200-500 tokens)
  
  -- Classification
  memory_type TEXT NOT NULL,        -- fact, decision, preference, task, correction, relationship
  entities TEXT[],                  -- people, projects, orgs mentioned
  project TEXT,                     -- optional project association
  categories TEXT[],               -- auto-inferred tags (CrewAI-inspired)
  scope TEXT,                       -- hierarchical path e.g. '/pfl-academy/oklahoma' (CrewAI-inspired)
  
  -- Scoring signals
  importance FLOAT DEFAULT 0.5,     -- LLM-assigned at extraction (0-1)
  confidence FLOAT DEFAULT 0.8,     -- extraction confidence (0-1)
  relevance_score FLOAT DEFAULT 1.0,-- composite score, updated on access
  access_count INT DEFAULT 0,       -- how often recalled
  reinforcement_count INT DEFAULT 1,-- times this fact was re-extracted from new conversations
  
  -- Temporal (Zep-inspired)
  valid_from TIMESTAMPTZ DEFAULT now(),  -- when this fact became true
  superseded_at TIMESTAMPTZ,              -- when this fact was replaced
  superseded_by UUID REFERENCES memories(id),
  
  -- Embedding
  embedding vector(1536),
  
  -- Provenance
  source_session TEXT,
  source_turn TEXT,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  last_accessed TIMESTAMPTZ,
  
  -- Extensible
  metadata JSONB
);

-- Indexes
CREATE INDEX idx_memories_agent ON memories(agent_id);
CREATE INDEX idx_memories_type ON memories(agent_id, memory_type);
CREATE INDEX idx_memories_scope ON memories(agent_id, scope);
CREATE INDEX idx_memories_relevance ON memories(agent_id, relevance_score DESC);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);

-- Session handoffs (Letta-inspired)
CREATE TABLE session_handoffs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL,
  session_key TEXT NOT NULL,
  summary TEXT NOT NULL,
  decisions_made JSONB,
  open_threads JSONB,
  active_projects JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Agent configuration
CREATE TABLE agent_config (
  agent_id TEXT PRIMARY KEY,
  context_budget INT DEFAULT 4000,         -- max tokens for memory injection
  recency_weight FLOAT DEFAULT 0.35,       -- scoring weight
  semantic_weight FLOAT DEFAULT 0.4,       -- scoring weight
  importance_weight FLOAT DEFAULT 0.15,    -- scoring weight
  access_weight FLOAT DEFAULT 0.1,         -- scoring weight (our addition)
  recency_half_life_days INT DEFAULT 14,   -- decay rate
  extraction_model TEXT DEFAULT 'gemini-flash-2.0',
  embedding_model TEXT DEFAULT 'text-embedding-3-small',
  identity JSONB,
  user_profile JSONB,
  metadata JSONB
);

-- Audit log (privacy requirement)
CREATE TABLE memory_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL,
  action TEXT NOT NULL,  -- 'extract', 'recall', 'delete', 'update', 'export'
  memory_id UUID,
  details JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Recall Algorithm (Updated)

```
FUNCTION recall(agent_id, conversation_context, budget_tokens=4000):

  1. LOAD agent_config for weights and budget
  
  2. ALWAYS INCLUDE (deducted from budget first):
     - Agent identity (from agent_config.identity)
     - User profile (from agent_config.user_profile)
     - Latest session handoff summary
     - Active corrections (superseded_at IS NULL, memory_type='correction')
     ≈ 500-1000 tokens typically
  
  3. EXTRACT context signals:
     - Entities mentioned in recent conversation
     - Current project/topic (inferred)
     - Embed the last 3 conversation turns
  
  4. CANDIDATE RETRIEVAL (cast a wide net):
     a. Semantic search on conversation embedding → top 50
     b. Entity match → all memories mentioning detected entities
     c. Scope match → all memories in detected project scope
     d. High-importance → all memories with importance > 0.8
     e. Recently accessed → memories accessed in last 48 hours
     f. Merge, deduplicate
  
  5. SCORE each candidate:
     semantic_sim = cosine_similarity(memory.embedding, context_embedding)
     recency = exp(-0.693 × days_since_created / half_life_days)
     importance = memory.importance × (1 + 0.1 × memory.reinforcement_count)
     access_freq = min(memory.access_count / 10, 1.0)  -- cap at 1.0
     
     composite = (semantic_weight × semantic_sim) 
               + (recency_weight × recency) 
               + (importance_weight × importance) 
               + (access_weight × access_freq)
     
     -- Bonuses
     IF memory_type IN ('correction', 'preference'): composite *= 1.3  -- prevent errors/frustration
     IF memory_type = 'decision' AND days_since < 7: composite *= 1.2  -- recent decisions matter
     IF superseded_at IS NOT NULL: composite = 0  -- never return superseded facts
  
  6. RANK by composite score (descending)
  
  7. FILL budget using tiered loading:
     remaining_budget = budget_tokens - always_include_tokens
     result = []
     
     FOR each candidate (ranked):
       IF remaining_budget <= 0: BREAK
       
       IF composite > 0.7:
         -- High relevance: include L1 (context level)
         tokens = estimate_tokens(candidate.context)
       ELSE:
         -- Medium relevance: include L0 (headline only)
         tokens = estimate_tokens(candidate.headline)
       
       IF tokens <= remaining_budget:
         result.append(candidate at appropriate tier)
         remaining_budget -= tokens
         UPDATE candidate SET last_accessed = now(), access_count = access_count + 1
     
  8. FORMAT as structured block:
     """
     ## Agent Memory Context
     ### Identity
     {identity block}
     ### User Profile  
     {user profile block}
     ### Recent Session
     {last handoff summary}
     ### Relevant Context
     {ranked memories, formatted by tier}
     ### Active Corrections
     {corrections to prevent errors}
     """
  
  9. RETURN formatted block (inject into system prompt)
```

---

## Product Name Brainstorm

The name should convey: memory, persistence, intelligence, lightweight.

| Name | Domain Available? | Notes |
|------|------------------|-------|
| **Engram** | engram.ai (likely taken) | Neuroscience term for a memory trace. Perfect metaphor. |
| **Mnemos** | mnemos.ai / mnemos.dev | Greek for memory (root of "mnemonic"). Distinctive. |
| **Cortex** | cortex.dev (likely taken) | Brain region for memory. Might be too generic. |
| **Anamnesis** | long | Philosophical term for recollection. Too academic. |
| **Retain** | retain.ai (likely taken) | Clear, verb-based. Simple. |
| **Recall** | recall.ai (definitely taken) | Too generic. |
| **Engrave** | engrave.ai | "Engraved in memory." Action-oriented. |
| **Synaptic** | synaptic.dev | Neural connections. Memory-adjacent. |
| **Imprint** | imprint.ai | Memory formation. Clean. |
| **Ponder** | ponder.ai (likely taken) | Reflective. Doesn't scream "memory." |

**Domain availability check (March 18, 2026):**
- engram.ai → taken (GitHub Pages)
- mnemos.ai → taken
- mnemos.dev → taken
- imprint.ai → taken
- synaptic.dev → **possibly available** ✅
- mnemonic.dev → **possibly available** ✅
- agentrecall.dev → **possibly available** ✅
- engram.dev → taken
- agentmem.dev → taken

**Top picks with available domains:** Synaptic (.dev), Mnemonic (.dev), AgentRecall (.dev)

Justin to weigh in on name preference before we commit.

---

*Last updated: March 18, 2026*
