# Show HN: 0Latency — Persistent memory layer for AI agents

**Title:** Show HN: 0Latency – Persistent memory that survives context compaction

**URL:** https://0latency.ai

---

**Post body:**

Long-running AI agents hit context limits. When the runtime compacts, agents lose decisions, preferences, and task state. They come back confused. This is the #1 reliability problem in production agents.

0Latency is a memory layer API that gives agents persistent memory across compaction events, session restarts, and model switches.

**Architecture:**

- Temporal decay: memories have half-lives. Unreinforced memories fade; referenced ones strengthen. No infinite accumulation.
- Proactive injection: relevant memories are injected into context *before* the agent needs them, based on conversation trajectory.
- Context budgets: memory payload respects the model's available window. You set the budget, we pack it optimally.
- Knowledge graphs: entity relationships with multi-hop traversal for reasoning across memory clusters.
- Contradiction detection: flags when new information conflicts with stored memories.

**Real-world proof:** My own AI agent (daily driver, not a demo) survived context compaction mid-session last night. It maintained full context across 3 companies, ongoing projects, technical decisions, and communication preferences — then completed 15+ tasks over the next 3 hours. Zero confusion. Full case study: https://0latency.ai/case-study-thomas.html

**What exists vs. what we built:** Mem0 and similar tools store memories but don't handle temporal decay, proactive injection, or context-budget-aware retrieval. They're append-only stores. 0Latency is a recall engine — it decides *what* to remember, *when* to surface it, and *how much* fits.

**Stack:** Python SDK, REST API, PostgreSQL + pgvector, MCP server for Claude Code/Cursor.

- PyPI: `pip install zerolatency`
- Docs: https://api.0latency.ai/docs
- GitHub: https://github.com/jghiglia2380/0Latency

Free tier available. Feedback welcome.
