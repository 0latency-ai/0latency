# RECENCY WEIGHTING — ANALYSIS
> **PARTIALLY SUPERSEDED — §7 / §7.1.** This document was written against `33d3916`.
> Its highest-severity finding, the unbounded recency from future-dated `event_at`,
> was fixed on 2026-08-25 by `8d8785c` ("restore the q22 recency clamp"). §7.1's
> verification block is therefore stale in every line: `RECENCY_CLAMP_ENABLED` now
> exists, `_compute_signal_spread_iqr()` now exists and is wired into
> `_compute_adaptive_weights`, `tests/test_recency_clamp.py` is present, and the
> `exp()` call is preceded by `days_since = max(0.0, days_since)`. §9's claim that
> "the missing clamp ... [is] still live exactly as measured" no longer holds.
>
> **The clamp landed on the PRIMARY PATH ONLY.** `recall_fixed` is clamped;
> `recall_cross_agent` is not — it still reads raw `created_at` with no floor at
> zero. The nine future-dated rows in §7's table remain unbounded on the
> cross-agent path. Do not read `8d8785c` as having closed §7 for both scorers;
> the asymmetry between the two paths that §6 documents is exactly what let the
> clamp land on one of them and not the other.
>
> `9333c04` itself remains contained by no branch. It was re-implemented, not
> cherry-picked, so §7.1's `git merge-base` and `git branch --contains` results
> still reproduce as written and are not evidence that the fix is absent.
>
> **Line numbers throughout this document are pre-`19f73cf`** and have shifted.
> `_load_agent_config` 423→437, `_retrieve_candidates_cross_agent` 1526→1542,
> `recall_cross_agent` 1579→1595, the 2.5x sub-day boost 1702→1718, the falsy-zero
> block 440-443→453-460. Resolve every `src/recall.py:NNN` citation by symbol, not
> by line.
>
> Everything outside §7 / §7.1 — the two-scorer divergence, the falsy-zero loader,
> the absent `agent_config` rows, the cross-tenant bleed, the 2.5x boost and the
> 0.4169 discontinuity — was re-verified against `19f73cf` on 2026-08-25 and still
> holds. Census figures drift with live ingestion; candidate-eligible measured
> 16,630 on 2026-08-25, against the 16,295 recorded in §2.1.
>
> The body below is preserved verbatim and has not been corrected.

**Date:** 2026-08-25
**Box:** 164.90.156.169 · `/root/.openclaw/workspace/memory-product`
**Status:** ANALYSIS ONLY. No code changed, no schema changed, no weights tuned.
**Trigger:** cross-agent recall pulls `user-justin` rows into the candidate pool
(10 every time) and then drops them below the `composite > 0.4` selection gate.
**Scope note:** all figures measured against prod on 2026-08-25 unless dated otherwise.

---

## 0. SUMMARY — WHAT THE MEASUREMENTS CHANGED

The premise in the brief is that recency weighting at 0.35 is burying old rows,
and that removing it might be unsafe while supersession is incomplete. The
measurements support the first half and **contradict the second**.

1. **Recency weighting is not one system, it is two, and they disagree.** The
   primary path already redistributes recency to semantic when timestamps are
   degenerate — measured live at `rec=0.005`, not 0.35. The cross-agent path has
   no such mechanism and runs the raw 0.35. The cross-agent scorer is an older
   scorer that never received four separate upgrades the primary path has.
2. **The dominant term is not decay, it is a 2.5x boost.** `recall_cross_agent`
   multiplies recency by 2.5 for rows under one day old. That is uncapped while
   every other signal is normalised to [0,1], so a row minutes old scores 0.875
   on recency alone — more than double the 0.4 gate — before relevance is
   considered at all. There is a **0.4169 discontinuity at exactly 1 day**, which
   is larger than the entire selection gate.
