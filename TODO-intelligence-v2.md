# Intelligence Framework V2 - ON HOLD

**Status:** Paused by Justin (March 25, 2026, 9:18 AM UTC)
**Reason:** Hold V1, put V2 on todo list

---

## The Vision

Three business intelligence agents running parallel operations, scanning markets/communities/competitors/emails, evaluating signals, routing appropriately.

**Framework:** Scan → Evaluate → Route

**Four Routing Pathways:**
1. **FYI → Justin** - Personally interesting, context matters, no action
2. **FYI → C-Suite** - Operationally relevant for Thomas/Steve/Scout/Sheila
3. **ENGAGE** - Comment, connect, repost, write response piece
4. **STRATEGIC** - Positioning adjustment needed (micro/macro pivot)

---

## The Three Agents

### Loop - 0Latency CMO
**Channels:**
- YouTube: Nate B Jones, @RAmjad, AI Revolution X, theMITmonk
- Reddit: r/ClaudeAI, r/ClaudeCode, r/AI_Agents, r/LocalLLaMA
- GitHub: Mem0, Zep, Hindsight, MCP repos (stars/forks/issues)
- X/Twitter: @0latencyai mentions, "MCP memory", "Claude memory" complaints
- HN: MCP/memory posts
- Discord: Anthropic MCP channels

**Focus:** Developer tools market, agent infrastructure, competitive intel

### Scout 2.0 - PFL Academy Business Agent
(Upgrade Scout from executor to full business operator)

**Intelligence Channels:**
- State DOE websites/procurement boards (all 50 states)
- Reddit: r/teachers, r/financialliteracy, r/education
- Ed-tech news: EdSurge, eSchool News, Education Week
- Financial literacy orgs: CEE, Jump$tart, NGPF
- K-12 RFP aggregators
- Email: justin@pflacademy.co, info@pflacademy.co

**Execution:** Cold outreach, follow-ups, pipeline management
**Focus:** Education policy, curriculum adoption, procurement opportunities

### Sheila 2.0 - Startup Smartup Business Agent
(Upgrade Sheila from reconnect specialist to full business operator)

**Intelligence Channels:**
- Enrichment program news
- Dual language/bilingual education communities
- After-school program associations
- Entrepreneurship education orgs (Network for Teaching Entrepreneurship, etc.)
- Title III funding announcements
- Email: justin@startupsmartup.com, contact@startupsmartup.com

**Execution:** HubSpot reconnects, partnership outreach, warm campaigns
**Focus:** Enrichment sales, partnership opportunities, funding

---

## V2 Enhancements (Build These)

### 1. Auto-Draft Responses (ENGAGE pathway)
- Don't just flag "you should comment" — provide ready-to-post draft
- One-click approve/edit/send
- Learn from which drafts Justin uses vs rejects

### 2. Cross-Agent Pattern Detection
- Surface intersections between agents' findings
- Example: "Loop + Scout convergence: AI in education procurement is accelerating"

### 3. Opportunity Scoring (1-10)
- Score alignment with current priorities
- High score = perfectly aligned, drop-everything opportunity
- Low score = interesting but not urgent

### 4. Backchannel Research (high-value signals)
- Auto-research high-priority people/orgs when detected
- Who are they? Reach? Influence? What else have they said?
- Example: RAmjad posts about memory → instant brief on audience, past content, connections

### 5. Sentiment Tracking Over Time
- Not just "here's what people are saying" but "sentiment is shifting from X to Y"
- Track how MCP memory complaints trend over weeks

### 6. Weekly Strategic Brief (Sundays)
- Beyond daily digest: trends, positioning recommendations, week-ahead planning
- "Here's what happened, here's what it means, here's what to do"

### 7. Action Tracking + Learning
- When Justin engages/adjusts strategy based on a signal, track the outcome
- Learn what types of opportunities convert vs which are noise

---

## Technical Architecture

### File Structure
```
/root/intelligence/
  framework/
    evaluator.py (shared evaluation logic)
    router.py (pathway decision tree)
    drafter.py (auto-response generation)
    researcher.py (backchannel research)
  agents/
    loop/config.json + scanner.py
    scout/config.json + scanner.py
    sheila/config.json + scanner.py
  scripts/
    scan_all.sh
    send_digest.py
    weekly_brief.py
  db/
    schema.sql
```

### Database Schema
```sql
CREATE TABLE intelligence.signals (
  id UUID PRIMARY KEY,
  agent TEXT, -- loop | scout | sheila
  source TEXT, -- youtube | reddit | github | email | etc
  content TEXT,
  url TEXT,
  timestamp TIMESTAMPTZ,
  threat_level INT, -- 0-10
  opportunity_level INT, -- 0-10
  urgency TEXT, -- low | medium | high | critical
  pathway TEXT, -- fyi_justin | fyi_csuite | engage | strategic
  status TEXT, -- new | reviewed | actioned | dismissed
  draft_response TEXT, -- auto-generated if ENGAGE
  outcome TEXT, -- tracked if actioned
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE intelligence.digest_history (
  id UUID PRIMARY KEY,
  agent TEXT,
  sent_at TIMESTAMPTZ,
  signals_included UUID[],
  recipient TEXT -- justin | csuite
);

CREATE TABLE intelligence.patterns (
  id UUID PRIMARY KEY,
  agents TEXT[], -- which agents detected
  pattern TEXT, -- description
  signals UUID[], -- contributing signals
  detected_at TIMESTAMPTZ
);

CREATE TABLE intelligence.sentiment_tracking (
  id UUID PRIMARY KEY,
  agent TEXT,
  topic TEXT,
  sentiment FLOAT, -- -1 to 1
  volume INT,
  measured_at TIMESTAMPTZ
);
```

### Cron Schedule
- **Loop:** Scan every 2 hours (7 AM - midnight PST)
- **Scout:** Scan every 4 hours (8 AM - 8 PM PST)
- **Sheila:** Scan every 4 hours (8 AM - 8 PM PST)
- **All:** Daily digest at 1 PM PST
- **All:** Weekly strategic brief Sunday 10 AM PST

---

## Implementation Priority

**Phase 1 (Core):**
1. Scanner infrastructure (RSS, Reddit API, GitHub API, email parsing)
2. Evaluation framework (threat/opp/urgency scoring)
3. Routing logic (four pathways)
4. Database schema
5. Daily digest delivery (Telegram)

**Phase 2 (Enhancements):**
6. Auto-draft responses
7. Opportunity scoring
8. Cross-agent pattern detection
9. Sentiment tracking
10. Weekly strategic brief
11. Backchannel research
12. Action tracking + learning

---

## When to Build

Build this when:
- 0Latency is launched and stable
- PFL Academy has breathing room
- Scout and Sheila have proven execution workflows
- Justin explicitly says "time to build intelligence V2"

**Do NOT build until explicitly asked.**

---

## Notes

- This replaces the March 25 aborted build (killed sub-agent df2f2e9c at 9:18 AM UTC)
- Original plan had separate Shea/Nellie agents; revised to upgrade Scout/Sheila instead
- Intelligence agents both FIND and WORK opportunities (not just routing)
- Email is part of intelligence, not separate
