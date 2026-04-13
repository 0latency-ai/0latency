# Instant Awareness - Product Vision

**Date:** April 1, 2026  
**Status:** P0 - turn_hook.py is the only missing piece  

---

## The Complete Picture

### Current State (Phase B)
- ✅ API live at api.0latency.ai
- ✅ Multi-tenant RLS working
- ✅ MCP server running (SSE at mcp.0latency.ai)
- ✅ Chrome extension capturing
- ✅ Wall-E extracting (every 15 min)
- ✅ Recall working (hybrid search, temporal decay fixed tonight)

### The Gap
**One missing script:** `turn_hook.py`

OpenClaw already has a hook system. After every turn, it can run a script automatically. Once wired:

1. OpenClaw finishes Thomas's response
2. Immediately calls `/root/scripts/turn_hook.py` with turn content (~200ms)
3. Script POSTs to `https://api.0latency.ai/extract`
4. Memory extracted, embedded (Gemini 768-dim vector), stored in PostgreSQL
5. **Available to Thomas AND Claude.ai within ~2 seconds**

### Cost Reality
~50 turns/session × 3 sessions/day = ~$0.004/day = <$2/month

The efficiency math holds.

---

## Instant Awareness Features

### P0: MCP Initialize Handler
When any client connects to mcp.0latency.ai, server fires `memory_recall` automatically before first message.

**Done signal:** New Claude.ai conversation with 0Latency connected → Claude knows who Justin is, what's being worked on, yesterday's context. Zero manual steps.

### P1: SSE Memory Push  
Chrome extension writes → SSE pushes `memory_update` event to all connected clients. Real-time, no polling.

### P2: Heartbeat Recall
Connected clients get periodic memory refresh (default 10 min) with relevant memories based on current context.

---

## Phase C - Onboarding (Future Product Line)

**Not a feature - a separate product.**

### What It Is
"Your new agent knows your company on day one."

**Core features:**
1. Conversation history import (Claude.ai, ChatGPT, Gemini)
2. Document ingestion (PDFs, Notion, Google Docs → structured memories)
3. Role-scoped onboarding packages
4. Privacy/consent dashboard
5. Standing feeds (Slack, CRM, meeting transcripts) - v2

### Pricing (Suggested)
- **Starter:** $199/mo (5 agents, 500K memories, 3 packages)
- **Growth:** $799/mo (25 agents, 5M memories, unlimited packages)
- **Enterprise:** Custom ($50K-$200K ACV, SSO, SOC 2, on-prem)

### Evaluation Framework

**Go signals:**
- Phase B hits $10K MRR with visible growth
- 3+ enterprise customers ask for document ingestion unprompted
- A customer hacks it together for employee onboarding
- Dedicated engineering resource available

**Wait signals:**
- Phase B MRR below $5K
- Recall quality issues unresolved
- No enterprise pipeline
- Still solo on engineering

**Decision rule:** Start Phase C planning when 3 enterprise customers ask for the same feature. Start building when 1 customer will pay before it ships.

---

## Roadmap 1: Phase B Hardening (Do Now)

These prevent migration tax later:

1. **Permission model:** Add roles table, namespace-level read/write permissions
2. **Memory schema:** Add source_type, visibility scoping, collections/tags
3. **Ingestion abstraction:** Extract layer interface for PDFs/docs/feeds
4. **Observability:** Expand canary checks, per-tenant usage metrics

**Principle:** Every Phase B decision made with Phase C in mind. Adding columns is free today. Migrating live production is a weekend incident.

---

## Next Steps

1. **Claude Code:** Wire turn_hook.py to OpenClaw memory-extract hook
2. **Verify:** Send one message to Thomas → 5 seconds later Claude.ai sees it via `memory_list`
3. **Build P0:** MCP initialize handler (auto-recall on connect)
4. **Launch:** "Memory That Loads Itself"

---

**The tagline:** Memory that loads itself.

**The test:** New Claude.ai conversation knows who you are before you type anything.

**The gap:** One script.
