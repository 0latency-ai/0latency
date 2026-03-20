# Memory Context (auto-generated)
_Last updated: 2026-03-20 01:10 UTC_
_29 memories loaded_

## Agent Memory Context

### Active Corrections
- ⚠️ Justin prioritizes real-time extraction, then dynamic context budget.: Justin wants the agent to prioritize tasks in the following order: 1) Real-time per-turn extraction, 2) Dynamic context budget. This order is based on impact, with real-time extraction being the most important.
- ⚠️ Multi-turn inference implemented: Extraction uses sliding window of 4 turns.: Multi-turn inference has been implemented, allowing the extraction process to consider a sliding window of the last 4 turns as context. This enables the agent to catch implications and connections across multiple messages, leading to more accurate and comprehensive memory extraction.
- ⚠️ Schemas: 'thomas' (memory), 'atlas' (performance).: The system uses two primary schemas: 'thomas' with 12 tables for the Thomas memory system, and 'atlas' with 4 tables (weekly_snapshots, metric_definitions, events, agent_performance) and 5 RPC functions for performance monitoring.
- ⚠️ Cron schedule: Heartbeat, context monitor, daily reset, Thomas pulse/check, reindex, reports.: The system has 11 cron jobs scheduled, including a heartbeat every 5 minutes, context monitoring, daily session reset at 6 AM Pacific, Thomas pulse at 8 AM Pacific, embedding reindex on Sundays, and morning reports at 7:30 AM Pacific.
- ⚠️ Sheila agent status: Active, HubSpot recon done, reconnect list staged.: Sheila is an active agent who has completed HubSpot reconnaissance and staged a reconnect list. HubSpot data shows 6,211 contacts, with 1,158 deemed warm/SS-relevant.

### User Preferences
- Banned phrases: Avoid formulaic AI throat-clearing.
- Run tasks >60 seconds as background jobs.
- Check task queue on session startup.
- Limit Reed/research agent batch size to 6 entities.
- Never migrate the gateway process manager while running on it.
- Log failed spawns in daily memory file.
- Try it first, report results if unsure of capability.
- Match the tool to the scope of the task.
- Be direct, no jargon, no filler in communication.
- Prefer prose over lists unless structure helps.

### Relevant Context
**Recent Decisions:**
  → The user said "ship it", indicating approval to proceed with wiring the agent's session transcripts into the memory daemon. This means the agent should now begin the process of integrating its transcripts into the memory system.

**Relevant Facts:**
  → Steve is an active agent who has completed both deliverables (case study and spotlight spec) and has two reference pillars loaded (Cody and Ras Mic). This indicates Steve is well-prepared and has necessary resources.
  → The agent identifies the 5-minute polling interval as a vulnerability. If a session gets killed, up to 4 minutes of work could be lost. Real-time per-turn extraction should be a priority, not just a 'nice to have'.
  → Justin is communicating directly with Echo regarding the gap analysis. This suggests a collaborative effort to address the memory gaps and potentially implement solutions.
  → The memory system's performance is assessed at 85-90% for extraction and storage, but only 75% for recall. This indicates a potential bottleneck in the recall process, suggesting that improvements are needed to retrieve information effectively.
  → The Wall-E sub-agent, tasked with polling agents for memory gaps, timed out after 2 minutes while writing the addendum to the extraction file. A staleness check will be performed directly.
  → The context monitor killed the previous session because it reached the limit of 175,000 tokens. This triggered a compaction event and a reset of the session.

**Active Tasks:**
  → On every session start, the agent must read the Capabilities Manifest in `TOOLS.md`. This lists every integration, API, and tool the agent has access to. This is necessary because context compaction kills capability awareness.
  → The user wants to actively measure why the memory broke and where it did after compaction. This is to identify if the measures being put in place are sufficient to fix it. The user will provide the starting line and indicate when they've caught up.