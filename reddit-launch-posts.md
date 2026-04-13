# Reddit Launch Posts for 0Latency

## r/ClaudeAI

**Title:** I built a persistent memory API for Claude after losing context mid-conversation one too many times

I've been using Claude Desktop + Claude Code heavily for the past few months, and context loss kept killing my workflow. Mid-conversation, Claude would forget decisions we made 2 hours ago. Building multi-session projects was painful.

So I built 0Latency — a memory layer that works across all Claude surfaces (Desktop, Code, claude.ai). It's a Model Context Protocol (MCP) server that gives Claude persistent memory with semantic search, temporal decay, and knowledge graphs.

The dogfooding part: I used Claude to build it, with 0Latency enabled. Claude would store architectural decisions, bug fixes, and edge cases as we worked. When context compacted, the memory layer kept everything accessible. We completed 15+ tasks in a single 5-hour session without losing anything.

Found real bugs this way. Like when Claude acknowledged something important but didn't persist it to the API — exactly the problem 0Latency solves. Fixed those before launch.

**What it does:**
- Sub-100ms recall (median ~60ms)
- Semantic search + temporal decay (recent memories score higher)
- Knowledge graph relationships
- Works with Claude Desktop, Claude Code, claude.ai via MCP
- Free tier: 10K memories, 3 agents, no credit card

GitHub: github.com/0latency-ai/0latency  
Docs: 0latency.ai

Happy to answer questions about the architecture or the dogfooding experience.

---

## r/AIAgents

**Title:** Launched 0Latency: persistent memory API for AI agents (dogfooded it while building it)

If you're building AI agents, you've hit the memory problem. Agents lose context across sessions. They forget decisions. You end up re-explaining the same things.

I built 0Latency as a universal memory layer for any AI agent framework. Works with LangChain, CrewAI, AutoGen, or custom agents via REST API. Also has native MCP support for Claude.

**The interesting part:** I used Claude Code with 0Latency enabled to build the product itself. Every architectural decision, every bug fix, every edge case got stored. When context compacted, memory persisted. 5-hour coding session, 15+ tasks completed, zero context loss.

This caught real bugs. Like when the agent would acknowledge information but not store it to the API. That's the exact failure mode we're solving. Fixed it before launch because we experienced it firsthand.

**Tech details:**
- Sub-100ms recall latency (p50 ~60ms)
- Vector search + pgvector for semantic matching
- Temporal decay (recent memories score higher)
- Knowledge graph with entity relationships
- Self-hosted or hosted options
- Python + TypeScript SDKs

**Integrations:**
- MCP (Claude Desktop, Code, claude.ai)
- LangChain, CrewAI, AutoGen
- REST API for any framework

Free tier: 10K memories, 3 agents. GitHub: github.com/0latency-ai/0latency

Built this because I needed it. Now shipping it.

---

## r/SideProject

**Title:** Built a memory API for AI coding assistants, dogfooded it while building it

**The problem:** I use Claude Code heavily. Every time context resets, I lose architectural decisions, bug fixes, and project context. Explaining the same things repeatedly kills productivity.

**What I built:** 0Latency — a memory layer for AI agents. It works with Claude, GPT, Cursor, and any AI framework via REST API or MCP (Model Context Protocol).

**The meta part:** I used Claude Code + 0Latency to build 0Latency itself. Every decision Claude made got stored. When context compacted (which happens around 150K tokens), the memory layer kept everything accessible. We completed a 5-hour coding session with 15+ tasks without losing context once.

This caught production bugs. Like when Claude would acknowledge information ("got it, stored") but not actually persist it to the API. That's the exact failure mode we're solving for users. Fixed it before launch because we hit it ourselves.

**Stack:**
- Backend: Node.js + Express
- Database: Supabase (Postgres + pgvector)
- Redis for caching
- TypeScript + Python SDKs

**Features:**
- Sub-100ms recall
- Semantic search with temporal decay
- Knowledge graphs
- Works across all Claude surfaces (Desktop, Code, web)
- LangChain, CrewAI, AutoGen integrations

Launched tonight. Free tier (10K memories, 3 agents). No credit card required.

GitHub: github.com/0latency-ai/0latency  
Live: 0latency.ai

Solo founder, dogfooding my own product. Happy to talk about the technical architecture or the weird experience of using AI to build AI memory infrastructure.

---

## r/mcp (if it exists - otherwise skip)

**Title:** 0Latency MCP Server: Persistent memory for Claude with sub-100ms recall

Built an MCP server that gives Claude persistent memory across sessions. Just launched tonight.

**What it does:**
- Stores memories with semantic search
- Sub-100ms recall (median ~60ms)
- Temporal decay (recent memories score higher)
- Knowledge graph relationships
- Works across Claude Desktop, Code, and claude.ai

**Installation:**
```bash
npm install -g @0latency/mcp-server
```

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["@0latency/mcp-server"],
      "env": { "ZERO_LATENCY_API_KEY": "zl_..." }
    }
  }
}
```

**Tools exposed:**
- memory_add
- memory_recall
- memory_search
- memory_list
- memory_delete
- memory_graph

**Dogfooding story:** Used Claude Code with 0Latency enabled to build 0Latency. 5-hour session, 15+ tasks, zero context loss. Caught bugs we wouldn't have found otherwise.

Free tier: 10K memories, 3 agents.

GitHub: github.com/0latency-ai/0latency  
Docs: 0latency.ai  
MCP Registry: Listed under io.github.0latency-ai/0latency

Questions about architecture or MCP integration welcome.

---

## Submission Notes

**Order of posting:**
1. r/ClaudeAI (biggest Claude audience)
2. r/mcp (if exists - most technical)
3. r/AIAgents (broader agent audience)
4. r/SideProject (founder/builder audience)

**Timing:**
- Space posts 2-4 hours apart
- Post r/ClaudeAI first, monitor engagement
- Respond to comments quickly (first hour is critical)

**Tone:**
- Technical but accessible
- Story-driven (the dogfooding angle is unique)
- No marketing hype
- Answer questions honestly
- Admit limitations if asked

**Account setup:**
- Username preference: 0Latency > ZeroLatency > 0LatencyAI
- Email: justin@0latency.ai
- Profile: "Building persistent memory infrastructure for AI agents. Founder at 0Latency."
- Link: 0latency.ai