3. **Effective reachability is 0.33%.** Of 16,295 candidate-eligible `user-justin`
   rows, **51–53 clear the cross-agent gate — and they are the same 51 rows for
   every query tested.** 51 of those 52 are under a day old and 51 of 52 cleared
   with cosine below 0.50. The gate is, in practice, query-independent.
4. **Recency is not protecting you from stale facts.** In **460 of 461** live
   duplicate-headline groups (99.8%), the newest member is already ≥30 days old,
   where recency is ~0 for *every* member. Recency cannot order stale-vs-current
   in 99.8% of the cases where that ordering actually matters. Removing it does
   not expose you to a risk it is currently absorbing.
5. **A separate, live, higher-severity defect surfaced.** Nine rows carry
   future-dated `event_at`. The primary path does not clamp negative age, so one
   row scores recency **2.05 × 10¹¹**. Verified live: it defeats the adaptive
   detector (`rec_info=1.000`) and consumes the entire result set. The commit
   that fixed this (`9333c04`, Q22) is **in no branch** despite being documented
   as shipped. See §7 — this is worth more than the tuning question.

---

## 1. THE FULL SCORING FORMULA — EVERY COMPONENT, EVERY WEIGHT

There are two scorers. Which one runs depends on `cross_agent` and, when true,
on whether the primary result clears `confidence_threshold`.

### 1.1 Where the weights come from

`_load_agent_config()` — `src/recall.py:423`. Reads `memory_service.agent_config`
by `agent_id`, falling back to hardcoded values at `:451-460`.

| weight | config column | code fallback (`:451-460`) |
|---|---|---|
| semantic | `semantic_weight` | **0.40** |
| recency | `recency_weight` | **0.35** |
| importance | `importance_weight` | **0.15** |
| access | `access_weight` | **0.10** |
| half-life | `recency_half_life_days` | **3 days** |

**For `user-justin`, every one of these is the code fallback.** There is no
`agent_config` row for `user-justin` — none under tenant thomas, none under any
tenant. The whole table holds 3 rows (`echo`, `thomas`, `default`), all owned by
"Default Tenant". So the 0.35 in the brief is correct, but it is a **default that
nobody chose**, not a tuned setting. Nothing has ever been configured for this agent.

Three defects in this loader, all latent today but worth recording:

- **Falsy-zero.** The pattern is `float(row[1]) if row[1] else 0.35` (`:440-443`).
  A deliberately configured weight of `0.0` is falsy and silently becomes the
  default. **Recency cannot be turned off through configuration** — setting it to
  zero yields 0.35. Any tuning attempt via the config table will fail this way.
- **Cross-tenant bleed.** The query filters on `agent_id` only (`:433`), with no
  `tenant_id` predicate. Isolation relies on RLS, but `agent_config` has
  `relforcerowsecurity = false` and the app connects as `doadmin`, the table
  owner — so RLS is bypassed. Verified: with tenant context set to thomas,
  `WHERE agent_id='thomas'` returns the **Default Tenant's** row. `user-justin`
  is unaffected only because no row exists anywhere.
- **Dead defaults.** `recall_cross_agent` reads `config.get("semantic_weight", 0.55)`
  (`:1638-1642`) — 0.55/0.15/0.20/0.10. Those literals are unreachable:
  `_load_agent_config` always returns every key. Reading the cross-agent function
  in isolation gives you the wrong weights.

### 1.2 Cross-agent scorer — `recall_cross_agent`, `src/recall.py:1579`

Candidate retrieval (`_retrieve_candidates_cross_agent`, `:1526`): for each of 12
agent namespaces, vector-nearest **`LIMIT 10`** (`:1560`), filtered to
`superseded_at IS NULL` and non-null embedding. No `raw_turn` exclusion — the
3,458 raw turns under `user-justin` compete for those 10 slots.

```
recency    = exp(-0.693 * days_since / 3)          # days_since from created_at ONLY
             * 2.5   if days_since < 1             # :1702  — uncapped
importance = min(importance * (1 + 0.1*min(reinforcement_count,5)), 1.0)
access     = min(access_count / 10, 1.0)

composite  = 0.40*similarity + 0.35*recency + 0.15*importance + 0.10*access

tier: composite > 0.7 -> L1 (full context)
      composite > 0.4 -> L0 (headline)
      else            -> DROPPED          # :1747-1752
```

