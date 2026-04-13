# TODO - High Priority Action Items

## 🧠 Task State Tracking Feature — 0Latency API

**Status:** Planned — ready to build  
**Priority:** High (competitive differentiator)  
**Estimated effort:** 2-3 hours (sub-agent build)  
**Added:** March 31, 2026  
**Trigger:** Openclaw Labs "Ralph Loops" video — his entire workaround (task files with completion markers, shell script loops) is manual infrastructure that this feature replaces natively.

### Objective
Let agents store, query, and update task state through the 0Latency API — so autonomous loops don't need external checklist files. Memory becomes the task tracker.

### Architecture (Additive — No Breaking Changes)

**Existing infrastructure we leverage:**
- `memory_type = 'task'` already exists in the schema and stats queries
- `metadata` is already a JSONB column on every memory
- Entity extraction already runs on stored content
- Webhook system already fires on `memory.created`

**New components:**

1. **Task metadata convention** (stored in existing `metadata` JSONB):
   ```json
   {
     "task_status": "not_started|in_progress|done|blocked|cancelled",
     "completion_marker": "output/company-research.md exists and >500 chars",
     "parent_task_id": "uuid-of-parent",  // optional, for subtasks
     "priority": "high|medium|low",
     "due": "2026-04-01T00:00:00Z",  // optional
     "progress_pct": 60,  // optional, 0-100
     "last_updated_by": "agent-id"
   }
   ```

2. **New endpoints (3 total):**

   **`PATCH /tasks/{memory_id}/status`** — Update task status
   - Body: `{ "status": "done", "agent_id": "research-agent" }`
   - Validates memory exists, is type `task`, belongs to tenant
   - Updates `metadata.task_status` and `metadata.last_updated_by`
   - Fires webhook: `task.status_changed`
   - Returns updated task

   **`GET /tasks`** — List tasks with filters
   - Query params: `status`, `agent_id`, `priority`, `parent_task_id`
   - Returns tasks ordered by priority, then created_at
   - Supports `?pending=true` shortcut (not_started + in_progress)

   **`POST /tasks`** — Create task (sugar over `/extract` with `memory_type: task`)
   - Body: `{ "headline": "Research Acme Corp", "agent_id": "research-1", "status": "not_started", "completion_marker": "...", "parent_task_id": "..." }`
   - Skips LLM extraction (task is already structured)
   - Generates embedding from headline+context for recall
   - Returns task with ID

3. **New webhook events:**
   - `task.created` — when a task memory is stored
   - `task.status_changed` — when status transitions
   - `task.completed` — specifically when status → done

4. **SDK additions** (JS + Python):
   - `client.tasks.create({...})`
   - `client.tasks.list({ status: "pending" })`
   - `client.tasks.update(id, { status: "done" })`

### Files to modify:
- `api/main.py` — 3 new endpoint functions (~80 lines)
- `src/storage_multitenant.py` — 2 new helper functions (~40 lines)
- `sdk/javascript/src/client.ts` — tasks namespace (~30 lines)
- `sdk/python/zerolatency/client.py` — tasks methods (~30 lines)

### What this does NOT touch:
- No schema migrations (metadata JSONB handles everything)
- No changes to existing `/extract`, `/recall`, `/memories` endpoints
- No changes to extraction pipeline or embedding logic
- No changes to auth, billing, or rate limiting

### Risks:
- Minimal — pure additive. If tasks endpoints fail, nothing else is affected.
- Only risk: JSONB query performance at scale → mitigate with partial index on `memory_type = 'task'`

### Verification:
1. Create task via `/tasks` → confirm stored with correct metadata
2. Query via `GET /tasks?status=not_started` → confirm filters work
3. Update via `PATCH /tasks/{id}/status` → confirm webhook fires
4. Recall via existing `/recall` → confirm tasks appear in memory search
5. SDK roundtrip in JS and Python

### Marketing angle:
"Stop building task files and shell scripts. Your agent's memory IS the task tracker."
— Directly addresses the Openclaw Labs audience and every developer doing Ralph-loop-style workarounds.

---

## 🐛 Pricing Page — Dynamic Plan Detection Bug

**Status:** Open
**Priority:** High (user-facing bug)
**Added:** March 31, 2026

**Problem:** Landing page pricing section (0latency.ai scrolled to pricing) shows "YOUR PLAN" badge on Pro ($29) even though the user is on Enterprise. The billing.html page correctly shows Enterprise. Dashboard correctly shows Enterprise.

**Root cause:** The pricing section on index.html likely hardcodes the highlight or doesn't query the user's actual Stripe subscription to determine which plan to badge.

**Fix needed:**
- Pricing cards on index.html need to check the user's plan (via API or localStorage) and dynamically apply the "YOUR PLAN" badge + "Current Plan" button to the correct tier
- Downgrade buttons currently link to `mailto:support@0latency.ai` — this is fine as a pattern but the email needs to actually work (see email forwarding task below)

---

## 📧 Email Forwarding Setup — 0latency.ai Addresses

**Status:** Open
**Priority:** High (launch blocker if support@ doesn't work)
**Added:** March 31, 2026

**Need:** Forward all @0latency.ai email addresses to justin@0latency.ai:
- support@0latency.ai
- info@0latency.ai
- Any other addresses that might receive inbound email

**Where:** Likely configured via DNS/email provider (Cloudflare email routing, or wherever 0latency.ai MX records point)

---

## 🎨 Landing Page — Features Section Improvements

**Status:** Open
**Priority:** Medium
**Added:** March 31, 2026

**Current state:** Features section shows 7 cards in a 3-column grid:
- Row 1: Temporal Intelligence, Knowledge Graph, Proactive Recall
- Row 2: Contradiction Detection, Negative Recall, Custom Criteria
- Row 3: Automatic Secret Detection (alone — looks unfinished)

**Changes needed:**
1. Add a section header/title above the feature cards (e.g. "Built for Agent Memory" or "Core Capabilities")
2. Add 2 more feature cards to fill row 3 to 3 columns (9 total, 3x3 grid):
   - **Agent Orchestration** — Multi-agent memory sharing, scoped access, coordination across agent teams
   - **Self-Improving Memory** — Confidence scoring increases with reinforcement, memories strengthen or decay based on usage patterns
   - (Alternative: Semantic Search & Recall — vector similarity + temporal weighting for precision recall)

---

## 🔐 URGENT - API Key Rotation Required

**Status:** ✅ DONE (March 31, 2026)  
**Priority:** CRITICAL  
**Due:** Tomorrow (March 31, 2026)  
**Time Required:** 10-15 minutes

**What happened:**
Thomas exposed full OpenAI and Gemini API keys in plaintext Telegram messages on March 30, 2026 at 05:13 UTC. Keys are compromised and must be rotated.

**Keys to rotate:**

1. **OpenAI API Key**
   - Platform: https://platform.openai.com/api-keys
   - Current key starts with: `sk-proj--UMUpWxDo...`
   - After rotating: Update `/root/.openclaw/workspace/memory-product/.env` and `/etc/systemd/system/zerolatency-api.service`

2. **Google/Gemini API Key**  
   - Platform: https://console.cloud.google.com/apis/credentials
   - Current key starts with: `AIzaSyDcUVJq...`
   - After rotating: Update `/root/.openclaw/workspace/memory-product/.env` and `/etc/systemd/system/zerolatency-api.service`

**After updating keys:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart zerolatency-api.service
sudo systemctl status zerolatency-api.service
```

**Context:** Security violation incident documented in `/root/.openclaw/workspace/memory/2026-03-30.md`

---

**Added by:** Thomas
