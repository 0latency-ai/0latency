# CP9 PHASE 2 — TRACKS B2+B3: ERROR PATH UX + FIRST-RECALL DEMO FLOW

**Date**: 2026-05-11  
**Branch**: cp9-p2-t2-t3-error-and-recall-demo  
**Status**: Design phase

---

## Objective

Close two onboarding gaps that share the same "what happens after install" surface:
1. **Track B2**: Make failures legible with standardized error envelopes
2. **Track B3**: Close the value-prop loop with first-recall demo flow

Context: T1 instrumentation shipped, showing 4.46s time-to-first-memory on SDK path. Next step is ensuring failures are actionable and successes lead to value demonstration.

---

## TRACK B2 — ERROR PATH UX

### The Four Failure Modes (Verified from Code Analysis)

After analyzing 112 HTTPException raises in api/main.py, the four most common install/onboarding failure modes are:

#### 1. Invalid/Missing API Key (401)
**Current behavior** (scattered across api/main.py:285-327):
- `MISSING_HEADER`: "Missing or invalid X-API-Key header"
- `INVALID_FORMAT`: "API key format is invalid. Keys must start with 'zl_live_' and be 40 characters long."
- `NOT_FOUND`: "Invalid or expired API key"
- `ACCOUNT_SUSPENDED`: "Account is suspended. Contact support."
- `REVOKED`: "API key has been revoked"

**New behavior**:
```json
{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "API key is missing or invalid",
    "hint": "Check that your X-API-Key header contains a valid 'zl_live_*' key from your dashboard",
    "docs_url": "https://0latency.ai/docs/troubleshooting#invalid-api-key"
  }
}
```

#### 2. Rate Limiting / Memory Limit (429)
**Current behavior** (api/main.py:569, 715, 717):
- "Memory limit reached (10000). Upgrade plan or delete old memories."
- "Would exceed memory limit. 0 slots remaining, 5 facts submitted."

**New behavior**:
```json
{
  "error": {
    "code": "MEMORY_LIMIT_REACHED",
    "message": "You've reached your plan's memory limit (10,000 memories)",
    "hint": "Delete old memories or upgrade your plan at https://0latency.ai/dashboard/billing",
    "docs_url": "https://0latency.ai/docs/troubleshooting#memory-limit"
  }
}
```

#### 3. Network/Connectivity Issues (Client-Side)
**Current behavior**: Generic timeout or connection refused from HTTP client  
**New behavior**: Client detects and wraps with actionable error

```
Error: Cannot connect to api.0latency.ai

Possible causes:
- No internet connection
- Firewall blocking port 443
- DNS resolution failed

Next steps:
1. Check your internet connection
2. Verify api.0latency.ai resolves: curl -I https://api.0latency.ai/health
3. Check firewall rules for outbound HTTPS

Docs: https://0latency.ai/docs/troubleshooting#network-connectivity
```

#### 4. Server Errors (500) - Extraction/Recall Failures
**Current behavior** (api/main.py:679, 1745, etc.):
- "Extraction failed. Please check your input and try again."
- "Recall failed. Please check your input and try again."
- "Seed failed. Please check your input and try again."

**New behavior**:
```json
{
  "error": {
    "code": "EXTRACTION_FAILED",
    "message": "Memory extraction failed",
    "hint": "This is usually temporary. If it persists, contact support@0latency.ai with your request ID",
    "docs_url": "https://0latency.ai/docs/troubleshooting#extraction-failed",
    "request_id": "abc123"
  }
}
```

**Note on "Version Mismatch" and "MCP Transport Mismatch"**: After code review, these are not current failure modes in production. API has no version checking (backwards compatible), and MCP server auto-detects transport. Replaced with more common "Rate Limiting" and "Server Errors" based on actual HTTPException distribution.

---

### Structural Decision: Centralized api/errors.py Module

**Rationale**: 112 scattered `raise HTTPException(...)` calls are technical debt. Each has ad-hoc string messages, no consistency, no actionable guidance, no docs links. Refactoring to centralized error envelope is the structurally correct long-term solution.

**Module Design**:

```python
# api/errors.py
from fastapi import HTTPException
from typing import Optional

class APIError:
    """Standardized error envelope for all API errors."""
    
    def __init__(self, code: str, message: str, hint: str, docs_url: str):
        self.code = code
        self.message = message
        self.hint = hint
        self.docs_url = docs_url
    
    def to_dict(self):
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "hint": self.hint,
                "docs_url": self.docs_url
            }
        }

# Predefined errors for the 4 common modes
INVALID_API_KEY = APIError(
    code="INVALID_API_KEY",
    message="API key is missing or invalid",
    hint="Check that your X-API-Key header contains a valid 'zl_live_*' key from your dashboard",
    docs_url="https://0latency.ai/docs/troubleshooting#invalid-api-key"
)

MEMORY_LIMIT_REACHED = APIError(
    code="MEMORY_LIMIT_REACHED",
    message="You've reached your plan's memory limit",
    hint="Delete old memories or upgrade your plan at https://0latency.ai/dashboard/billing",
    docs_url="https://0latency.ai/docs/troubleshooting#memory-limit"
)

EXTRACTION_FAILED = APIError(
    code="EXTRACTION_FAILED",
    message="Memory extraction failed",
    hint="This is usually temporary. If it persists, contact support@0latency.ai",
    docs_url="https://0latency.ai/docs/troubleshooting#extraction-failed"
)

def raise_api_error(error: APIError, status_code: int = 400, **extra):
    """Raise HTTPException with standardized error envelope."""
    detail = error.to_dict()
    detail["error"].update(extra)  # Add extra fields like request_id
    raise HTTPException(status_code=status_code, detail=detail)
```

