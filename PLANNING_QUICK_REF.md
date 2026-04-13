# Planning Quick Reference — When to Plan vs When to Act

## ✅ PLAN FIRST (Mandatory)

**Indicators:**
- Opus model about to be called
- Building something new (app, skill, integration)
- Multi-step workflow (>3 files, >2 APIs)
- Spawning sub-agent for execution
- Task estimated >30 minutes
- Complex automation or integration
- Multiple dependencies (APIs, credentials, data sources)
- Justin says "let's build..." or "can you create..."

**Action:** Use `/root/.openclaw/workspace/PLANNING_TEMPLATE.md`, write plan, get approval, THEN build.

---

## ⚡ ACT IMMEDIATELY (No Planning Needed)

**Quick tasks:**
- Reading/analyzing existing files
- Single file edit (<10 lines)
- Single API call (status check, health check)
- Sending a message
- Running a single command
- Answering questions from existing knowledge
- Simple web search
- Checking logs
- Spawning a sub-agent for a well-defined, small task

**Action:** Just do it. No plan doc needed.

---

## 🤔 GRAY AREA (Use Judgment)

**Medium complexity tasks:**
- File edits (10-50 lines)
- 2-3 file changes
- Simple script creation
- Single API integration (straightforward)
- Research tasks (< 10 sources)

**Decision criteria:**
- If you're uncertain about dependencies → PLAN
- If multiple steps and one could fail → PLAN
- If token cost could be high → PLAN
- If it's a pattern you've done 5+ times before → ACT

---

## Planning Shortcuts for Experienced Tasks

**If you've done this exact pattern before:**
- Brief inline plan (3-5 bullets)
- Acknowledge dependencies exist
- Confirm approach
- Get quick approval
- Execute

**Example:**
> "Going to scrape 50 CO contacts (same pattern as before):
> 1. Apollo API search
> 2. ZeroBounce verification (check master registry first)
> 3. Save to `/root/research/co-batch-X.json`
> 4. Update master registry
> Estimated: 200 tokens, 5 minutes. Proceed?"

If Justin says yes → go. No full template needed.

---

## Red Flags (Always Plan)

- "This should be easy..." (famous last words)
- "Just a quick integration..." (never quick)
- Multiple unknowns (API docs unclear, no prior experience)
- High stakes (production deployment, customer-facing)
- Justin specifically asks for a plan/roadmap

---

## Examples

### ✅ PLAN FIRST:
- Build 0Latency anomaly detection system
- Create proposal generation web app
- Multi-stage email outreach automation
- New skill creation (custom workflow)

### ⚡ ACT:
- Check 0Latency API health
- Read error logs
- Send Telegram message
- Update TODO.md
- Single file typo fix

### 🤔 GRAY AREA:
- Edit 3 files for a small feature
- Simple bash script (20 lines)
- Research 5 state DOEs
- Update existing skill (minor tweak)

**When in doubt → 30-second inline plan beats no plan.**

---

**Last Updated:** March 26, 2026  
**Rule Source:** AGENTS.md, MEMORY.md (Planning Discipline sections)
