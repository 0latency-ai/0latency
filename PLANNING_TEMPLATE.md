# Planning Template — Design Before Building

**Use this template ANY time you're about to build something. Fill it out, get approval, THEN execute.**

---

## 1. Objective
**What are we building/solving?**
- Clear, one-sentence goal
- Success criteria (what does "done" look like?)

---

## 2. Requirements Analysis
**What goes in, what comes out, what are the constraints?**

### Inputs:
- Data sources
- User inputs
- Configuration needed

### Outputs:
- Expected deliverables
- Format (file, API response, UI, etc.)
- Where it goes (file path, database, Telegram, etc.)

### Constraints:
- Time/budget limits
- Technical limitations
- Dependencies on other systems

---

## 3. Dependencies
**What do we need before we can build?**
- APIs (which ones, do we have keys?)
- Files (which files, do they exist?)
- Credentials (what auth is needed?)
- Data sources (databases, third-party services)
- External tools (installed? configured?)

**Missing dependencies:** (list anything we need to obtain/configure first)

---

## 4. Architecture / Approach
**How will this work?**

### Components:
- List major pieces (scripts, files, API calls, etc.)

### Flow:
- Step-by-step logic (A → B → C)
- Branching/conditional logic
- Error handling approach

### Data Model:
- What data structures/formats will we use?
- Where will data be stored?

---

## 5. Risk Assessment
**What could go wrong?**

### Known Risks:
- API rate limits
- Missing data / null values
- Authentication failures
- File permissions
- Token budget overruns

### Edge Cases:
- What happens if input is malformed?
- What if API is down?
- What if file doesn't exist?

### Mitigation:
- How we'll handle each risk
- Fallback strategies

---

## 6. Execution Steps
**Ordered task breakdown (what we'll actually do)**

1. Step one (e.g., "Set up API credentials")
2. Step two (e.g., "Create data schema")
3. Step three (e.g., "Build scraper script")
4. ...

Estimate per step:
- Tokens
- Time
- Complexity (simple/medium/hard)

---

## 7. Verification Plan
**How will we test/validate this works?**

### Unit Tests:
- What individual pieces need testing?

### Integration Tests:
- Does it work end-to-end?

### Manual Checks:
- What should a human verify?

### Success Metrics:
- How do we know it's working correctly?

---

## 8. Estimates
**Rough cost projection**

- **Token estimate:** (if using LLM-heavy operations)
- **Time estimate:** (wall-clock time to build + test)
- **Complexity:** Simple / Medium / Complex
- **Risk level:** Low / Medium / High

---

## 9. Approval Decision
**After writing this plan:**

- [ ] Plan reviewed
- [ ] Dependencies confirmed available
- [ ] Risks acceptable
- [ ] Estimates reasonable
- [ ] **APPROVED → Proceed to build**

---

**Examples of when to use this template:**
- Building a new skill
- Creating a web application
- Multi-step automation workflow
- Complex data pipeline
- Integration with new API
- Spawning sub-agent for execution work

**When you can skip this:**
- Simple file edits (<10 lines)
- Single API call
- Reading/analyzing existing files
- Quick one-off commands
- Responding to messages

**Rule of thumb:** If you're thinking "this might take a while" or "there are multiple steps" → PLAN FIRST.

---

**Added:** March 26, 2026  
**Hardcoded by:** Thomas, per Justin's directive
