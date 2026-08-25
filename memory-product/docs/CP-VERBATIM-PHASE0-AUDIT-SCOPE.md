# CP-VERBATIM-PHASE0-AUDIT-SCOPE — Locked CC Scope

> **PHANTOM-COMMIT WARNING.** This document anchors to commit `9333c04`. It was discarded on
> 2026-05-22 by a `reset: moving to origin/master` on the workspace box: the commit
> was local-only, never pushed, and the reset moved HEAD onto `e50694d` from
> another machine. It is reachable by hash but contained by no branch, so the
> code this document describes was never in `master`.
> This document survived only because it was untracked, and `git reset` does not
> touch untracked files.
>
> **Therefore unverified:** its instruction to treat Q21/Q22 as "closed, live (`9333c04`)" and its statement that
> `master` HEAD is `9333c04` are both false. Any line-number reference it gives for the
> `raw_turn` persist site points into a tree that is not `master`.
>
> The body below is preserved verbatim and has not been corrected. See
> `docs/RECENCY-WEIGHTING-ANALYSIS.md` §7 for the full reconstruction.

**Type:** Audit only. NO fix code. NO migrations. NO ranker changes.
**Authored:** 2026-05-18 (lead engineer, pre-dispatch)
**Mandate source:** `HANDOFF-2026-05-18-VERBATIM-FOUR-PHASE.md` Phase 0 + `SCOPE-EXTRACTION-AUDIT.md` method.
**Deliverable:** One written document: a Shape-A-vs-Shape-B verdict against the **actual production DB**, with raw rows pasted (never summarized), plus Q1/Q3/Q4 answers.
**Estimate:** 2–4 hours investigation in Opus-in-CC mode.

---

## SCOPE LOCK — read before doing anything

This is a diagnosis job. The single largest documented process failure on this project was repeatedly trusting a flawed verification instrument (the key/sha saga). The DB inspection in this audit IS the decision-driving measurement. If you find yourself about to write "the verbatim text is there" without a pasted raw row proving it byte-checkably, STOP — that is the exact failure mode this scope exists to prevent.

**Hard boundaries — violating any of these fails the job:**

1. **No fix code. No migrations. No ranker edits.** Not one line. The output is a written verdict. Build scope is undefined until this verdict lands; anyone (including you) who proposes a build timeline before the verdict is guessing.
2. **Do NOT touch Q21/Q22 work or the ranker.** That work is closed, live (`9333c04`), and 76%@20 is banked. This audit does not regress-test it, re-run it, or modify it. You may *read* ranker code for diagnosis only.
3. **Key / .env / systemd are permanently OUT of scope.** Do not read, rotate, regenerate, inspect, or reference the API key, `.env`, `.env.benchmark`, or systemd units. This audit does not need the Anthropic key. If any step seems to require touching credentials or systemd, it is out of scope — stop and report instead.
4. **No n=25, no n=500, no LongMemEval harness runs.** This audit does not benchmark. The synthetic-paste threshold test (Step E) is bespoke and small, not a benchmark.
5. **Raw rows or it didn't happen.** Every hit/miss claim in the deliverable must be backed by a pasted raw `memory_service.memories` row excerpt (column values, truncated to first/last 200 chars per long column with char counts stated). Narrative summaries of DB contents are rejected as evidence.

---

## CONTEXT (the question this answers)

The Contentsquare deck — already sent to Luke Elders — claims **"Atoms preserve verbatim source," "Every atom traceable."** That claim is currently UNPROVEN. A ~5000-word Anthropic Dreaming transcript pasted 2026-05-11 could not be recalled 7 hours later by any path. We do not yet know whether:

- **Shape B** = content IS stored verbatim somewhere in `memory_service.memories` (or a related table), and the recall ranker buries it. *Good outcome — fix is recall-path work, days.*
- **Shape A** = content was captured and reached the pipeline, but extraction summarized it away before the DB write; verbatim bytes never landed. *Expensive outcome — requires Artifact Vault build, weeks.*
- **Shape C (CAPTURE-GAP)** = the content never entered the pipeline at all. No ingress path fired on the surface/session where it was pasted, OR it fired but wrote to the wrong tenant/agent namespace and was never associated with the user. The bytes were never offered to extraction *or* the ranker. *This is neither A nor B and has a different fix class entirely (capture-surface coverage, not storage or recall).* This shape was added because the reproducer was pasted into a chat session, and the 2026-05-11 window overlapped a documented Chrome-extension namespace/auth instability (saves landing in `thomas` instead of `user-justin`). **CC MUST treat Shape C as a first-class possible verdict and MUST NOT collapse a capture-gap MISS into a Shape-A verdict. A Shape-A MISS and a Shape-C MISS look identical in a single-tenant DB query and lead to opposite fixes — distinguishing them is a primary objective of this audit, not a footnote.**