### 1.3 Primary scorer — `recall_fixed`, `src/recall.py:839`

Same four base signals, then **six mechanisms the cross-agent path does not have**:

| # | mechanism | line | effect |
|---|---|---|---|
| 1 | `event_at` fallback | `:1117` | uses `event_at or created_at`; cross-agent uses `created_at` only |
| 2 | **adaptive rebalancing** | `:82`, `:1122` | redistributes degenerate recency into semantic |
| 3 | semantic floor | `:51`, `:1146` | `RECALL_SEMANTIC_FLOOR=0.50`; sub-floor candidates dropped outright |
| 4 | keyword match | `:24`, `:1029` | `RECALL_KEYWORD_MATCH_ENABLED=true` → `kw_weight=0.15`, recency 0.35→0.20 |
| 5 | type/entity/topic bonuses | `:1160+` | dampened when signals degenerate |
| 6 | lower gates | `:1299` | L1 >0.45, L0 >**0.25** — cross-agent drops at 0.4, 60% higher |

**Mechanism 2 is the crux.** `_compute_adaptive_weights` (`:82`) measures the
spread of recency across candidates. When all candidates are old, spread ≈ 0,
recency is judged uninformative, and its weight is redistributed to semantic —
the only query-dependent signal.

Measured live, primary path, query "What do we know about Justin?":

```
[ADAPTIVE] rec_spread=0.0000 sem_spread=0.1940 rec_info=0.023 sem_info=0.997
           weights: sem=0.596 rec=0.005 imp=0.150 acc=0.100 type_dampen=0.617
```

**Recency weight 0.35 → 0.005.** On the primary path recency is already, in
effect, switched off for this store. The 0.35 the brief is aimed at is live on
one path only.

### 1.4 Embeddings

`RECALL_USE_VOYAGE=false` → the `local_embedding` column, **all-MiniLM-L6-v2**
(384-dim). This sets the realistic similarity ceiling and is essential to §2:
MiniLM cosine for related-but-not-identical prose runs far below 1.0.

---

## 2. HOW MUCH OF THE STORE IS UNREACHABLE — MEASURED

### 2.1 Census (tenant thomas, `agent_id='user-justin'`)

| | rows |
|---|---:|
| total | **17,100** |
| not superseded | 16,305 |
| has `local_embedding` | 17,090 |
| **candidate-eligible** (both) | **16,295** |
| of which `raw_turn` | 3,458 |
| carrying `event_at` | 4,478 |

> The brief and `b19f58d` say 17,060. Now 17,100, and 17,106 twenty minutes later
> when §5 was measured — the store is live and ingesting, so totals drift between
> queries in this document by a handful of rows. Percentages are unaffected. Figures below use the 16,295 that can actually be retrieved.

Age: **median 99.1 days, mean 99.6 days.**

### 2.2 What similarity each row would need

With `static = 0.35*recency + 0.15*importance + 0.10*access`, a row clears the
0.4 gate only if `similarity > (0.4 - static)/0.4`. Mean static across the
16,295 rows is **0.1120**, i.e. the average row needs **cosine ≈ 0.72**.

| required cosine | rows | share |
|---|---:|---:|
| > 1.00 (impossible) | 0 | 0% |
| > 0.90 | 27 | 0.2% |
| > 0.80 | 3,834 | 23.5% |
| > 0.70 | 9,011 | 55.3% |
| ≤ 0.50 | 100 | 0.6% |

Nothing is *arithmetically* unreachable. Reachability is decided by what cosine
all-MiniLM actually produces.

### 2.3 What similarity is actually achievable

Six realistic queries, embedded with the same `_embed_text_local` the service
uses, scored against all 16,295 rows:

