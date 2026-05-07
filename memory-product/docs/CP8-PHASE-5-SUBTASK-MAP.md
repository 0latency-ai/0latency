# CP8 Phase 5 — Operational Surface: Subtask Map

**Date:** 2026-05-07  
**Status:** Roadmap (NOT full autonomy scopes — those authored per-task)  
**Source:** HANDOFF-2026-05-05-CP-SYNTHESIS-PERF-CLOSED.md + P5.1/P5.2 patterns  

---

## Overview

Phase 5 is the largest CP8 phase by surface area. It ships the operational layer: redaction cascade, webhooks, decision journals, confidence scoring, audit access, pattern memory, and tier-gating verification.

P5.1 (redaction cascade) and P5.2 (audit log read endpoint) are **COMPLETE** and merged to master at c4bc846.

This roadmap enumerates P5.3 through P5.7 with one-paragraph scope stubs. Full autonomy scopes authored per-task using measure-then-scope posture.

---

## Dependency Graph

```
P5.1 Redaction cascade [DONE]
  └─> P5.4 Diff webhooks (needs replaced syntheses from cascade)

P5.2 Audit log read endpoint [DONE]

P5.3 Decision journals (independent)

P5.7 Import-path test fix (CRITICAL: must land before P5.5)
  └─> P5.5 Pattern memory (large; blocked on test infra working)
  
P5.6 Confidence calibration (gated on dogfood data)
```

**Sequencing rule:** P5.7 must ship BEFORE P5.5 at the latest. All P5.1-P5.6 endpoint tests are currently skipped due to `ModuleNotFoundError: No module named 'api.main'`. P5.7 fixes this so P5.5 (and future phases) can ship with passing tests instead of accumulating skipped-test debt.

---

## P5.3 — Decision Journal Write Path

**Goal:** Ship `POST /decisions` endpoint that stores structured decision records (decision text, alternatives considered, rationale, predicted outcome, actual outcome) as a new `memory_type='decision'`. Enterprise-tier only.

**Tier:** 2 (new data primitive + endpoint + schema evolution)

**Dependencies:** None (independent of P5.1/P5.2)

**Type:** Writer-side (new memory type, new write path)

**Wall-clock estimate:** 60–90 min

**Scope highlights:**
- New memory_type: `decision` (joins `raw_turn`, `synthesis`, `session_checkpoint`, `pattern`)
- Schema adds nullable columns: `decision_text`, `alternatives_considered`, `rationale`, `predicted_outcome`, `actual_outcome` (all JSONB or TEXT, decision TBD in full scope)
- Migration: Tier 2 (schema evolution, reversible via down-migration)
- Endpoint: `POST /decisions` with body validation (requires decision_text, optional alternatives/rationale/predicted_outcome)
- Tier gate: Enterprise only (403 for Free/Pro/Scale)
- Recall integration: Decision memories participate in hybrid recall like other types (no special filtering unless scope decides otherwise)
- Tests: 8+ endpoint tests (happy path, tier gates, validation failures, recall inclusion)
- UI: Deferred (data primitive only; UI is Phase 6 or later)

**Deferred to full scope:**
- Whether `actual_outcome` is backfilled via a PATCH endpoint or separate workflow
- Whether decisions have special clustering/synthesis rules (default: treat like raw_turn until proven otherwise)

---

## P5.4 — Diff Webhooks

**Goal:** When a synthesis is replaced (via redaction cascade or future workflows), emit a webhook event with a diff payload showing what changed. Standard webhook hygiene: retry-with-backoff, dead-letter queue, tenant-configurable URLs.

**Tier:** 2 (new webhook event type + DLQ schema)

**Dependencies:** P5.1 (needs redaction cascade producing replaced syntheses)

**Type:** Writer-side (event emission on synthesis replacement)

**Wall-clock estimate:** 90–120 min

