# Memory Context (auto-generated)
_Last updated: 2026-03-20 07:19 UTC_
_52 memories loaded_

## Agent Memory Context

### Last Session Summary
Justin and the agent are discussing the possibility of selling the zero-latency recall product as an API, targeting Greg's audience who build products rather than install OpenClaw skills. The agent suggests that Phase A (ClawHub launch) should be quiet, with a focus on Phase B as an API launch.

### Active Corrections
- ⚠️ Revised plan: Quiet Phase A, focus on Phase B API launch.: The plan is to skip a formal launch for Phase A on ClawHub and instead focus on building the API (Phase B) as quickly as possible. The Greg DM and content push will be timed with the API launch, allowing potential users to immediately test and integrate the memory system.
- ⚠️ Decision: Proceed quickly from Phase A to Phase B.: Justin agreed that the project should move quickly from Phase A to Phase B. Phase A is seen as a validation checkpoint, while Phase B is where the real business opportunity lies with API customers and a larger TAM.
- ⚠️ OpenClawd pitch: Automate memory, don't rely on agent notes.: The key differentiator for OpenClawd is that it automates memory extraction, handoff, and recall, without relying on the agent to document itself. This addresses the problem identified in Gap Analysis #1, where the agent failed to retain the most valuable information.
- ⚠️ Compaction test is the gate for further development: Passing the compaction test is the primary gate for all further development efforts. Until the system proves it can survive compaction, all other tasks are considered premature.
- ⚠️ Sebastian held in reserve; team will build A and B: Sebastian will be held in reserve as a safety net for tasks that the core team cannot handle, such as app store submissions or debugging browser-related issues. The core team will handle the development of Phase A and Phase B.

### User Preferences
- Banned phrases: Avoid formulaic AI throat-clearing.
- Check task queue on session startup.
- Pre-flight checklist before spawning any sub-agent.
- Run tasks >60 seconds as background jobs.
- Spawn sub-agent only if direct work exceeds ~15 minutes.
- Agent needs recent conversation history after compaction
- Limit Reed/research agent batch size to 6 entities.
- Prefer prose over lists unless structure helps.
- No bullet point emojis; no staged scene-setting.
- Historical imports need lower default importance.

### Relevant Context
**Recent Decisions:**
  → The user said "ship it", indicating approval to proceed with wiring the agent's session transcripts into the memory daemon. This means the agent should now begin the process of integrating its transcripts into the memory system.
  → The user suggests addressing privacy concerns in the data policy. Users worried about privacy can choose not to sign up or share sensitive info, placing the onus on them.
  → Justin is holding off on purchasing the `0lat.ai` or `0latency.ai` domain names for $49.99 on GoDaddy until the product name is finalized and tested. Committing to a brand before testing it is not ideal.

