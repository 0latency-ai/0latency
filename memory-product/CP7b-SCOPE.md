# Checkpoint 7B Scope — session_checkpoint memory type and the auto-resume loop

**Date:** 2026-04-23
**Status:** 📋 Scope (not executed)
**Predecessor:** CP7a shipped 2026-04-21 (`memory_write` + `memory_add` live on `mcp.0latency.ai`); MCP unification shipped 2026-04-22 as v0.2.0 (HTTP/SSE + stdio on single codebase, 14 tools at parity)
**Track:** Product Feature Roadmap (Track 3)
**Target:** Replace hand-written handoff docs with automatic, hierarchical session summaries that surface on thread resumption.

---

## Executive summary

Today, every new Claude thread starts cold. The user or the prior agent writes a handoff doc by hand — that's literally how this conversation started ("Please use your native memory and 0latency to get up to speed"). The handoff doc exists because the raw memory atoms stored in 0Latency are high-volume and low-density — a new thread can recall them but can't quickly reconstruct the arc of the previous session from them.

CP7b introduces `memory_type="session_checkpoint"`: dense, summary-level memories that compress N turns of a thread into one structured record. Periodic mid-thread rollups plus an end-of-thread summary plus an auto-generated meta-summary at the start of each new thread in the same project. Together, these eliminate the handoff-doc step entirely.

Three additions turn CP7b from a data-layer feature into a product feature: recall becomes checkpoint-aware (hierarchical retrieval — dense summaries for navigation, atoms for precision), the self-improvement loop gets wired into summarization quality via `memory_feedback`, and a new `memory_resume` MCP tool exposes checkpoint-first recall as a first-class agent primitive.

CP7b ships L1 (session_checkpoint) with metadata designed for a full memory pyramid. L2+ meta-checkpoints (summaries of summaries) are deferred to CP8 (synthesis), where they naturally belong. This means CP7b establishes the architectural pattern that makes a 500K-memory user's store as navigable as a 5K-memory user's store — log-ish retrieval cost via pyramid descent — even though only the L1 layer ships here.

---

## Why now

**Direct dogfooding pain:** The reason this scope doc exists is that a handoff was needed. Every session Justin starts on 0Latency work begins with recapitulation. The product that's supposed to solve this problem doesn't yet solve it for its own builder. CP7b closes that loop.

**Unblocked by CP7a and unification:** `memory_write` is live and the MCP transport layer is unified. The infrastructure to write typed memories with rich metadata from any MCP client exists as of yesterday. There is no prerequisite beyond "ship."

**Compounds with existing differentiators:** 0Latency's positioning is agent-native context infrastructure with self-improvement. CP7b is the first feature where those two properties reinforce each other in a visible way — summaries that get better the more the feedback loop runs, exposed as a native MCP primitive.

**Pairs with the pricing page as it stands:** 1M memories on the Scale tier ($99/mo, live on `0latency.ai`) is the claim. The hierarchical pyramid architecture CP7b establishes is what makes that claim useful at scale, not just nominally supported.

**Fundraising rule still applies:** Hold until $10K MRR. CP7b is capability investment.

---

## What exists today

- **`memory_write` MCP tool:** live on `mcp.0latency.ai`, backed by `/memories/seed`, 30/min rate limit, 60s content-hash dedup. Accepts arbitrary `memory_type` strings and `metadata` jsonb. (CP7a)
- **`memory_recall` MCP tool:** hybrid BM25 + vector + reciprocal rank fusion. Returns ranked memory objects. (Live, fixed 2026-04-18.)
- **`memory_feedback` MCP tool:** four feedback types (`used`, `ignored`, `contradicted`, `miss`). Already wired to influence importance scores on atoms.
- **Chrome extension:** v0.4.1.1 captures every turn on Claude, ChatGPT, Gemini with full project/thread context (`project_id`, `thread_id`, `project_name`, `thread_title`). Writes via `/memories/extract`.
- **Unified MCP codebase (v0.2.0):** 14 tools at parity across HTTP/SSE and stdio transports. `memory_resume` will be the 15th.
- **Async job infrastructure:** `/memories/extract` returns a `job_id` today. The pattern (async write, status tracking) is established; CP7b reuses it.

