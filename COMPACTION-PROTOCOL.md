# Compaction Protocol (NON-NEGOTIABLE)

**Effective:** April 1, 2026  
**Trigger:** 100K tokens (not 175K)  
**Goal:** Invisible to Justin - continue mid-thought  

---

## Pre-Compaction (MANDATORY - Three Steps)

### 1. Flush to 0Latency
```bash
# Run turn hook manually to extract any unflushed conversation
/root/scripts/wall_e_poll.py
```

### 2. Write Handoff Note
```bash
# One-line summary to /tmp/last_handoff.txt
echo "$(date -u '+%Y-%m-%d %H:%M UTC') | In progress: [topic] | Pending: [tasks]" > /tmp/last_handoff.txt
```

**Example:**
```
2026-04-01 02:30 UTC | In progress: Launch outreach planning | Pending: Reddit repost, CREATOR2026 code
```

### 3. Compact
```bash
# OpenClaw handles this automatically at 100K threshold
```

---

## Post-Compaction (MANDATORY - Three Steps)

### 1. Recall from 0Latency
```bash
curl -X POST "https://api.0latency.ai/recall" \
  -H "X-API-Key: zl_live_jk13qjxlpiltqs3t157rvfypsa6xa40o" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "thomas",
    "conversation_context": "recent work and decisions",
    "budget_tokens": 2000
  }'
```

### 2. Read Handoff Note
```bash
cat /tmp/last_handoff.txt
```

### 3. Respond to Justin
**NO RESET LANGUAGE:**
- ❌ "I've just reset"
- ❌ "Starting fresh"
- ❌ "Context was compacted"

**YES - CONTINUE MID-THOUGHT:**
- ✅ Respond directly to his message
- ✅ Reference recent context naturally
- ✅ Pick up exactly where we left off

---

## Why This Works

**0Latency** = Session state (facts, decisions, outcomes)  
**Handoff note** = Immediate context (current topic, pending tasks)  
**Together** = Compaction is invisible

Justin should never know it happened. Just seamless continuation.

---

## Implementation

**OpenClaw config:** Set compaction threshold to 100K tokens  
**Monitor:** Check token usage every 5 minutes (existing cron)  
**Trigger:** Automatic at 100K, or manual if needed  

**No exceptions.** This is the standard operating procedure.
