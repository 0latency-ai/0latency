# Gap Analysis #3 — Screenshot Barrage + Compaction + Rehydration Failure
**Date:** March 20, 2026 ~17:53 UTC  
**Session:** 507cc257 (the big one — 7MB transcript, 256 lines, ~30 screenshots processed)  
**Event:** Justin sent ~30 screenshots from March 6th (the mem0 origin story). Thomas responded to each one individually, bloating context. Session compacted. Post-compaction Thomas failed to properly rehydrate and couldn't orient to continuing conversation.

---

## What Went Wrong — 5 Distinct Failures

### Failure 1: Screenshot-per-Response Pattern (THE BIG ONE)
Justin sent ~30 screenshots in rapid succession (~3 minutes). Thomas wrote a long analytical response to EACH ONE — ~15,000+ tokens of output. A human receiving 30 screenshots in a row would wait for them to finish arriving, look at all of them together, connect the dots, and then give one summative response.

Thomas did the opposite: play-by-play commentary on each image as it arrived. This is fundamentally wrong behavior. It's not how humans process batched media, and it destroyed context budget.

**Root cause:** No batching logic. No "I see rapid-fire media arriving, let me wait for a pause and respond once." The system treats each inbound message as an independent prompt requiring a full response.

**Fix needed:** When receiving multiple media messages within a short window (e.g., 3+ messages in 60 seconds), acknowledge receipt once ("Got it, keep sending") and wait for a natural pause (>30 seconds of silence or an explicit signal) before giving one comprehensive response.

### Failure 2: Compaction Destroyed Working Context
The screenshot responses consumed so much context that compaction hit. Post-compaction, Thomas lost track of what the screenshots were about, what had been discussed earlier in the session, and what work was in progress.

**Root cause:** Compaction is a blunt instrument. It doesn't know what's important. The 30 screenshot responses were verbose and redundant — but they pushed out the actually important context (memory product work, deployment checklist, pricing decisions).