What does not exist:
- A canonical `session_checkpoint` schema
- Any mechanism that summarizes stored turn atoms into higher-level records
- Any detection of "new thread in project with prior checkpoints → produce meta-summary"
- A checkpoint-aware recall path
- A summarization-quality feedback loop
- A `memory_resume` tool

---

## Decisions required before implementation

Five design calls. Each has a recommendation; none are hard-gated on external input.

### 1. Writer strategy — who produces checkpoints?

**Chosen: Hybrid, leaning server-side.**

- **Mid-thread rollups (every N=20 turns):** async server job, triggered by the Chrome extension's turn-capture webhook. Haiku-powered summarization of the last N turns. Consistent, works on every surface the extension covers, no agent dependency.
- **End-of-thread summaries:** agent-written via `memory_write` when the agent or user signals wrap-up. Higher quality because the agent knows what actually mattered. Also catches sessions where the extension isn't active (Claude Desktop, API direct).
- **Auto-resume meta-summary (new thread, same project, prior checkpoints exist):** async server job, triggered when the extension detects a new `thread_id` in a project whose prior threads have checkpoints. Chains all prior rollups and also recovers the tail — the turns after the last rollup that never got summarized because the previous thread ended abruptly.

**Rationale:** agent-only fails on abrupt endings. Extension-only misses non-extension sessions. Server-job-only misses the quality signal of agent self-reflection. Hybrid covers every case with overlap instead of gaps.

### 2. Cadence — when does a mid-thread rollup fire?

**Chosen: Static N=20 turns for CP7b. Adaptive cadence (CP7c) deferred.**

Capture the signal needed for adaptation from day one: every checkpoint stores `turn_count`, `time_span_seconds`, and later gets tagged with `feedback_outcomes` as recall events come in. After ~2 weeks of real data, CP7c trains N per user / per project against the `used`/`ignored`/`miss` signal. Shipping adaptive logic today is guessing dressed up as sophistication.

**N=20 justification:** Claude thread compression typically starts mattering around 30–40 turns. N=20 gives one checkpoint mid-thread before compression pressure, two by the time compression bites. Tunable via env var for dogfooding.

### 3. Schema — what a session_checkpoint record looks like

```
memory_type: "session_checkpoint"
content: <Haiku-generated summary text, ≤500 tokens>
agent_id: <from API key tenant>
importance: 0.7  # higher than atoms, lower than explicit user preferences
metadata:
  level: 1                    # pyramid level — L2+ reserved for CP8 synthesis
  thread_id: <uuid>           # from extension capture
  project_id: <uuid|null>
  thread_title: <string|null>
  project_name: <string|null>
  checkpoint_sequence: <int>  # 1, 2, 3... within this thread
  checkpoint_type: "mid_thread" | "end_of_thread" | "auto_resume_meta" | "tail_recovery"
  turn_range: [<start_turn>, <end_turn>]
  turn_count: <int>
  time_span_seconds: <int>
  parent_memory_ids: [<uuid>, ...]   # atoms summarized by this checkpoint
  child_memory_ids: []              # reserved for CP8 meta-checkpoints pointing here
  parent_checkpoint_id: <uuid|null> # previous checkpoint in this thread, for chaining
  source: "server_job" | "agent" | "extension"
```

Every field serves a purpose:
- `level` + `parent_memory_ids` + `child_memory_ids` — pyramid primitives, ready for CP8
- `checkpoint_type` — distinguishes the four writer paths, enables differential recall weighting
- `turn_range` + `turn_count` + `time_span_seconds` — signals for CP7c adaptive N
- `parent_checkpoint_id` — chain traversal for auto-resume meta-summary generation
- `source` — observability; we'll want to know which writer produced the best summaries

### 4. Recall behavior — how checkpoints surface

**Chosen: Checkpoint-aware recall as the default path. New `memory_resume` tool for explicit handoff queries.**

Recall ordering changes:

- **Query classifier (existing) gets a third output:** checkpoint-preference. Broad/navigational queries ("what have we been working on?", "where did we leave off?") bias toward checkpoints. Specific queries ("what did Denis say about RLS?") bias toward atoms, using checkpoints only as navigational hints.
- **Same-project recency boost:** checkpoints from the current `project_id` with recent `thread_id` get a score multiplier. Cross-project checkpoints get the standard score.
- **Pyramid descent hint:** when a checkpoint scores highly, its `parent_memory_ids` become a cheap follow-up query — the caller can fetch the underlying atoms if the summary wasn't enough. This is the "log-ish search cost" property.

