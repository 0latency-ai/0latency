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

## Immediate Next Steps (Phase A)

1. [ ] Debug and verify all features work end-to-end after compaction (THE TEST)
2. [ ] Package as OpenClaw skill (SKILL.md, installer script, config templates)
3. [ ] Create hosted Postgres option (Supabase project for Pro users)
4. [ ] Record demo video: gap analysis before/after
5. [ ] Write ClawHub listing copy
6. [ ] Submit to ClawHub
7. [ ] Draft Greg Eisenberg DM
8. [ ] Post in OpenClaw Discord

---

*Created March 20, 2026. Born from a compaction failure, built in one night, shipping this week.*
