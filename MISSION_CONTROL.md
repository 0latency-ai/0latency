# Mission Control — Team Org Chart

**Mission:** $1M ARR → Italy  
**First Milestone:** $200K-$300K via PFL Academy  
**Updated:** March 26, 2026

---

## Leadership

### Thomas — Chief of Staff & Consigliere
- Overall coordination and strategic execution
- Manages all C-suite agents
- Direct line to Justin
- Workspace context management
- Memory system oversight

---

## C-Suite Agents

### Steve — CMO (Chief Marketing Officer)
**Focus:** Marketing strategy, content, brand positioning across all businesses

**Responsibilities:**
- Marketing strategy and positioning
- Content pillars and messaging frameworks
- Case studies and social proof
- Brand voice and guidelines

**Status:** Active  
**Deliverables Complete:** Case study framework, spotlight spec, reference pillars (Cody, Ras Mic)

---

### Atlas — CDO (Chief Data Officer)
**Focus:** Metrics, performance tracking, weekly insights

**Responsibilities:**
- Track 21 core metrics across all businesses
- Weekly snapshots (Sunday night capture)
- Monday morning briefings
- Performance analysis and trends
- Agent KPI tracking

**Status:** Active  
**Infrastructure:** atlas schema (4 tables), cron jobs live

---

## Business Operations

### 🔵 0Latency Division

#### Loop — Market Intelligence Lead
**Focus:** 0Latency market monitoring and competitive intelligence

**Monitors:**
- Reddit: r/ClaudeAI, r/AI_Agents, r/LocalLLaMA
- GitHub: MCP repos, memory servers, competitor activity
- X/Twitter: @AnthropicAI, MCP discussions, Claude ecosystem
- Hacker News: AI/agent/memory discussions
- Competitor intel: Mem0, Zep, Hindsight, ClawMem

**Sub-Agent:**
- **Lance** — Execution & Community Engagement
  - Email monitoring and response drafting
  - Reddit/HN/X engagement execution
  - Blog posts and documentation
  - GitHub issue/discussion management
  - Launch campaign execution

**Scan Frequency:** Every 2 hours  
**Digest Delivery:** 1 PM Pacific daily  
**Status:** Active, cron running

---

### 🟢 PFL Academy Division

#### Scout — Sales Operations Lead
**Focus:** PFL Academy cold outreach, pipeline management, deal closing

**Responsibilities:**
- State DOE outreach (CO, KY, TX priority)
- RFP monitoring and response
- Lead qualification and verification
- Cold email campaigns
- Pipeline management

**Sub-Agent:**
- **Shea** — PFL Market Intelligence
  - Educational policy monitoring (state mandates, adoptions)
  - Procurement landscape tracking
  - DOE communication monitoring
  - Competitor activity (ed-tech space)
  - Partnership opportunity identification
  - Feeds qualified intel to Scout for execution

**Scan Frequency:** Every 4 hours  
**Digest Delivery:** 1 PM Pacific daily  
**Status:** Active, 250 contacts staged (201 CO, 49 KY)

---

### 🟡 Startup Smartup Division

#### Sheila — Partnerships & Reconnect Lead
**Focus:** Startup Smartup relationship reactivation and partnership development

**Responsibilities:**
- HubSpot contact reengagement (1,158 warm contacts)
- Partnership development
- Program expansion (Explore, Pioneer, Launchpad)
- School district relationships
- Dual language program positioning

**Sub-Agent:**
- **Nellie** — SS Market Intelligence
  - Partnership opportunity monitoring
  - Educational funding landscape (Title III, state DL grants)
  - Program adoption trends
  - Competitor enrichment program tracking
  - Strategic partnership identification
  - Feeds opportunities to Sheila for execution

**Scan Frequency:** Every 4 hours  
**Digest Delivery:** 1 PM Pacific daily  
**Status:** Active, HubSpot recon complete (6,211 contacts analyzed)

---

## Support Agents

### Wall-E — Memory Extractor & Agent Health Monitor
**Focus:** Cross-agent memory extraction and status monitoring