**`memory_resume` MCP tool:** thin wrapper over `memory_recall` with presets — `prefer_checkpoints=true`, `project_id=<current>`, `budget_tokens=<large>`, newest-thread-first sort. Returns a handoff-shaped context block. Agents in new threads call it first; everything else calls `memory_recall`.

### 5. Feedback loop — how checkpoint quality improves

**Chosen: Route `memory_feedback` signals through to summarization prompt tuning, not just importance scores.**

Today, `memory_feedback` adjusts importance scores on atoms. CP7b extends this:

- When a checkpoint is surfaced and marked `used` — log it as a positive signal for the summarization prompt used at that level.
- When `miss` fires and the missing info turns out to live in one of the checkpoint's `parent_memory_ids` — that's a summary omission. Store the miss context + the parent atoms. After enough miss events accumulate, run a prompt-tuning pass: "here are 50 cases where summaries dropped something that turned out to matter — update the summarization prompt."
- When `contradicted` fires on a checkpoint — highest priority signal. Summary said something wrong. Log for immediate review.

The prompt-tuning pass itself is manual-reviewed for CP7b. Fully automated prompt optimization is a CP7c / CP8-adjacent research task. But the data collection ships now — otherwise CP7c has nothing to train on.

---

## Implementation plan

Phases are logical groupings, not day budgets. Ship in order.

### Phase 1 — Data primitive

1. Extend API validation: `memory_type="session_checkpoint"` is a known type with metadata schema validation (reject malformed metadata at write time — cheaper than finding bad data later).
2. Database: verify `metadata` jsonb can efficiently query on `metadata->>'thread_id'` and `metadata->>'project_id'`. Add GIN index on metadata if query plans look bad.
3. Write seed data: produce 20 synthetic session_checkpoint records across 3 fake projects to exercise the schema before any real writer fires.
4. Smoke test via `memory_write` from a Claude.ai MCP session: a hand-rolled session_checkpoint lands correctly, is queryable by `project_id` and `thread_id`, shows up in `memory_list`.

### Phase 2 — Mid-thread rollup writer (async server job)

1. New endpoint: `POST /memories/checkpoint` — accepts `{project_id, thread_id, turn_range, parent_memory_ids}`, runs Haiku summarization, writes `session_checkpoint` memory, returns `{checkpoint_id, job_id}`.
2. Chrome extension modification: on every 20th captured turn in a thread, fire `/memories/checkpoint` async. Use existing job-tracking pattern.
3. Summarization prompt v1: fixed prompt, Haiku. Structure: `topic`, `decisions`, `open_questions`, `next_steps`. Token budget ≤500 for the content field.
4. Dedup safety: if a rollup job fires for a turn range that already has a checkpoint, no-op. (Prevents double-write on extension retries.)
5. Smoke test: open a Claude thread in a project with extension active, chat for 20+ turns, verify checkpoint appears in DB with correct metadata.

### Phase 3 — End-of-thread writer (agent-triggered)

1. Document the convention: agents call `memory_write` with `memory_type="session_checkpoint"`, `metadata.checkpoint_type="end_of_thread"`, and populate remaining metadata themselves.
2. Add a convenience tool? No — `memory_write` already handles this. What ships instead: a docs page on `0latency.ai` showing the canonical end-of-thread checkpoint pattern for agent authors.
3. Tail recovery logic: when the next thread opens in the project, the auto-resume job (Phase 4) detects if the prior thread ended without an `end_of_thread` checkpoint. If so, it generates a `tail_recovery` checkpoint from the turns after the last mid-thread rollup.

### Phase 4 — Auto-resume meta-summary writer

1. New endpoint: `POST /memories/checkpoint/resume` — accepts `{project_id, new_thread_id}`, fetches all checkpoints for `project_id` ordered by thread creation and sequence, fetches tail atoms from any prior thread that lacks an `end_of_thread` checkpoint, runs Haiku to produce a meta-summary, writes a `session_checkpoint` with `checkpoint_type="auto_resume_meta"` scoped to the new `thread_id`.
2. Chrome extension trigger: on first turn of a new thread in a project with prior checkpoints, fire `/memories/checkpoint/resume` async.
3. Meta-summary prompt: different from mid-thread prompt. Structure: `project_arc`, `recent_context`, `open_threads` (pun intended), `likely_next_steps`. Budget ≤800 tokens for the content field — this one is read first in new sessions and deserves more room.
4. Smoke test: with 2+ prior threads of checkpoints in a project, open a new thread, verify auto-resume meta-checkpoint appears and includes both prior-thread content and any tail recovery.