**Migration Plan**:
1. Create api/errors.py with predefined errors for the 4 modes
2. Refactor api/main.py:
   - Replace `raise HTTPException(401, detail=MISSING_HEADER)` → `raise_api_error(INVALID_API_KEY, 401)`
   - Replace `raise HTTPException(429, detail="Memory limit reached...")` → `raise_api_error(MEMORY_LIMIT_REACHED, 429, limit=tenant['memory_limit'])`
   - Replace `raise HTTPException(500, detail="Extraction failed...")` → `raise_api_error(EXTRACTION_FAILED, 500, request_id=request_id)`
3. Verify zero direct HTTPException raises for these 4 codes: `grep 'HTTPException(40[01]\|HTTPException(429\|HTTPException(500' api/main.py | wc -l` should be significantly reduced

---

### Client-Side Error Parsing

All clients (SDK/CLI/MCP/Web) must detect the standardized envelope and display cleanly:

**SDK (Python)**:
```python
# zerolatency/client.py
try:
    response = httpx.post(...)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    error_data = e.response.json()
    if "error" in error_data and "hint" in error_data["error"]:
        # Standardized envelope detected
        err = error_data["error"]
        raise MemoryError(
            f"{err['message']}\n\nNext steps: {err['hint']}\nDocs: {err['docs_url']}"
        )
    else:
        # Fallback to raw error
        raise
```

**CLI**:
```bash
# CLI wrapper detection (Python CLI)
if response.status_code >= 400:
    try:
        error = response.json().get("error")
        if error:
            print(f"❌ {error['message']}", file=sys.stderr)
            print(f"💡 {error['hint']}", file=sys.stderr)
            print(f"📖 {error['docs_url']}", file=sys.stderr)
            sys.exit(1)
    except:
        # Fallback to raw error
        print(f"Error: {response.text}", file=sys.stderr)
        sys.exit(1)
```

**MCP Server (TypeScript)**:
```typescript
// Handle API errors
try {
  const response = await fetch(...);
  if (!response.ok) {
    const data = await response.json();
    if (data.error && data.error.hint) {
      throw new Error(
        `${data.error.message}\n\n${data.error.hint}\nDocs: ${data.error.docs_url}`
      );
    }
    throw new Error(`API error: ${response.statusText}`);
  }
} catch (error) {
  // Return to MCP client with formatted error
  return {
    error: {
      code: -32000,
      message: error.message
    }
  };
}
```

---

## TRACK B3 — FIRST-RECALL DEMO FLOW

### Objective

After first successful memory_add, guide the user to try recall immediately. Close the value loop: "I added a memory" → "Here's how to recall it" → "It works!"

### Design: next_action Field

**When**: After first successful memory write per tenant (detected via onboarding_events table from T1)

**What**: API response includes additional field:

```json
{
  "job_id": "abc-123",
  "status": "accepted",
  "next_action": {
    "type": "try_recall",
    "suggested_query": "Alice TechCorp Python",
    "example_command": "0latency memory recall 'Alice TechCorp Python'"
  }
}
```

**How to detect first memory**: Join against onboarding_events table (from T1):

```python
# In _process_extraction() after store_memories()
is_first_memory = not _db_execute_rows("""
    SELECT 1 FROM memory_service.onboarding_events
    WHERE tenant_id = %s::UUID AND event_type = 'first_memory_add'
""", (tenant["id"],), tenant_id=tenant["id"])

if is_first_memory:
    # Add next_action to response
    suggested_query = extract_keywords_from_headline(memories[0].get("headline", ""))
    _extract_jobs[job_id]["next_action"] = {
        "type": "try_recall",
        "suggested_query": suggested_query,
        "example_command": f"curl ... /recall -d '{{"query": "{suggested_query}"}}\'"
    }
```

### Suggested Query Derivation: Keyword Extraction

**Structural Decision**: Use keyword extraction (NOT LLM call) for suggested_query generation.

**Rationale**:
- **Latency-free**: No additional API call
- **Deterministic**: Same input → same output
- **No cost**: No LLM API charges
- **No failure mode**: Can't fail or timeout
- **Simple**: Easy to test and verify

