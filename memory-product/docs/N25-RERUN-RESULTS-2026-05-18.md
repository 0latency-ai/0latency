# N25 RERUN RESULTS — 2026-05-18

> **PHANTOM-COMMIT WARNING.** This document anchors to commits `2e544f4` (workspace) and `9333c04` (the code the API served). Both were discarded on
> 2026-05-22 by a `reset: moving to origin/master` on the workspace box: the commits
> were local-only, never pushed, and the reset moved HEAD onto `e50694d` from
> another machine. They are reachable by hash but contained by no branch, so the
> code this document describes was never in `master`.
> This document survived only because it was untracked, and `git reset` does not
> touch untracked files.
>
> **Therefore unverified:** this run measured a tree that is not `master`, so its own measured numbers — including
> the 10/25 (40%) accuracy result and the pre-flight certification that "code is at
> expected HEAD" — do not describe `master`. The prior banked 76%@20 / MRR 0.5366 it
> compares against is attributed to `0ceb578`, which IS in `master`. The run is also
> self-declared "COMPLETED WITH DEGRADED SCORING", which is a separate caveat from this
> one.
>
> The body below is preserved verbatim and has not been corrected. See
> `docs/RECENCY-WEIGHTING-ANALYSIS.md` §7 for the full reconstruction.

**Run type:** Measurement (no code changes, no re-ingestion, no fixes)
**Status:** COMPLETED WITH DEGRADED SCORING — see Findings below

---

## 1. Pre-Flight Summary Block

| # | Check | Resolved Value | Status |
|---|-------|----------------|--------|
| 1 | Service live | `zerolatency-api` PID 2020860, port 8420, 1 worker, uptime 4h+ (started 04:50:29 UTC) | PASS |
| 2 | Code at expected HEAD | Workspace: `2e544f4`. Process started after `9333c04` (04:37:32). Only diff `9333c04`→`2e544f4` = `benchmarks/longmemeval/run_benchmark.py` — API code identical | PASS |
| 3 | RECENCY_CLAMP_ENABLED | Not in process env or `.env` → defaults to `true` per `recall.py:36` | PASS (ON) |
| 4 | Tenant name | `longmemeval-benchmark-20260510` (UUID `382faaf1-5cbf-49a1-b689-5ffef8918d10`) | PASS |
| 5 | Queue state | extraction: 0 queued, 0 WIP, 5 failed (stale), 0 deferred. RQ worker PID 2009471 alive | PASS |
| 6 | Disk health | 41% used (20G/48G) | PASS |
| 7 | Corpus row count | **15,401 active / 16,500 total** (Gate07 banked had 10,067 — growth from Q21/Q22 validation runs) | NOTED |
| 8 | Extraction model | `claude-haiku-4-5-20251001` (from `/proc/2020860/environ`) | PASS |
| 9 | Scorer | Requested: `llm` (Claude Sonnet judge). **ACTUAL: substring fallback** — Anthropic API key exhausted (resets 2026-06-01) | **DEGRADED** |
| 10 | Cost cap | `--max-cost 3` confirmed supported per runner `--help` | PASS |
| 11 | Shell env | `set -a && source .env && set +a` executed at 08:55:15 UTC in same shell as runner invocation | PASS |

### First-Class Provenance Fields

| Field | Value |
|-------|-------|
| **Extraction model** | `claude-haiku-4-5-20251001` |
| **Corpus/tenant row count** | 15,401 active memories |
| **Scorer** | `llm` (requested) → **substring fallback** (actual — all 25 questions) |
| **Commit SHA** | `2e544f4` (workspace); API serves `9333c04` code (identical for API paths) |
| **Run date** | 2026-05-18 08:55:17 UTC |

---

## 2. Runner Invocation

```
python3 run_benchmark.py stratified_25.json -n 25 -s 0 --scorer llm --max-cost 3 --confirm-cost -o n25-rerun-2026-05-18.json
```

**`-s 0` (max-sessions=0) rationale:** `run_benchmark.py` always extracts haystack sessions before recalling. Extraction of 6,175 turns at Haiku pricing estimates $12.47, exceeding the mandatory $3 cap. The scope says "No re-ingestion. The corpus is correct and frozen." Setting `-s 0` skips extraction and runs recall-only against the existing 15,401 memories, staying under budget ($0.55 combined estimate) and aligned with the no-re-ingestion rule.