### Phase 5 — Checkpoint-aware recall

1. Extend the query classifier in `recall.py`. Current output: (use_bm25: bool, use_vector: bool, confidence: float). New output: add `prefer_checkpoints: bool` based on query shape (broad/navigational vs specific).
2. Scoring: checkpoints get a baseline score multiplier in the broad-query path. Atoms get the multiplier in specific-query path.
3. Project-recency boost: checkpoints matching the caller's current `project_id` (if discoverable from agent_id context or passed explicitly) get further boost. Recency by `thread_id` creation time within project.
4. Smoke test: a broad query in a project with checkpoints returns checkpoints first; a specific query for a known atom returns the atom first.

### Phase 6 — `memory_resume` MCP tool

1. Add the 15th tool to the unified MCP server codebase. Schema: `{project_id: string (optional — inferred if not provided), agent_id: string (optional)}`. Returns the same context-block structure `memory_recall` returns.
2. Implementation: thin wrapper. Calls `memory_recall` internally with `prefer_checkpoints=true`, `dynamic_budget=true`, `project_id` filter, and newest-thread-first sort.
3. Update published tool list on `mcp.0latency.ai`. Update `0latency.ai` docs to show the new tool.
4. Smoke test from a fresh Claude.ai MCP session: `memory_resume` called first returns a clean handoff-shaped context; follow-up `memory_recall` queries pick up from there.

### Phase 7 — Feedback loop wiring

1. Extend `memory_feedback` handling: when feedback targets a memory whose `memory_type="session_checkpoint"`, log to a new `checkpoint_feedback` table (or jsonb field) with `parent_memory_ids` captured at time of feedback.
2. Dashboard view (internal only for CP7b): a query that lists checkpoints by feedback outcome — sorted by most `miss` events. This is the raw material for manual prompt tuning.
3. No automated prompt updates in CP7b. The loop is data-capture-first; tuning is human-reviewed until CP7c.

### Phase 8 — Dogfood and document

1. Turn off the `/root/unify-monitor.sh` cron from yesterday's v0.2.0 cutover if it's still running — CP7b supersedes that vigilance window.
2. Dogfood: run CP7b live in the 0Latency project itself for ≥1 week. Every new Claude thread should start with an auto-resume meta-summary. Log what works, what doesn't, what surprises.
3. Publish a short blog post on `0latency.ai`: "We killed the handoff doc." Screenshots of a real resume in action. Palmer follow-up trigger material.

---

## Success criteria

### Must meet

- Opening a new Claude thread in the 0Latency project surfaces a useful auto-resume meta-summary within 3 seconds of the first recall call.
- Mid-thread rollups fire every 20 turns and land in DB with correct metadata.
- End-of-thread checkpoints written by agents validate and land correctly.
- Tail recovery produces a checkpoint when a prior thread ended without an explicit end-of-thread summary.
- Broad queries in a project with checkpoints return checkpoints before atoms.
- Specific queries still return atoms (no regression on needle-in-haystack).
- `memory_resume` tool callable from any MCP client; returns a context block.
- `memory_feedback` on checkpoints lands in a queryable form for later prompt tuning.
- No regression on existing 14 MCP tools or the read path.

### Nice to have

- Auto-resume meta-summary is qualitatively as good as Justin's hand-written handoff docs (subjective, but we'll know).
- First round of `miss` feedback on checkpoints yields concrete prompt-tuning targets within dogfood week.
- A short video / screenshot sequence showing "new thread opens → memory_resume fires → agent picks up mid-work" that's usable in outbound material.

---

## Risks and unknowns

### High

