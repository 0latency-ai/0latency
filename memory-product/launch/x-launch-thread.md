# X/Twitter Launch Thread

**Tweet 1 (Hook):**
Anthropic just shipped Auto Dream — memory consolidation for Claude Code.

Great if you only use Claude.

I built the cross-platform version.

Works with Claude, GPT, Cursor, any agent framework. Not locked to one tool.

Ships today.

🧵

---

**Tweet 2 (The Problem):**
Every AI session starts from zero.

You give context. Agent builds something great. Session ends.

Next day: "I don't have access to that information."

You're not building on top of previous work. You're re-explaining the same codebase every single time.

---

**Tweet 3 (Auto Dream vs 0Latency):**
Auto Dream: Built into Claude Code. Works great if that's your only tool.

0Latency: Cross-platform API.
• Works with Claude, GPT, Cursor, custom agents
• Not locked to one vendor
• API access (integrate anywhere)
• Self-hosting option (Enterprise)

Think of us as "Auto Dream for everyone else."

---

**Tweet 4 (What it does):**
0Latency gives agents actual memory:

✅ Temporal decay (recent matters more)
✅ Negative recall (learns from failures)
✅ Contradiction detection (updates stale facts)
✅ Graph relationships (entities + semantic links)
✅ Sentiment analysis (understands context)
✅ Confidence scoring (validated vs inferred)

---

**Tweet 5 (How it works):**
MCP server install (30 seconds):

```bash
npx @0latency/mcp-server
```

Add your API key to Claude Desktop config. Done.

Now Claude can use the `remember` tool.

Every session recalls what matters. Your context compounds instead of resetting.

---

**Tweet 6 (Cross-platform):**
Works with:
• Claude Desktop
• Claude Code
• Any MCP client
• GPT (via API)
• Cursor (via API)
• Any agent framework

Your memory follows you. Not locked to one platform.

---

**Tweet 7 (Pricing / CTA):**
**Free tier:** 10K memories
**Pro:** 100K memories, $19/mo
**Scale:** 1M memories + graph features, $89/mo

(64% cheaper than Mem0 for comparable features)

Try it: https://0latency.ai

Docs: https://0latency.ai/docs

---

**Tweet 8 (Social proof / validation):**
Already powering my two products (PFL Academy + this).

Built because I needed agents that remember context across days/weeks.

The brain layer isn't Notion. It's infrastructure.

---

**Tweet 9 (Call for feedback):**
Feedback welcome.

Especially bugs — want this bulletproof before wider launch.

DM or comment if you try it. Want to hear what breaks and what you'd change.

Let's build the memory layer the agent era actually needs.