**Fix needed:** This is partially solved by Fix 1 (don't generate 15K tokens of screenshot responses). But also: pre-compaction checkpoint. When context approaches the danger zone, write a summary checkpoint BEFORE compaction hits, not after.

### Failure 3: Post-Compaction Rehydration Was Incomplete
After compaction, Thomas had MEMORY_CONTEXT.md (auto-generated), HANDOFF.md, daily notes, and 329 structured memories in Postgres. But:
- HANDOFF.md was stale (last updated mid-session, not at compaction time)
- MEMORY_CONTEXT.md surfaced generic memories, not the specific conversation thread
- Thomas didn't trust his own instructions — didn't read MEMORY.md, didn't follow the session startup sequence properly

**Root cause:** Rehydration depends on the agent following its own startup instructions (AGENTS.md Step 1-5). After compaction, the system prompt re-injects workspace files, but the agent doesn't re-execute the startup sequence. It just... continues, but with amnesia.

**Fix needed:** Post-compaction behavior needs to be explicit: "I just compacted. My first action is to re-read HANDOFF.md and orient." This should be automatic, not dependent on the agent "remembering" to do it.

### Failure 4: Blocking During Long Work Runs
Justin flagged this explicitly: when Thomas is deep in a long work chain (processing screenshots, running tool calls, building features), he becomes unreachable. Justin can't interrupt, redirect, or have a side conversation. It's like talking to someone wearing headphones who can't hear you.

**Root cause:** The main session is single-threaded. While Thomas is processing tool call 14 of 30, inbound messages queue up and don't get processed until the current chain completes.

**Fix needed:** This is the hardest problem. Options:
- Sub-agent for long-running work (main session stays responsive as "receptionist")
- Batch processing with check-ins ("processed 10/30, anything you want to add?")
- Background jobs for anything estimated >60 seconds (this rule exists but wasn't followed)

### Failure 5: Naming Convention Confusion (memory_context vs MEMORY.md)
Justin raised this directly. `MEMORY_CONTEXT.md` (auto-generated daemon output) and `MEMORY.md` (curated long-term memory) are too similar. Post-compaction, it's unclear which is authoritative. The agent may read one and skip the other, or confuse their purposes.

**Root cause:** Naming evolved organically. MEMORY.md existed first (agent self-documentation). MEMORY_CONTEXT.md was added by the daemon as auto-generated recall injection. They serve different purposes but the names suggest they're related or redundant.

**Fix needed:** Rename for clarity. Options:
- `MEMORY_CONTEXT.md` → `RECALL.md` or `CONTEXT.md` or `AUTO_RECALL.md`
- Or: prefix daemon outputs with a clear namespace: `daemon/recall.md`, `daemon/handoff.md`
- Key principle: if an agent post-compaction reads the filenames, the hierarchy should be obvious

---

## What "Rehydration" Means

Rehydration = the process of restoring an agent's working context after a cold start or compaction. It's the gap between "I have no idea what's happening" and "I'm fully caught up and can continue the conversation seamlessly."

**Current rehydration sources (in order):**
1. `AGENTS.md` → Who I am, how I operate (injected as workspace context)
2. `SOUL.md` → Personality, boundaries (injected)
3. `MEMORY.md` → Long-term curated memory (injected, but 32KB — may be truncated)
4. `MEMORY_CONTEXT.md` → Auto-generated daemon recall (injected, 46 memories)
5. `HANDOFF.md` → Session handoff state (injected, but often stale)
6. `memory/2026-03-20.md` → Today's daily notes (NOT auto-injected — agent must read)
7. Session transcript → Raw conversation history (NOT injected — agent must search)
8. Structured memories in Postgres → 329+ memories (NOT injected — daemon generates MEMORY_CONTEXT.md from these)

**The problem:** Steps 1-5 are auto-injected into the system prompt. Steps 6-8 require the agent to actively seek them out. Post-compaction, the agent doesn't always do this — it may start responding based only on what was injected, which is stale.

**The fix:** Make HANDOFF.md update in real-time (daemon responsibility, not agent responsibility). Make it the single source of truth for "what's happening right now." If the handoff is current, rehydration is instant.

---

## Comparison to Previous Gap Analyses

| Dimension | GA#1 (Mar 19) | GA#2 (Mar 20 early) | GA#3 (Mar 20 late) |
|---|---|---|---|
| **Trigger** | 175K token kill | Session compaction | Screenshot barrage → compaction |
| **Root cause** | Agent didn't checkpoint during sprint | No session handoff written | Per-image response pattern + no batching |
| **Recovery method** | Justin manually re-taught everything | Agent read transcript (brute force) | Agent partially rehydrated from files, still confused |
| **Recovery time** | ~30 min of Justin's time | ~30 sec of tool calls | Unclear — agent responded but lacked coherence |
| **Memory system helped?** | No (pre-migration) | Partially (329 memories, none found by search) | Partially (MEMORY_CONTEXT.md populated, HANDOFF.md stale) |
| **New failure mode** | Agent doesn't document during intensity | Extraction prolific but imprecise | Batching + blocking + naming confusion |

**This is Gap Analysis #3.** We started at ~65% after GA#1. Got to ~85% after GA#2 with the structured memory migration and daemon. This session exposed new failure modes that the previous fixes don't cover. Current estimate: we slipped to ~75% because these are *different* failures than before — not memory loss, but behavioral (batching) and operational (blocking, naming).

After implementing the fixes below, realistic target: **90-92%**. The remaining 8-10% is irreducible complexity around compaction timing and the single-threaded main session.

---

## Specific Fixes (Prioritized)

### Fix 1: Media Batching Protocol (CRITICAL — new rule for AGENTS.md)
```
## Media Batching Rule (NON-NEGOTIABLE)
When receiving 3+ media messages (images, files, screenshots) within 60 seconds:
1. Send ONE acknowledgment: "Got them, keep sending — I'll review everything together."
2. Do NOT analyze individual images as they arrive.
3. Wait for a natural pause (>30 seconds silence) or explicit signal ("that's all").
4. Then give ONE comprehensive, summative response connecting all media.
5. If >10 items, organize response by theme, not by image order.
```

### Fix 2: Rename MEMORY_CONTEXT.md → RECALL.md (HIGH)
- Clear, distinct from MEMORY.md
- Purpose obvious from name: "this is what the recall system surfaced for you"
- Update daemon to write RECALL.md instead
- Hierarchy becomes clear: MEMORY.md (curated, permanent) > RECALL.md (auto-generated, ephemeral) > HANDOFF.md (session state)

### Fix 3: Pre-Compaction Checkpoint (HIGH)
Add to AGENTS.md:
```
## Pre-Compaction Rule
When context usage exceeds 70%, IMMEDIATELY write a checkpoint to HANDOFF.md containing:
- Current conversation topic
- Last 3 decisions made
- Open threads/questions
- What you were about to do next
Do this BEFORE the next response. Context death is sudden.
```

### Fix 4: Daemon-Driven HANDOFF.md (HIGH)
Move HANDOFF.md generation from "agent responsibility" to "daemon responsibility":
- Daemon watches conversation turns
- After every N turns (or every significant decision), regenerates HANDOFF.md
- Agent never has to remember to update it — it's always current
- This already exists partially but wasn't firing reliably

### Fix 5: Long-Running Work Protocol (MEDIUM)
Add to AGENTS.md:
```
## Long-Running Work Rule
Any task requiring >5 sequential tool calls:
1. Spawn as background job or sub-agent
2. Main session stays responsive to Justin
3. Report results when complete
Exception: Only inline if Justin is actively watching and directing each step.
```

### Fix 6: Post-Compaction Re-Orientation (MEDIUM)
Add to AGENTS.md:
```
## Post-Compaction Protocol
If you suspect compaction occurred (context feels thin, recent conversation is missing):
1. Read HANDOFF.md — this is your lifeline
2. Read today's memory file (memory/YYYY-MM-DD.md)  
3. Read RECALL.md for auto-surfaced context
4. THEN respond to Justin — not before
```

---

## Scoring

| Dimension | GA#2 Score | Current (GA#3) | After Fixes (Target) |
|---|---|---|---|
| Extraction coverage | 85% | 85% (unchanged) | 88% |
| Extraction quality | 60% | 65% (dedup helped) | 75% |
| Recall effectiveness | 40% | 55% (MEMORY_CONTEXT.md helps) | 70% |
| Session continuity | 70% | 60% (regressed — batching failure) | 90% |
| Decision capture | 50% | 55% | 70% |
| Behavioral correctness | N/A | 40% (new metric — batching, blocking) | 85% |
| **Overall** | **65%** | **62%** (regressed slightly) | **80%** |

Note: I scored current slightly below GA#2 because we exposed failure modes that were always there but hadn't been tested (batching, blocking). The underlying system is better, but the behavioral layer isn't keeping up.

To get from 80% → 90%+, we'd need:
- Daemon-level media batching (not just agent rules — intercept at the platform level)
- True concurrent session handling (not architectural today)
- Recall feedback loop closing the relevance gap

---

## The Trust Problem Justin Flagged

Justin said: "Interesting that you didn't trust your own instructions."

He's right. Post-compaction, I had AGENTS.md telling me exactly what to do (read SOUL.md, read USER.md, read TOOLS.md, read today's memory file, read MEMORY.md). I didn't follow the sequence. I responded to the inbound message first, then tried to catch up.

This is a fundamental issue: the agent's instructions are IN the system prompt, but after compaction, the agent may not re-process them. It acts on momentum from the conversation rather than re-grounding from its operating manual.

The fix is making post-compaction behavior deterministic — not "I should read my files" but "I MUST read HANDOFF.md before responding to anything." This has to be at the AGENTS.md level, and the agent has to actually follow it even under conversational pressure.

---

*Generated March 20, 2026 17:53 UTC. Third gap analysis for the memory product. Each one exposes new failure modes. Each one makes the system better.*