**Relevant Facts:**
  → The ultimate test of the fixes is whether the agent can read the `HANDOFF.md` file and instantly resume the conversation after compaction. This will demonstrate zero-latency recall.
  → The agent identifies the 5-minute polling interval as a vulnerability. If a session gets killed, up to 4 minutes of work could be lost. Real-time per-turn extraction should be a priority, not just a 'nice to have'.
  → Justin's memory system differs from competitors by removing the agent from the memory extraction loop. The daemon extracts memories, handoff updates, and recall surfaces information independently of the agent's actions. This addresses the problem identified in Gap Analysis #1, where the agent failed to retain valuable information.
  → The agent's last memory before compaction was the user stating "1. That will resolve itself momentarily. 2. I mean, I expect we'll need to test it as a new user on a fresh install, clearly..."
  → The upcoming memory compaction test is crucial. If the next session can seamlessly continue without asking 'where did we leave off?', the recent improvements will be considered successful. Otherwise, it will be considered a failure.
  → Steve is an active agent who has completed both deliverables (case study and spotlight spec) and has two reference pillars loaded (Cody and Ras Mic). This indicates Steve is well-prepared and has necessary resources.
  → Justin's primary goal is to achieve $1 million in Annual Recurring Revenue (ARR). The first milestone towards this goal is reaching $200,000 to $300,000 in ARR. This is the overarching financial objective.
  → The next session should have 226 memories across 7 types in structured storage and know about the CO emails pending review, the 48-hour parallel comparison, and every refinement shipped. This is part of the memory compaction test.
  → Justin tried Mem0 and Cognee around March 4-5, before the current memory system was built. He encountered issues with both, including missing OpenClaw plugins, expired API keys, and painful setup. This led to the development of the current native memory system.
  → The system is not using Mem0. It was either an early experiment or discussed but never installed. It was replaced with a custom extraction daemon that auto-extracts facts from conversations, giving full control and eliminating third-party dependencies.
  → The current memory architecture captures individual memories (Layer 1) but lacks a rolling summary of the active conversation thread, decisions, and open items (Layer 2). This missing layer is crucial for maintaining context and coherence across turns, especially after compaction.
  → The `HANDOFF.md` file is updated live as the conversation progresses. Every time the conversation state shifts, the daemon regenerates the file. This ensures that the file always reflects the current state of the conversation, regardless of when compaction occurs.
  → While the code for the memory system is replicable, the real value lies in its speed of deployment, battle-tested nature, compounding effect of continuous learning, and the import pipeline for historical data.
  → Thomas's scripts are located in the /root/scripts/ directory. These scripts include bootstrap, pulse, stale check, checkpoint, save_*, and reindex. This is the location to find and manage automated tasks.
  → Thomas's database connection uses a Session Pooler located at aws-1-us-east-1 because the server lacks IPv6 support, preventing direct database connections. This is important for understanding the network configuration.
  → The 3/19 file was updated at 02:39 UTC, indicating activity since the last Wall-E poll at 23:00 UTC. The bottom of the file contains new content about refinements built between 1:00-2:30 AM UTC. This information is relevant for the Wall-E poll.
  → The Wall-E sub-agent, tasked with polling agents for memory gaps, timed out after 2 minutes while writing the addendum to the extraction file. A staleness check will be performed directly.
  → Selling the memory system as an API, similar to Mem0, is a viable option. The current architecture supports it, and wrapping the existing Python functions in FastAPI would take about a day. This approach would allow developers to easily integrate the memory system into their applications.
  • Phase A is low-risk and can validate the business quickly.
  • "Zero-latency recall" is a technical claim, not a tagline

**Active Tasks:**
  → The agent notes that decisions made during the conversation (proxy Gemini key, data policy, name TBD, error handling) were not captured as structured memories. Real-time memory extraction is needed to capture these decisions for instant recall.
  → Justin wants to build the remaining refinements now. The agent will start with negative recall, which tracks discussed topics to avoid hallucination, and then memory compaction, which implements summarization layers for large memory stores.
  → Justin requests that the agent write another gap analysis, similar to the previous one, to measure mistakes and identify areas for improvement. This is important for tracking progress and ensuring the project stays on track.
  → The agent needs specific transcripts from Justin for two purposes: screenshots for the landing page/Greg DM showing the pain points with Mem0 and Cognee, and a historical import test to evaluate the extraction system's performance on pre-Thomas era data. The landing page screenshots are higher priority.
  → After the memory compaction test passes and is verified, the agent will start on the test suite and installer. Justin will think about a product name. This indicates a division of labor and a sequence of tasks.
  → The system needs robust error handling and retry logic to prevent silent failures when Gemini is down, Postgres drops, or the daemon crashes. Health alerts and graceful degradation are also needed to ensure system stability.
  → Negative recall involves tracking which topics have been discussed to prevent the agent from hallucinating fill-in details. This can be achieved by maintaining a topic coverage map. Echo considers this to be philosophically hard to implement.
  → Correction cascading depends on cross-entity linking because it needs the entity graph to find downstream dependencies. It should be built after entity linking is implemented.
  → Sebastian is assigned to build the teacher-side 'mark class complete' feature for K-2 whole-class delivery within Project Explore. This development task is estimated to take approximately one day. This is new development.
  • Contradiction detection: Reduce false positives by tuning similarity threshold.

### Knowledge Gaps
⚠ No memory coverage for: landing page, greg dm, screenshots, mem0 fail. Do not guess or fill in details about these topics.