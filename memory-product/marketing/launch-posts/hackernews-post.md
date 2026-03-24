# Hacker News Post

## Title Options (pick one)

1. **Show HN: 0Latency – Sub-100ms memory layer for AI agents with temporal decay and reinforcement**
2. **Show HN: I built a startup on 624 memories – a persistent memory layer for AI agents**
3. **Show HN: 0Latency – Biologically-inspired memory for LLM agents (open SDK, MCP server)**
4. **Show HN: We replaced 2000-word context dumps with 624 memories and built a whole product**
5. **Show HN: 0Latency – Persistent agent memory with temporal decay, sub-100ms recall**

---

## HN Comment/Intro (~200 words)

**Show HN: 0Latency – Sub-100ms memory layer for AI agents with temporal decay**

I've been building AI agents for my EdTech company and kept hitting the same wall: agents forget everything between sessions. Every workaround — context files, RAG pipelines, conversation summaries — felt like duct tape.

So I built 0Latency: a memory layer for AI agents inspired by how biological memory actually works. Memories have temporal decay (unused ones fade), reinforcement (frequently accessed ones strengthen), and negative recall (explicit "this is no longer true" markers). Retrieval is under 100ms.

It ships as an MCP server (one JSON config edit for Claude Desktop/Code) and a Python SDK (`pip install zerolatency`). No infrastructure to manage.

I tested it by building an entire product launch with 5 AI agents coordinating across 36 US state deployments — on just 624 memories over 5 days. Every agent maintained context across sessions without re-prompting.

The pricing gap in this space is wild: Mem0 is $249/mo, Zep is $475/mo. Our Scale tier ($89/mo) includes everything they charge 3x for. Free tier gives you 10K memories.

Bootstrapped, built alongside my main business. Technical deep-dive on the architecture: [blog post link]

Site: https://0latency.ai | SDK: `pip install zerolatency`