| query | max cos | p99 | p95 | rows ≥0.50 | **clear 0.4 gate** |
|---|---:|---:|---:|---:|---:|
| How does Justin prefer to work? | 0.648 | 0.256 | 0.166 | 27 | **52** |
| What are Justin's communication preferences? | 0.713 | 0.320 | 0.200 | 45 | **53** |
| How should I give Justin feedback? | 0.599 | 0.289 | 0.194 | 12 | **51** |
| What do we know about Justin? | 0.647 | 0.246 | 0.132 | 18 | **51** |
| What is Justin's approach to making decisions? | 0.622 | 0.294 | 0.198 | 25 | **51** |
| What does Justin find difficult about criticism? | 0.634 | 0.283 | 0.176 | 27 | **51** |

Best cosine observed anywhere: **0.713**. p95 sits at 0.13–0.20. The mean row
needs 0.72. **The requirement exceeds the ceiling.**

### 2.4 The result set is query-independent — the decisive measurement

| | |
|---|---:|
| rows clearing the gate, per query | 52, 53, 51, 51, 51, 51 |
| union across all six queries | **54 distinct rows** |
| intersection (clear for *every* query) | **51 rows** |
| intersection as share of smallest result set | **100.0%** |

Six different questions. The same 51 rows every time. Their character:

| of the 52 rows clearing for query 1 | count |
|---|---:|
| under 1 day old (get the 2.5x boost) | **51** |
| under 7 days | 51 |
| 30 days or older | 1 |
| **cleared despite cosine < 0.50** | **51** |

**Answer to the question as posed: 16,241 of 16,295 rows — 99.67% — are
unreachable through cross-agent recall across all six queries.** The 0.33% that
get through do so because they were written today, not because they matched. The
similarity term is not deciding anything; it is decoration on a recency filter.

### 2.5 Why: the store's age profile

| age bucket | rows |
|---|---:|
| < 1 day | 56 |
| 1–7 days | 61 |
| 7–30 days | **0** |
| ≥ 30 days | **16,183 (99.28%)** |

With a 3-day half-life, `0.35 * exp(-0.693*d/3)` contributes 0.00034 at 30 days
and 0 at 99. For 99.28% of the store the recency term is **identically zero** —
it does not rank them badly, it does not rank them at all. Meanwhile the 2.5x
boost hands the newest 56 rows up to 0.875 unearned.

Note the empty 7–30 day bucket: this store is bimodal — a 16k-row mass at 99+
days and a ~117-row fresh sliver. There is no middle for a decay curve to act on.
A half-life of 3 days on a 99-day-median store is not a tuning choice; it is a
step function that happens to be written as an exponential.

### 2.6 The 1-day cliff

| age | recency | 0.35 × recency |
|---|---:|---:|
| 0.00 d | 2.500 | **0.875** ← clears the 0.4 gate alone |
| 0.50 d | 2.227 | **0.780** ← clears alone |
| 0.99 d | 1.989 | **0.696** ← clears alone |
| **1.00 d** | 0.794 | **0.278** |
| 3 d | 0.500 | 0.175 |
| 30 d | 0.001 | 0.0003 |
| 99 d | ~0 | ~0 |

**Composite drops 0.4169 across an instant at 1 day — larger than the 0.4 gate
itself.** Two memories written 20 minutes apart on either side of midnight-minus-24h
are ranked as though they were different classes of object. This is not decay
behaviour and it is not defensible as decay; it is an undocumented cliff. Note
also that 2.5 is *uncapped* while similarity, importance and access are all
normalised to [0,1] — recency is the only signal permitted to exceed its own scale.

### 2.7 For contrast: the primary path on the same store

Primary-path reachability is bounded by the semantic floor (`≥0.50`), giving
**12–45 rows per query — and the count varies with the query** (see §2.3). That
is a relevance bar doing relevance work. Cross-agent yields a near-constant 51
regardless of the question. Same store, same embeddings, same day: one path
discriminates, the other does not.

---

