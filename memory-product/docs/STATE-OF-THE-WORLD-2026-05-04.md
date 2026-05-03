# State of the World — 2026-05-04

**Compiled:** 2026-05-03 evening, after live audit against `root@164.90.156.169`
**HEAD on origin/master:** `4eb70ab`
**Audit method:** direct psql + filesystem inspection on prod DO server. Memory and v3 scope reconciled against ground truth.

---

## Executive summary

Phase 1 of CP8 is fully landed on prod (schema, tables, code, defaults). Phase 2 of CP8 has shipped its verbatim verification slice (T9–T11) but the synthesis writer body (T1–T7) is not started, and T8 documentation is missing. CP-architecture-1 (MCP stateless-edge refactor) is confirmed as a real architectural gap and is queued P0 ahead of further Phase 2 work. Memory's claim that "Phase 1 is closed" is correct; the v3 scope doc was forward-looking when written and reality has caught up.

The next 4 sessions are sequenced: state audit (this session, complete) → CP-architecture-1 implementation → synthesis writer scope-doc authoring → synthesis writer chained execution.

---

## CP8 Phase 1 — CLOSED ✅

All eleven tasks landed. Verified directly against prod schema and code on 2026-05-03.

### Schema additions to `memory_service.memories` (Task 1)

All 10 columns present with correct defaults and indexes:

| Column | Type | Default | Index |
|---|---|---|---|
| `synthesis_version` | int | 1 | — |
| `source_memory_ids` | uuid[] | — | GIN partial |
| `role_tag` | text | — | btree |
| `redaction_state` | text | `'active'` | btree |
| `confidence_score` | float | — | — |
| `contributing_agents` | text[] | `'{}'` | — |
| `consensus_method` | text | `'single_agent'` | — |
| `synthesis_prompt_version` | text | — | — |
| `superseded_by` | uuid | — | btree partial |
| `is_pinned` | boolean | `false` | — |

`check_redaction_state` constraint enforces `redaction_state ∈ {active, redacted, modified, pending_resynthesis}`.

### New tables (Tasks 3, 4, 5)

- `memory_service.tenant_roles` — present
- `memory_service.synthesis_audit_events` — present (append-only trigger from Task 4 verified earlier)
- `memory_service.synthesis_rate_limits` — present

`memory_service.synthesis_disagreements` is **not** present — that's a Phase 3 (multi-agent consensus) table, not Phase 1. Out of scope for Phase 1 closure.

### Tenant roles seeded (Task 5 follow-on)

Default 5-role set populated for tenant `44c3080d-c196-407d-a606-4ea9f62ba0fc`:
`public`, `engineering`, `product`, `revenue`, `legal`.

### Code-side Phase 1 (Tasks 6, 7, 8, 10)

- `src/synthesis/policy.py` — present (8849 bytes)
- `src/synthesis/redaction.py` — present (14127 bytes)
- `src/synthesis/state_machine.py` — present (6096 bytes)
- `src/tier_gates.py` — present (9208 bytes)

