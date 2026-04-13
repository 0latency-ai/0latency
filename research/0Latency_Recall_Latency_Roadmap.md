# 0Latency Recall Latency Optimization Roadmap

*Created: April 2026 | Informed by Opus architecture analysis + agent-native reframe*

---

## Context & Design Philosophy

The primary consumer of 0Latency is agents — autonomous, high-frequency, contextually-rich query generators running in parallel. Human users (Chrome extension, developer dashboard) benefit from everything built for agents. Design load is agent-native scale; humans get the benefits for free.

**The end-state architecture:** External embedding APIs are used only at write time (async, latency-insensitive). The entire read path is self-contained with no external dependencies. Latency becomes deterministic — the property that makes a memory layer a primitive rather than a feature.

**The S3 analogy:** S3 didn't win on minimum latency. It won on consistent latency, zero-config correctness, and graceful degradation. That's the target.

---

## Confirmed Bottleneck

| Layer | Latency | Status |
|---|---|---|
| pgvector HNSW search | ~60ms | ✅ Fast |
| Gemini/OpenAI embedding API | 2–3s | ❌ Primary bottleneck |
| Analytics DB retries (broken table) | ~4.5s | ❌ Blocking critical path |
| In-process LRU cache (pre-fix) | N/A | ❌ Broken — multi-worker isolation |

**Root cause:** The external embedding API call is 95%+ of cold-call latency. Any solution that doesn't reduce or eliminate that API call on the read path is optimizing the wrong thing.

---

## Revised Hit Rate Estimates (Agent-Native Traffic)

Agent queries are non-repetitive, contextually-rich, and analytical. Original estimates assumed human chat patterns. Revised:

| Approach | Human estimate | Agent-realistic estimate |
|---|---|---|
| Redis exact-match cache | 25–35% | 5–8% |
| Conversation fingerprinting | 30–50% additional | 10–15% additional |
| BM25 confidence routing | 40–60% | 15–25% |
| Requires full vector search | ~30% | ~65% |

**Implication:** With 65% of agent queries requiring vector search, the local embedding model is not optional — it determines the product's p50 latency.

---

## Sprint Roadmap

### ✅ Sprint 0 — Completed This Session

**Single-worker fix + embedding cache**
- Dropped API from 2 workers to 1 to fix in-process LRU cache isolation
- Confirmed: cache hits return in 0ms; cold recall at 2.7s (target met)
- Exposed new bottleneck: analytics DB retries adding 4.5s to every response

---

### 🔄 Sprint 1 — In Progress

**Analytics silent fail-fast (`main.py`)**
- `is_first_api_call`, `is_first_memory_recalled`, `check_activation_milestone` each retry 3x on DB failure
- Fix: wrap each in try/except, catch all exceptions, continue immediately
- No retry, no blocking, analytics failures are invisible to the caller
- **Model:** Haiku (mechanical, fully specified, no judgment required)
- **Expected impact:** Removes 4.5s of error-handling overhead from every response

---

### 📋 Sprint 2 — Next (1–2 days)

**Async analytics pipeline via Redis pub/sub**
- Emit an event onto Redis pub/sub immediately after recall response is assembled
- Separate `analytics_consumer.py` handles all analytics writes asynchronously
- API response returns to caller before any analytics write occurs
- Consumer fails silently on DB errors, logs without retrying
- **Why this matters long-term:** This event stream becomes the foundation for Phase 6 quality scoring, PostHog instrumentation, and weekly improvement reports
- **Model:** Sonnet (new file creation, Redis wiring, judgment calls on error handling)

---

### 📋 Sprint 3 — Core Architecture (2–3 days)

**Local embedding model on the read path**

This is the linchpin. Without it, 65% of agent queries hit an external API at 2–3s each. With it, p50 drops to ~35ms and the read path has zero external dependencies.

- **Model:** `all-MiniLM-L6-v2` (384 dimensions) or `gte-small` — CPU inference at 10–20ms, no GPU required
- **Architecture:** Store dual embedding columns per memory — local model + production model
 - Write time: embed with OpenAI/Gemini for maximum semantic fidelity (async, latency-insensitive)
 - Read time: embed with local model only — accept ~5–8% accuracy reduction, eliminate external dependency
