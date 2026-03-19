# Competitive Teardown: AI Agent Memory Systems

*Compiled: March 18, 2026*

---

## Table of Contents
1. [OpenViking (Volcengine/ByteDance)](#1-openviking)
2. [Mem0](#2-mem0)
3. [Zep](#3-zep)
4. [Letta (formerly MemGPT)](#4-letta)
5. [LangChain Memory / Deep Agents](#5-langchain-memory)
6. [CrewAI Memory](#6-crewai-memory)
7. [Other Notable Entrants](#7-other-notable-entrants)
8. [Differentiation Matrix](#8-differentiation-matrix)
9. [Strategic Takeaways for Our Approach](#9-strategic-takeaways)

---

## 1. OpenViking

**GitHub:** [volcengine/OpenViking](https://github.com/volcengine/OpenViking) — ⭐ 15,769 stars | 1,068 forks | Created Jan 2026

### What It Is

OpenViking is an open-source "Context Database" for AI agents developed by Volcengine (ByteDance's cloud division). Launched in early 2026, it abandons traditional flat-storage RAG in favor of a **file system paradigm** that organizes all agent context — memory, resources, and skills — into a hierarchical virtual filesystem accessible via a `viking://` protocol. It positions itself as a unified context management layer, not just a memory store.

### Architecture

- **File System Paradigm:** All context is organized as files and directories in a virtual filesystem. Memory, resources (documents, data), and skills (tool definitions) all live in the same tree structure.
- **Tiered Context Loading (L0/L1/L2):**
  - **L0 (Summary):** Ultra-compact summaries for quick orientation. Minimal tokens.
  - **L1 (Overview):** Expanded context with key details. Medium token budget.
  - **L2 (Full):** Complete content when deep context is needed.
  - Context is loaded on-demand at the appropriate level, saving tokens significantly.
- **Storage:** Uses embedding models for vectorization + semantic retrieval. Supports Volcengine Doubao, OpenAI, Jina embeddings. VLM (vision-language model) for image/content understanding.
- **Extraction:** Automatic session management compresses conversations, extracts resource references and tool calls, and generates long-term memory. Self-iterating — the agent gets smarter over time.
- **Recall:** Directory-recursive retrieval combining directory positioning with semantic search. Supports visualization of retrieval trajectories for debugging.
- **Protocol:** `viking://` URI scheme for addressing any context node.

### What It Does Well

- **Closest to our three-layer approach.** The L0/L1/L2 tiered loading is almost exactly what we're building (summary → overview → full). This is the main competitor to watch.
- **Unified context management.** Doesn't just handle memory — handles resources and skills too. Single paradigm for everything an agent needs.
- **Observable retrieval.** Visualization of how context was retrieved and assembled. Debugging-first design.
- **Framework agnostic.** Already has an OpenClaw memory plugin. Works with multiple agent frameworks.
- **Self-evolving.** Automatic compression and memory extraction from conversations.
- **Open source (Apache 2.0).** Fully self-hostable.

### Where It Falls Short

- **Very new (Jan 2026).** Limited production battle-testing. Documentation still evolving.
- **ByteDance affiliation.** Some enterprises may have concerns about Chinese tech company origins (Volcengine is ByteDance's cloud arm), though the project is fully open-source.
- **Heavy infrastructure.** Requires Go 1.22+, C++ compiler (GCC 9+ / Clang 11+), Python 3.10+. Non-trivial to deploy compared to simpler solutions.
- **No managed cloud offering yet.** Self-hosted only as of March 2026.
- **Limited ecosystem integrations.** Fewer framework integrations than Mem0 or Zep currently.
- **No temporal dynamics.** No explicit decay, reinforcement, or time-weighted relevance scoring — context is either in the tree or not.

### Pricing

- **Free / Open Source** (Apache 2.0). No managed service. You pay for your own embeddings + LLM API calls.

### Adoption / Traction

- 15,769 GitHub stars in ~2.5 months — very fast growth, likely boosted by ByteDance's distribution.
- 1,068 forks.
- ByteDance internal usage (likely powers internal agent systems).
- OpenClaw plugin already exists (community/internal contribution).

### Comparison to Our Approach

OpenViking is the **most architecturally similar** to our three-layer design. Key differences:
- Their tiered loading (L0/L1/L2) maps closely to our extraction → storage → recall pipeline, but they frame it as a filesystem rather than a memory pipeline.
- They don't have **temporal dynamics** (decay, reinforcement). Our approach with time-weighted relevance is a differentiator.
- They unify memory/resources/skills; we're focused specifically on **memory** with deeper extraction intelligence.
- Their filesystem metaphor is elegant but may be overengineered for pure memory use cases.

---

## 2. Mem0

**GitHub:** [mem0ai/mem0](https://github.com/mem0ai/mem0) — ⭐ 50,303 stars | 5,605 forks | Created Jun 2023

### What It Is

Mem0 (pronounced "mem-zero") is a "universal memory layer for AI agents" that enhances AI assistants with persistent, personalized memory. Originally launched as EmbedChain (a RAG framework), it pivoted to become a dedicated memory layer. YC-backed with significant funding. Offers both an open-source package and a fully managed platform (api.mem0.ai). Claims +26% accuracy over OpenAI Memory on the LOCOMO benchmark, 91% faster responses, and 90% fewer tokens vs full-context approaches.

### Architecture

- **Memory Pipeline:**
  1. **Add:** Pass conversation messages to `memory.add()`. Mem0 uses an LLM to extract discrete facts/preferences from the conversation.
  2. **Store:** Facts are stored as individual memory records in a vector store. Supports multiple vector backends (Qdrant, Pinecone, ChromaDB, etc.). Also supports a **graph memory** mode (Pro plan) for relationship-aware storage.
  3. **Search:** `memory.search()` retrieves relevant memories via semantic similarity search over the vector store.
- **Memory Types:**
  - **User Memory:** Long-lived knowledge tied to a person (preferences, facts).
  - **Session Memory:** Short-lived context for the current task/channel.
  - **Agent Memory:** State specific to the agent itself (learned behaviors).
  - **Organizational Memory:** Shared context across multiple agents/teams.
- **Graph Memory (Pro):** Uses a knowledge graph layer on top of vector storage for relationship-aware retrieval. Available on Pro plan and above.
- **Extraction:** LLM-based automatic extraction of facts from conversations. No manual tagging required.
- **Recall:** Semantic search with optional metadata filters. Developer must explicitly call `memory.search()` and inject results into prompts.

### What It Does Well

- **Massive adoption.** 50K+ GitHub stars. Largest community in this space.
- **Simple API.** Three core methods: `add()`, `search()`, `get_all()`. Very low barrier to entry.
- **Multi-level memory.** User/session/agent/org separation is well-thought-out.
- **Auto-extraction.** LLM automatically pulls facts from conversations — no manual tagging.
- **Cross-platform SDKs.** Python, TypeScript/JavaScript, REST API.
- **Managed platform.** SOC 2, audit logs, enterprise features available.
- **Research-backed.** Published paper with benchmark results (LOCOMO).
- **Broad integrations.** LangChain, LangGraph, CrewAI, Vercel AI SDK, Chrome extension.

### Where It Falls Short

- **No proactive recall.** Developer must explicitly query memories and inject them. Mem0 doesn't automatically decide what context to include — it's pull, not push.
- **No context budget management.** Doesn't manage how much memory goes into the context window. Developer is responsible for `limit` parameter and prompt construction.
- **No temporal dynamics.** No decay, reinforcement, or time-weighted scoring. All memories are equally weighted regardless of age or access frequency.
- **Graph memory is paywalled.** Only available on Pro ($249/month) and above.
- **Flat memory structure.** Individual facts stored as independent records — no hierarchical organization or tiered loading.
- **OSS version is limited.** Graph memory, analytics, and advanced features are platform-only.

### Pricing

| Plan | Price | Memories | API Calls/mo |
|------|-------|----------|-------------|
| Hobby | Free | 10,000 | 1,000 |
| Starter | $19/mo | 50,000 | 5,000 |
| Pro | $249/mo | Unlimited | 50,000 |
| Enterprise | Custom | Unlimited | Unlimited |

Also supports usage-based pricing. Startup program offers 3 months free Pro for companies under $5M funding.

### Adoption / Traction

- **50,303 GitHub stars** — largest in the memory space by far.
- YC-backed (Y Combinator).
- Has raised funding (amount undisclosed publicly, but significant — YC + follow-on).
- Published research paper (arXiv:2504.19413).
- Chrome extension for cross-platform memory (ChatGPT, Perplexity, Claude).
- v1.0.0 released with API modernization.

### Comparison to Our Approach

- Mem0 handles extraction well but is **weak on recall intelligence and context budgeting** — exactly where our approach aims to differentiate.
- No tiered loading. All memories are flat facts retrieved by similarity.
- No proactive injection — developer must manually bridge memory → prompt.
- Our three-layer approach (extraction → storage → recall) covers the full pipeline; Mem0 covers extraction → storage but leaves recall to the developer.

---

## 3. Zep

**GitHub:** [getzep/zep](https://github.com/getzep/zep) — ⭐ 4,249 stars | 594 forks | Created Apr 2023
**Related:** [getzep/graphiti](https://github.com/getzep/graphiti) — ⭐ 23,935 stars | 2,357 forks

### What It Is

Zep is a "context engineering platform" that assembles personalized, relationship-aware context from multiple data sources — chat history, business data, documents, and app events — for AI agents. It has pivoted from a simple memory store to a full context assembly platform built on top of **Graphiti**, their open-source temporal knowledge graph framework. Zep Cloud is the managed service; the open-source Community Edition has been **deprecated** (moved to a `legacy/` folder) in favor of the cloud-only model.

### Architecture

- **Graphiti (Temporal Knowledge Graph):** The core engine. Builds and maintains knowledge graphs that track how facts change over time. Each fact has `valid_at` and `invalid_at` dates.
  - **Entities (nodes):** People, products, concepts — with summaries that evolve.
  - **Facts/Relationships (edges):** Triplets (Entity → Relationship → Entity) with temporal validity windows.
  - **Episodes (provenance):** Raw data as ingested — ground truth. Every derived fact traces back here.
  - **Custom Types:** Developer-defined entity and edge types via Pydantic models.
- **Context Assembly:** Pre-formatted, relationship-aware context blocks optimized for LLMs. Includes user summaries + relevant facts from the knowledge graph.
- **Data Ingestion:** Feed chat messages, business data, JSON, and events. Zep automatically extracts relationships and maintains the temporal graph.
- **Retrieval:** Hybrid retrieval (semantic + keyword + graph traversal). `graph.search()` for low-level queries, `thread.get_user_context()` for pre-assembled context blocks.
- **Fact Invalidation:** When new data contradicts a prior fact, the old fact is marked with an `invalid_at` timestamp — not deleted.

### What It Does Well

- **Temporal awareness is best-in-class.** Only system that seriously tracks how facts change over time with validity windows. Published paper on temporal knowledge graphs (arXiv:2501.13956).
- **Context assembly, not just retrieval.** Zep pre-formats context blocks optimized for LLMs. This is closer to proactive recall than any competitor.
- **Graph-based understanding.** Relationships between entities, not just isolated facts.
- **Sub-200ms latency.** Production-ready performance claims.
- **Enterprise-grade.** SOC 2 Type II, HIPAA compliance, audit logs.
- **Graphiti is a strong OSS project.** 24K stars, active development, MCP server available.
- **Multi-framework.** SDKs for Python, TypeScript, Go. Integrations with LangChain, LlamaIndex, AutoGen.

### Where It Falls Short

- **Open-source is effectively dead.** Community Edition deprecated. Graphiti is OSS but Zep itself is cloud-only. This is a significant risk for self-hosting requirements.
- **No self-hosted option** (current). Enterprise BYOC (Bring Your Own Cloud) exists but is managed by Zep.
- **Complex pricing.** Credit-based system where an "Episode" = 1 credit, with size multipliers. Not intuitive.
- **Heavy infrastructure dependency.** Requires Neo4j (for Graphiti graph store) + embedding models + LLMs.
- **No auto-extraction from conversations** in the traditional sense — you feed data in, and Zep builds the graph, but it's not passively monitoring agent conversations.
- **Graphiti ≠ Zep.** The good stuff (temporal graphs) is in Graphiti (OSS), but Zep Cloud adds the managed layer, context assembly, and enterprise features.

### Pricing

| Plan | Price | Credits/mo | Rate Limit |
|------|-------|-----------|-----------|
| Free | $0 | 1,000 | Limited |
| Flex | $25/mo | 20,000 | 600 RPM |
| Flex Plus | $475/mo | 300,000 | 1,000 RPM |
| Enterprise | Custom | Custom | Custom |

Credits: 1 credit per Episode (any data object). Episodes > 350 bytes cost multiple credits. Unused credits roll over 60 days.

### Adoption / Traction

- Zep repo: 4,249 stars (modest, declining since OSS deprecation).
- Graphiti repo: 23,935 stars (strong, growing fast — 2x Zep).
- Raised funding (undisclosed amount).
- SOC 2 Type II certified.
- Published academic paper.
- Currently hiring engineers and DevRel.

### Comparison to Our Approach

- Zep's **temporal dynamics** are superior to what most competitors offer and is an area we should study carefully.
- Their **context assembly** (pre-formatted blocks) is close to our recall layer's proactive injection concept.
- However, they've abandoned open-source — our self-hosted approach is a differentiator.
- Their architecture is graph-heavy; our approach is lighter-weight with the three-tier extraction → storage → recall pipeline.
- **Graphiti** specifically is worth studying for temporal fact management patterns.

---

## 4. Letta (formerly MemGPT)

**GitHub:** [letta-ai/letta](https://github.com/letta-ai/letta) — ⭐ 21,651 stars | 2,275 forks | Created Oct 2023

### What It Is

Letta is a platform for building "stateful agents" — AI systems with advanced memory that can learn and self-improve over time. Born from the MemGPT academic paper (2023), which introduced the concept of virtual context management for LLMs (inspired by OS virtual memory / paging). The core idea: give agents tools to manage their own memory, so they can decide what to remember, forget, and recall. Now positioned as a full agent platform with memory as a core differentiator.

### Architecture

- **Memory Blocks:** Memory is organized into labeled blocks (strings) that are pinned to the system prompt. Agents have tools to read and write their own memory blocks.
  - **Core Memory:** Always in context. Typically includes `human` block (user info) and `persona` block (agent identity).
  - **Archival Memory:** Out-of-context storage. Agent can search and retrieve from archival using built-in tools.
  - **Recall Memory:** Conversation history. Agent can search past messages.
  - **Shared Memory Blocks:** Blocks that multiple agents can read/write for shared state.
- **Self-Editing Memory:** The key differentiator. Agents have tools like `core_memory_append`, `core_memory_replace`, `archival_memory_insert`, `archival_memory_search`. The agent decides what to remember.
- **Compaction:** When the context window fills up, Letta compacts/evicts older messages but preserves them in the database. Old messages are still searchable via recall tools.
- **Persistence:** All state (memories, messages, reasoning, tool calls) persisted to a database. Nothing is ever truly lost.
- **Multi-Agent:** Shared memory blocks enable cross-agent state sharing. Built-in tools for sync/async inter-agent messaging.

### What It Does Well

- **Agent-driven memory.** The agent decides what's important — not the developer, not a static rule. This is philosophically elegant and works well with capable models.
- **Virtual context management.** Inspired by OS memory management (paging). Sophisticated approach to context window limitations.
- **Full persistence.** Everything is stored — messages, tool calls, reasoning. Agents can revisit anything.
- **Multi-agent support.** Shared memory blocks + message passing tools. Best multi-agent memory support in the space.
- **Active development.** Regular releases, Letta Code CLI, model leaderboard.
- **Self-hosted + Cloud.** Both options available. API with Python/TypeScript SDKs.
- **Academic foundation.** MemGPT paper is well-cited and respected.

### Where It Falls Short

- **Agent-dependent extraction.** Memory quality depends entirely on the LLM's judgment about what to save. No structured extraction pipeline — it's ad-hoc tool calls.
- **No automatic extraction.** The agent must actively choose to use memory tools. If it forgets to save something, it's lost from core memory (though still in message history).
- **No temporal dynamics.** No decay, reinforcement, or time-weighting. Memory blocks are static strings that the agent manually edits.
- **No context budget management.** Beyond basic compaction, there's no intelligent management of how much context to load. Agent must manually search archival.
- **Platform lock-in.** Letta is a full agent platform, not a memory library. You build your agent inside Letta. Can't easily use Letta memory in a non-Letta agent.
- **Complexity.** The agent-as-memory-manager approach adds inference overhead. Every memory operation is an LLM call.
- **Pricing creep.** API plan charges per active agent + per-second tool execution. Can get expensive at scale.

### Pricing

| Plan | Price | Agents |
|------|-------|--------|
| Free | $0 | Limited |
| Pro | $20/mo | Up to 20 |
| Max Lite | $100/mo | Up to 50 |
| Max | $200/mo | Unlimited-ish |
| API | $20/mo + $0.10/active agent/mo + $0.00015/sec tool execution | Unlimited |

LLM usage is pay-as-you-go on top. Recommends Opus 4.5 and GPT-5.2 for best performance.

### Adoption / Traction

- 21,651 GitHub stars.
- 2,275 forks.
- MemGPT paper well-cited in the academic community.
- Raised funding (undisclosed, but enough for a team and platform).
- Active Discord community.
- Letta Code CLI launched for terminal-based agent use.

### Comparison to Our Approach

- Letta's philosophy is **agent manages its own memory** vs our philosophy of **system manages memory for the agent**.
- Our automatic extraction pipeline removes the burden from the LLM — more reliable, less inference overhead.
- Our tiered recall (summary → overview → full) is more structured than Letta's "agent searches when it feels like it."
- Letta's shared memory blocks for multi-agent are worth studying.
- Their full-platform approach means they're not really competing in the "memory as a library" space where we operate.

---

## 5. LangChain Memory / Deep Agents

**GitHub:** [langchain-ai/langchain](https://github.com/langchain-ai/langchain) — ⭐ 130,089 stars | 21,451 forks

### What It Is

LangChain is the dominant open-source framework for building LLM applications. Its memory modules were historically the go-to for adding conversation memory to chains and agents. However, LangChain has significantly evolved: the legacy `ConversationBufferMemory` / `ConversationSummaryMemory` classes are deprecated in favor of LangGraph's persistence layer and the new **Deep Agents** architecture, which includes built-in memory with automatic compression, virtual filesystems, and subagent spawning.

### Architecture

**Legacy Memory (Deprecated):**
- `ConversationBufferMemory` — stores full conversation history. Simple but token-heavy.
- `ConversationSummaryMemory` — LLM summarizes older messages. Saves tokens but lossy.
- `ConversationSummaryBufferMemory` — hybrid: recent messages verbatim + summary of older ones.
- `VectorStoreRetrieverMemory` — stores messages in a vector store, retrieves by similarity.
- `ConversationEntityMemory` — extracts and tracks entities from conversations.

**Current Approach (LangGraph + Deep Agents):**
- **LangGraph Persistence:** Checkpointer-based state persistence. Agent state is saved at each step and can be resumed.
- **Deep Agents:** "Batteries-included" agent architecture with:
  - Automatic compression of long conversations
  - Virtual filesystem for agent state
  - Subagent spawning for context isolation
  - Built on LangGraph for durable execution
- Memory is now a concern of the **agent architecture**, not a standalone module.

### What It Does Well

- **Massive ecosystem.** 130K+ stars. Most LLM developers have touched LangChain.
- **Educational value.** The legacy memory classes taught the industry how to think about conversation memory. Well-documented patterns.
- **Deep Agents is modern.** Automatic compression, virtual filesystem, subagent context isolation — these are meaningful capabilities.
- **LangGraph persistence.** Durable, checkpoint-based state management. Resume agents across sessions.
- **Model agnostic.** Works with any LLM provider.
- **LangSmith integration.** Tracing, debugging, evaluation.

### Where It Falls Short

- **Memory is not the product.** LangChain is an agent framework that happens to have memory. Memory is not their primary focus or differentiator.
- **Legacy modules are deprecated.** The old memory classes (which most tutorials reference) are no longer recommended. Migration path is non-trivial.
- **No dedicated memory extraction.** Deep Agents compresses conversations but doesn't extract structured facts or build knowledge graphs.
- **No temporal dynamics.** No decay, reinforcement, relevance scoring.
- **No standalone memory service.** Can't use LangChain memory outside of LangChain/LangGraph.
- **Framework lock-in.** Deep Agents only work within the LangChain ecosystem.
- **Abstraction overhead.** LangChain's abstraction layers can be heavy for simple use cases.

### Pricing

- **Open Source** (MIT License). LangChain, LangGraph, Deep Agents are all free.
- **LangSmith** (observability/tracing) has paid plans but is not required.
- No managed memory service.

### Adoption / Traction

- 130,089 GitHub stars — largest in the entire AI dev tools space.
- Massive funding (LangChain Inc. has raised $25M+ Series A from Sequoia).
- Deep Agents is relatively new — adoption still ramping.
- Dominant framework but memory is a small part of the offering.

### Comparison to Our Approach

- LangChain proved the market need for agent memory but never built a dedicated solution.
- Their memory modules are educational but primitive compared to what we're building.
- Deep Agents' auto-compression is similar to our extraction layer but less sophisticated.
- Our approach is **framework-agnostic** and **memory-first** — the opposite of LangChain's framework-first approach.
- There's an opportunity to be the memory layer that LangChain users adopt.

---

## 6. CrewAI Memory

**GitHub:** [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) — ⭐ 46,479 stars | 6,270 forks

### What It Is

CrewAI is a multi-agent orchestration framework with a recently overhauled unified memory system. Rather than separate short-term, long-term, entity, and external memory types (the old approach), CrewAI now offers a single `Memory` class that uses an LLM to analyze content when saving (inferring scope, categories, and importance) and supports adaptive-depth recall with composite scoring.

### Architecture

- **Unified Memory Class:** Single `Memory()` API replaces the old fragmented memory types.
- **Store:** `memory.remember(text)` — LLM analyzes content and infers:
  - **Scope:** Hierarchical path (like a filesystem, e.g., `/project/alpha`, `/agent/researcher`).
  - **Categories:** Auto-generated tags.
  - **Importance:** Numerical importance score.
- **Recall:** `memory.recall(query)` — composite scoring blending:
  - **Semantic similarity** (embedding cosine distance)
  - **Recency** (exponential decay with configurable half-life)
  - **Importance** (LLM-assigned weight)
- **Hierarchical Scopes:** Memories organized in a tree structure. Scopes are inferred by the LLM or set explicitly. Supports `memory.scope("/agent/researcher")` for subtree views.
- **Extraction:** `memory.extract_memories(text)` pulls atomic facts from longer text.
- **Scoring Weights:** Configurable `recency_weight`, `semantic_weight`, `importance_weight`, `recency_half_life_days`.
- **Four Integration Modes:** Standalone, with Crews, with Agents, inside Flows.

### What It Does Well

- **Composite scoring is sophisticated.** Blending semantic similarity + recency + importance is exactly right. Configurable weights and half-life are thoughtful.
- **Hierarchical scopes.** LLM-inferred scope tree is elegant. Self-organizing structure without schema design.
- **Fact extraction built in.** `extract_memories()` pulls atomic facts from text — auto-extraction out of the box.
- **Crew integration.** After each task, crew auto-extracts facts; before each task, agent auto-recalls context. This is **proactive recall** within the CrewAI framework.
- **Recency decay.** Has actual temporal dynamics with configurable half-life. One of the few systems with this.
- **Clean API.** `remember()`, `recall()`, `forget()`, `tree()`, `info()` — intuitive and complete.

### Where It Falls Short

- **CrewAI-locked.** Memory system is deeply integrated into CrewAI's Crew/Agent/Flow model. Can't use it standalone outside CrewAI (well, the `Memory` class works standalone, but the proactive recall only works within Crews).
- **No managed memory service.** Part of CrewAI framework, not a standalone product.
- **No temporal fact tracking.** Has recency decay but doesn't track fact validity windows (when something became true/false).
- **No graph memory.** Flat fact storage with scope hierarchy. No relationship awareness between facts.
- **LLM-dependent scope inference.** Scope placement quality depends on the LLM. May produce inconsistent hierarchies.
- **No context budget management.** No explicit management of how much memory goes into the prompt. Uses `limit` parameter but no intelligent budgeting.
- **No knowledge graph or entity resolution.** Can't answer "what changed" or "how are X and Y related."

### Pricing

- **Free / Open Source** (Apache 2.0 for the framework).
- CrewAI Enterprise platform exists with paid plans (for crew deployment, monitoring) but memory is part of the open-source framework.

### Adoption / Traction

- 46,479 GitHub stars (for CrewAI overall — memory is a subsystem).
- 6,270 forks.
- Significant VC funding (CrewAI Inc.).
- Very active community.
- Memory was recently overhauled — the new unified system is weeks/months old.

### Comparison to Our Approach

- CrewAI's composite scoring (semantic + recency + importance) is the **closest to our temporal dynamics vision**.
- Their scope hierarchy is similar to OpenViking's filesystem approach.
- Key gap: no context budget management, no tiered loading (summary → overview → full).
- Their proactive recall (auto-inject before tasks) is something we should implement.
- Framework-locked. Our approach being framework-agnostic is a significant advantage.

---

## 7. Other Notable Entrants

### Cognee (cognee-ai/cognee)
- Open-source "memory engine for AI agents" using knowledge graphs.
- Extracts entities and relationships from data, builds a graph, retrieves via graph traversal.
- Less mature than the main competitors but growing.

### OpenAI Memory (ChatGPT)
- Built into ChatGPT. Auto-extracts facts from conversations. User can view/edit/delete memories.
- Not available as an API or library. Proprietary. Benchmark target (Mem0 claims +26% accuracy vs OpenAI Memory).

### Google Gemini Memory
- Google's approach with Gems and conversation memory in Gemini.
- Proprietary, API-accessible only within Google's ecosystem.

### Anthropic / Claude Memory (MCP + Projects)
- Claude's "Projects" feature provides persistent context. MCP (Model Context Protocol) enables external memory integration.
- Not a standalone memory product but MCP is becoming a standard for tool integration.

### Supermemory
- Open-source "memory layer for the internet." More consumer-focused (bookmarks, saved content) than agent-focused.
- Not a direct competitor for agent memory.

### LlamaIndex Memory
- LlamaIndex has conversation memory modules similar to LangChain's legacy approach.
- Buffer, summary, and vector-based memory. Not a standalone product.

---

## 8. Differentiation Matrix

| Dimension | OpenViking | Mem0 | Zep/Graphiti | Letta | LangChain | CrewAI |
|-----------|-----------|------|-------------|-------|-----------|--------|
| **Auto-extraction** | ✅ Auto from sessions | ✅ LLM extracts facts | ✅ Auto graph building | ⚠️ Agent must choose | ⚠️ Compression only | ✅ LLM extracts + infers scope |
| **Structured storage** | ✅ Filesystem hierarchy + embeddings | ⚠️ Flat facts + metadata | ✅ Temporal knowledge graph | ⚠️ String blocks + archival | ❌ Raw messages or summaries | ✅ Scoped hierarchy + categories |
| **Proactive recall** | ✅ Tiered auto-loading (L0/L1/L2) | ❌ Dev must query + inject | ✅ Pre-assembled context blocks | ❌ Agent must search | ⚠️ Deep Agents auto-compress | ✅ Auto-inject before tasks (in Crews) |
| **Temporal dynamics** | ❌ No decay/reinforcement | ❌ No decay/reinforcement | ✅ Validity windows (valid_at/invalid_at) | ❌ No decay/reinforcement | ❌ No decay/reinforcement | ✅ Recency decay + importance scoring |
| **Context budget mgmt** | ✅ L0/L1/L2 tiered loading | ❌ Dev manages limits | ⚠️ Pre-formatted blocks (implicit) | ⚠️ Compaction only | ⚠️ Auto-compression | ❌ Dev manages limits |
| **Multi-agent support** | ⚠️ Shared filesystem | ⚠️ Agent-level memory type | ⚠️ Per-user graphs | ✅ Shared memory blocks + messaging | ⚠️ LangGraph state sharing | ✅ Crew-shared + agent-scoped memory |
| **Framework agnostic** | ✅ Standalone + plugins | ✅ Framework-agnostic library | ✅ Framework-agnostic API | ❌ Letta platform only | ❌ LangChain only | ❌ CrewAI only |
| **Self-hosted option** | ✅ Fully OSS | ✅ OSS (limited) + Cloud | ⚠️ Graphiti OSS, Zep Cloud-only | ✅ Self-hosted + Cloud | ✅ Fully OSS | ✅ Fully OSS |
| **Pricing** | Free (OSS) | Free → $249/mo → Enterprise | Free → $25/mo → $475/mo → Enterprise | Free → $20-200/mo → API plan | Free (OSS) | Free (OSS) |

### Legend
- ✅ = Strong / Native support
- ⚠️ = Partial / Limited support
- ❌ = Not supported or not applicable

---

## 9. Strategic Takeaways for Our Approach

### Where the Market Is

1. **Auto-extraction is table stakes.** Everyone (except LangChain and Letta) does LLM-based fact extraction. We must have this.
2. **Context budget management is the gap.** Only OpenViking (L0/L1/L2) has real context budget management. This is our biggest opportunity.
3. **Temporal dynamics are rare.** Only Zep (validity windows) and CrewAI (recency decay) address time. This is a differentiator.
4. **Proactive recall is underserved.** Most systems require the developer to manually query and inject. Automatic, intelligent context injection is a major value prop.
5. **Framework lock-in is a weakness.** CrewAI, Letta, and LangChain memories only work within their ecosystems. Framework-agnostic is a clear positioning advantage.

### Our Differentiation (Three-Layer: Extraction → Storage → Recall)

| Our Layer | What It Does | What Competitors Miss |
|-----------|-------------|----------------------|
| **Extraction** | Auto-extract structured facts from conversations/data | Most do this. Must be at least as good as Mem0/CrewAI. |
| **Storage** | Typed, hierarchical storage with temporal metadata | OpenViking has hierarchy. Zep has temporal. Nobody has both + types. |
| **Recall** | Proactive, budget-aware context injection with tiered loading | **This is the killer feature.** Only OpenViking has tiered loading. Nobody does proactive + budget-aware + temporal-weighted recall. |

### Key Competitive Threats

1. **OpenViking** — Most architecturally similar. Watch closely. ByteDance distribution power. But no temporal dynamics and very new.
2. **Mem0** — Market leader by adoption. Will likely add features we're building. Speed matters.
3. **CrewAI Memory** — Best composite scoring. But framework-locked. If they unbundle it, it's a threat.
4. **Zep/Graphiti** — Best temporal awareness. But cloud-only lock-in creates an opening for us.

### Recommendations

1. **Study OpenViking's L0/L1/L2 deeply.** Their tiered loading is the closest prior art. Learn from it, improve on it with temporal weighting.
2. **Steal CrewAI's scoring model.** Semantic + recency + importance composite scoring with configurable weights is the right approach.
3. **Study Graphiti's temporal patterns.** Validity windows on facts (valid_at/invalid_at) are elegant. Consider adopting.
4. **Be framework-agnostic from day one.** This is a clear positioning advantage over half the field.
5. **Context budget management is the pitch.** "The memory layer that manages its own token budget" — nobody else does this well.
6. **Ship fast.** OpenViking is 2.5 months old and already has 16K stars. The window for differentiation is narrowing.