**Scorer mismatch vs bank:** The banked 76%@20 (Gate07, commit `95e8b89`) was produced by `run_q3_async.py` with a multi-strategy fuzzy matcher (5 strategies: exact substring, token overlap, numeric pattern, proper noun, bidirectional overlap + full_content fallback). This run used `run_benchmark.py --scorer llm`, which due to API key exhaustion fell back to simple `expected.lower() in context.lower()` substring matching. The scoring instruments are fundamentally different. Numbers are **not directly comparable** to the banked 76%.

---

## 3. Raw Runner Output (verbatim)

```
Shell env sourced in same shell: Mon May 18 08:55:15 UTC 2026
EXTRACTION_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY present: yes

Launching runner: run_benchmark.py stratified_25.json -n 25 -s 0 --scorer llm --max-cost 3 --confirm-cost -o n25-rerun-2026-05-18.json

Loaded 25 questions from stratified_25.json

  COST PRE-FLIGHT ESTIMATE
  Model: claude-haiku-4-5-20251001
  Pricing: $0.80/1M input, $4.00/1M output
  Turns: 0  Questions: 25
  Est. input tokens:       200,000
  Est. output tokens:            0
  ---
  PROJECTED COST:      $    0.1600
  BUDGET (--max-cost): $      3.00
  PASS: $2.84 headroom remaining
  + LLM Judge (Sonnet): ~$0.3911 (25 questions)
  COMBINED ESTIMATE:    $0.5511

Running LongMemEval benchmark (n=25)...
Tenant: 382faaf1-5cbf-49a1-b689-5ffef8918d10
API: https://api.0latency.ai
Max sessions per question: all
Max zero streak: 10
Concurrency: 8 workers

[1/25] 6a1eabeb — Match: False — Latency: 2490ms — Wall: 2.5s
[2/25] 6aeb4375 — Match: True — Latency: 476ms — Wall: 0.5s
[3/25] 830ce83f — Match: True — Latency: 519ms — Wall: 0.5s
[4/25] 852ce960 — Match: True — Latency: 504ms — Wall: 0.5s
[5/25] 0a995998 — Match: True — Latency: 483ms — Wall: 0.5s
[6/25] 6d550036 — Match: True — Latency: 660ms — Wall: 0.7s
[7/25] gpt4_59c — Match: False — Latency: 671ms — Wall: 0.7s
[8/25] b5ef892d — Match: False — Latency: 1105ms — Wall: 1.1s
[9/25] 7161e7e2 — Match: False — Latency: 1132ms — Wall: 1.1s
[10/25] c4f10528 — Match: False — Latency: 1271ms — Wall: 1.3s
[11/25] 89527b6b — Match: False — Latency: 9372ms — Wall: 9.4s
[12/25] e9327a54 — Match: False — Latency: 812ms — Wall: 0.8s
[13/25] 8a2466db — Match: False — Latency: 407ms — Wall: 0.4s
[14/25] 06878be2 — Match: False — Latency: 409ms — Wall: 0.4s
[15/25] 75832dbd — Match: False — Latency: 425ms — Wall: 0.4s
[16/25] 0edc2aef — Match: False — Latency: 541ms — Wall: 0.5s
[17/25] e47becba — Match: True — Latency: 353ms — Wall: 0.4s
[18/25] 118b2229 — Match: False — Latency: 391ms — Wall: 0.4s
[19/25] 51a45a95 — Match: True — Latency: 349ms — Wall: 0.4s
[20/25] 58bf7951 — Match: True — Latency: 543ms — Wall: 0.5s
[21/25] gpt4_591 — Match: False — Latency: 584ms — Wall: 0.6s
[22/25] gpt4_f49 — Match: False — Latency: 432ms — Wall: 0.4s
[23/25] 71017276 — Match: True — Latency: 403ms — Wall: 0.4s
[24/25] b46e15ed — Match: True — Latency: 474ms — Wall: 0.5s
[25/25] e831120c — Match: False — Latency: 495ms — Wall: 0.5s

ALL 25 questions: WARN LLM judge failed (API usage limit reached, resets 2026-06-01), fell back to substring.

=== SUMMARY ===
Accuracy: 40.0% (10/25)
p50 latency: 504ms
p95 latency: 2490ms
Cost: $0.0000 / $3.00
```