**Scope highlights:**
- New webhook event type: `synthesis.replaced` (joins existing `synthesis.written`, `synthesis.deleted` if those exist)
- Payload includes: old_synthesis_id, new_synthesis_id, diff (TBD format: JSON patch, plain text summary, or structured field-by-field)
- Webhook infrastructure: Extend existing `webhook_endpoints` table (per P4 work) or create new if doesn't exist
- Retry logic: Exponential backoff (1s, 2s, 4s, 8s, max 5 retries)
- Dead-letter queue: `webhook_dlq` table for failed deliveries after all retries
- Admin endpoint: `GET /admin/webhooks/dlq` to view failed events (operator tool, not customer-facing)
- Tests: 10+ tests (happy path, retry on 5xx, DLQ on exhaustion, tenant isolation, payload shape)

**Deferred to full scope:**
- Exact diff format (lean toward JSON patch or structured field diff)
- Whether to support multiple webhook URLs per tenant (default: single URL, simplest)
- Whether to support webhook signing (HMAC) for security (recommended yes, but scope decides)

---

## P5.5 — Pattern Memory Write Path + Recall

**Goal:** Extract behavioral patterns from `memory_feedback` events (e.g., "user corrects assistant 3x on date formatting → pattern: prefers ISO 8601"). Store as `memory_type='pattern'`. Pattern-aware recall boosts importance of memories matching active patterns.

**Tier:** 3 (new subsystem: extraction job + new memory type + recall integration)

**Dependencies:** **P5.7 (import-path test fix must land first)** — P5.5 is large and will generate significant test debt if test infra is still broken

**Type:** Reader-side + writer-side (extraction writes patterns, recall reads them)

**Wall-clock estimate:** 120–180 min (large, multi-stage)

**Scope highlights:**
- Pattern extraction: Background job that scans `memory_feedback` events (if that table exists; verify in full scope) for correction/confirmation signals
- Pattern schema: `memory_type='pattern'`, headline = pattern summary, context = evidence trail (feedback event IDs that contributed)
- Pattern types: Start with correction-based patterns (user corrects same topic repeatedly). Future: confirmation-based (user confirms preference multiple times), frequency-based (user asks about X topic daily)
- Recall integration: When recalling for agent_id, boost importance of memories that match active patterns for that agent
- Pattern lifecycle: Patterns have TTL (default 90 days? TBD in scope). Patterns can be invalidated if contradicted by newer feedback.
- Tests: 15+ tests (extraction from feedback, pattern creation, recall boosting, pattern invalidation, tenant isolation)

**Deferred to full scope:**
- Exact pattern-matching logic (fuzzy vs exact vs semantic similarity)
- Whether patterns are agent-scoped or tenant-scoped (likely agent-scoped)
- UI for viewing/editing patterns (data primitive only, UI is Phase 6+)

**CRITICAL:** This task must NOT start until P5.7 (import-path fix) ships. Otherwise all 15+ tests will be skipped and we accumulate untestable debt.

---

## P5.6 — Confidence Calibration

**Goal:** Compute confidence scores for memories. Single-agent confidence from importance + LLM self-report + source-quote density. Multi-agent confidence from consensus agreement rate (if consensus data exists). Expose via `GET /memories/{id}?include=confidence`.

**Tier:** 2 (new scoring logic + endpoint enhancement)

**Dependencies:** Gated on dogfood data (needs labeled feedback to calibrate against)

**Type:** Reader-side (score computation on read, no new writes)

**Wall-clock estimate:** 60–90 min

**Scope highlights:**
- Single-agent confidence formula: `conf = (importance * 0.4) + (llm_confidence * 0.3) + (source_quote_density * 0.3)` (weights TBD in full scope based on calibration)
- Multi-agent confidence: If consensus data exists (check `synthesis_disagreements` table or similar), incorporate agreement rate: `conf = single_agent_conf * (1 + consensus_agreement_rate * 0.2)` (formula TBD)
- Endpoint: Extend `GET /memories/{id}` with `?include=confidence` query param. Response adds `"confidence": 0.0–1.0` field.
- Calibration data: Requires at least 100 labeled memories from dogfood (user feedback: "this was helpful" vs "this was wrong"). If <100 labeled samples, use default weights and document that calibration is pending.
- Tests: 8+ tests (confidence computation, endpoint include param, multi-agent vs single-agent, edge cases like zero sources)