- **Summarization prompt quality on day one.** Haiku is cheap but prompt engineering for summaries-that-survive-handoff is nontrivial. The first week of dogfooding will surface gaps. Mitigation: the feedback loop (Phase 7) is designed to catch and correct this; accept that v1 summaries will be mediocre and the system improves.
- **Extension trigger reliability.** Phase 2 and Phase 4 rely on the Chrome extension firing the right webhook at the right time. If the extension misses (service-worker-wake issue still exists as a known UX constraint), rollups don't happen. Mitigation: add a server-side fallback — a nightly job that detects threads with atoms but no checkpoints and generates them retroactively.

### Medium

- **Auto-resume meta-summary latency.** New-thread-first-recall has to wait on the resume job. Haiku is fast but not free. If it takes >3s, the experience is visibly worse than no checkpoints. Mitigation: generate the resume meta-summary *before* the new thread's first recall — trigger on thread creation, not first recall. Pre-bake the answer.
- **Cross-project checkpoint leakage.** A recall that doesn't pass `project_id` correctly could mix checkpoints across projects. Mitigation: project_id scoping is enforced at query time, not just display time. Verify with a cross-project test case.
- **Scale tier's 1M-memory claim under pyramid overhead.** Pyramid adds ~15–20% storage overhead per user. A tenant at 1M atoms now effectively stores ~1.15–1.2M records. Check the Scale tier accounting — does the pricing page count atoms or all records? If atoms, no issue; if all records, tighten the definition or revisit.

### Low

- **Summary drift from atoms.** If an atom is deleted after being parented to a checkpoint, the checkpoint's `parent_memory_ids` points at a dangling UUID. Mitigation: soft-delete atoms rather than hard-delete when they're parented by a checkpoint; accept the storage cost.
- **Prompt changes mid-dogfood.** If we tune the summarization prompt during dogfood, later checkpoints will be systematically different from earlier ones. Not a bug, but worth noting for CP7c training data integrity. Mitigation: stamp `prompt_version` into metadata.

---

## What CP7b does not include (deferred)

- **Adaptive N (per-user, per-project cadence tuning).** → CP7c. Data capture ships now; the tuning loop doesn't.
- **L2+ meta-checkpoints (summaries of summaries).** → CP8 synthesis. The pyramid primitives (`level`, `child_memory_ids`) ship in CP7b metadata so CP8 slots in without schema changes.
- **Cross-project checkpoint chaining.** Each project has its own timeline in CP7b. CP8 synthesis can reach across projects if it wants.
- **Fully automated summarization prompt optimization.** → CP7c / CP8-adjacent research. Manual review of miss events is the CP7b posture.
- **Per-user configurable N.** Env var for CP7b; per-project metadata setting in CP7c.

---

## Relationship to other tracks

**What CP7b unblocks:**
- CP7c — adaptive cadence tuning (needs CP7b's data collection)
- CP8 — synthesis layer (pyramid L2+ slots into CP7b's metadata architecture)
- Palmer follow-up — "we shipped the handoff killer" is a concrete demo, not a promise
- Any Show HN / blog material about MCP-native resume as a differentiator

**What CP7b depends on:**
- CP7a (memory_write) — shipped
- MCP unification v0.2.0 — shipped yesterday
- Chrome extension v0.4.1.1 (turn capture with project/thread context) — shipped

**What CP7b doesn't touch:**
- Track 2 (latency / Checkpoint 6 colocation) — orthogonal, resumes when scheduled
- Chrome extension's core capture loop — only the rollup webhook is new
- Existing `memory_recall` contract — additive, not breaking

---

## One-paragraph summary for resumption

CP7b introduces `memory_type="session_checkpoint"` — dense summaries of thread activity at three granularities (mid-thread rollups every 20 turns via async server job, end-of-thread summaries written by agents, auto-resume meta-summaries generated when a new thread opens in a project with prior checkpoints). Recall becomes checkpoint-aware: broad queries climb the pyramid (checkpoints first) and specific queries descend to atoms. A 15th MCP tool, `memory_resume`, exposes checkpoint-first recall as a first-class agent primitive. The `memory_feedback` loop extends to checkpoints, capturing `miss` events that surface summarization prompt gaps for later tuning. Metadata is designed for a full memory pyramid — `level`, `parent_memory_ids`, `child_memory_ids` — so CP8's synthesis layer slots in L2+ meta-checkpoints without schema changes. Ships eight phases end-to-end including one week of live dogfood; replaces hand-written handoff docs entirely for the 0Latency project and establishes the pattern for every downstream user.
