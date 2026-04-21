# 0Latency — Claude Thread Memory: The Gorilla in the Room

## Brief for External Evaluation (Gemini)

### Context
0Latency is an AI memory infrastructure startup (pre-launch, bootstrapped). We built a persistent memory API that gives AI agents the ability to store and recall context across sessions — sub-100ms retrieval, temporal decay, negative recall, graph memory. Python SDK (`pip install zerolatency`) and MCP server.

During product development, we realized something bigger than our original thesis.

### The Original Thesis
**Compaction memory** — when an AI agent hits its context window limit (e.g., 200K tokens), the session resets and everything is lost. 0Latency catches memories before compaction and restores them after. We proved this works: our own AI agent (Thomas) hit 175K tokens, session reset, and came back immediately with full context. Built the entire product on 624 memories.

### The New Thesis — Thread Memory
Claude Desktop (and soon other LLM interfaces) supports MCP (Model Context Protocol). Our MCP server already works with Claude. This means:

**Any Claude Desktop user can add one config block and get persistent memory across ALL threads — not just surviving compaction within a thread, but carrying context BETWEEN threads.**

This is fundamentally different from what we originally built for. The implications:

1. **TAM explosion.** We were targeting developers building multi-agent systems (niche). Thread memory targets every Claude Desktop user, every Cursor user, every MCP-compatible tool user. That's potentially millions of users vs. thousands.

2. **Zero-code adoption.** Our developer API requires `pip install` and code integration. MCP requires pasting a JSON config block. That's it. The barrier to entry drops to near zero.

3. **Solves a universal pain point.** Every Claude user has experienced: "I told you this yesterday in another thread." Claude's built-in memory (Projects, conversation history) is limited and siloed per thread. 0Latency breaks that wall.

4. **Platform-agnostic memory.** A user could talk to Claude in Thread A, switch to Cursor for coding, come back to Claude in Thread B — and all three sessions share the same memory layer. No LLM vendor offers this.

### What We Already Have Built
- ✅ MCP server (TypeScript, published)
- ✅ Memory API with store/recall/search/extract
- ✅ Sub-100ms retrieval
- ✅ Temporal decay (recent memories weighted higher)
- ✅ Negative recall (agent knows what to forget)
- ✅ Multi-tenant isolation
- ✅ Secret detection (won't store API keys/passwords)
- ✅ Landing page with MCP integration section
- ✅ Free tier: 10,000 memories

### What We Don't Have
- ❌ Chrome extension for ChatGPT/Claude web interfaces (built but not in Chrome Web Store)
- ❌ Obsidian plugin
- ❌ VS Code extension
- ❌ Marketing positioned around thread memory (currently positioned for developers)
- ❌ User base / social proof
- ❌ Funding

### Competitive Landscape
- **Mem0** ($5.3M raised): Has MCP server too. 10K free memories. But their retrieval is 200-300ms and they lack temporal decay, negative recall, and context budgeting.
- **Zep** ($13.5M raised): Enterprise-focused, $475/mo for high-throughput. No MCP server. No consumer play.
- **Claude's built-in memory:** Anthropic's Projects feature stores context but it's per-project, manual, and doesn't work across threads automatically.
- **ChatGPT's memory:** OpenAI has basic memory but it's opaque, not user-controlled, and doesn't work via API.

### The Strategic Question
Should 0Latency pivot messaging (not product — the product already does this) to lead with "persistent memory for Claude" as the primary go-to-market, rather than "memory infrastructure for AI agent developers"?

### Arguments For:
- Massive TAM (all Claude Desktop users vs. niche developer audience)
- Near-zero friction (MCP config vs. code integration)
- Solves an immediate, felt pain point
- Could drive viral adoption (users tell other users)
- Free tier is sustainable (10K memories, most users never hit it)
- First-mover on this specific positioning

### Arguments Against:
- Claude Desktop user base is still relatively small vs. ChatGPT
- Consumer users have lower willingness to pay than developers
- Anthropic could build this natively and kill us overnight
- We'd be dependent on MCP protocol stability
- Developer audience has higher LTV and stickier usage
- Positioning as "Claude memory" limits perceived value for other platforms

### What We Need Evaluated:
1. **Is this a real market or are we hallucinating?** Is "Claude thread memory" a genuine mass-market need, or is it a niche within a niche?
2. **Platform risk.** How real is the threat that Anthropic just builds this into Claude? What's the timeline?
3. **Can we serve both audiences?** Developer API + consumer MCP — same product, different marketing funnels?
4. **Positioning.** If we lead with "Give Claude a memory," does that limit or enhance our developer story?
5. **Go-to-market.** What does the launch look like? Product Hunt? Hacker News? Claude community forums? Reddit r/ClaudeAI?
6. **Pricing implications.** Does a consumer audience change the pricing model we just finalized?

### Our Current Pricing
| Tier | Price | Memories | RPM | Key Features |
|------|-------|----------|-----|--------------|
| Free | $0 | 10,000 | 20 | Basic recall, negative recall, 5 agents |
| Pro | $19/mo | 100,000 | 100 | Priority support, 25 agents |
| Scale | $89/mo | 1,000,000 | 500 | Graph memory, unlimited agents, SLA |
| Enterprise | Custom | Unlimited | Custom | SSO, audit logs, dedicated support |

### The 624 Story
We built this entire AI startup — 5 agents, 36-state sales deployment, full product launch, competitive analysis, pricing strategy — on 624 memories. In 5 days. From idea to 92% production-ready. That's the proof that efficient memory architecture matters more than raw storage volume.

---

*Requesting: Unbiased strategic evaluation. Don't be nice — be right. If this is a bad idea, say so and explain why. If it's the right move, tell us what we're missing and what could kill us.*