## 3. IS RECENCY WEIGHTING APPROPRIATE FOR THIS STORE?

**For the general case of this store: no, and the codebase already agrees with
that conclusion on the path that matters.**

The brief's framing — "a memory from March about how I work is not less true than
one from August" — is a claim about **fact class**, and it is right. But the
sharper finding is that the current implementation is not expressing a belief
about staleness at all:

- It cannot discriminate among 99.28% of the store (all recency ≈ 0).
- It discriminates violently within the newest 24 hours (2.5x, uncapped).
- So it is functionally an **ingestion-recency filter** — "was this written
  today?" — not a staleness signal. It answers a question nobody asked.

Decay is defensible when memories have a natural validity horizon and the store
is dense across the decay window. Neither holds here. This store is dominated by
identity, preference and working-style facts, and it is empty between 7 and 30
days. There is no population for a 3-day half-life to sort.

**However — "remove recency" is the wrong prescription, for two reasons.**

*First*, the primary path already effectively removed it, adaptively and with a
principled trigger (`rec_info=0.023 → rec=0.005`). The correct move is not a new
policy but **closing the gap between the two scorers**. The cross-agent path is
running a scorer that predates the adaptive work, the semantic floor, the
`event_at` fallback, the keyword term and the current gate thresholds. Framing
this as "tune recency down" would paper over the real fault, which is that one
retrieval path silently missed five years of ranking improvements.

*Second*, recency is doing one job worth preserving: **tie-breaking among
near-identical candidates**, which matters precisely because supersession
under-fires (§5). That job needs a bounded, monotone signal — not a 2.5x spike in
a 24-hour window followed by a numerical cliff.

What the evidence supports, in order of confidence:

1. **The 2.5x boost (`:1702`) is indefensible as written** — uncapped, undocumented,
   discontinuous, and the sole cause of the query-independent result set. Highest
   confidence, smallest change.
2. **The cross-agent path should inherit the adaptive rebalancer**, so degenerate
   recency is redistributed there as it already is on the primary path.
3. **A 3-day half-life is wrong for a 99-day-median store** regardless of the
   above; the `default` agent already uses 14 days, and even that is short here.
4. **Do not set recency to 0** — both because it still tie-breaks, and because
   the falsy-zero bug (§1.1) means you cannot express 0 through config anyway.

---

## 4. WHAT THE FIELD DOES

Systems reporting 92–96% on LongMemEval do not get there by tuning a decay
constant. The consistent pattern is **relevance plus explicit versioning**, with
time used as *metadata and evidence*, not as a ranking multiplier.

| system | reported | how time is handled |
|---|---|---|
| Supermemory | **95% overall**, Knowledge Update **99%**, Temporal Reasoning 91% | semantic search over atomic facts + **dual timestamps** (`documentDate` vs `eventDate`) + relational versioning (`updates`/`extends`/`derives`). No decay weight disclosed; ambiguity resolved through **relational chains, not time-decay**. |
| Mem0 | Knowledge Update **93.6%**, single-session 98.2–98.6%, multi-session 88.0% | multi-signal retrieval — semantic + BM25 + entity matching. Temporal decay not part of the fusion. Its Knowledge-Update ceiling is attributed to an **ADD-only architecture** where old facts are preserved rather than overwritten. |
| Memoria | 88.78% overall | retrieval-led; time-aware indexing + query expansion reported to lift temporal-reasoning recall **7–11%** — indexing, not score decay. |

Three findings bear directly on this store:

- **Pure recency ranking is measured as actively harmful at long tenure.** In a
  longitudinal study, a token-matched recency-window baseline collapsed to
  **73.0%** at short horizon and **42.9–66.4%** by week 9 — worse than any real
  memory architecture. The same work reports a "tenure crossover": architectures
  that discard or down-weight old material lead early and lose later, with the
  map-style system falling **96.3% → 72.2%** on early-epoch questions as eviction
  consumed the oldest material. **This store is at week ~14.**
