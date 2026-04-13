# Hacker News + Product Hunt Launch Drafts

**Status:** Draft - Ready for Justin's review  
**Account:** u/0LatencyAI (Reddit), TBD for HN/PH  
**Created:** 2026-03-30

---

## Hacker News - Show HN Post

### Title (60 char limit)
**Show HN: 0Latency – Persistent memory for AI coding assistants**

### Post Body

I built 0Latency after losing 2 hours of work to Claude's context compaction mid-refactor.

The problem: Every LLM has amnesia. You can have a 5-hour conversation with Claude Code, make architectural decisions, document edge cases—then context compacts and it all disappears. You're back to square one.

Existing solutions either lock you to one tool (Anthropic's Dream is Claude Code only) or require complex setup (Mem0, Zep). I wanted something simpler: a memory layer that works everywhere.

**What it does:**
- Persistent memory across sessions for any AI agent
- Works with Claude (Desktop, Code, claude.ai), GPT, Cursor, Gemini
- MCP-native for Claude, REST API + SDKs for everything else
- Sub-100ms recall latency
- Semantic search + temporal decay + knowledge graphs

**The meta part:**
I used Claude Code + 0Latency to build 0Latency itself. Every architectural decision got stored. When context compacted, memory persisted. We completed a 5-hour session, 15+ tasks, without losing anything.

This caught production bugs. Like when Claude would acknowledge storing information but the API call would silently fail—the exact failure mode we're solving. Fixed it before launch because we hit it ourselves.

**Tech stack:**
- Node.js + Express for API
- Supabase (Postgres + pgvector) for vector storage
- Redis for caching
- TypeScript + Python SDKs

**Try it:**
- Docs: https://0latency.ai
- GitHub: https://github.com/0latency-ai/0latency
- Free tier: 10K memories, 3 agents, no credit card

**Integration examples:**
```bash
# Claude Desktop (MCP)
npm install -g @0latency/mcp-server

# LangChain (Python)
pip install 0latency
from zerolatency import Memory
mem = Memory("zl_live_...")

# REST API (any language)
POST https://api.0latency.ai/memories
X-API-Key: zl_live_...
```

Built this because I needed it. Figured others might too. Happy to answer questions about the architecture, the dogfooding experience, or why cross-platform memory matters.

**Pricing:** Free tier + $29/mo Pro + $89/mo Scale. Cheaper than Mem0, simpler setup than building it yourself.

---

### HN Posting Strategy

**Best time:** Tuesday-Thursday, 8-10 AM Pacific (11 AM - 1 PM Eastern)

**Why this works:**
1. **Lead with the pain** - "lost 2 hours of work" is relatable
2. **Show, don't tell** - Code examples, specific technical details
3. **Honest positioning** - Acknowledges competitors, explains differentiation
4. **Dogfooding story** - Using AI to build AI memory is interesting
5. **Open about pricing** - No hidden costs, upfront comparison

**Response strategy:**
- Reply to EVERY comment within first hour
- Be technical, not marketing-y
- If someone finds a bug, fix it immediately and follow up
- If someone prefers Mem0/Zep, genuinely explain the differences
- Share more details when asked (latency benchmarks, architecture decisions)

**Red flags to avoid:**
- Don't argue with critics
- Don't be defensive about pricing
- Don't oversell features that aren't ready
- Don't ignore negative feedback

**Backup plan if post doesn't gain traction:**
- Repost next day with different angle: "Ask HN: How do you handle memory in AI agents?"
- Focus on problem discussion, not product
- Link to 0Latency as "here's what I built" in comments

---

## Product Hunt Launch

### Tagline (60 characters)
**Persistent memory for AI agents. Works everywhere.**

### Short Description (160 characters)
Your AI forgets everything between sessions. 0Latency remembers. Works with Claude, GPT, Cursor, and any agent framework. Sub-100ms recall.

### Full Description

**The Problem**

You're deep in a conversation with Claude Code. You've made architectural decisions, documented edge cases, discussed tradeoffs. Then context compacts. Everything's gone. Claude asks you to re-explain decisions from 30 minutes ago.

Every AI has amnesia. It's not a bug—it's fundamental. LLMs have no persistent memory between sessions.

**The Solution**

0Latency is a memory layer for AI agents. It works with every tool—Claude Desktop, Claude Code, claude.ai, GPT, Cursor, Gemini, custom agents.

When your AI stores something to memory, it's there forever. Semantic search finds it when needed. Sub-100ms recall means zero latency (hence the name).

**How It Works**

**For Claude users:**
Install via Model Context Protocol (MCP). Native integration, no hacks.

```bash
npm install -g @0latency/mcp-server
```

Add to `claude_desktop_config.json` and you're done. Claude can now remember across sessions.

**For developers:**
REST API + Python/TypeScript SDKs. Works with any LLM or agent framework.

```python
from zerolatency import Memory
mem = Memory("zl_live_...")
mem.add("User prefers concise code reviews")
result = mem.recall("How should I format this review?")
```

**For frameworks:**
Native integrations with LangChain, CrewAI, AutoGen. Drop-in memory layer.

**Features**

✅ **Semantic search** - Vector embeddings, not keyword matching  
✅ **Temporal decay** - Recent memories score higher  
✅ **Knowledge graphs** - Relationships between entities  
✅ **Cross-platform** - One memory, every tool  
✅ **Fast recall** - Sub-100ms latency (median 60ms)  
✅ **GDPR compliant** - Right to be forgotten built-in  
✅ **Self-hosted option** - Run on your own infrastructure  

**The Dogfooding Story**

I used Claude Code + 0Latency to build 0Latency itself. Meta, I know.

Every architectural decision Claude made got stored. When context compacted, memory persisted. We completed a 5-hour coding session without losing anything.

This caught real bugs. Like when Claude acknowledged storing information but the API call failed silently. That's the exact failure mode we're solving for users. Fixed it before launch because we experienced it ourselves.

**Pricing**

**Free:** 10K memories, 3 agents, no credit card  
**Pro:** $29/month - 100K memories, 10 agents  
**Scale:** $89/month - 1M memories, unlimited agents, knowledge graphs  
**Enterprise:** Custom - Unlimited everything, SLA, SSO  

40% cheaper than Mem0. Simpler than building it yourself.

**Why 0Latency?**

**vs Anthropic Dream:** Dream only works in Claude Code. We work everywhere.

**vs Mem0/Zep:** They're built for enterprises. We're built for developers. Simpler setup, cheaper pricing, MCP-native.

**vs Building It Yourself:** You could build this in 6 weeks. Or ship your product this week. We handle embeddings, search, multi-tenancy, GDPR, scaling. You focus on your agent.

**Links**

🌐 Website: https://0latency.ai  
📚 Docs: https://0latency.ai/docs  
💻 GitHub: https://github.com/0latency-ai/0latency  
🚀 Get Started: https://app.0latency.ai  

Built by a solo founder who got tired of re-explaining the same context to AI every session.

---

### Product Hunt Assets Needed

**Screenshots (6-8 images):**
1. Hero: "Your AI's long-term memory" tagline + demo
2. Claude Desktop integration (MCP config)
3. Memory dashboard (showing stored memories)
4. Recall in action (semantic search results)
5. Knowledge graph visualization
6. Code example (Python SDK)
7. Pricing comparison (0Latency vs Mem0)
8. Architecture diagram (how it works)

**Demo Video (60-90 seconds):**
1. Problem: Show Claude forgetting context (0:00-0:15)
2. Solution: Install 0Latency via MCP (0:15-0:30)
3. Demo: Claude remembering across sessions (0:30-0:60)
4. CTA: "Try it free at 0latency.ai" (0:60-0:90)

**Maker Comment (first comment on launch):**
> Hey Product Hunt! 👋
>
> I'm Justin, and I built 0Latency after one too many context resets with Claude Code.
>
> **The backstory:** I was deep in a refactor with Claude. We'd made architectural decisions, documented edge cases, the works. Then context compacted and it all vanished. Claude asked me to re-explain decisions from 30 minutes earlier.
>
> That's when I realized: every AI has amnesia. It's not their fault—LLMs fundamentally can't remember between sessions. But we can fix it with a memory layer.
>
> **The meta part:** I used Claude Code + 0Latency to build 0Latency itself. Every decision got stored. When context compacted, memory persisted. We completed a 5-hour session without losing anything. And we caught bugs this way—like when the API would silently fail to store memories. Fixed before launch.
>
> **What makes it different:**
> - Works everywhere (not just Claude)
> - MCP-native (no hacks or wrappers)
> - Sub-100ms recall (feels instant)
> - 40% cheaper than competitors
>
> Free tier is 10K memories, no credit card. Try it and let me know what breaks. I'm here all day to answer questions!
>
> Links: [0latency.ai](https://0latency.ai) | [GitHub](https://github.com/0latency-ai/0latency)

---

### Product Hunt Launch Strategy

**Launch day:** Tuesday or Thursday (highest engagement)  
**Launch time:** 12:01 AM PST (first post of the day advantage)

**Hour-by-hour plan:**

**12:01 AM - 8:00 AM:**
- Post goes live
- Maker comment posted immediately
- Monitor for early comments, reply to all

**8:00 AM - 12:00 PM:**
- Peak voting hours
- Share on Twitter, Reddit, LinkedIn
- Email personal contacts: "I launched on PH today, would love your support"
- Reply to every comment within 15 minutes

**12:00 PM - 6:00 PM:**
- Maintain engagement
- Share interesting questions/feedback on Twitter
- Update maker comment if FAQs emerge

**6:00 PM - 11:59 PM:**
- Final push for #1 spot
- Thank everyone who supported
- Plan follow-up content based on feedback

**Success metrics:**
- Top 5 product of the day (goal: #1)
- 200+ upvotes
- 50+ comments
- 20+ reviews
- Featured in PH daily newsletter

**Community engagement:**
- Reply to EVERY comment (even negative ones)
- Be helpful, not defensive
- Offer to help even if they don't use the product
- Turn critics into advocates by solving their problems

---

## Launch Timeline

**Monday evening (tonight):**
- [ ] Finalize Reddit posts for r/ClaudeAI, r/SideProject, r/AIAgents
- [ ] Schedule HN Show HN post for Tuesday 8 AM PT
- [ ] Prepare Product Hunt listing (schedule for Thursday 12:01 AM PT)

**Tuesday morning:**
- [ ] Post Show HN at 8 AM PT
- [ ] Monitor HN, respond to all comments
- [ ] Share HN post on Twitter

**Tuesday afternoon:**
- [ ] Post to r/SideProject (2-3 hours after HN)
- [ ] Monitor engagement across all channels

**Tuesday evening:**
- [ ] Post to r/AIAgents (4-6 hours after r/SideProject)
- [ ] Recap day's stats

**Thursday 12:01 AM:**
- [ ] Product Hunt launch
- [ ] All-day engagement marathon

**Why this sequence:**
1. Reddit first (Monday night) - Warm up the audience
2. HN Tuesday morning - Prime time for dev audience
3. Product Hunt Thursday - Peak engagement day, separate from HN

**Cross-promotion:**
- Each platform references the others organically
- "Also on HN/PH if you want to discuss there"
- Share user feedback across platforms

---

## Asset Checklist

**For HN:**
- [x] Post copy ready
- [ ] Demo ready to share if asked
- [ ] Architecture diagram if deep questions
- [ ] Benchmarks ready (latency, throughput)

**For Product Hunt:**
- [ ] 6-8 screenshots
- [ ] 60-90 second demo video
- [ ] Maker profile updated
- [ ] Thumbnail image (1270x760)
- [ ] Gallery images (1270x760 each)

**For both:**
- [x] Landing page ready
- [x] Docs complete
- [x] Free tier signup works
- [x] Support email monitored
- [ ] Analytics tracking URLs

---

**READY FOR JUSTIN'S REVIEW**

Changes from original strategy:
- HN post is more technical, less marketing
- Product Hunt has fuller description with code examples
- Launch sequence spread across 3 days (not all at once)
- Dogfooding story emphasized in both