Phase 1 retroactive fixes from migrations 016–020 are landed (per memory #19, #22). `tests/synthesis/test_redaction.py` 8/8 passing on prod DO.

### Tasks 9 and 11 status

Memory claims Phase 1 closed. Tasks 9 (cron cadence design) and 11 (cadence docs) were code-side / docs-only and have either landed or been folded into Phase 2 cron work (T11 nightly contract test cron landed 2026-05-03). Treating Phase 1 as closed for planning purposes.

---

## CP8 Phase 2 — Partial

Phase 2 in v3 scope is eleven tasks split into two halves:

| Task | Description | Status |
|---|---|---|
| T1 | Clustering engine | ❌ Not started |
| T2 | Single-agent synthesis writer | ❌ Not started |
| T3 | Source-quote validation | ❌ Not started |
| T4 | DB-backed jobs table | ❌ Not started |
| T5 | `POST /synthesis/run` manual trigger | ❌ Not started |
| T6 | Cron schedule for synthesis | ❌ Not started |
| T7 | Audit-and-rate-limit-aware writes | ❌ Not started |
| T8 | Verbatim audit + `docs/VERBATIM-GUARANTEE.md` | ⚠️ Audit implicit in code; doc missing |
| T9 | `GET /memories/{id}/source` endpoint | ✅ Shipped (commit `963a5e8`) |
| T10 | `zerolatency verify` CLI verb | ✅ Shipped (commit `df87493`) |
| T11 | Nightly contract test cron | ✅ Shipped (commit `4eb70ab`) — see hollow-pass risk below |

**Verbatim slice (T8–T11):** mostly done. T8 docs are the only gap.
**Synthesis writer body (T1–T7):** not started.

### T11 hollow-pass risk

The nightly contract test exits 0 (PASS) when 0 atoms are extracted from the sentinel input. This means the test silently always passes regardless of whether the verbatim path is functioning. Fix is queued for next sprint: bypass extraction by writing the sentinel directly via `/memories/seed` and verifying the verbatim path on the seeded row. Not blocking; the endpoint and CLI are correct, only the test wiring is at fault.

---

## CP-architecture-1 — Confirmed Needed (P0)

Live audit of `/root/0latency-mcp-unified/src/server-sse.ts` confirms the architectural debt described in the 2026-05-03 handoff, with one clarification.

### What's actually there

```
Line 432, 450: console.log("with valid API key" : "MISSING API KEY")  ← cosmetic check only
Line 434, 452: if (!apiKey || !apiKey.startsWith("zl_"))              ← prefix-only validation
Line 457:      const tenantId = await getTenantId(apiKey);            ← real DB lookup happens here
```

### What this means

The MCP server does perform a real tenant lookup (`getTenantId(apiKey)` at line 457), but only *after* the cosmetic `startsWith("zl_")` gate passes. The misleading log at 432/450 fires before any real validation, which is why "valid API key" appeared in logs throughout the 2026-05-02 cascade despite the key being dead.

The **handoff's framing was slightly off**: there is no `MCP_API_KEY` env var being held against — the grep returned nothing. The real issue is that the cosmetic prefix check is followed by a tenant lookup that, when it fails, produces an error path that hasn't been instrumented as clearly as the cosmetic check. Net effect is the same — silent 401 cascade with misleading logs — but the fix is simpler than originally scoped: kill the cosmetic check, kill the lying log, surface the tenant-lookup failure clearly.

### Smithery URL key-embedding (third symptom)

The Smithery published listing embeds the API key as `?key=` in the URL. Every customer key rotation invalidates their Smithery listing. This is the same root cause's third symptom and gets resolved when the MCP becomes a stateless edge.

### Operational lesson (until CP-architecture-1 ships)

Any server-side key rotation requires updating the chat-side MCP connector configuration as a separate manual step. The DB rotation does not propagate to the connector. After CP-architecture-1, the only place that needs to know the new key is wherever the client-side connector lives.

---

## Open items by priority

### P0 — Blocks further CP8 P2 work

- **CP-architecture-1** — MCP server stateless-edge refactor. Scope doc separate.

### P1 — Queued for next sprint

- **T11 contract test hollow-pass fix** — switch to `/memories/seed` path so the test actually verifies the verbatim contract.
- **T8 leftover** — `docs/VERBATIM-GUARANTEE.md`. Fold into CP-architecture-1 scope-doc session for efficiency (it's writing, not coding).

### P2 — Carried forward, address as convenient

- 19 other `_db_execute + split('|||')` call sites — same vulnerability class as the 2026-04-29 fix
- `analytics_events` schema-qualifier bug — single-line fix
- Jobs table persistence — CP8 Phase 2 T4 fixes this
- `GET /tenant/info` 404 — MCP server hits non-existent FastAPI route
- `.env` discipline — pre-commit hook
- Memory #6 backup file path — unverified
- Smithery listing has stale key embedded as `?key=` — re-publish without key after CP-architecture-1
- Build/deploy hygiene — `/root/0latency-mcp-sse/dist/` not git-tracked, deploys via `cp -r`, no rollback

### Long-running

- Denis onboarding — GitHub access + Supabase project access
- Mobile dashboard.html — missing layout pieces
- Seb re-clone after 2026-04-25 force-push
- LongMemEval benchmark — post-synthesis-layer quality gate
- Show HN — gated on platform stability and synthesis layer shipping

---

## Next 4 sessions

| # | Surface | Model | Work | Estimated wall clock |
|---|---|---|---|---|
| 1 | Chat (this session) | Opus | State audit + this doc + CP-architecture-1 scope doc | Complete |
| 2 | CC | Sonnet | CP-architecture-1 implementation: kill cosmetic check, kill lying log, surface tenant-lookup failure cleanly. Plus T8 `VERBATIM-GUARANTEE.md` if folded in. | 1–2 hr |
| 3 | Chat | Opus | Pre-author 5–7 autonomy scope docs for synthesis writer body (T1–T7) | 3–4 hr |
| 4 | CC | Sonnet | Single chained run executing all synthesis writer scope docs | ~30 min (if pacing holds) — see caveat |

### Caveat on Session 4 estimate

The 10-minute T10+T11 chained run was on unusually mechanical tasks (stdlib-only, single API call + assertion, no migrations, no service restarts). Synthesis writer tasks involve clustering, source-quote validation, DB schema for jobs, and async race-condition surface area. Hold the 30-minute estimate loosely. Scope-doc tightness for synthesis tasks needs to be higher than it was for T10/T11 because the failure surface is bigger.

---

## Working principles (carry forward, unchanged)

- Strategic frame: **enterprise drives architecture, consumer drives surface**. Default decision lens: *"What would Mem0 do at this stage, and what serves 0Latency's long-term position vs Mem0?"*
- Build quality bar: 8–9 figure platform target, never ship fast that breaks.
- Model selection: Opus for chat (architectural judgment, scope-doc authoring); Sonnet for CC (mechanical execution); Haiku for extraction.
- DESK-MODE always on: SSH + CC + Mac terminal already open; commands specify surface upfront, one at a time, expected output stated.
- No questionnaires during execution: when next step is obvious, make the call.
- Prime directive on prod DB: never ask Justin to paste output containing secrets; state safety upfront on every command.