- **The recommended structure is lossless + versioned, not decayed.** The winning
  design combines an unbounded provenance-typed graph with focused per-question
  retrieval, explicitly to avoid recency-biased ranking.
- **Decay is endorsed only as a *secondary* signal on top of supersession** — so
  that facts nobody ever explicitly contradicts still fade. The stated trade-off:
  "tuned too aggressively will lose a user's name; tuned too laxly will keep
  stale state forever." A 3-day half-life on a 99-day store is the aggressive end
  of that dial by a wide margin.

The `event_at` / `created_at` split this codebase already has is exactly
Supermemory's `eventDate` / `documentDate` distinction. The primary path uses it
(`:1117`). **The cross-agent path ignores `event_at` entirely** and only 4,478 of
17,100 rows populate it. The infrastructure for the field-standard approach is
half-built and half-wired.

**Sources:**
- [Supermemory — LongMemEval research](https://supermemory.ai/research/longmembench/)
- [Mem0 — AI Memory Benchmarks 2026](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)
- [Ground Truth First: … the Tenure Crossover in Memory-Architecture Rankings](https://arxiv.org/html/2607.21962v1)
- [Supersede: Diagnosing and Training the Memory-Update Gap in LLM Agents](https://arxiv.org/html/2606.27472v1)
- [Mem0 — Memory eviction and forgetting in AI agents](https://mem0.ai/blog/memory-eviction-and-forgetting-in-ai-agents)
- [LongMemEval (benchmark)](https://xiaowu0162.github.io/long-mem-eval/)
- [Benchmarking Memoria on LongMemEval](https://medium.com/@matrixorigin-database/benchmarking-memoria-on-longmemeval-strong-memory-retrieval-clear-reader-separation-ee6c89c75d76)

---

## 5. INTERACTION WITH SUPERSESSION — THE HYPOTHESIS IS TESTABLE, AND IT FAILS

The concern: if stale facts are not marked dead, recency may be the only thing
keeping current facts on top, so removing it without the supersession work makes
things worse.

**Correction to the premise first.** Supersession is not missing. It is
implemented, live, and has fired **4,645 times**; **796 of `user-justin`'s 17,106 rows (4.65%) carry `superseded_at`**, and 796 distinct
corrections did the superseding (measured this session; the design doc's 802 is a
slightly different query from 2026-08-21). Per `docs/CONTRADICTION-DETECTION-DESIGN.md`
(2026-08-21, design-only, B2/B3 not started), it is reachable only through gates
the extraction LLM must walk unaided, and it under-fires:

| `user-justin` | measured |
|---|---:|
| corrections | 813 |
| no `contradicts_id` (Gate 2 miss) | **109 (13.4%)** |
| dangling `contradicts_id` | 0 |
| actually superseded (design doc, 2026-08-21) | 802 |
| rows carrying `superseded_at` (measured 2026-08-25) | 796 |
| contradiction seen but misclassified (Gate 1 miss) | **116** |
| live duplicate-headline groups (2026-08-21) | 448 |

So the *backlog* the hypothesis worries about is real. The question is whether
recency is currently suppressing it.

**It is not.** Live duplicate-headline groups among unsuperseded `user-justin`
rows, today:

| | count |
|---|---:|
| duplicate-headline groups | **461** (991 rows) |
| groups whose **newest** member is < 7 days old | **1** |
| groups whose newest member is ≥ 30 days old | **460** |
| **share where recency cannot discriminate at all** | **99.8%** |

In 460 of 461 groups every member is old enough that recency evaluates to ~0 for
all of them. Recency is not choosing the current fact over the stale one — it is
returning the same ~0 for both and letting similarity, importance and access
decide. **The protection the hypothesis is worried about losing is not currently
present.**

There is a second, independent reason to doubt it: **the experiment has already
been run.** The primary path serves every non-cross-agent recall and has been
running at `rec≈0.005` — recency effectively off — via the adaptive rebalancer.
If near-zero recency caused stale facts to surface, that regression would already
be in production on the main path, not hypothetical.

**Revised conclusion for Q5.** The dependency runs the other way. Supersession
work is independently necessary — 13.4% Gate-2 miss and 461 live duplicate groups
are a real defect, and the field data says Knowledge Update accuracy is exactly
what an ADD-only architecture caps. But it is **not a prerequisite for fixing the
cross-agent scorer**, because recency is not currently doing the job the
prerequisite argument assumes. The two can proceed independently, and the scorer
fix is the smaller and better-evidenced of the two.

One caveat, stated honestly: this analysis measures *exact* headline duplicates.
Semantic contradictions with differing headlines (§2.3 of the design doc — the
"silent miss" class) are by construction invisible to this query, and the design
doc calls that class the one the architecture cannot see even in principle. The
99.8% figure is about the measurable duplicate surface, not a claim that no
stale-fact risk exists anywhere.

---

## 6. WHY CROSS-AGENT DIVERGED — MECHANISM, NOT TUNING

`recall_cross_agent` is a fork of an older `recall_fixed`. Everything the primary
path gained since, it lacks:

| capability | primary | cross-agent |
|---|---|---|
| adaptive weight redistribution | ✅ `:82`, `:1122` | ❌ |
| `event_at` as temporal reference | ✅ `:1117` | ❌ `created_at` only |
| semantic floor (0.50) | ✅ `:51` | ❌ |
| keyword-match term | ✅ `:1029` | ❌ |
| type/entity/topic bonuses | ✅ `:1160+` | ❌ |
| 2.5x sub-day recency boost | ❌ | ⚠️ `:1702` |
| L0 drop threshold | 0.25 `:1299` | 0.40 `:1750` |
| `raw_turn` excluded from candidates | ✅ | ❌ (3,458 rows compete) |

The cross-agent path is harsher at every stage — cruder scoring, no floor, no
adaptation, a 60%-higher drop gate, and a boost the primary path deliberately
does not have. This is drift, not policy.

---

## 7. SEPARATE LIVE DEFECT — UNBOUNDED RECENCY FROM FUTURE `event_at`

Found while tracing §1.3. **Higher severity than the tuning question.**

The primary path computes `days_since = (now - (event_at or created_at))` at
`:1118` with **no floor at zero**. A future-dated `event_at` gives negative age
and therefore recency **greater than 1** — without bound.

Nine such rows exist under tenant thomas right now:

| agent | headline | event date | days ahead | unclamped recency |
|---|---|---|---:|---:|
| user-justin | temp-slide-repo directory: 23 subdirecto… | 2026-12-16 | 112.8 | **205,159,630,931** |
| default | Notable December film festivals… | 2026-12-01 | 97.8 | 6,415,958,251 |
| user-justin | ZLVERIFY2-134206-M3 cutover window opens | 2026-11-14 | 80.8 | 126,411,650 |
| default | Notable November film festivals… | 2026-11-01 | 67.8 | 6,274,813 |
| default | Purchased sectional sofa on October 30th | 2026-10-30 | 65.8 | 3,953,272 |
| user-justin | Revenue path to $100K-by-fall-2026 target | 2026-09-30 | 35.8 | 3,866 |
| default | Dan Kennedy email on information… | 2026-09-22 | 27.8 | 609 |
| user-justin | Targeting YC submission for fall 2026 | 2026-09-01 | 6.8 | 4.76 |
| user-justin | Outreach to Rachel Powell about Project… | 2026-08-28 | 2.8 | 1.89 |

Verified live, primary path, query "Tell me about the temp-slide-repo directory
and its subdirectories":

```
[ADAPTIVE] rec_spread=12649936025.2111 sem_spread=0.1552 rec_info=1.000 sem_info=0.985
           weights: sem=0.400 rec=0.200 imp=0.150 acc=0.100 type_dampen=1.000
```

Two failures at once. The outlier inflates std-dev-based spread to 1.26 × 10¹⁰,
so `rec_info` saturates at **1.000** — the adaptive rebalancer concludes recency
is maximally informative and **redistributes nothing**. The result set collapsed
to that single memory. Any query retrieving one of these nine rows as a candidate
has its ranking destroyed, and the safety mechanism from §1.3 is turned off
exactly when it is needed.

### 7.1 The fix for this already exists and is in no branch

Commit **`9333c04`** — *"fix(recall): clamp recency to (0,1], IQR adaptive spread
— bound unbounded future-event_at boost [q22-recency-clamp]"*, 2026-05-18 — adds:

- `RECENCY_CLAMP_ENABLED` flag (default true)
- `days_since = max(0.0, days_since)` before `exp()` → recency ∈ (0,1], and
  structurally kills a year-2600 `OverflowError`
- `_compute_signal_spread_iqr()`, swapping std-dev for IQR precisely so outliers
  cannot fake informative recency
- `tests/test_recency_clamp.py` (135 lines)

**None of it is in the live code.** Verified:

```
git merge-base --is-ancestor 9333c04 master   -> NO
git branch -a --contains 9333c04              -> (no branch contains it)
grep -rn RECENCY_CLAMP src/ api/              -> (nothing)
ls tests/test_recency_clamp.py                -> No such file
src/recall.py:1119                            -> unclamped exp(), no max(0.0, …)
src/recall.py:73-79                            -> _compute_signal_spread is std-dev
```

`docs/CP-LONGMEMEVAL-N25-RERUN-SCOPE.md` states Q21 and Q22 are *"shipped,
verified, live"* and calls them *"the two open temporal-reasoning failures."*
Q21's commit `243309e` is likewise not an ancestor of master. **The documentation
and the disk disagree.** Both commits appear to be orphaned — reachable by hash,
in no branch, presumably lost in a rebase or a reset.

This is reported, not fixed, per the brief. I have not re-applied `9333c04`. It
should be verified against current `recall.py` before any cherry-pick — the file
has moved considerably since May, and the banked 76%@20 figure was measured on a
tree that included it, which may mean that number no longer describes master.

---

## 8. MISMATCHES BETWEEN BRIEF AND DISK

Recorded per the brief's instruction to flag rather than guess.

| # | brief / doc says | disk says |
|---|---|---|
| 1 | 17,060 `user-justin` rows | 17,100 today; 16,295 candidate-eligible. Live ingestion; not a discrepancy, just drift. |
| 2 | "recency is weighted 0.35" | True for cross-agent. Primary path measured at **0.005** after adaptive redistribution. Two scorers, one number. |
| 3 | "the missing supersession layer" | Supersession is implemented and has fired 4,645 times (796 on `user-justin`). It **under-fires**; it is not missing. |
| 4 | "CP12" | No CP12 workstream exists. `CP12` appears once, in `docs/CP8-P5-3-SCOPE.md:191`, as a deferred dashboard UI — unrelated. The supersession work is **Chain B** (`docs/CONTRADICTION-DETECTION-DESIGN.md`, B1 design complete 2026-08-21, B2/B3 not started). Flagging in case a different workstream was meant. |
| 5 | Q21/Q22 "shipped, verified, live" (`CP-LONGMEMEVAL-N25-RERUN-SCOPE.md`) | Neither `9333c04` nor `243309e` is an ancestor of master; no branch contains them; the clamp, the IQR spread, the flag and the test file are all absent. See §7.1. |
| 6 | implied: recency protects current facts pending supersession | 99.8% of live duplicate groups have all members ≥30 days old, where recency is ~0 for every member. Not currently protecting. |

---

## 9. WHAT WAS NOT DONE

No code, schema, weight or config was changed. No commit was cherry-picked. The
2.5x boost, the missing clamp, the absent adaptive rebalancing on the cross-agent
path and the nine future-dated rows are all still live exactly as measured.

Recommended sequencing if this is taken forward — **§7 first**: it is a live
ranking-destroying defect on the primary path with an existing, tested fix, and
it is independent of every tuning question in §3.
