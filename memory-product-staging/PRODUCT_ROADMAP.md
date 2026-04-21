# Memory Product — Go-to-Market Roadmap

## The Thesis
Every AI agent has the same memory problem: flat files, manual documentation, context loss on compaction. We built the fix. Now ship it.

## Phase A → B → C: Progressive Build

Yes, they grow out of each other. Each phase reuses and extends the previous one.

```
Phase A: OpenClaw Skill (ClawHub)
   ↓ validates demand, builds user base, battle-tests at scale
Phase B: Memory API (SaaS)
   ↓ extracts the engine into a standalone service, widens market
Phase C: Hosted Agent Platform
   ↓ full product — the agent that actually remembers
```

---

## Phase A: OpenClaw Skill on ClawHub
**Goal:** First revenue + market validation
**Timeline:** 1-2 weeks to ship MVP, iterate from there
**Revenue model:** Free tier (50 memories, 1 agent) → Pro ($9/mo, unlimited memories, multi-agent, historical import)

### What Ships
- Installable OpenClaw skill — `openclaw skills install memory-engine`
- Auto-configures: creates Postgres schema, starts extraction daemon, wires into workspace
- Zero-config for the user: install → restart gateway → working
- Includes:
  - Automatic extraction (every turn, no agent decision needed)
  - Multi-turn inference (4-turn sliding window)
  - Structured storage (typed memories with embeddings)
  - Contradiction detection + correction cascading
  - Identity permanence (names/preferences never decay)
  - Ephemeral memories (TTL-based)
  - Dynamic context budget (scales with conversation complexity)
  - Negative recall (knows what it doesn't know)
  - Memory health dashboard (`/memory health`)
  - Daily decay + compaction crons

### What Doesn't Ship (Yet)
- Historical import (Phase A.1 — fast follow, 1 week after launch)
- Cross-entity linking (included but advanced — enable by default, document later)
- Recall feedback loop (needs more real-world data to tune)
- Conversational momentum (included but marked experimental)

### Technical Requirements
- User needs: Supabase account (free tier works for <1000 memories) OR any Postgres with pgvector
- OR we host a shared Postgres instance for Pro users (simplest UX, we eat the DB cost)
- Gemini Flash API key for extraction (user provides, or we proxy through our key for Pro)
- OpenClaw v2026.3+ (hooks support)

### Go-to-Market
1. Ship on ClawHub with demo video showing compaction gap analysis
2. DM Greg Eisenberg with the skill + demo — "here's what your agent forgets vs. what mine remembers"
3. Post in OpenClaw Discord #showcase
4. Write a short blog post: "We Lost 36% of Our Agent's Most Important Work. Here's How We Fixed It."
5. Reddit: r/OpenClaw, r/LocalLLaMA, r/ArtificialIntelligence

### Success Metrics
- 100 installs in first month
- 10 Pro conversions ($90/mo MRR)
- <5% churn (memory is sticky — literally)
- NPS from first 20 users

### Pricing Rationale
- Cost per user: ~$0.93/mo (Gemini Flash extraction + Postgres storage)
- $9/mo = 90% margin
- Free tier limited to 50 memories — enough to see value, not enough to not upgrade
- Pro includes hosted Postgres (we eat ~$0.50/user/mo in DB costs)

---

## Phase B: Memory API (SaaS)
**Goal:** Platform-agnostic memory service, wider TAM
**Timeline:** 4-6 weeks after Phase A launch (once A validates demand)
**Revenue model:** API pricing — $19/mo (10K extractions/mo) → $49/mo (50K) → Enterprise

### What's New vs. Phase A
- REST API: `POST /extract`, `POST /recall`, `GET /health`, `POST /import`
- Works with any agent framework (LangChain, CrewAI, AutoGen, custom)
- Multi-tenant architecture (isolated schemas per customer)
- OAuth for LLM imports — connect Claude/ChatGPT/Gemini accounts, auto-import history
- Hosted extraction — user sends conversation turns, we handle everything
- Dashboard UI (web app) — memory explorer, health metrics, recall audit trail
- SDKs: Python, TypeScript/Node

### Technical Delta from A
- API gateway (FastAPI or Express)
- Multi-tenant Postgres (schema-per-tenant or row-level security)
- Auth (API keys + OAuth for LLM imports)
- Rate limiting, usage metering
- Simple web dashboard (React)
- Hosted Gemini Flash extraction (user doesn't need their own key)

### What Carries Over from A
- Entire extraction/storage/recall pipeline (unchanged)
- Negative recall, entity linking, correction cascading (unchanged)
- Memory compaction, decay, feedback loop (unchanged)
- The OpenClaw skill becomes a thin client that calls the API

### Go-to-Market
- Launch on Product Hunt
- Integrate with LangChain/CrewAI docs as a "persistent memory provider"
- Partner with agent framework creators
- Content: "Why Your Agent Forgets Everything (And How to Fix It)"
- Greg Eisenberg follow-up: "Remember that memory skill? Now it works with everything."

### Pricing Rationale
- $19/mo = individual developers, small teams
- $49/mo = startups, multiple agents
- Enterprise = custom, SOC2, dedicated infra
- Unit economics: $0.93 cost → $19 price = 95% margin (from original analysis)

---

## Phase C: Hosted Agent Platform
**Goal:** Full "agent that remembers" product — compete with Abacus Claw
**Timeline:** 3-6 months after Phase B (once API is stable + proven)
**Revenue model:** $29-49/mo hosted agent with memory built-in

### What's New vs. Phase B
- Fully hosted OpenClaw instance (like Abacus Claw)
- Zero-config: sign up → connect messaging → customize personality → live
- Memory system pre-installed and configured (our differentiator)
- Historical import during onboarding ("connect your Claude account to bootstrap memory")
- Multi-agent support (separate agents for work, personal, specific projects)
- Mobile-friendly web dashboard
- Team features (shared memory across agents)

### What We Have That Abacus Claw Doesn't
- Structured memory with all 12+ features we built
- Historical import from other LLMs
- Memory that actually works after compaction (proven, not claimed)
- Negative recall (agent knows its limits)
- Recall feedback loop (self-improving)

### What Abacus Claw Has That We'd Need
- Cloud hosting infrastructure (VPS fleet management)
- Payment processing / billing
- User management / auth
- Support infrastructure
- Security certifications (SOC2 etc.)

### Go-to-Market
- Position against Abacus Claw: "Same ease of setup. Actually remembers."
- Demo: side-by-side comparison after 30 days of usage
- Target: founders, operators, agencies (Greg's audience exactly)
- Price: $29/mo (undercut Abacus Claw's $20/mo + credit costs)

---

## Enterprise Readiness (Phased)

Enterprise-grade features signal maturity to all users, not just enterprise buyers. Build progressively.

### Phase A (ship with MVP)
- **Audit trail / activity log** — every extraction, recall, edit, deletion logged with timestamp + actor. `memory_audit_log` table already exists. Surface it.
- **Status page** — StatusPage.io (free for 1 component). Shows uptime, signals professionalism.
- **Data policy** — Clear language: "Don't send data you wouldn't want processed by a cloud service. Self-hosted = zero exposure." Onus on user.
- **Schema designed for RBAC** — Don't expose it yet, but design tables so adding roles later doesn't require refactoring.

### Phase B (ship with API)
- **RBAC** — Admin / member / viewer roles. Teams can share agents with granular access.
- **Data residency selection** — Supabase region picker at signup. "Where is my data?" answered at onboarding.
- **Rate limiting + usage dashboards** — API usage patterns, anomaly detection, per-team quotas. Built on top of existing metering.
- **Data retention policies** — Configurable TTL per account. Extend ephemeral memory concept. Required for healthcare/finance verticals.
- **Webhook notifications** — POST on extraction, contradiction, cascade events. Integrates with existing observability stacks.
- **Encryption at rest with CMK** — Optional customer-managed keys. Zero-knowledge option. Already designed in privacy architecture.

### Phase C (ship with platform)
- **SSO / SAML** — Okta, Azure AD, Google Workspace via Auth.js.
- **SOC 2 certification** — $5K-20K. Only when enterprise revenue justifies it.
- **Dedicated infrastructure option** — Isolated instances for enterprise accounts. RLS is fine until then.
- **SLA commitment** — 99.5%+ uptime guarantee with contractual backing.

### What We DON'T Build Until Revenue Demands It
- ISO 27001
- 24/7 support (docs + email + Discord through Phase B)
- Pen testing (Phase C)
- HIPAA/FERPA compliance (only if vertical demand appears)

---

## Dependencies & Risks

### Phase A Risks
- ClawHub adoption is still early — marketplace traffic may be low
- Postgres requirement adds friction (mitigate: offer hosted option)
- OpenClaw hooks may not fire for message events (known issue — daemon fallback works)

### Phase B Risks
- Building a SaaS is a different game than building a skill (auth, billing, support)
- Multi-tenant security is non-trivial
- LLM import OAuth may require partnerships with Anthropic/OpenAI/Google

### Phase C Risks
- Competing with well-funded companies (Abacus AI has raised $300M+)
- Infrastructure costs at scale
- Support burden

### Mitigations
- Phase A is low-risk: if it flops, we've lost 2 weeks. If it works, we have signal.
- Each phase validates the next before we commit resources.
- The memory engine is the moat at every phase — it's what makes us different.

---

## Key Decision Points

1. **After Phase A launch (Week 3):** Do we have 50+ installs and positive feedback? → Green light Phase B
2. **After Phase B launch (Month 3):** Do we have 50+ API customers and <5% churn? → Green light Phase C
3. **Continuous:** Is anyone replicating our memory architecture? If yes, accelerate. If no, we have runway.

---

## Pre-Launch: Memory Quality Gate (BEFORE Phase A)

**Nothing ships until memory quality hits 99%. This is priority 1, 2, and 3.**

Gap Analysis #2 scored the system at 65% effective (329 memories extracted, recall failed to surface them). Target: 99%.

### Fix 1: Session Handoff on Compaction/Session End (CRITICAL — 2 hours)
- [ ] Write `session_handoff` record when session ends or compaction is imminent
- [ ] Contains: active thread, open decisions, pending actions, key context
- [ ] Table exists (`session_handoffs`), currently empty
- **Impact:** Eliminates 90% of cold-start orientation time

### Fix 2: Decision Extraction Quality (HIGH — 1 hour)
- [ ] Add decision-specific extraction template to prompt
- [ ] Capture: what, why, who, what it supersedes, action items
- [ ] Currently decisions are captured as vague tasks
- **Impact:** Decisions become actionable memories

### Fix 3: Structured List Preservation (HIGH — 1 hour)
- [ ] When extraction encounters ordered lists, preserve as ONE memory
- [ ] Currently a 9-item checklist becomes 9 disconnected tasks
- [ ] Ordering, dependencies, and structure lost
- **Impact:** Preserves coherent plans and checklists

### Fix 4: Deduplication Pass (MEDIUM — 2 hours)
- [ ] Post-extraction dedup: >0.90 similarity + same type = merge/skip
- [ ] Currently 60-80 duplicates in 329 memories
- [ ] Daemon extracts from transcript AND individual turns = overlap
- **Impact:** Better signal-to-noise ratio

### Fix 5: Recall Query Optimization (MEDIUM — 2 hours)
- [ ] Verify embeddings generated and indexed
- [ ] Test recall paths end-to-end
- [ ] Add hybrid search (semantic + keyword)
- [ ] Semantic search returned 0 results for valid query
- **Impact:** Makes structured memory actually findable

### Fix 6: Reduce Correction Type Overuse (LOW — 30 min)
- [ ] Only classify as "correction" when explicitly superseding prior memory
- [ ] Currently 95/329 (29%) are corrections; most are mislabeled facts
- **Impact:** Cleaner type distribution, better filtering

### Quality Milestones
- [ ] **85% → 90%:** Fixes 1 + 2 (session handoff + decision quality)
- [ ] **90% → 95%:** Fixes 3 + 4 (list preservation + dedup)
- [ ] **95% → 99%:** Fixes 5 + 6 (recall optimization + type accuracy)
- [ ] **Validation test:** Simulate compaction, verify instant recall of active threads

---

## Phase A Next Steps (AFTER quality gate passes)

1. [ ] Package as OpenClaw skill (SKILL.md, installer script, config templates)
2. [ ] Create hosted Postgres option (Supabase project for Pro users)
3. [ ] Build static Mission Control dashboard (GitHub Pages)
4. [ ] Write test suite (extraction, storage, recall, compaction survival)
5. [ ] Build installer with dependency checks
6. [ ] Test on fresh Supabase project
7. [ ] Add error handling + retry logic to daemon
8. [ ] Pick a product name
9. [ ] Record demo video: gap analysis before/after
10. [ ] Write ClawHub listing copy
11. [ ] Submit to ClawHub
12. [ ] Draft Greg Eisenberg DM
13. [ ] Post in OpenClaw Discord

---

*Created March 20, 2026. Born from a compaction failure, built in one night, shipping this week.*