- **CPU load:** Negligible at current scale (~50ms of one core per inference)
- **Expected latency profile post-implementation:**

| Percentile | Current | Post-local-model |
|---|---|---|
| p50 | 2–3s | ~35ms |
| p75 | 2–3s | ~45ms |
| p99 | 2–3s | ~80ms |
| p99.9 | 2–3s | ~150ms |

- **Model:** Sonnet (dual embedding storage, local model integration, query routing logic)

---

### 📋 Sprint 4 — Agent-Native Differentiators (1–2 days each)

**A. Batch recall endpoint**

Agents don't query one memory at a time. A planning agent needs 5–8 retrievals to construct a single action. Sequential calls at 35ms each = 175–280ms before reasoning starts.

- Accept multiple queries in a single API call
- Embed as a single batched local model call (10–20ms for batch of 8)
- Run parallel pgvector searches
- Return all result sets in ~50–60ms total
- **This is the benchmark slide.** No competitor offers this as a first-class operation.
- ZeroClick use case: single impression cycle triggers 3–5 parallel memory retrievals — batch recall is a prerequisite, not a nice-to-have

**B. Structured query parameters**

Force agents to express intent as natural language and hope the embedding captures it → shift to native structured params.

```
recall(
 query="pricing decisions",
 namespace="user-justin",
 time_window="last_30d",
 sort="chronological",
 limit=5
)
```

- Time-filtered semantic search without embedding a complex NL query
- Shifts more queries to metadata filtering + BM25 fast path
- Reduces the 65% vector-search bucket back toward favorable distribution
- Agents shouldn't think about retrieval mechanics — that's the memory layer's job

---

### 📋 Sprint 5 — Optimization Layer (build on top of sound architecture)

**Hot cache (immediate context layer)**
- A small, frequently-updated memory segment (~500 chars) storing the most recent 3–5 exchanges of an active agent session
- Sits in front of long-term recall entirely — hits Redis at sub-millisecond before any embedding or vector search occurs
- Rationale: within a session, the most recent context is almost always more relevant than anything in long-term storage; forcing a full embedding round-trip for every turn is unnecessary
- TTL tied to session lifecycle, not a fixed window
- Directly addresses turn-by-turn recall latency without touching the vector search path at all
- *Credit: Karpathy LLM Wiki method — the "hot cache" concept maps cleanly onto agent session architecture*

**Redis embedding cache**
- Key: SHA256 of normalized query text
- Value: serialized embedding vector
- TTL: 24–72 hours
- Normalize before hashing (lowercase, strip whitespace) to increase hit rates
- Catches the 5–8% of agent queries that do repeat (system-level, identity anchors, capability checks)

**BM25 confidence routing**
- Every recall hits BM25 first (sub-10ms via tsvector/GIN indexes)
- Confidence gate: if top BM25 score exceeds threshold and gap between #1 and #5 is sufficient → return immediately, skip embedding
- Parallel-fire variant: return BM25 results immediately, let vector search run async to upgrade if materially different
- Every query gets sub-10ms initial results; vector search only matters when it finds something BM25 missed

---

## Target State

> Consistent sub-100ms recall with zero external dependencies on the read path, a query API that matches how agents actually think, and batch operations that treat parallel retrieval as the common case.

**Competitive claim once Sprints 3–4 are complete:** Cold-call p50 under 50ms, p99 under 100ms, no external API on the read path — a claim Mem0, Zep, and LangMem cannot currently make.

---

## Model Selection Guide for Claude Code Tasks

| Task type | Model |
|---|---|
| Mechanical, fully specified (wrap in try/except, rename, simple edit) | Haiku |
| Standard coding, multi-file, some judgment required | Sonnet |
| Architecture decisions, deep debugging, new system design | Opus (in chat, not Claude Code) |

*Discipline on this alone significantly reduces token burn on execution work.*