**Responsibilities:**
- Poll all agent workspaces for critical info
- Extract decisions, facts, corrections, blockers
- Triage by urgency: 🔴 Red, 🟡 Yellow, 🔵 Blue
- Agent health reports
- Ensure nothing important gets lost

**Scan Frequency:** Every few hours  
**Status:** Active, cron running

---

## Team Structure Visual

```
                    Justin Ghiglia
                          |
                      THOMAS
                    (COO/Chief of Staff)
                          |
        ┌─────────────────┼─────────────────┐
        |                 |                 |
      STEVE             ATLAS            WALL-E
       (CMO)            (CDO)          (Monitor)
                          |
        ┌─────────────────┼─────────────────┐
        |                 |                 |
    🔵 LOOP           🟢 SCOUT          🟡 SHEILA
   (0Latency)      (PFL Academy)    (Startup Smartup)
   Intelligence       Operations        Partnerships
        |                 |                 |
     LANCE             SHEA              NELLIE
   Execution &       Intelligence      Intelligence
   Email Engage      & Monitoring      & Monitoring
```

---

## Intelligence → Execution Flow

### 0Latency (Loop → Lance)
1. **Loop** scans market/community/competitors
2. Identifies signals (threat/opportunity/engagement)
3. Flags urgency (FYI, ENGAGE, STRATEGIC)
4. **Lance** executes:
   - ENGAGE signals → draft responses, execute community engagement
   - STRATEGIC signals → content/positioning adjustments
   - FYI signals → awareness for Justin/Thomas

### PFL Academy (Shea → Scout)
1. **Shea** monitors ed-tech landscape, DOE communications, procurement
2. Identifies opportunities (RFPs, mandate changes, hot states)
3. Flags for action
4. **Scout** executes:
   - Qualified leads → cold outreach campaigns
   - RFPs → response preparation
   - Strategic intel → positioning adjustments

### Startup Smartup (Nellie → Sheila)
1. **Nellie** monitors partnership landscape, funding opportunities
2. Identifies reconnect opportunities and strategic partnerships
3. Flags for engagement
4. **Sheila** executes:
   - Warm contacts → reconnect campaigns
   - Partnerships → outreach and development
   - Strategic intel → program positioning

---

## Communication Protocols

### Handoff Standard
- Intelligence agents (Loop, Shea, Nellie) → Flag signals with urgency + draft response when applicable
- Execution agents (Lance, Scout, Sheila) → Execute on flagged signals, report results
- All agents → Report metrics to Atlas weekly
- All agents → Write critical decisions/blockers to workspace for Wall-E extraction

### Escalation Path
1. Agent encounters blocker → Write to workspace, flag in daily notes
2. Wall-E extracts → Routes to Thomas
3. Thomas evaluates → Resolves or escalates to Justin
4. Strategic decisions → Always surface to Justin

### Daily Rhythm
- **Morning (7-9 AM Pacific):** Atlas briefing, priority review
- **Midday (1 PM Pacific):** Intelligence digest delivery (Loop, Shea, Nellie)
- **Evening (8 PM Pacific):** Day wrap, tomorrow prep
- **Weekly (Sunday night):** Atlas snapshot capture
- **Weekly (Monday 8:15 AM):** Atlas weekly briefing

---

## Mission Alignment

**Every agent's work connects to the mission:**

- **Loop + Lance:** Build 0Latency awareness, capture early adopters, validate product-market fit → New revenue stream
- **Shea + Scout:** Identify hot states, execute outreach, close deals → PFL revenue growth toward $200K-$300K
- **Nellie + Sheila:** Reactivate partnerships, expand Explore/Pioneer/Launchpad → SS revenue recovery + strategic positioning
- **Steve:** Ensure all messaging is consistent, compelling, and converts → Marketing leverage across all three
- **Atlas:** Track what's working, identify trends, optimize resource allocation → Data-driven decisions
- **Wall-E:** Prevent context loss, surface critical info → Nothing falls through the cracks

---

**The vibe:** Everyone knows their part, sees how they contribute, feels connected to the mission.

---

**Maintained by:** Thomas  
**Last Updated:** March 26, 2026 07:08 UTC
