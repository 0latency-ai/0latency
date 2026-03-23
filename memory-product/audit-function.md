# 0Latency Function Audit — Features, Flow, Completeness

**Date:** 2026-03-23 | **Benchmark:** mem0.ai

---

## Critical Findings

### 1. Conversion Funnel is Broken

The "Get API Key" CTA links to Swagger docs, not a signup flow. There is no way for a developer to create an account, get an API key, or start using the product without admin intervention via a localhost-restricted endpoint (`POST /api-keys`).

**Required flow that doesn't exist:**
Landing → Pricing → Sign Up (OAuth/email) → API Key → Dashboard → Docs

**What's missing:** Signup page, OAuth (GitHub/Google), email login, session management, self-service tenant creation. The dashboard exists but requires pasting an API key you have no way to obtain.

### 2. No Pricing Page

The comparison table implies tiers exist ("free plan"), the stats show "$0.93/user/month," and the system has hardcoded plan limits (Free: 1K memories, Pro: 50K, Enterprise: 500K) — but there is no pricing page anywhere. A developer evaluating this against mem0's clear pricing grid ($0/$19/$249/custom) has nothing to compare.

### 3. No Billing Integration

No Stripe, no checkout, no subscription management. Plans are set by admin at tenant creation. Revenue cannot flow.

### 4. No Auth System

No OAuth providers, no email/password auth, no password reset, no email verification. API-key-only authentication with no self-service key provisioning.

---

## High-Priority Findings

### 5. Developer Trust Signals are Sparse

| Signal | 0Latency | mem0.ai |
|--------|----------|---------|
| GitHub stars | Not displayed | ~48K, prominently shown |
| Customer logos/testimonials | None | Multiple |
| Compliance badges | "Roadmap" | SOC 2 + HIPAA |
| Funding/backers | None | "$24M Series A" + YC badge |
| Adoption metrics | None | "13M+ PyPI downloads" |
| Benchmarks | None | LOCOMO (26% better than OpenAI Memory) |

The stats bar (42 endpoints, 147 tests, <50ms, $0.93/user) provides engineering credibility but reads as "we built a lot" not "people use this." Even one beta user quote would help.

### 6. SEO is Failing

Has `<title>` and `<meta description>`. Missing everything else:

- **Open Graph tags** — link shares on Twitter/Discord/Slack show blank previews
- **Twitter Card tags** — no image, no summary
- **Canonical URL** — duplicate content risk
- **JSON-LD structured data** — no rich snippets
- **robots.txt, sitemap.xml** — search engines have no guidance
- **llms.txt** — emerging standard, missed opportunity
- **Favicon** — browser tab shows default icon

### 7. API Documentation is Swagger-Only

FastAPI auto-generates endpoint listing at `/docs`, but lacks: conceptual overview (what is extraction vs recall?), authentication guide, quickstart tutorial, error code reference, rate limiting docs, SDK installation. Mem0 has a full docs site at `docs.mem0.ai` with framework-specific guides.

### 8. Missing Pages vs mem0.ai

| Page | mem0.ai | 0Latency |
|------|---------|----------|
| Pricing | 4 tiers with CTA | **Missing** |
| Login/Signup | OAuth + email | **Missing** |
| Docs site | Comprehensive | Swagger only |
| Blog | SEO-optimized posts | **Missing** |
| Changelog | Regular updates | **Missing** |
| Status page | status.mem0.ai | Health endpoint only |
| Discord community | 6,600+ members | **Missing** |
| Integrations page | LangGraph, CrewAI, Vercel AI, AWS | **Missing** |
| Research/benchmarks | LOCOMO paper | **Missing** |
| Legal (Privacy/Terms) | Present | **Missing** |
| Light theme variant | N/A | Referenced but doesn't exist |

---

## Medium-Priority Findings

### 9. First Impression is Strong but Incomplete

**What works:** "Your agent forgets 36% of critical context. We fix that." is specific, quantified, and creates urgency — arguably better than mem0's category-defining "The Memory Layer." The code example (`extract()` + `recall()` in 10 lines) is the best element on the page.

**What's missing:** No category-defining statement above the fold. A developer skimming might confuse "zero latency" with LLM inference speed. Add a one-liner: "Persistent memory for AI agents."

### 10. Value Proposition Risks Confusion

"0Latency" as a name could mean: (a) zero memory recall latency (intended), (b) zero LLM response latency, or (c) zero configuration latency. The subtitle clarifies, but a developer skimming will interpret based on the name alone.

### 11. Feature Comparison Table is Effective but Cherry-Picked

Comparing the free tier against mem0's $249/mo Pro is bold and memorable. Four "EXCLUSIVE" badges on real differentiators. Honest about SOC 2 gap.

**But:** Doesn't mention mem0's $19/mo Starter tier — only comparing against $249 feels selective. Missing rows that matter: SDK languages (mem0 has Python + JS), framework integrations (mem0 has 6+), deployment options. The strongest pricing wedge — graph memory on all plans vs mem0's $249 paywall — deserves its own row with emphasis.

### 12. Code Examples Need Breadth

The Python quickstart is excellent but:
- No JavaScript/TypeScript example (SDK exists at `sdk/typescript/` but isn't shown)
- No curl example for API-first devs
- No copy button on the code block
- No install command (`pip install zerolatency`)

---

## Nice-to-Have Findings

### 13. Content Gaps — Unanswered Developer Questions

1. How do I sign up?
2. What are the exact pricing tiers and limits?
3. How is my data stored and secured?
4. What LLM providers does this use? Do I need my own API keys?
5. Can I self-host?
6. What frameworks does this integrate with (LangChain, CrewAI, etc.)?
7. How does temporal decay actually work? (needs a technical blog post)
8. Is there a free trial?
9. What's the SLA / uptime guarantee?
10. Where's the JavaScript SDK?

### 14. Chrome Extension Section Has a CSS Bug

`.platform-badge` class is used in the HTML for ChatGPT/Claude/Gemini/Perplexity badges but the CSS rule is never defined. Badges render as unstyled inline spans.

### 15. Blog Would Anchor the "36%" Claim

The headline claims agents forget 36% of critical context. This is a strong hook but there's no supporting content — no blog post, no benchmark, no citation. A single post titled "Why Your AI Agent Forgets" would serve as both SEO content and credibility evidence.

---

## Priority Action List

| # | Action | Severity | Effort |
|---|--------|----------|--------|
| 1 | Build signup flow (GitHub OAuth → tenant → API key) | Critical | Large |
| 2 | Create pricing page with tier details and CTAs | Critical | Medium |
| 3 | Fix "Get API Key" CTA to point to signup, not Swagger | Critical | Tiny |
| 4 | Add Open Graph tags + favicon | High | Small |
| 5 | Create docs landing page (quickstart, auth guide, concepts) | High | Medium |
| 6 | Add JS/curl code examples + copy button | Medium | Small |
| 7 | Add robots.txt + sitemap.xml + JSON-LD | Medium | Small |
| 8 | Fix `.platform-badge` CSS bug | Medium | Tiny |
| 9 | Write "Why Your Agent Forgets" blog post | Medium | Medium |
| 10 | Add one beta user testimonial | Medium | Small |

---

*Generated by Claude Code — session https://claude.ai/code/session_01ERECg1srA7xY6a6siRqsGu*
