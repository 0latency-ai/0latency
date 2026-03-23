# Loom Video Script — 0Latency Demo

**Total time:** ~3 minutes
**Vibe:** Casual, founder-to-developer. Like explaining it to a friend.
**Setup:** Have these tabs open before recording: 0latency.ai, the case study page, PyPI page, API docs.

---

## Section 1: The Problem (0:00–0:45)

**Show on screen:** 0latency.ai homepage

**Talking points:**
- "Hey — I'm Justin. I built 0Latency because I had a problem that was driving me crazy."
- "I run an AI agent as my Chief of Staff. It handles real work for my businesses every day — emails, DNS, publishing packages, building features."
- "But every few hours, it hits its context limit. The system compresses the conversation, and suddenly my agent has amnesia."
- "It forgets what we were working on. It forgets my preferences. It forgets decisions we made an hour ago."
- "If you've run any long-lived agent, you've hit this. It's the #1 reliability problem."

---

## Section 2: What I Built (0:45–1:30)

**Show on screen:** Scroll down the homepage to features section / code examples

**Talking points:**
- "So I built a memory layer. Three lines of code — you store memories, and they come back when your agent needs them."
- "But it's not just a database. Memories decay over time if they're not reinforced — like how humans forget things they don't use."
- "And the system proactively injects relevant memories into your agent's context *before* it asks for them."
- "It respects your model's context budget. You tell it how much room you have, it packs the most important stuff."
- "Works with any model, any framework — LangChain, CrewAI, Claude, GPT, whatever you're using."

---

## Section 3: Real Proof (1:30–2:30)

**Show on screen:** Switch to the case study page (case-study-thomas.html). Scroll through slowly.

**Talking points:**
- "This isn't theoretical. Last night, my agent hit context compaction in the middle of a session."
- "It had subagents running, multiple projects going, DNS configuration half-done."
- "After compaction, it picked up like nothing happened. Relayed results from a subagent it shouldn't have remembered. Kept working."
- Scroll to the stats: "Five-hour session. Fifteen tasks completed. Six subagents. Zero context lost."
- Scroll to the deliverables: "After the compaction, we published a Python SDK, configured Cloudflare, built a secret scanner, created framework integrations — all without losing a beat."
- "This is the product running on itself. The best demo I could give you is the one I'm already using."

---

## Section 4: Try It (2:30–3:00)

**Show on screen:** PyPI page or terminal with `pip install zerolatency`

**Talking points:**
- "It's live right now. `pip install zerolatency` — that's it."
- "Free tier to start. API docs are at api.0latency.ai/docs."
- "If you're building agents that need to remember things longer than a single conversation, this is what it's for."
- "Link to everything is in the description. Thanks for watching."

---

## Recording Tips

- **Don't script word-for-word.** These are talking points — say it naturally.
- **Move your mouse** to guide the viewer's eye on screen.
- **Pause for a beat** when switching tabs — gives the viewer time to orient.
- **It's okay to mess up.** Loom lets you trim the start and end. If you stumble mid-sentence, just pause and say it again — you can't edit the middle, so just keep going.
- **Aim for 3 minutes.** Under 3 is great. Over 4 and people stop watching.