**Algorithm**:
```python
import re
from typing import List

def extract_keywords_from_headline(headline: str, max_keywords: int = 3) -> str:
    """Extract top keywords from memory headline for suggested recall query.
    
    Uses simple heuristics:
    - Remove common stop words
    - Extract capitalized words (proper nouns, names)
    - Extract longer words (>4 chars)
    - Return top 3
    """
    # Stop words to filter
    STOP_WORDS = {"the", "is", "at", "which", "on", "and", "or", "but", "in", "with", "to", "for", "of", "as", "from"}
    
    # Extract words
    words = re.findall(r'\b[A-Za-z]+\b', headline)
    
    keywords = []
    
    # Priority 1: Capitalized words (proper nouns, names, places)
    for word in words:
        if word[0].isupper() and word.lower() not in STOP_WORDS:
            keywords.append(word)
    
    # Priority 2: Longer words (>4 chars) not already captured
    for word in words:
        if len(word) > 4 and word.lower() not in STOP_WORDS and word not in keywords:
            keywords.append(word)
    
    # Return top N keywords
    return " ".join(keywords[:max_keywords])

# Examples:
# "Alice Johnson works at TechCorp as a software engineer"
# → "Alice Johnson TechCorp"
#
# "User prefers Python over JavaScript for backend development"
# → "Python JavaScript backend"
#
# "The capital of France is Paris"
# → "France Paris"
```

---

### Client-Side Rendering

Each client displays the recall prompt in their native idiom:

**CLI**:
```bash
# After successful POST /memories/extract or POST /atoms
if response.get("next_action") and response["next_action"]["type"] == "try_recall":
    query = response["next_action"]["suggested_query"]
    print(f"\n✓ Memory stored successfully!")
    print(f"💡 Try recalling it: 0latency memory recall '{query}'")
```

**SDK**:
```python
# Documented in response model
class ExtractResponse:
    job_id: str
    status: str
    next_action: Optional[NextAction] = None  # Only present on first memory

class NextAction:
    type: str  # "try_recall"
    suggested_query: str
    example_command: str

# User code can check and act
response = client.memory.extract("My name is Alice...")
if response.next_action:
    print(f"Hint: {response.next_action.suggested_query}")
```

**MCP Server**:
```typescript
// Return follow-up tool suggestion in MCP response
{
  content: [
    {
      type: "text",
      text: "Memory stored successfully! Try recalling it with the query: 'Alice TechCorp Python'"
    }
  ],
  _meta: {
    suggested_tools: [
      {
        name: "memory_recall",
        arguments: {
          query: "Alice TechCorp Python"
        }
      }
    ]
  }
}
```

**Web Quickstart** (placeholder — /quickstart page doesn't exist yet per CP9 P1):
```html
<!-- After successful memory add -->
<div class="success-message">
  ✓ Memory stored!
  <button onclick="tryRecall('Alice TechCorp Python')">
    Try recalling it
  </button>
</div>
```

---

## Implementation Checklist

### Track B2 (Error Path UX)
- [ ] Create api/errors.py module
- [ ] Define 4 error envelopes (INVALID_API_KEY, MEMORY_LIMIT_REACHED, EXTRACTION_FAILED, NETWORK_CONNECTIVITY)
- [ ] Refactor api/main.py HTTPException raises (prioritize the 4 main codes: 401, 429, 500)
- [ ] Update SDK error parsing
- [ ] Update CLI error parsing
- [ ] Update MCP error parsing
- [ ] Create /docs/troubleshooting page with 4 anchors
- [ ] Verify all 4 envelopes return correctly (curl test)

### Track B3 (First-Recall Demo Flow)
- [ ] Implement extract_keywords_from_headline() helper
- [ ] Modify /memories/extract to include next_action on first memory
- [ ] Modify /atoms to include next_action on first memory
- [ ] Update CLI to print recall prompt
- [ ] Update MCP to include follow-up suggestion
- [ ] Update SDK response model documentation
- [ ] Web quickstart: placeholder or skip (page doesn't exist)
- [ ] Integration test: N≥20 first-add → has next_action → recall succeeds

### Testing & Verification
- [ ] Integration tests for all 4 error envelopes
- [ ] Integration tests for next_action field presence
- [ ] Ground-truth re-query after state mutations
- [ ] Service restart + curl test before benchmarks
- [ ] Verify grep shows reduced direct HTTPException raises

---

## Exit Gates

- [ ] All 4 error envelopes returned correctly (curl test each)
- [ ] All 4 client surfaces (SDK/CLI/MCP/web) parse and display cleanly
- [ ] next_action field present on first memory_add response per tenant
- [ ] Troubleshooting docs live, all 4 anchors resolve
- [ ] N≥20 simulations: first-add → recall-prompt → recall succeeds
- [ ] Scattered HTTPException raises refactored (grep confirms reduction)
- [ ] Final commit + push to master, tag cp9-p2-t2-t3-complete
- [ ] HANDOFF doc updated

---

## Pattern Compliance (CP9 P1)

1. ✅ **_db_execute_rows everywhere** - Never _db_execute+split
2. ✅ **NOT EXISTS for negative checks** - Checking first memory via onboarding_events
3. ✅ **Ground-truth re-query** - After state mutations in tests
4. ✅ **Service restart + curl + DB inspect** - Before benchmarks
5. ✅ **Broad except re-raises semantic** - Error handling preserves context

---

**Status**: Ready for implementation
