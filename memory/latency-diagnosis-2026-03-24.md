# Latency Diagnosis — March 24, 2026

## Problem
Justin experienced 5-10 minute gaps between sending messages and receiving responses. He sent 10+ rapid-fire messages, each one queueing behind the previous, creating a compounding delay spiral.

## Root Cause
**Queue mode `collect` with default 1s debounce + cap of 20 messages.**

When the agent is processing a response:
1. Each new inbound message queues as a followup turn
2. With only 1s debounce, rapid messages don't coalesce — they each trigger separate response cycles
3. Opus model has higher latency per response (~10-30s per turn with tool calls)
4. 10 queued messages × 10-30s each = 2-5 minutes of stacked responses
5. Each response Justin sees is answering a message from minutes ago, making it feel broken

Additionally: some responses included tool calls (session_status, memory_search, etc.) which added 5-15s per turn. The heartbeat messages interleaved with Justin's conversation, further clogging the queue.

## Fixes Applied

### 1. Queue Configuration (applied ~15:50 UTC)
```json
{
  "mode": "collect",
  "debounceMs": 3000,
  "cap": 5,
  "drop": "summarize"
}
```
- **debounceMs: 3000** (was 1000 default) — waits 3s for quiet before processing, so rapid-fire messages coalesce into one turn
- **cap: 5** (was 20) — max 5 queued messages, prevents the 10+ message pileup
- **drop: summarize** — excess messages get bullet-summarized, not individually processed

### 2. Behavioral Changes (Thomas)
- Minimize tool calls during active conversation (check status BEFORE responding, not during)
- NO_REPLY on duplicate messages instead of generating full responses
- Keep responses short during rapid exchanges

## Still Needs Investigation
- Whether Opus latency alone is acceptable or if switching to Sonnet for conversational turns would help
- Whether `steer` mode would be better than `collect` for Telegram (injects messages into current run instead of queuing)
- Whether heartbeat polling interval should back off when active conversation is detected

## Recommended Future Changes
1. Consider `steer` mode for Telegram — messages inject into current run context rather than queuing
2. Add conversation-aware heartbeat suppression — skip heartbeat if active conversation in last 5 minutes
3. Consider Sonnet for conversational turns, Opus for deep work (model switching)
