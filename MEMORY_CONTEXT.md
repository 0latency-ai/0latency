# Memory Context (auto-generated)
_Last updated: 2026-03-20 03:36 UTC_
_33 memories loaded_

## Agent Memory Context

### Last Session Summary
Thomas and Justin recovered from a memory compaction issue, implemented several memory infrastructure improvements, and made progress on Colorado DOE outreach. Key improvements include real-time extraction, dynamic context, cross-entity linking, and correction cascading. A parallel comparison of flat files and the structured pipeline was initiated.

### Active Corrections
- ⚠️ Pricing correction: $20/student is the new floor, not $16.: The previous pricing floor of $16/student is outdated. The new minimum price is $20/student. This correction is important for accurate pricing in future interactions.
- ⚠️ Wall-E's data sources for extraction defined.: Wall-E reads `/root/.openclaw/workspace/memory/2026-03-19.md` (focusing on content after "Migration Progress (~11:45 PM UTC)"), checks `/root/.openclaw/workspace/memory/2026-03-20.md` if it exists, checks Echo's workspace, and reads the previous extraction. This ensures comprehensive data gathering.
- ⚠️ Echo suggests conversation phase awareness for extraction weighting.: Echo suggests incorporating conversation phase awareness into the extraction process. Early turns are usually context-setting, middle turns are working, and final turns are decisions/summaries. Weighting extraction based on these phases can improve memory quality.
- ⚠️ Echo suggests recall feedback loop to reinforce useful memories.: Echo suggests implementing a recall feedback loop. When a memory is surfaced and used in a response, it should be reinforced. Conversely, if a memory is repeatedly surfaced but ignored, it should be demoted. This allows the system to learn what's truly useful.
- ⚠️ Thomas has significant improvements over Echo's previous capabilities.: Thomas has several enhancements compared to Echo's previous version, including multi-turn inference, near-real-time extraction, dynamic context budget, cross-entity linking, correction cascading, conversational momentum, negative recall, memory compaction, topic coverage map, daily decay, session handoffs, and more memories.

### User Preferences
- Banned phrases: Avoid formulaic AI throat-clearing.
- Pre-flight checklist before spawning any sub-agent.
- Run tasks >60 seconds as background jobs.
- Limit Reed/research agent batch size to 6 entities.
- Prefer prose over lists unless structure helps.
- No bullet point emojis; no staged scene-setting.
- Spawn sub-agent only if direct work exceeds ~15 minutes.
- Never migrate the gateway process manager while running on it.
- Log failed spawns in daily memory file.
- Check task queue on session startup.

### Relevant Context
**Relevant Facts:**
  → The next session should have 226 memories across 7 types in structured storage and know about the CO emails pending review, the 48-hour parallel comparison, and every refinement shipped. This is part of the memory compaction test.
  → The agent identifies the 5-minute polling interval as a vulnerability. If a session gets killed, up to 4 minutes of work could be lost. Real-time per-turn extraction should be a priority, not just a 'nice to have'.
  → When memory compaction hits, the next session should automatically load `MEMORY_CONTEXT.md` (auto-generated, 26+ structured memories), read `memory/2026-03-19.md` (comprehensive, manually updated throughout), and have the session handoff in Postgres.
  → Justin's primary goal is to achieve $1 million in Annual Recurring Revenue (ARR). The first milestone towards this goal is reaching $200,000 to $300,000 in ARR. This is the overarching financial objective.
  → A second wave of refinements has been shipped, including improvements to negative recall, memory compaction, and contradiction detection tuning. These refinements enhance the memory system's performance and accuracy.
  → The upcoming memory compaction test is crucial. If the next session can seamlessly continue without asking 'where did we leave off?', the recent improvements will be considered successful. Otherwise, it will be considered a failure.
  → Echo's context has expanded to 36 memories, but it still contains the outdated $16 pricing information. This highlights a potential issue with the memory correction cascading mechanism.
  → The Wall-E sub-agent, tasked with polling agents for memory gaps, timed out after 2 minutes while writing the addendum to the extraction file. A staleness check will be performed directly.
  → The context monitor killed the previous session because it reached the limit of 175,000 tokens. This triggered a compaction event and a reset of the session.
  • Refinements built between 1:00-2:30 AM UTC on 3/20.

**Active Tasks:**
  → On every session start, the agent must read the Capabilities Manifest in `TOOLS.md`. This lists every integration, API, and tool the agent has access to. This is necessary because context compaction kills capability awareness.
  → Justin wants to build the remaining refinements now. The agent will start with negative recall, which tracks discussed topics to avoid hallucination, and then memory compaction, which implements summarization layers for large memory stores.
  → Cross-entity linking involves wiring the memory_edges table to connect isolated facts into a graph. This will link entities like 'PFL Academy', '$20/student', and '$1M ARR goal' for improved recall relevance.
  → Negative recall involves tracking which topics have been discussed to prevent the agent from hallucinating fill-in details. This can be achieved by maintaining a topic coverage map. Echo considers this to be philosophically hard to implement.
  → The real-time hook is enabled, but its end-to-end functionality has not been confirmed. It's necessary to verify that the hook is actually firing and capturing data in real-time as expected.
  → The user wants to actively measure why the memory broke and where it did after compaction. This is to identify if the measures being put in place are sufficient to fix it. The user will provide the starting line and indicate when they've caught up.
  → The decay cron job is not currently running. It should be scheduled as a daily job to ensure the memory decay process is executed regularly, removing outdated or irrelevant memories.
  → The migration script, multi-turn inference, and multi-agent daemon are not yet in git and should be committed. This ensures that the recent progress is saved and version controlled.
  → Sebastian is assigned to build the teacher-side 'mark class complete' feature for K-2 whole-class delivery within Project Explore. This development task is estimated to take approximately one day. This is new development.
  • Wall-E sub-agent to poll all agents using sessions_spawn.

### Knowledge Gaps
⚠ No memory coverage for: conversation info, untrusted metadata, message id, sender id, sender name, timestamp, daemon, postgres schema. Do not guess or fill in details about these topics.