**On the 5-11 diagnostic memory (`228326f2-e88b-4b79-b1af-a58cb372de07`):** it asserts content was "apparently summarized into oblivion by the extraction pipeline." That word *apparently* is load-bearing. This memory is a real-time HYPOTHESIS written during the failure, NOT a verified finding. It is exactly the class of plausible self-report this audit exists to confirm or refute against raw rows. CC must treat it as the thing under test, never as evidence. Do not cite it as proof of Shape A. The Artifact Vault idea memory (`765c1387-3c2e-494b-a267-5f1e1e17e6c5`) is product context, not diagnostic evidence — same rule.

CP8 `raw_turn` preservation (`9deed596`, 2026-04-30) is supposed to persist the raw turn with `parent_memory_ids=[raw_turn_id]`. **It has never been independently verified to fire on the large-paste ingress path.** Its existence is not evidence it fires on the path the reproducer used. This audit determines, with raw rows, whether it does.

**Known confound (factor into Step C):** the 2026-05-11 window overlapped a period of Chrome-extension namespace/auth instability — extension saves were landing in the wrong agent namespace (`thomas` vs `user-justin`) around that time. The originating-tool field and namespace correlation on the *original* reproducer rows may therefore be unreliable. This is exactly why this scope mandates a fresh re-ingest as the clean instrument, with the original trace as corroboration.

---

## METHOD (locked sequence — do steps in order, do not skip)

### Step A — Orient (read-only, no writes)

- Server: `root@164.90.156.169`, workspace `/root/.openclaw/workspace/memory-product`.
- Identify, by reading code (grep-verified, cite file:line in the deliverable):
  - Every ingress write path that reaches `memory_service.memories`: Chrome extension capture, MCP `memory_add` direct, CLI capture, direct API. Map each to the function that performs the DB insert.
  - Where extraction runs relative to the raw-turn persist in each path. The decisive structural question: **on each path, is the raw/verbatim row written BEFORE extraction runs, or is extraction the only thing between user input and the DB?**
  - The CP8 `raw_turn` persist site (`extract_memories()` per the handoff). Confirm it exists in current `master` HEAD `9333c04` and document the exact insert and what columns receive the raw bytes.
  - Any size/length/token branch in any ingress or extraction path (the Q1 threshold candidate). Grep for length checks, token counts, truncation, "summariz", chunk logic. Document each with file:line.
- Output of Step A: an ingress-path map (path → insert site → extraction-vs-persist ordering → any size branch), code-cited.

### Step B — Original reproducer trace (ground truth, may be partial)

- Target: Justin's primary tenant. Resolve the tenant `id` (uuid) via `_db_execute_rows` (`memory_service.tenants` PK is `id`, not `tenant_id`). Do NOT print the live API key; you only need the tenant uuid.
- Pull every `memory_service.memories` row for that tenant with `created_at` in **2026-05-11 13:30–18:30 UTC** (±30 min padding on the documented 14:00–18:00 window).
- For each row inspect `headline`, `context`, `full_content`. Search every `full_content` (and `context`, and any other text column) for distinctive Anthropic Dreaming transcript phrases. Use a generous phrase set, not one string: `Dreaming`, `file system Claude manages`, `optimistic concurrency`, `consolidat`, plus 2–3 more distinctive multi-word phrases you select from a known copy of the transcript if one is on-server; if none is on-server, state that and proceed with the listed phrases.
- Document **per row**: row id, created_at, source/originating-tool field if present, char length of each text column, hit/miss per phrase. Paste the raw matching row(s) (truncated per the 200-char rule). If zero rows in window, state that explicitly with the exact query used.
- Also check related tables for raw storage: any `raw_turn`-typed rows, any `parent_memory_ids` lineage pointing to a raw row, any `source`/`blob`/`artifact`-like table. Follow `parent_memory_ids` from any in-window atom to its claimed raw parent and inspect that parent's columns too.
- **Confound handling:** because of the namespace instability, also run the same window query WITHOUT the tenant filter (all tenants) and scan for the transcript phrases — the bytes may have landed in the wrong namespace. Document if so.
- Step B verdict-input: does verbatim transcript text exist in ANY row for the original reproducer? HIT / MISS / AMBIGUOUS, each backed by pasted rows.

