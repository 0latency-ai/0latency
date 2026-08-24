# Namespace Unification — Scope

**Date:** 2026-08-24
**Status:** SCOPE — nothing migrated, nothing written to `memories`. Investigation was read-only.
**Box:** 164.90.156.169 (= `mcp.0latency.ai`, same machine-id `bfcb6149…`)
**DB:** `defaultdb`, schema `memory_service`, DO managed Postgres
**Migration tier:** see [§6](#6-migration-tier). Merge is **Tier 3** as briefed, **Tier 2** at best. The recommended option needs **no migration at all**.

---

## 0. READ THIS FIRST — the brief's premise does not survive contact with the data

The brief says one person's memories are split across three `agent_id`s, and names
tenant `thomas`'s ~4,739 rows under `agent_id='default'` as the drawer nobody opens.

**The row count is exactly right: 4,739. What is in it is not what the brief assumes.**

```
tenant thomas / agent_id='default'      4739 rows
  source_session LIKE 'longmemeval%'    4690   (99.0%)   <- LongMemEval benchmark fixtures
  everything else                         49   ( 1.0%)   <- genuinely Justin
```

Sampled headlines from the 4,690: *"Stretching routine consistency strategy"*,
*"Kibbeh bulgur recipe recommendation"*, *"Match shampoo selection to your hair type"*,
*"Vinyl record cleaning solutions"*, *"Tang Dynasty calligraphers' cultural legacy"*,
*"Planning to contact Tropical Birding Tours"*. Every sampled row carries
`source_session = longmemeval_<hash>_session_<n>`. 287 of their headlines are
byte-identical to rows in the `longmemeval-bench` / `longmemeval-benchmark-20260510`
tenants.

**Merging `default` into `user-justin` as briefed would inject 4,690 synthetic
benchmark rows into the real person's memory namespace** — recall would start
answering Justin's questions with a stranger's shampoo preferences. That is worse
than the problem being solved.

The brief's framing appears to trace to a real comment at `api/main.py:314-316`:

> *"agent_id scopes recall, and tenant 'thomas' alone holds 4,739 rows under
> agent_id='default' that flipping the default would strand."*

That comment is accurate and says only that flipping the MCP default would strand
those rows. It does not claim they are Justin's. The claim that they are is the
part that does not hold.

**This is the mismatch. The decision below is yours, and the recommendation changes
on it:** the genuine recovery target in `default` is 49 rows, not 4,739.

---

## 1. Exact row counts per tenant per agent_id

Not assuming the three names. The table holds **122 distinct `agent_id` values**
across **315 distinct (tenant, agent_id) pairs**.

### 1.1 Tenant `thomas` (`44c3080d-c196-407d-a606-4ea9f62ba0fc`) — 24,852 rows, 53 agent_ids

| agent_id | rows | first | last | what it is |
|---|---:|---|---|---|
| `user-justin` | 17,060 | 2026-03-30 | 2026-08-24 | **the person.** Also `tenants.default_agent_id` |
| `default` | 4,739 | 2026-04-11 | 2026-08-22 | **99% benchmark** — see §0 and §2 |
| `thomas` | 2,351 | 2026-03-19 | 2026-08-24 | the Thomas agent's own work memory |
| *50 others* | 702 | — | — | benchmarks, sub-agents, test fixtures |

The 702 tail, largest first: `lme-e47becba` 244, `loop` 106, `echo` 58,
`claude-code` 55, `wall-e` 43, `test-agent` 35, `lance` 21, `lme-fast-*` 56 across
five ids, `cp7b-test-agent` 10, `justin` 9, `atlas` 6, `system_consensus` 6,
`quickstart-agent` 5, and 37 more with ≤4 rows each (`nellie`, `shea`, `scout`,
`sheila`, `steve`, `reed`, `contract-test`, `zz-a1-latency-probe`, assorted
`test-*` / `part2-*` / `b-3-stage-*`).

### 1.2 Tenant `john` (`65b92798-…`) — 801 rows, a separate customer

| agent_id | rows | first | last |
|---|---:|---|---|
| `default` | 758 | 2026-06-29 | 2026-08-23 |
| `apostasy-toolkit` | 43 | 2026-06-29 | 2026-06-30 |

### 1.3 `agent_id='default'` is used by **16 tenants**, not one

| tenant | rows | | tenant | rows |
|---|---:|---|---|---:|
| thomas | 4,739 | | Denis Bodea | 53 |
| longmemeval-bench | 1,215 | | longmemeval-benchmark-20260510 | 45 |
| Brendan | 793 | | Default Tenant | 20 |
| **john** | **758** | | Matthew Smith | 18 |
| Victor D | 80 | | CP7A Test Tenant | 8 |
| bench-probe-a | 54 | | *4 more* | ≤6 each |

**Any `UPDATE … WHERE agent_id='default'` that is not tenant-scoped silently
rewrites John's 758 rows and Brendan's 793.** Tenant scoping is the only thing
separating them.

### 1.4 Tenant sprawl for the same human

Beyond `thomas`, there are **nine tenants named "Justin Ghiglia"** (all but one
empty) plus `justin-ghiglia` (5 rows) — 6 rows of real content total, from
2026-03-24/25 signup testing. Out of scope for a within-tenant merge, and noted
only so it is not discovered later as a surprise. Tenant is the security boundary;
merging across tenants is a different and much larger question.

---

## 2. Which rows genuinely belong to Justin as one person

Judged on content, `source_session`, and `source_type` — not on the name.

| namespace | rows | verdict |
|---|---:|---|
| `user-justin` | 17,060 | **Justin.** Personal + work, unambiguous. Partner Ellen, a relationship conflict, bedbug diagnosis, Canvas admin access, Project Explore Season 4 tiers, K-4 literacy research, DB constraint failures |
| `default` → non-benchmark | **49** | **Justin.** Preferences ("prefers dark mode", "primarily works with Python and TypeScript", "workspace location", "solo, non-technical, ~$10K cash"), Project Explore partnership research, PFL Academy pricing benchmarks, ATDLE 2026 booking, migration notes. ~40 substantive; the rest are `Raw turn —` placeholders and two literal `test` rows |
| `default` → benchmark | **4,690** | **Not Justin.** LongMemEval fixtures. Do not merge |
| `thomas` | 2,351 | **Judgement call.** Justin's *work context*, authored by the Thomas agent: 0Latency differentiators, Loop's channel list, Desert Sands email state, Phase B decisions. Legitimately a separate voice — an agent's operational log, not the person's memory |
| `justin` | 9 | **Residue.** All 2026-04-03, and all *about* a namespace migration: "Chrome Extension defaults to user-justin", "Deferred migration of thomas to agent-thomas", "Database deletion of justin records completed". A prior unification already ran in April 2026 and this is its debris |
| `claude-code` | 55 | Justin's CC sessions via MCP (`source_type='claude_code_mcp'`, 2026-08-23/24). Deliberately separate per the `api/main.py` convention |
| `loop`/`echo`/`wall-e`/`lance`/`atlas`/`nellie`/`shea`/`scout`/`sheila`/`steve`/`reed` | ~240 | **Not Justin.** Autonomous sub-agents with their own memory |
| `lme-*`, `test-*`, `cp7*`, `bench-*`, `part2-*`, `synthetic-agent-*` | ~460 | **Not Justin.** Fixtures |

**Recovery target if you unify: 49 rows.** `user-justin` already holds the person.

---

## 3. What breaks if agent_ids are merged

### 3.1 `agent_id` is on 22 tables, not one

`agent_config`, `agent_roles`, `consolidation_queue`, `entity_index`, `entity_nodes`,
`entity_relationships`, `memories`, `memories_backup_20260425`,
`memories_backup_march27`, `memory_archive`, `memory_audit_log`, `memory_clusters`,
`memory_duplicates`, `memory_edges`, `memory_type_backup_20260429`,
`onboarding_events`, `recall_criteria`, `recall_feedback`, `recall_telemetry`,
`session_handoffs`, `synthesis_jobs`, `topic_coverage`.

A merge that touches only `memories` desynchronises the rest. Current derived
volume for tenant `thomas`:

```
entity_index    user-justin 29,695   default 14,418   thomas   412
entity_nodes    user-justin  8,317   default  7,233   thomas   480
```

Those 14,418 + 7,233 `default` entity rows are overwhelmingly benchmark-derived
and would follow the merge into Justin's graph.

Satellite tables already carry `agent_id`s that do not exist in `memories` at all —
`default-agent`, `user-justin-staging-test`, `thomas-chief-of-staff`,
`thomas-orchestrator`, `thomas-test-tier`, and a raw tenant UUID
`44c3080d-c196-407d-a606-4ea9f62ba0fc` used as an agent_id. Divergence is
pre-existing.

### 3.2 Read paths that filter on agent_id

`src/recall.py` — 69 references. Every retrieval predicate is single-valued
equality: `WHERE agent_id = %s` (lines 279, 433, 481, 511, 519, 1462, 1556), or
`WHERE (agent_id = %s OR memory_type = 'synthesis')` (lines 649, 692, 710, 729,
951). There is no list form on the primary path. Post-merge these keep working
but their scope silently widens to whatever was folded in.

**Live defect found while tracing this.** `recall_cross_agent()` (`src/recall.py:1579`)
defaults to a hardcoded namespace list at line 1605:

```python
agent_ids = ["thomas", "wall-e", "steve", "scout", "reed",
             "atlas", "sheila", "lance", "justin", "loop", "echo"]
```

`user-justin` and `default` are **not in it**. `recall_with_fallback()` (line 1788)
— which is what the API's `cross_agent=true` calls — invokes `recall_cross_agent`
without passing `agent_ids`, so it takes that default. **Cross-agent recall today
cannot see Justin's 17,060 memories.** It searches `justin` (9 rows) instead of
`user-justin` (17,060). This must be fixed under either option and is arguably the
single highest-value line in this document.

### 3.3 Write paths and surfaces

| surface | agent_id written | note |
|---|---|---|
| API / MCP untagged | `resolve_agent_id()` → `tenants.default_agent_id` | for tenant `thomas` this is **`user-justin`** — already correct |
| `api/main.py` fallbacks | literal `"default"` at lines 673, 825, 905, 2197 | fires when tenant has no `default_agent_id` — i.e. **john, Brendan, everyone else** |
| MCP server | `resolveAgentId()` (`tools.ts:46`) is a pass-through; `agent_id` optional on all 11 tool schemas | server-side resolution does the work |
| Chrome extension | `config.agentId`, default literal `'chrome-extension'` (`background.js:48`) | in practice configured to `user-justin` — the 102 extension rows all landed there |
| CC capture hook | `CC_CAPTURE_AGENT_ID`, default `"claude-code"` (`staging/cc-capture/cc-capture-drain.py:22`) | **staged, not installed** — `/root/.claude/settings.json` is `{}`. The 55 `claude-code` rows arrived via MCP `X-Client`, not this hook |
| Synthesis | `synthesis_jobs.agent_id`, filtered `AND agent_id = %s` (`src/synthesis/jobs.py:304`) | jobs are per-namespace; merging re-scopes future synthesis and orphans queued jobs keyed to the old id |
| `agent_config` | keyed by `agent_id`, **3 rows**: `default`, `echo`, `thomas` — all under the `00000000-…` Default Tenant | `_load_agent_config()` (`recall.py:433`) looks up by `agent_id` with no tenant predicate. There is **no `user-justin` row**, so the person's recall runs on hardcoded defaults today. A merge orphans the `default` config row, which is currently the only one carrying an identity/profile for that namespace |
| Tier gates | no `agent_id` coupling found | plan/tier logic keys on tenant, not agent |

### 3.4 The silent-wrong-scope risks, ranked

1. **Cross-tenant clobber.** `UPDATE … WHERE agent_id='default'` without a tenant
   predicate rewrites 16 tenants including a paying customer. Highest severity,
   easiest to do by accident.
2. **Benchmark poisoning.** 4,690 fixture rows plus ~21k derived entity rows enter
   the person's namespace. Recall quality degrades in a way that is hard to
   attribute later.
3. **Derived-table desync.** Merging `memories` alone leaves 21 tables pointing at
   an id that no longer has rows.
4. **Config orphaning.** The `default` `agent_config` row stops being reachable.
5. **Queued-job orphaning.** In-flight `synthesis_jobs` / `consolidation_queue`
   rows keyed to the merged-away id.

---

## 4. Merge versus recall-time alias

### Option A — merge (rewrite `agent_id` on stored rows)

- Touches 22 tables to be correct.
- Irreversible without capturing the original `agent_id` first.
- Imports 4,690 benchmark rows unless the merge is filtered to the 49
  — and a filtered merge is a bespoke one-off, not a general fix.
- Fixes every read path at once, including ones nobody has enumerated.
- Leaves no runtime cost.

### Option B — recall-time alias (map several agent_ids to one identity, stored rows untouched)

- No migration. Stored rows keep their provenance, so "which surface wrote this"
  stays answerable — and that provenance is exactly what let this investigation
  separate benchmark from person.
- Reversible by deleting a row or reverting one commit.
- Lets the alias be *selective*: `user-justin` + `thomas` + the 49, without the
  4,690.
- Requires touching the read paths in §3.2 — the single-valued `agent_id = %s`
  predicates need a list form (`= ANY(%s)`). That is real work and the main cost.
- Adds a resolution step on every recall.
- Anything not routed through the alias (ad-hoc SQL, dashboards, new endpoints)
  keeps seeing the split.

**Existing scaffolding for B, both incomplete:**

- `memory_service.agent_roles` already has `read_namespaces text[]` and
  `write_namespaces text[]` with default `{*}`. It has **0 rows and 0 source
  references** — dead schema, but the intended shape. It is a natural home for the
  alias and costs no new table.
- `recall_cross_agent()` already retrieves across a namespace list and merges
  results. The machinery exists; only its list is wrong (§3.2).

### Recommendation — **Option B, and narrowly**

Reasoning:

1. **The merge's headline prize is 49 rows.** Rewriting 4,739 rows across 22
   tables to recover 49 is a bad trade at any risk level.
2. **99% of what would be merged is not the person's data.** Option A cannot fix
   the split without also importing the benchmark, unless it becomes a hand-filtered
   one-off — at which point it is not a namespace-unification mechanism.
3. **`thomas` (2,351) should stay distinct.** It is an agent's operational log.
   Alias makes it *readable* alongside Justin without pretending it was authored by
   him; merge destroys that distinction permanently.
4. **Provenance is load-bearing.** The only reason the benchmark rows were
   identifiable is that `agent_id` and `source_session` still say what wrote them.
5. **The cheapest real win is not a migration at all.** Fixing the `recall_cross_agent`
   hardcoded list to include `user-justin` (§3.2) recovers most of the practical
   benefit for a one-line change, and is a prerequisite for B anyway.

**Suggested order, smallest first — each independently useful:**

1. Fix the `recall_cross_agent` list. One line. No data touched. Do this regardless
   of everything else.
2. Move the 49 non-benchmark `default` rows to `user-justin`. Tenant-scoped,
   `source_session NOT LIKE 'longmemeval%'`, 49 rows, fully enumerable and
   reversible by id. This is small enough to be a data fix rather than a migration.
3. Decide whether `thomas` should be alias-readable from `user-justin`. Product
   decision, not a technical one.
4. Only if 1–3 prove insufficient, build the alias into `agent_roles` and convert
   the §3.2 predicates to `= ANY(%s)`.

**Do not** run a blanket `default → user-justin` merge.

---

## 5. Rollback

**For the recommendation (Option B / steps 1–3):**

| step | undo |
|---|---|
| 1. cross-agent list | `git revert <sha>`; restart `memory-api`. No data touched |
| 2. the 49 rows | Capture ids **before** the update: `CREATE TABLE memory_service.ns_unif_rollback_20260824 AS SELECT id, agent_id FROM memory_service.memories WHERE tenant_id='44c3080d-…' AND agent_id='default' AND (source_session IS NULL OR source_session NOT LIKE 'longmemeval%');` Undo is `UPDATE memories m SET agent_id=r.agent_id FROM ns_unif_rollback_20260824 r WHERE m.id=r.id;` Exact, row-for-row, no guessing |
| 3. alias rows in `agent_roles` | `DELETE FROM memory_service.agent_roles WHERE …`. Stored memories never changed |
| 4. `= ANY(%s)` predicates | `git revert`; redeploy |

Plus `bash scripts/db_backup.sh` before step 2, per the Tier-1 gate — verified
exit 0, file >1MB, `gunzip -t` passes.

**If Option A is chosen against this recommendation**, rollback *requires* that the
original `agent_id` is captured first, for every one of the 22 tables, in the same
transaction as the update. Without that snapshot the merge is unrecoverable: once
`default` and `user-justin` are the same string there is no field left that
distinguishes them — `source_session` covers the benchmark rows but nothing marks
the other 49, and `created_at` ranges overlap. A restore from `db_backup.sh` would
also discard every legitimate write since the backup.

---

## 6. Migration tier

Per `docs/AUTONOMY-PROTOCOL.md` §Migration Tiers:

| option | tier | why |
|---|---|---|
| **Merge as briefed** (bare `UPDATE agent_id`) | **Tier 3 — always human** | "Data backfill that cannot be reversed mechanically." Once the ids are identical, nothing distinguishes the merged rows. CC halts even if the rest of the chain succeeds |
| **Merge with a pre-captured rollback table** | **Tier 2 — halt for human apply** | Reversible, but still a backfill touching existing rows across 22 tables |
| **Step 1** (cross-agent list fix) | not a migration | ordinary code change |
| **Step 2** (49 rows, with rollback table) | **Tier 2** | touches existing rows; small and enumerable, but not additive |
| **Step 3/4** (alias rows + `= ANY`) | **Tier 1** for the `agent_roles` inserts (purely additive, reversible by DELETE); code change otherwise | |

**Nothing here is Tier 1 except the alias inserts. No part of the merge is
autonomous.** Halt condition 9 ("migration tier escalation") applies if an
implementation run discovers the backfill is wider than scoped — which §3.1 says it
will be, since the brief contemplates `memories` only.

---

## 7. Method / what was and was not done

Read-only throughout: `SELECT` only, no writes to `memories` or any other table, no
migration run. Queries were run as `doadmin` against `defaultdb` from
`/root/.openclaw/workspace/memory-product` with `DATABASE_URL` from `.env`.

Evidence for the §0 finding, in order of strength:

1. `source_session LIKE 'longmemeval%'` on 4,690 of 4,739 rows — direct provenance.
2. 287 headlines byte-identical to rows in the `longmemeval-*` tenants.
3. Content sampling: consumer/lifestyle Q&A indistinguishable from the benchmark
   tenants and unlike anything in `user-justin` or `thomas`.
4. Date clustering: 4,462 of 4,739 in 2026-05, matching the LongMemEval run window.

**Unresolved / not investigated:**

- Whether the 2,351 `thomas` rows *should* be readable as Justin is a product call,
  deliberately left open.
- The nine "Justin Ghiglia" tenants (§1.4) — cross-tenant, out of scope here.
- Why satellite tables carry agent_ids absent from `memories` (§3.1). Pre-existing;
  worth its own look before any merge.
- 5 orphaned `entity_nodes` rows under `agent_id='cleanroom-d2'` remain from an
  unrelated 2026-08-23 probe whose `memories` rows were deleted. Evidence that
  **deleting from `memories` does not cascade to derived tables** — directly
  relevant to any merge or cleanup plan.