Results JSON: `benchmarks/longmemeval/runs/n25-rerun-2026-05-18.json`

---

## 4. Standard Metric Set

**Note:** `run_benchmark.py` produces accuracy (match/no-match) per question. It does NOT compute rank-based metrics (Recall@k, MRR, precision) because it does not track at which rank the answer-bearing memory appears. The banked 76%@20 metrics were produced by `run_q3_async.py` which tracks per-memory ranks. Therefore, a full Recall@k / MRR / precision table cannot be produced from this instrument.

| Metric | This Run (substring fallback) | Banked Gate07 (fuzzy matcher) | Comparable? |
|--------|-------------------------------|-------------------------------|-------------|
| Accuracy (match) | 10/25 (40%) | 19/25 (76%@20) | **NO** — different scorer |
| p50 recall latency | 504ms | N/A (not tracked by Gate07) | — |
| p95 recall latency | 2490ms | N/A | — |
| Recall@1 | N/A | 12/25 (48%) | Not produced by this instrument |
| Recall@5 | N/A | 15/25 (60%) | Not produced by this instrument |
| Recall@10 | N/A | 16/25 (64%) | Not produced by this instrument |
| Recall@20 | N/A | 19/25 (76%) | Not produced by this instrument |
| Recall@50 | N/A | 19/25 (76%) | Not produced by this instrument |
| MRR | N/A | 0.5366 | Not produced by this instrument |
| Precision | N/A | 0.9851 | Not produced by this instrument |

---

## 5. Cross-Check

### Per-Question Comparison (Gate07 fuzzy matcher vs this run substring fallback)

| Q | ID | Type | Gate07 (R@20) | This Run | Movement | Notes |
|---|-----|------|---------------|----------|----------|-------|
| 1 | 6a1eabeb | knowledge-update | FOUND (R4) | FALSE | ↓ | Long expected answer: "25 minutes and 50 seconds (or 25:50)" — substring not found verbatim |
| 2 | 6aeb4375 | knowledge-update | FOUND (R1) | TRUE | = | Expected "four" — short word, plausible true positive |
| 3 | 830ce83f | knowledge-update | FOUND (R1) | TRUE | = | Expected "the suburbs" — plausible true positive |
| 4 | 852ce960 | knowledge-update | FOUND (R1) | TRUE | = | Expected "$400,000" — specific, likely true positive |
| 5 | 0a995998 | multi-session | FOUND (R1) | TRUE | = | Expected = integer `3`. **Likely false positive** — single digit in 17k chars |
| 6 | 6d550036 | multi-session | FOUND (R2) | TRUE | = | Expected = integer `2`. **Likely false positive** — single digit in 17k chars |
| 7 | gpt4_59c | multi-session | FOUND (R1) | FALSE | ↓ | Long expected text about model kits — substring won't match verbatim |
| 8 | b5ef892d | multi-session | FOUND (R15) | FALSE | ↓ | Expected "8 days." |
| 9 | 7161e7e2 | ss-assistant | FOUND (R1) | FALSE | ↓ | Long expected text about shift rotation |
| 10 | c4f10528 | ss-assistant | NOT_FOUND | FALSE | = | |
| 11 | 89527b6b | ss-assistant | FOUND (R1) | FALSE | ↓ | Long expected text about Plesiosaur color |
| 12 | e9327a54 | ss-assistant | FOUND (R1) | FALSE | ↓ | Expected "The Sugar Factory at Icon Park." |
| 13 | 8a2466db | ss-preference | FOUND (R1) | FALSE | ↓ | Long preference text about Adobe Premiere |
| 14 | 06878be2 | ss-preference | FOUND (R20) | FALSE | ↓ | Long preference text about Sony accessories |
| 15 | 75832dbd | ss-preference | NOT_FOUND | FALSE | = | |
| 16 | 0edc2aef | ss-preference | NOT_FOUND | FALSE | = | |
| 17 | e47becba | ss-user | FOUND (R1) | TRUE | = | Expected "Business Administration" — plausible true positive |
| 18 | 118b2229 | ss-user | FOUND (R7) | FALSE | ↓ | Expected "45 minutes each way" |
| 19 | 51a45a95 | ss-user | FOUND (R1) | TRUE | = | Expected "Target" — plausible true positive |
| 20 | 58bf7951 | ss-user | FOUND (R18) | TRUE | = | Expected "The Glass Menagerie" — plausible true positive |
| 21 | gpt4_591 | temporal | NOT_FOUND | FALSE | = | |
| 22 | gpt4_f49 | temporal | NOT_FOUND | FALSE | = | |
| 23 | 71017276 | temporal | FOUND (R1) | TRUE | = | Expected = integer `4`. **Likely false positive** — single digit in 13k chars |
| 24 | b46e15ed | temporal | FOUND (R3) | TRUE | = | Expected = integer `2`. **Likely false positive** — single digit in 17k chars |
| 25 | e831120c | multi-session | NOT_FOUND | FALSE | = | |