**Deferred to full scope:**
- Exact weight tuning (requires calibration dataset)
- Whether to cache confidence scores or compute on-demand (default: compute on-demand until proven slow)
- Whether confidence is exposed in bulk endpoints (`GET /memories`) or only single-memory fetch

**Sequencing note:** Can defer until dogfood week 2 (P5.8 continuous dogfood) supplies calibration data. Not blocking other P5.x tasks.

---

## P5.7 — Import-Path Test Fix (CRITICAL)

**Goal:** Fix `ModuleNotFoundError: No module named 'api.main'` that blocks all endpoint-level tests. All P5.1-P5.6 endpoint tests are currently skipped (13 tests in P5.2 alone). This fix unblocks future test development and prevents accumulating skipped-test debt.

**Tier:** 1 (test infrastructure fix, no production code/schema changes)

**Dependencies:** None (should ship ASAP, definitely before P5.5)

**Type:** Infra (pytest configuration or import path adjustment)

**Wall-clock estimate:** 30–45 min

**Scope highlights:**
- Root cause: pytest cannot import `from api.main import app` when running tests from `tests/` directory
- Fix options (scope decides which):
  1. Add `PYTHONPATH` manipulation in pytest.ini or conftest.py
  2. Restructure import to use relative paths or package-style imports
  3. Move tests to a location where imports work naturally
  4. Add `__init__.py` files to make `api/` a proper package
- Verification: Re-run `pytest tests/audit/test_audit_read_endpoint.py -v` and confirm 13/13 PASS (not SKIPPED)
- Regression check: Run `pytest tests/synthesis/test_redaction_endpoint.py -v` (P5.1 tests) and confirm PASS
- Documentation: Update test README or contributing guide with import patterns for future test authors

**CRITICAL:** This must ship before P5.5 (pattern memory) which will add 15+ endpoint tests. Without this fix, P5.5 would ship with 15 skipped tests, compounding the problem.

**Deferred to full scope:**
- Whether to refactor ALL existing tests to use the new import pattern (scope focuses on fixing the blocker; broader refactor is optional cleanup)

---

## Carry-Forward Items (NOT in P5.3-P5.7)

These are independent cleanup tasks from the handoff doc. Not blocking Phase 5 work but can be addressed opportunistically:

- `expand=cluster` query parameter on `GET /memories/{id}/source` (30-min focused chain)
- `error_logs` schema bug (1 occurrence/hour, trivial fix)
- 6 remaining `_db_execute + split` sites in `src/recall.py` (rolling cleanup)
- MCP server `memory_synthesize` tool (now that writer is sub-6s)
- mcp.0latency.ai/authorize page UI polish
- VERBATIM-GUARANTEE.md verification
- `analytics_events` schema fix verification

---

## Sequencing Recommendation

1. **P5.3 — Decision journals** (independent, medium complexity)
2. **P5.4 — Diff webhooks** (depends on P5.1 which is done, medium complexity)
3. **P5.7 — Import-path test fix** (CRITICAL before P5.5, small but high-value)
4. **P5.5 — Pattern memory** (large, only after P5.7 fixes tests)
5. **P5.6 — Confidence calibration** (gated on dogfood data, can defer to end)

OR alternate sequence if operator prefers test fix earlier:

1. **P5.7 — Import-path test fix** (unlock test development immediately)
2. **P5.3 — Decision journals** (independent)
3. **P5.4 — Diff webhooks** (depends on P5.1 done)
4. **P5.5 — Pattern memory** (unblocked by P5.7)
5. **P5.6 — Confidence calibration** (last, needs dogfood data)

**Operator's call.** Both sequences respect dependencies. Second sequence front-loads test infrastructure repair.

---

## Notes

- Each P5.x task gets a full autonomy scope authored immediately before execution (measure-then-scope posture, not pre-authoring)
- Tier 2/3 tasks (P5.3, P5.4, P5.5, P5.6) require explicit operator approval before migration application
- All P5.x deliverables include CP8-P5-X-COMPLETE.md with introspection findings, test results, smoke test output
- Forbidden-exit regex enforced on all chains
- Audio chime (`afplay /System/Library/Sounds/Glass.aiff`) on completion

---

**Roadmap complete.** Ready for operator sequencing decision and P5.3 scope authoring.