### Step C — Fresh re-ingest (the clean instrument — this drives the verdict)

- Obtain the same ~5000-word Anthropic Dreaming transcript. If a copy exists on-server, use it; otherwise reconstruct an equivalent ~5000-word long-form transcript-class document (state which, and its exact char/word count, in the deliverable). Byte-stable: save the exact input to a file on-server and record its sha256 so later steps can byte-compare against a fixed reference.
- Ingest it through the **MCP `memory_add` direct path** (most controllable, fewest moving parts, no browser/extension confound). Record the exact call, timestamp, tenant, agent namespace used.
- Note for verdict reasoning: testing the MCP-direct path first isolates extraction behavior cleanly. The extension path is a known confound and is tested in Step D only if MCP-direct is HIT (to check path divergence) or if time allows.
- Wait for the extraction pipeline to settle (poll, do not assume; check the rq queue is drained for this job — read-only inspection of queue state, do not touch workers' env).
- Pull every `memory_service.memories` row created in the ingest window for that tenant. Same per-row inspection as Step B. Follow `parent_memory_ids` lineage to any claimed raw/source row and inspect it.
- **Byte check, not gist check:** for any row claimed to contain the verbatim source, extract the candidate verbatim column value to a file and run a byte/sha comparison (or a longest-common-substring measurement) against the saved input reference. Report: exact-match / substring-of-input-but-truncated / paraphrased-not-substring / absent. "Substantially similar" is not a pass — byte-identical or a verbatim substring of the input is the only thing that counts as stored-verbatim.
- Step C verdict-input: the authoritative HIT/MISS, backed by pasted rows AND a byte-comparison result.

### Step D — Shape determination

- **Shape B** if: a row (atom, raw_turn, or related-table row) contains the input as a byte-exact value or a verbatim substring of the input, reachable by `parent_memory_ids` lineage or directly. The bytes exist; the problem is recall. Then additionally: run the five original failing `memory_search` queries (read-only, against the freshly-ingested data), capture top-20 with scores, report where the verbatim-bearing row ranks (or that it never appears). Diagnose which leg (BM25 / vector / RRF combine / downstream filter) buries it. **Do not change the ranker** — diagnose only.
- **Shape A** if: no row anywhere contains the input verbatim or as a substring; only summarized/paraphrased atoms exist. The bytes never landed. Then additionally: from the Step A code map, state exactly where in the path the content was reduced (which function, file:line) and confirm by code reading that no raw persist precedes that reduction on this path.
- **Shape C (capture-gap)** if: Step B finds no transcript bytes for the target tenant AND the all-tenant scan (Step B confound query) finds no transcript bytes anywhere either — i.e. the 5-11 content is absent from the entire DB, not just the user's namespace — WHILE Step C (fresh MCP-direct re-ingest) is a HIT. That combination proves the pipeline preserves content when actually fed, and the original failure was the content never entering the system on that surface, not extraction loss. To strengthen a Shape-C call: from the Step A code map, identify whether the surface used on 5-11 (a chat session with extension claimed-active) has a code path that actually persists to `memory_service.memories`, and check extension/MCP server logs (read-only) in the 5-11 window for a write attempt to a wrong namespace. **A Shape-C verdict requires the all-tenant absence AND a fresh-ingest HIT — never declare Shape A on a single-tenant MISS alone.** If the all-tenant scan finds the bytes under a different namespace, that is itself the Shape-C proof (capture fired, wrong namespace) — document the namespace it landed in.
- **Disambiguation rule (mandatory):** the verdict MUST explicitly state how Shape A and Shape C were distinguished, citing the all-tenant scan result and the fresh-ingest result. A verdict that says "Shape A" without addressing why it is not Shape C is rejected.
- **Path-divergence finding:** if Step B (original) and Step C (fresh) disagree, that disagreement is itself a primary finding — document it as evidence the behavior is path- or time-dependent (feeds Q1).

### Step E — Threshold curve (Q1)

- Through the same MCP-direct path, ingest synthetic long-form documents at **500 / 1000 / 2000 / 5000 / 10000 chars** (transcript/prose class, not code/lists — content type may matter; note it).
- Per size, after settle: input chars → output atom count → total output chars across atoms → presence of a verbatim ≥50-char N-gram from the input in any stored row (yes/no) → presence of a full verbatim row (yes/no).
- Present as a table. This empirically locates the threshold and its type (fixed char count vs model heuristic vs content-type rule). Cite the code branch from Step A that explains the curve if one exists.

### Step F — Q3 / Q4

- **Q3 (min-invasive fix per shape):** state the candidate fix that matches the diagnosed shape, referencing the three options in `SCOPE-EXTRACTION-AUDIT.md` (Fix 1 store-the-source / Fix 2 better extraction / Fix 3 recall tune). Recommend one with rationale. Do NOT design or estimate the build — name the fix class and why, one paragraph. Reconcile explicitly with `CHECKPOINT-ARTIFACT-VAULT-SCOPE.md` (does Fix 1 == Artifact Vault V0 text-only?) and `CHECKPOINT-9-SCOPE.md` (its `zerolatency verify <id>` / verbatim-page references a source-retrieval surface — flag overlap, do not build).
- **Q4 (cost delta):** 3×3 table (Fix 1/2/3 × storage / extraction-model / recall-latency). Use measured numbers where the audit produced them (e.g. storage from observed atom sizes vs raw size at p50/p99 paste); clearly mark any cell that is an estimate vs measured. No new benchmark runs to fill this — estimate-and-mark is acceptable for cells the audit didn't measure.

---

## DELIVERABLE

Single file on-server: `/root/.openclaw/workspace/memory-product/docs/VERBATIM-PHASE0-AUDIT-FINDINGS.md`, also `cat` the full contents back into the CC session output so it is captured in the transcript. Sections:

1. **Ingress-path map** (Step A, code-cited file:line)
2. **Original reproducer trace** (Step B, raw rows pasted, confound noted)
3. **Fresh re-ingest trace** (Step C, raw rows pasted + byte-comparison result + input sha256)
4. **VERDICT: Shape A, Shape B, or Shape C (capture-gap)** — one bolded sentence, then the evidence chain, then a mandatory sub-paragraph stating how A vs C was disambiguated (all-tenant scan result + fresh-ingest result, both cited with pasted rows/queries). If AMBIGUOUS, say so and state exactly what additional measurement would disambiguate. Do not force a verdict the rows don't support. The 5-11 diagnostic memory is the hypothesis under test, never cited as evidence.
5. **Recall diagnosis** (Step D, only if Shape B) OR **reduction-site code citation** (only if Shape A)
6. **Threshold curve table** (Step E, Q1)
7. **Q3 recommended fix class + Vault/CP9 reconciliation** (one paragraph, no build design)
8. **Q4 cost table** (3×3, cells marked measured/estimate)
9. **Decision-ready paragraph:** "Justin should do X next, here's why" — names the next phase scope size (recall-path days vs Artifact Vault weeks) grounded in the verdict.

**Receipts standard:** every factual claim about DB state = a pasted raw row. Every code claim = file:line. Every "it fired"/"it didn't" = the row or the absence query that proves it. No agent self-report accepted as evidence anywhere in the document. If a step cannot be completed (logs rotated, transcript copy unavailable), say so explicitly and state the impact on verdict confidence — a partial honest verdict beats a confident guess.

---

## OPERATIONAL CONSTRAINTS CARRIED INTO CC

- `_db_execute_rows`, never legacy stringify+split.
- `python3`, never `python`.
- Read-only DB inspection except the deliberate Step C/E ingests via the normal `memory_add` path. No direct SQL writes, no migrations, no `db_migrate.sh`.
- `memory_service.tenants` PK = `id` (uuid). `memory_service.memories` text columns: `headline`, `context` (NOT NULL), `full_content` (NOT NULL); no single `content` column.
- Never print the API key, `.env`, or any credential in session output. Tenant uuid only.
- Do not touch rq workers' environment, systemd, or `.env`. Queue state inspection is read-only.
- Branch: `master`, HEAD `9333c04`. Do not commit anything — this audit produces a doc, not a code change. The findings doc may be added but no source/migration changes.
