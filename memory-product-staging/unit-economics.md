# Unit Economics Model — Agent Memory Service

**Date:** March 18, 2026
**Status:** Draft

---

## Cost Components Per User

### 1. Extraction (per conversation turn)

The extraction layer processes each user↔agent exchange to pull out structured facts.

| Model | Input cost/1M tokens | Output cost/1M tokens | Est. tokens/turn (in) | Est. tokens/turn (out) | Cost/turn |
|-------|---------------------|----------------------|----------------------|----------------------|-----------|
| Claude Haiku 3.5 | $0.80 | $4.00 | ~800 | ~300 | $0.0019 |
| Gemini Flash 2.0 | $0.075 | $0.30 | ~800 | ~300 | $0.00015 |
| GPT-4o Mini | $0.15 | $0.60 | ~800 | ~300 | $0.0003 |
| Local (Llama 3.1 8B) | $0 (compute) | $0 (compute) | ~800 | ~300 | ~$0.0001* |

*Local model cost = GPU amortization. On a $6/mo DigitalOcean droplet, inference is slow but effectively free for low volume.

**Recommendation:** Gemini Flash 2.0 at $0.00015/turn is 10x cheaper than Haiku with comparable extraction quality for structured tasks. Test both.

### 2. Embedding (per memory stored)

Each extracted memory needs to be embedded for semantic search.

| Provider | Model | Dimensions | Cost/1M tokens | Est. tokens/memory | Cost/memory |
|----------|-------|-----------|----------------|-------------------|-------------|
| OpenAI | text-embedding-3-small | 1536 | $0.02 | ~100 | $0.000002 |
| OpenAI | text-embedding-3-large | 3072 | $0.13 | ~100 | $0.000013 |
| Voyage AI | voyage-3-lite | 512 | $0.02 | ~100 | $0.000002 |
| Local (all-MiniLM) | — | 384 | $0 | ~100 | ~$0 |

**Embedding cost is negligible.** Even at 100 memories/day, it's < $0.001/day.

### 3. Storage (per user per month)

| Component | Provider | Free Tier | Paid Tier | Est. per user |
|-----------|----------|-----------|-----------|---------------|
| Postgres + pgvector | Supabase | 500MB, 50K rows | $25/mo for 8GB | ~$0.05-0.10/user at 1000 users |
| Postgres + pgvector | Neon | 512MB | $19/mo for 10GB | ~$0.02-0.05/user at 1000 users |
| Self-hosted SQLite | User's machine | $0 | $0 | $0 |

**Storage is cheap.** A year of memories for one agent ≈ 50-100MB including embeddings.

### 4. Recall (per query)

Recall involves: semantic search (vector similarity) + ranking algorithm + optional model call for context summarization.

| Component | Cost | Frequency |
|-----------|------|-----------|
| Vector similarity search | ~$0 (database query) | Every 5 turns + session start |
| Ranking algorithm | ~$0 (server-side compute) | Same |
| Optional summary model call | $0.0003-0.002/call | Only if context budget exceeded |

**Recall is essentially free** — it's database queries + math.

---

## User Profile Scenarios

### Casual User (personal assistant, light use)
- 30 turns/day
- 10-15 new memories/day
- 1-2 sessions/day

| Component | Daily Cost | Monthly Cost |
|-----------|-----------|-------------|
| Extraction (Flash) | $0.0045 | $0.14 |
| Embedding | $0.00003 | $0.001 |
| Storage | — | $0.05 |
| Recall | ~$0 | ~$0 |
| **Total** | **$0.005** | **$0.19** |

### Power User (business operator like Justin)
- 150 turns/day
- 30-50 new memories/day
- 5-8 sessions/day

| Component | Daily Cost | Monthly Cost |
|-----------|-----------|-------------|
| Extraction (Flash) | $0.023 | $0.68 |
| Embedding | $0.0001 | $0.003 |
| Storage | — | $0.10 |
| Recall | ~$0.005 | $0.15 |
| **Total** | **$0.028** | **$0.93** |

### Heavy User (enterprise agent team, 5 agents)
- 500 turns/day across agents
- 100+ memories/day
- Continuous sessions

| Component | Daily Cost | Monthly Cost |
|-----------|-----------|-------------|
| Extraction (Flash) | $0.075 | $2.25 |
| Embedding | $0.0002 | $0.006 |
| Storage | — | $0.50 |
| Recall | ~$0.01 | $0.30 |
| **Total** | **$0.085** | **$3.06** |

---

## Pricing Model Options

### Option A: We Absorb Model Costs (Simpler UX)

| Tier | Price/mo | Target User | Our Cost/mo | Margin |
|------|---------|------------|------------|--------|
| Free (self-hosted) | $0 | Hobbyists, developers | $0 | N/A |
| Starter | $9/mo | Casual users | $0.50-1.00 | 89-94% |
| Pro | $19/mo | Power users | $1.00-3.00 | 84-95% |
| Team | $49/mo (up to 5 agents) | Small businesses | $3.00-5.00 | 90-94% |
| Enterprise | Custom | Large orgs | Custom | 80%+ |

**Verdict:** Margins are excellent. Even power users cost us <$3/mo. This model works.

### Option B: User Brings Own API Key (Lower Barrier)

| Tier | Price/mo | What's Included |
|------|---------|----------------|
| Free (self-hosted) | $0 | Everything, self-managed |
| Hosted | $5/mo | Managed Postgres + dashboard |
| Hosted Pro | $12/mo | + analytics, multi-agent, priority support |

User pays their own extraction model costs ($0.15-$3.00/mo typically).

**Verdict:** Lower price point, but adds friction (user needs API keys). Better for developer audience. Worse for non-technical users.

### Recommendation: Hybrid

- **Free tier:** Self-hosted, bring your own everything
- **Hosted tiers:** We absorb model costs (included in price). Simpler. Higher price but zero friction.
- Start with Option A pricing. Revisit if costs spike with scale.

---

## Break-Even Analysis

**Fixed costs (monthly):**
| Item | Cost |
|------|------|
| DigitalOcean droplet (API server) | $24/mo (4GB) |
| Supabase Pro (database) | $25/mo |
| Domain + DNS | $1/mo |
| **Total fixed** | **$50/mo** |

**Break-even:** 6 Starter users OR 3 Pro users OR 2 Team users.

**At 100 Pro users:** $1,900/mo revenue — $300/mo variable costs — $50/mo fixed = **$1,550/mo profit (82% margin)**

**At 1,000 Pro users:** $19,000/mo revenue — $3,000/mo variable — $200/mo fixed (scaled infra) = **$15,800/mo profit (83% margin)**

---

## Key Takeaways

1. **The unit economics work.** Variable costs per user are under $3/mo even for power users. Margins are 80-95% at $9-19/mo pricing.
2. **Gemini Flash 2.0 is the extraction model to start with.** 10x cheaper than Haiku, good enough for structured extraction.
3. **Storage and recall are essentially free.** The cost is almost entirely in extraction model calls.
4. **Self-hosted free tier costs us nothing** and serves as the funnel for hosted conversions.
5. **Break-even is trivially achievable** — 3-6 paying users covers all fixed costs.
6. **This is a high-margin SaaS business** if it gets traction. The question is market size and adoption, not economics.

---

*Last updated: March 18, 2026*