### Cross-Check Assessment

The 40% number is **not informative** for comparison against the banked 76% because:

1. **Scorer mismatch**: Substring fallback (`expected.lower() in context.lower()`) is fundamentally different from both the LLM judge and the Gate07 fuzzy matcher. It produces false negatives on long expected texts (sentences/paragraphs won't match verbatim) and false positives on short/numeric answers (single digits match trivially in large context blocks).
2. **Suspected false positives**: At least 4 of the 10 matches (Q5, Q6, Q23, Q24) have single-digit integer expected values that would match anywhere in 13-17k chars of context.
3. **Suspected false negatives**: At least 8 questions that Gate07 found (Q1, Q7, Q8, Q9, Q11, Q12, Q13, Q14) show FALSE here because their long expected texts don't appear verbatim in context — the fuzzy matcher would likely find them.
4. **No confirmatory re-run was performed** — a re-run with the same broken scorer would produce the same uninformative result.

---

## 6. Tripwire Verdict

**TRIPWIRE EVALUATION REMOVED** per task instructions (measurement-only run, no HALT on threshold).

However, the 40% number **cannot be meaningfully compared** to the banked 76% because the scoring instruments are different (substring fallback vs fuzzy matcher). No tripwire conclusion can be drawn from this data.

---

## 7. Recommendation

**This run does not produce a valid measurement.** Three compounding issues prevent it:

1. **Anthropic API key exhausted** (resets 2026-06-01): The LLM judge (`--scorer llm`) failed for all 25 questions, falling back to simple substring matching. This is the most severe issue — the requested scorer did not execute.

2. **Extraction cost exceeds cap**: `run_benchmark.py` requires extraction of 6,175 turns ($12.47 estimated) before recall, but the mandatory $3 cap correctly blocks this. Extraction was skipped via `-s 0` to stay under cap, running recall-only against 15,401 existing memories.

3. **Instrument mismatch**: `run_benchmark.py` produces binary accuracy (match/no-match), not rank-based metrics (Recall@k, MRR, precision). The banked 76% was produced by `run_q3_async.py` which tracks per-memory rank position. The standard metric set (Recall@1/@5/@10/@20/@50 + MRR + precision) cannot be produced by this instrument.

### Path Forward

To produce a valid comparable measurement:
- **Wait for API key reset** (2026-06-01) to enable the LLM judge, OR use a different funded Anthropic key.
- **Use `run_q3_async.py --recall-only --skip-wipe`** for rank-based metrics comparable to the banked Gate07 results.
- **The $3 cap is sufficient for recall-only + LLM scoring** (\~$0.55 estimated). It is NOT sufficient for full extraction+recall (\~$12.47).

---

## 8. Bugs Observed But NOT Fixed

1. **Anthropic API key usage limit reached** — All LLM-model API calls fail with "You have reached your specified API usage limits. You will regain access on 2026-06-01." This affects the LLM judge scorer, extraction (if attempted via Haiku), and temporal reasoning. **Not fixed** per scope (no key/.env changes).

2. **`zerolatency-worker.service` in failed state** — Systemd-managed worker crashed/failed \~12h ago. A manually-started RQ worker (PID 2009471) is running on the extraction queue. **Not fixed** per scope (no systemd changes).

3. **Corpus drift**: Benchmark tenant has 15,401 active memories vs 10,067 at Gate07 banked run. Growth from Q21/Q22 validation ingestions. **Not fixed** per scope (no re-ingestion, no purge).
