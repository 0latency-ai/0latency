# 0Lat Origin Story — From Mem0 Failure to Zero-Latency Recall

## The Timeline

### March 4, 2026 — The Attempt
- Justin sends a YouTube video about OpenClaw memory solutions
- Previous Thomas recommends Mem0 as "Priority 1 — External Memory"
- Plan: sign up at app.mem0.ai, get API key, install plugin
- Thomas: "That's the big win — memory that lives outside the context window and can't be destroyed by compaction"
- Instructions given: `clawdbot plugins install @mem0/openclaw-mem0`

### March 5, 2026 — The Failure
- API key expired on first attempt
- Thomas discovers: "There's no @mem0/openclaw-mem0 plugin — that TODO was based on videos showing experimental/hypothetical features"
- The plugin literally didn't exist for OpenClaw
- Fallback: manual SSH + JSON config editing (`ssh ubuntu@your-server-ip`, `nano ~/.clawdbot/clawdbot.json`)
- Justin manually uploading mem0 key via SSH + nano
- Result: ❌ MEM0 plugin | Auto-capture/recall | Doesn't exist for Clawdbot+
- Also explored: Cognee (required Docker: `docker run -p 8000:8000 cognee/cognee:latest`) — too heavy

### March 8, 2026 — Server Rebuilt
- AWS server lost. Rebuilt from scratch on DigitalOcean
- Thomas rebuilt from zero — no memory of previous attempts survived

### March 12, 2026 — The Seed
- Justin asks: "Can this all be tied into SQLite database and vector search to possibly make for a more robust memory capacity?"
- This is the first articulation of what would become the structured memory system

### March 18, 2026 — The Decision
- Justin sends video about OpenClaw memory mistakes
- Thomas does full competitive teardown: Mem0, Zep, Letta/MemGPT, OpenViking, CrewAI, LangChain
- Key finding: Mem0 "weak on recall intelligence and context budgeting — developer must manually query and inject"
- Justin greenlights building our own memory system

### March 19, 2026 — The Build
- 8+ hour marathon session
- Built: extraction, storage, recall, negative recall, entity linking, topic coverage, contradiction detection
- 329 memories extracted from the session itself
- Compaction hits at 175K tokens — the first real test

### March 20, 2026 — Gap Analysis + Fixes
- Post-compaction: 329 memories existed but recall returned 0 for valid queries
- Scored 65% effective (up from 64% on previous gap analysis)
- 6 fixes implemented in 2 hours:
  1. Session handoff (Layer 2) — rolling conversation state
  2. Decision extraction quality — rationale captured
  3. Structured list preservation — checklists stay coherent
  4. Deduplication — two-tier similarity check
  5. Hybrid recall — semantic + keyword search
  6. Correction type tightened
- API scaffold built (FastAPI, 7 endpoints)
- Competitive analysis of 10+ ClawHub memory skills
- Product named: 0Lat (zero-latency recall)
- Strategy: skip Phase A launch fanfare, go direct to Phase B API

## The Pitch (One Sentence)
"I tried every memory solution on the market — Mem0, Cognee, 10+ ClawHub skills. None worked. So I built one that does. It removes the agent from the extraction loop entirely. Zero-latency recall after compaction."

## The Proof
- Gap Analysis #1: Vanilla memory retained 64%. The important 36% was lost.
- Gap Analysis #2: Our system extracted 329 memories but recall scored 40%. Fixed to target 99%.
- The handoff system: post-compaction agent reads one file and orients instantly.

## Key Screenshots (saved as inbound media)
1. `file_318` — March 4-5 overview: Mem0 and Cognee as the two options
2. `file_319` — Detailed: "Your Todo When Home: Get Mem0 API key"
3. `file_320` — "What about going back to original configurations?"
4. `file_321` — The pain cascade: plugin doesn't exist, key expired, SSH config
5. `file_322` — The same chat showing current config (working) vs mem0 attempts (failed)

## For the Landing Page
Before: "SSH into your server. Edit the JSON config. Upload API keys via nano. Hope the plugin exists. It didn't."
After: "One install. Zero configuration. Your agent remembers everything."

## For the Greg DM
"Watched your pod with Moritz. He's right that memory is the pain point. Every memory tool on ClawHub tries to help the agent organize its own notes better. We proved that approach is fundamentally broken. The agent forgets to write down the important stuff. We measured it: 64% retained, and the 36% lost was the most valuable.

So we built something different: a system that removes the agent from the extraction loop entirely. Every turn gets extracted into structured memory automatically. Conversation state updates in real-time. After compaction, the agent orients in under a second.

We're calling it zero-latency recall. Here's a demo showing what happens when the context window resets."

## Additional Screenshots (file_326 through file_332)
- file_326: AWS terminal — `echo 'export MCP...'`, `nano ~/.bashrc`, `sed` commands. Raw server admin for memory setup.
- file_327: Wider view of terminal commands + "isn't there just an echo command I can use?"
- file_328: **THE HERO SHOT** — "YOU'RE NOT REMEMBERING THAT I'M TRYING TO MAINTAIN GOOD API HYGIENE HERE!!! THIS IS THE FUCKING PROBLEM - YOU'RE NOT REMEMBERING ANYTHING!!!" followed by Thomas apologizing and then discovering Mem0 plugin doesn't exist.
- file_329: Additional context from the same exchange
- file_330: Fallback to built-in memory-lancedb plugin — solutions table showing what's actually available
- file_332: **DEFINITIVE OVERVIEW** — Full "mem0" search results (left panel) + SSH/jq/nano exchange (right panel). Entire timeline in one frame.

## Total Screenshot Inventory: 13 screenshots (file_318 through file_332)

## Pricing Revision (based on Gemini deep research)
- Mem0: $19 Starter (crippled) → $249 Pro (graph) → Custom Enterprise
- Revised 0Lat pricing:
  - Free: 1,000 memories, vector recall, 1 agent
  - Pro ($29/mo): Unlimited, graph/entity edges, conversation state, hybrid recall, multi-agent, import
  - Team ($99/mo): Everything + multi-tenant, RBAC, webhooks, priority support
  - Enterprise ($249/mo): SSO, data residency, SLA, dedicated support
- Strategy: own the $19-$249 gap that Mem0 skips entirely
