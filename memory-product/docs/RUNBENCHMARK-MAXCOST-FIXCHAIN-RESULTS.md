# RUNBENCHMARK-MAXCOST-FIXCHAIN-RESULTS

> **PHANTOM-COMMIT WARNING.** This document anchors to commits `2e544f4` and `f893c18`. Both were discarded on
> 2026-05-22 by a `reset: moving to origin/master` on the workspace box: the commits
> were local-only, never pushed, and the reset moved HEAD onto `e50694d` from
> another machine. They are reachable by hash but contained by no branch, so the
> code this document describes was never in `master`.
> This document survived only because it was untracked, and `git reset` does not
> touch untracked files.
>
> **Therefore unverified:** the `--max-cost` kill-switch this document reports as delivered is **not in `master`**,
> and neither is the `cost_killswitch.py` module it depends on. `benchmarks/longmemeval/`
> in `master` has no runtime spend ceiling; `run_benchmark.py` has only an advisory
> `estimate_cost()` and a pre-flight `--confirm-cost` gate, neither of which can abort a
> run in progress. Given the $400+/$603 unbraked-spend incident this chain was written to
> prevent, treat that protection as absent until the commits are recovered.
>
> The body below is preserved verbatim and has not been corrected. See
> `docs/RECENCY-WEIGHTING-ANALYSIS.md` §7 for the full reconstruction.

**Chain:** CP-RUNBENCHMARK-MAXCOST-FIXCHAIN-SCOPE.md  
**Executed:** 2026-05-18  
**Commit:** `2e544f4` on `master`  
**Pattern source:** `f893c18` (run_q3_async.py 2-hook cost_killswitch integration)  
**origin/master:** `0ceb578` — untouched  

---

## 1. Resolved Chokepoint Line Numbers + Hook Set + Non-Bypassability

**Chokepoints (patched line numbers):**

| Hook | Location | Patched Lines | Cost Stream |
|------|----------|---------------|-------------|
| Hook A | `run()` after `load_dataset()` | 443–489 | Pre-flight gate (extraction + recall + judge estimate) |
| Hook B1 | `submit_extraction_job()` top | 161–167 | Extraction (Haiku) — estimated tokens before API POST |
| Hook B2 guard | `llm_judge()` before API call | 377–379 | Judge (Sonnet) — abort check before Anthropic call |
| Hook B2 accum | `llm_judge()` after API call | 390–394 | Judge (Sonnet) — actual tokens, price-ratio scaled |
| Abort check | `run()` question loop end | 563–587 | Clean shutdown with partial results + exit(5) |
| Summary | `run()` after metrics | 644–645 | stderr print only |

**Why non-bypassable:**

1. Every extraction API call enters through `submit_extraction_job` (single chokepoint). All `ThreadPoolExecutor` threads in `extract_sessions` call `extract_single_session` which calls only `submit_extraction_job`. Hook B1 gates every call.
2. Every judge API call enters through `llm_judge` (single chokepoint). The only call site is `run()` line 456. Hook B2 guard + accumulation gates every call.
3. Both streams feed the same `CostAccumulator` instance. Judge tokens are price-ratio scaled (Sonnet/Haiku = 3.75x for default config) so the accumulator's cost calculation accurately represents combined USD spend across both models.
4. The question loop is sequential. After each question's extraction + recall + judge, the abort check runs. A breached budget during multi-threaded extraction sets `accumulator.aborted = True`, which blocks all subsequent `submit_extraction_job` calls (threads see the flag immediately) and all subsequent `llm_judge` calls.

---

## 2. Full Git Diff (verbatim)

```diff
diff --git a/memory-product/benchmarks/longmemeval/run_benchmark.py b/memory-product/benchmarks/longmemeval/run_benchmark.py
index bbddc1e..70e1a5d 100755
--- a/memory-product/benchmarks/longmemeval/run_benchmark.py
+++ b/memory-product/benchmarks/longmemeval/run_benchmark.py
@@ -25,6 +25,12 @@ from datetime import datetime
 from concurrent.futures import ThreadPoolExecutor, as_completed
 import anthropic
 
+from cost_killswitch import (
+    preflight_estimate, CostAccumulator,
+    estimate_tokens_from_content, ESTIMATED_OUTPUT_TOKENS_PER_EXTRACTION,
+    get_prices,
+)
+
 # Load benchmark credentials
 env_file = Path(__file__).parent / ".env.benchmark"
 if not env_file.exists():
@@ -67,7 +73,7 @@ if not ANTHROPIC_API_KEY:
 class LongMemEvalRunner:
     def __init__(self, dataset_path: str, max_questions: int = 5, max_sessions: int = None,
                  smoke_mode: bool = False, max_zero_streak: int = 10, confirm_cost: bool = False,
-                 scorer: str = "substring", max_workers: int = 8):
+                 scorer: str = "substring", max_workers: int = 8, max_cost: float = 20.0):
         self.dataset_path = Path(dataset_path)
         self.max_questions = max_questions
         self.max_sessions = max_sessions
@@ -87,6 +93,10 @@ class LongMemEvalRunner:
         self.zero_streak = 0
         self.dataset_total_count = 0
         self.consecutive_failures = 0
+        self.accumulator = None
+        self.max_cost = max_cost
+        self._judge_input_ratio = 1.0
+        self._judge_output_ratio = 1.0
         
         if self.scorer == "llm":
             if not ANTHROPIC_API_KEY:
@@ -148,6 +158,14 @@ class LongMemEvalRunner:
     
     def submit_extraction_job(self, payload: Dict) -> Tuple[str, str, int]:
         """Submit single extraction job to async endpoint. Returns (job_id, error, status_code)."""
+        # COST KILL-SWITCH: Hook B1 - accumulate + check before extraction submission
+        if self.accumulator:
+            if self.accumulator.aborted:
+                return None, "cost_abort", 0
+            est_input = estimate_tokens_from_content(payload.get("content", ""))
+            if self.accumulator.add(est_input, ESTIMATED_OUTPUT_TOKENS_PER_EXTRACTION):
+                return None, "cost_abort", 0
+
         max_retries = 1  # Only 1 retry at benchmark layer (workers retry 3x internally)
         
         for attempt in range(max_retries + 1):
@@ -356,6 +374,10 @@ Recalled context:
 Does the recalled context contain information that correctly answers the question with the expected answer (verbatim, paraphrased, or clearly inferable)?
 Reply with ONLY "YES" or "NO"."""
 
+        # COST KILL-SWITCH: Hook B2 - check abort before judge API call
+        if self.accumulator and self.accumulator.aborted:
+            return expected.lower() in context.lower()
+
         try:
             response = self.anthropic_client.messages.create(
                 model="claude-sonnet-4-5-20250929",
@@ -365,6 +387,11 @@ Reply with ONLY "YES" or "NO"."""
             )
             verdict = response.content[0].text.strip().upper()
             self.total_judge_tokens += response.usage.input_tokens + response.usage.output_tokens
+            # COST KILL-SWITCH: Hook B2 - accumulate actual judge tokens (price-ratio scaled)
+            if self.accumulator:
+                scaled_input = int(response.usage.input_tokens * self._judge_input_ratio)
+                scaled_output = int(response.usage.output_tokens * self._judge_output_ratio)
+                self.accumulator.add(scaled_input, scaled_output)
             return verdict == "YES"
         except Exception as e:
             print(f"WARN: LLM judge failed ({e}), falling back to substring", file=sys.stderr)
@@ -413,7 +440,50 @@ Reply with ONLY "YES" or "NO"."""
         """Run benchmark and save results."""
         questions = self.load_dataset()
         total_in_dataset = self.dataset_total_count
-        
+
+        # COST KILL-SWITCH: Pre-flight gate (Hook A)
+        _extraction_model = os.getenv("EXTRACTION_MODEL", "claude-haiku-4-5-20251001")
+        all_turns_for_estimate = []
+        for q in questions:
+            sessions = q.get("haystack_sessions", [])
+            if self.max_sessions is not None:
+                sessions = sessions[:self.max_sessions]
+            for session in sessions:
+                idx = 0
+                while idx < len(session) - 1:
+                    if session[idx].get("role") == "user" and session[idx + 1].get("role") == "assistant":
+                        content = f"Human: {session[idx]['content']}\n\nAssistant: {session[idx + 1]['content']}"
+                        all_turns_for_estimate.append({"content": content})
+                        idx += 2
+                    else:
+                        idx += 1
+        preflight_report = preflight_estimate(
+            turns=all_turns_for_estimate,
+            num_questions=len(questions),
+            model=_extraction_model,
+            enable_reasoning=False,
+            max_cost=self.max_cost,
+        )
+        self.accumulator = CostAccumulator(max_cost=self.max_cost, model=_extraction_model)
+        # Price-ratio for judge stream: scale Sonnet tokens to extraction-model-equivalent
+        _ext_prices = get_prices(_extraction_model)
+        _judge_prices = get_prices("claude-sonnet-4-5-20250929")
+        self._judge_input_ratio = _judge_prices["input"] / _ext_prices["input"] if _ext_prices["input"] > 0 else 1.0
+        self._judge_output_ratio = _judge_prices["output"] / _ext_prices["output"] if _ext_prices["output"] > 0 else 1.0
+        if self.scorer == "llm":
+            est_judge_input_per_q = 5200
+            est_judge_output_per_q = 3
+            judge_cost_est = (
+                est_judge_input_per_q * len(questions) * _judge_prices["input"] / 1_000_000 +
+                est_judge_output_per_q * len(questions) * _judge_prices["output"] / 1_000_000
+            )
+            combined_est = preflight_report["estimated_cost_usd"] + judge_cost_est
+            print(f"  + LLM Judge (Sonnet): ~${judge_cost_est:.4f} ({len(questions)} questions)")
+            print(f"  COMBINED ESTIMATE:    ${combined_est:.4f}")
+            if combined_est > self.max_cost:
+                print(f"  HALT: Combined estimate exceeds --max-cost ${self.max_cost:.2f}")
+                sys.exit(5)
+
         timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
         if output_path is None:
             prefix = "smoke" if self.smoke_mode else "run"
@@ -490,7 +560,31 @@ Reply with ONLY "YES" or "NO"."""
                 self.zero_streak = 0
             
             print("", file=sys.stderr)
-        
+
+            # COST KILL-SWITCH: clean abort check after each question
+            if self.accumulator and self.accumulator.aborted:
+                print(f"\n  COST ABORT: {self.accumulator.abort_reason}", file=sys.stderr)
+                print(f"  Writing partial results...", file=sys.stderr)
+                if output_path:
+                    partial_data = {
+                        "metadata": {
+                            "timestamp": timestamp,
+                            "sample_size": len(questions),
+                            "completed_questions": i,
+                            "halted_reason": "cost_abort",
+                            "cost_summary": self.accumulator.summary(),
+                            "scorer": self.scorer,
+                        },
+                        "results": results,
+                    }
+                    output_file = Path(__file__).parent / "runs" / output_path
+                    output_file.parent.mkdir(exist_ok=True)
+                    with open(output_file, "w") as f:
+                        json.dump(partial_data, f, indent=2)
+                    print(f"  Partial results written to: {output_file}", file=sys.stderr)
+                print(f"  {self.accumulator.summary()}", file=sys.stderr)
+                sys.exit(5)
+
         # Smoke test final validation
         if self.smoke_mode:
             matches = sum(r["match"] for r in results)
@@ -547,6 +641,8 @@ Reply with ONLY "YES" or "NO"."""
         print(f"\n=== SUMMARY ===", file=sys.stderr)
         print(f"Accuracy: {accuracy:.1f}% ({sum(r['match'] for r in results)}/{len(results)})", file=sys.stderr)
         print(f"p50 latency: {output_data['aggregate']['p50_recall_latency_ms']}ms", file=sys.stderr)
+        if self.accumulator:
+            print(f"  {self.accumulator.summary()}", file=sys.stderr)
         print(f"p95 latency: {output_data['aggregate']['p95_recall_latency_ms']}ms", file=sys.stderr)
         
         return output_data
@@ -565,6 +661,8 @@ if __name__ == "__main__":
     parser.add_argument("--scorer", choices=["substring", "llm"], default="substring",
                         help="Scoring method: substring (exact match) or llm (Claude Sonnet judge)")
     parser.add_argument("--max-workers", type=int, default=8, help="Max concurrent sessions for extraction")
+    parser.add_argument("--max-cost", type=float, default=20.0,
+                        help="Hard cost ceiling in USD (default: $20)")
     
     args = parser.parse_args()
     
@@ -582,7 +680,8 @@ if __name__ == "__main__":
         max_zero_streak=args.max_zero_streak,
         confirm_cost=args.confirm_cost,
         scorer=args.scorer,
-        max_workers=args.max_workers
+        max_workers=args.max_workers,
+        max_cost=args.max_cost
     )
     
     runner.run(output_path=args.output)
```

**Diff stats:** 1 file changed, 103 insertions(+), 4 deletions(-)

---

## 3. Non-Contamination Proof

**Static diff confirmation:** The diff touches ONLY `benchmarks/longmemeval/run_benchmark.py`. Zero edits to any scoring/recall/prompt/judge-logic/extraction/payload/corpus/migration/.env/systemd file.

**Bit-identical argument (non-tripped path):**

On the non-tripped path (accumulator.aborted remains False throughout):

1. **Hook B1 (submit_extraction_job, lines 161–167):** `aborted` is False → skip first early return. `accumulator.add()` returns False → skip second early return. Falls through to original retry loop. `est_input` and `accumulator.add()` write only to the accumulator's internal `_input_tokens`/`_output_tokens` counters. They do not read/write `payload`, `self.headers`, `API_BASE_URL`, or any HTTP request variable. The POST body/headers/URL/retry logic are identical.

2. **Hook B2 guard (llm_judge, lines 377–379):** Condition is False → falls through to existing `try:` block. The Anthropic `messages.create()` call receives identical `model`, `max_tokens`, `temperature`, `messages`, prompt string. No parameter touched.

3. **Hook B2 accumulation (llm_judge, lines 390–394):** Executes AFTER `verdict = response.content[0].text.strip().upper()` and AFTER `self.total_judge_tokens += ...`, BEFORE `return verdict == "YES"`. Reads `response.usage` (token counts), writes only to `self.accumulator`. Does not read/write `verdict`, `response.content`, `prompt`, `context`, `question`, `expected`. The `return verdict == "YES"` evaluates the identical verdict string.

4. **Hook A (run(), lines 443–489):** Executes between `total_in_dataset = self.dataset_total_count` and `timestamp = datetime.now().strftime(...)`. Creates new local variables (`all_turns_for_estimate`, `preflight_report`, `_ext_prices`, `_judge_prices`) and new instance attributes (`self.accumulator`, `self.max_cost`, `self._judge_input_ratio`, `self._judge_output_ratio`). None shadow or overwrite existing variables. No variable used by the benchmark loop (`questions`, `total_in_dataset`, `self.scorer`, `self.headers`, `self.anthropic_client`, `self.max_sessions`, `self.max_workers`) is modified.

5. **Abort check (run(), lines 563–587):** `accumulator.aborted` is False → entire block skipped.

6. **Cost summary (run(), lines 644–645):** Prints to stderr only, after all results computed and written. Does not alter `output_data`, `results`, `accuracy`, or saved metrics. JSON output file identical.

7. **__init__ (lines 76, 96–99):** New parameter `max_cost` (default 20.0) and 4 new attributes. Do not shadow existing attributes.

8. **Argparse (lines 664–665, 683–684):** New `--max-cost` arg (default 20.0). No existing arg modified.

**Conclusion:** On the non-tripped path, every new `if` evaluates False and falls through. The only executed side effects are `accumulator.add()` writing to internal counters and `print()` to stderr. Neither reads from nor writes to any variable in prompt construction, payload assembly, API parameters, verdict evaluation, recall, or result aggregation. **Bit-identical to pre-change.**

---

## 4. Trip-Test Results

### Mode (a): Pre-flight refusal

```
$ python3 run_benchmark.py smoke_q3.json -n 1 --max-cost 0.001 --scorer llm

Loading first 1 questions with jq (memory-efficient)... OK
Loaded 1/1 questions from smoke_q3.json

  COST PRE-FLIGHT ESTIMATE
  Model: claude-haiku-4-5-20251001
  Pricing: $0.80/1M input, $4.00/1M output
  Turns: 6  Questions: 1
  Est. input tokens:        12,555
  Est. output tokens:        2,400
  ---
  PROJECTED COST:      $    0.0196
  BUDGET (--max-cost): $      0.00
  HALT: Projected cost exceeds budget. Refusing to start.
  Increase --max-cost or reduce dataset size.
EXIT_CODE=5
```

**Result:** Hard exit code 5. Zero API calls made. Projected $0.0196 > budget $0.001.

### Mode (b): Runtime abort — MOCK (explicitly labeled)

**Why a natural sub-$0.50 trip is not constructible:** The pre-flight estimate includes recall tokens (`num_questions * 8000 * input_price`) that the runtime accumulator does NOT track (recall uses a separate API path). This makes the pre-flight total a strict superset of the runtime accumulator's achievable total for extraction costs. For --scorer llm, the supplementary judge estimate covers the judge stream. Any --max-cost that passes the combined pre-flight provides enough headroom that the runtime accumulator (extraction + actual judge) stays under for small datasets. A natural trip requires actual judge tokens to exceed the estimate by more than the recall padding — data-dependent and not reliably constructible.

**Mock test (exercises actual run_benchmark.py code paths with pre-loaded accumulator):**

```
============================================================
MOCK TRIP-TEST: Runtime abort (mode b)
============================================================

--- TEST 1: submit_extraction_job abort on accumulator breach ---
  Accumulator pre-loaded: $0.008800 / $0.01
  Aborted before submit: False
  submit_extraction_job returned: job_id=None, error=cost_abort, status_code=0
  Accumulator after submit: $0.010412 / $0.01
  Aborted: True
  Abort reason: Cumulative cost $0.0104 exceeded --max-cost $0.01 (in=9,015 out=800)
  PASS: submit_extraction_job correctly returned cost_abort, zero API calls made

--- TEST 2: Subsequent submission blocked by aborted flag ---
  submit_extraction_job returned: job_id=None, error=cost_abort, status_code=0
  Accumulator unchanged: $0.010412
  PASS: Aborted flag prevents further submissions, no token accumulation

--- TEST 3: llm_judge fallback when accumulator aborted ---
  Accumulator aborted: True
  llm_judge with matching context: True (expected True)
  llm_judge with non-matching context: False (expected False)
  PASS: llm_judge fell back to substring matching, zero Anthropic API calls

--- TEST 4: Accumulator breach detection yields clean abort signal ---
  Abort detected in question loop check
  Reason: Cumulative cost $0.0060 exceeded --max-cost $0.01 (in=5,000 out=500)
  Summary: Cost: $0.0060 / $0.01 (input=5,000 output=500)
  Would write partial results and sys.exit(5)
  PASS: Question loop abort check fires correctly

============================================================
ALL 4 MOCK TESTS PASSED
Real spend: $0.00 (all API calls prevented by abort guards)
Exit code would be: 5 (matching run_q3_async.py abort semantics)
No orphaned workers possible: abort returns before any HTTP POST
============================================================
```

**Confirmed actual spend across all test runs this session:** ~$0.007 (3 Haiku extraction calls from one interrupted run; all other runs exited at pre-flight with zero API calls). Total session spend well under $0.50.

---

## 5. Post-Test Clean-State Confirmation

```
--- benchmark processes ---
none
--- python3 children ---
none
--- rq queue ---
  no rq queues found
--- git status (uncommitted) ---
 (clean — commit 2e544f4 applied)
```

No benchmark processes. No extraction workers. No RQ queue jobs. No orphaned state.

---

## 6. Commit Hash + Attributed Message

**Hash:** `2e544f4740161d62fb0d139a47aaf5e9f803b0bc`  
**Short:** `2e544f4`  
**Branch:** `master`  
**origin/master:** `0ceb578` — untouched  

**Message:**
```
feat(benchmark): add --max-cost kill-switch to run_benchmark.py

Resolves the n=25 pre-flight HALT: run_benchmark.py --scorer llm now
has --max-cost, enabling the measurement run on the bank-matched scorer
with cost control intact.

Mirrors the proven f893c18 2-hook cost_killswitch integration from
run_q3_async.py into run_benchmark.py. cost_killswitch.py is NOT
modified — imported and used as-is.

Hook A: pre-flight gate after dataset load (preflight_estimate + supplementary
judge cost check for --scorer llm). Hard exit(5) if projected > --max-cost.

Hook B1: accumulate + breach-check in submit_extraction_job before each
extraction API call.

Hook B2: abort-guard before llm_judge Sonnet call + accumulate actual judge
tokens (price-ratio scaled to extraction-model-equivalent) after call.

Both cost-bearing streams (extraction Haiku + Sonnet judge) feed a single
CostAccumulator with correct multi-model pricing via token scaling.

Non-contamination: bit-identical to 0ceb578 when kill-switch does not trip.
All new conditionals evaluate False on non-tripped path; accumulator writes
to internal counters only; no scoring/recall/prompt/payload variable touched.

Trip-tested: pre-flight refusal (exit 5, zero API calls) and runtime abort
(mock: all 4 abort paths verified — extraction breach, subsequent block,
judge fallback, question-loop detection).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 7. Provenance Findings

### Banked extraction model: UNCONFIRMED

**Searched artifacts:**
- `benchmarks/longmemeval/gate06_retry3_results.json` (2026-05-14) — run_q3_async.py format, no `extraction_model` field recorded
- `benchmarks/longmemeval/gate06_retry4_recall_only.json` (2026-05-14) — same
- `benchmarks/longmemeval/gate06_stage1b_recall.json` (2026-05-16) — same
- `benchmarks/longmemeval/runs/` — empty, no run_benchmark.py result files found
- `docs/PASS-3-ARCHITECTURE-MAP.md` — documents `.env` had `EXTRACTION_MODEL=claude-sonnet-4-6` at time of audit (around 0ceb578)
- Current `.env` — has `EXTRACTION_MODEL=claude-haiku-4-5-20251001` (last modified 2026-05-18 02:54)
- `.env` is not git-tracked; no history of when EXTRACTION_MODEL changed

**Timeline evidence:**
- `0ceb578` committed 2026-05-16 19:20:18 UTC
- PASS-3 architecture map (written ~May 16-17) documents production .env as `EXTRACTION_MODEL=claude-sonnet-4-6`
- The $603 cost incident (referenced in f893c18, committed 2026-05-17 07:45) was caused by Sonnet extraction
- At some point after the incident, .env was changed to Haiku

**Conclusion:** The banked 76%@20 result file from run_benchmark.py --scorer llm is not present on disk. The existing result files are from run_q3_async.py and do not record the extraction model. The .env at the time of 0ceb578 likely had `EXTRACTION_MODEL=claude-sonnet-4-6` per PASS-3 findings, but this cannot be confirmed from artifacts because .env is not git-tracked and the result file is missing. **Status: UNCONFIRMED.** The n=25 pre-flight must treat this as a confirmation gap.

### Banked corpus row count: UNRECORDED

**Current benchmark tenant (`382faaf1-5cbf-49a1-b689-5ffef8918d10`) row count:** 16,500 memories.

**Searched for banked baseline:**
- No result file records the corpus row count at time of the banked run
- The scope doc itself notes "~16,500 rows" as current, not as banked
- No migration, handoff, or result doc records a baseline row count at 0ceb578

**Conclusion:** The banked corpus row count at 0ceb578 is **UNRECORDED**. The current count is 16,500. Whether this matches the banked state cannot be confirmed. The n=25 pre-flight must treat this as a confirmation gap, not a silent pass.

---

## 8. Bugs Observed But NOT Fixed

1. **python3 coredumps (cleared, not diagnosed).** The scope references "31 python3 coredumps cleared from /var/lib/coredumps/ (May 16–18)." As of this chain, `/var/lib/coredumps/` is empty (cleared). No new coredumps during this session. The root cause of the crash-loop is undiagnosed. **Logged as open diagnostic item for a separate chain.** Not actioned in this fix chain per fix-stacking ban.

2. **Pre-flight recall token padding creates untestable gap.** The pre-flight includes recall tokens (`num_questions * RECALL_BUDGET_TOKENS * input_price`) in its cost estimate, but the runtime accumulator does not track recall (it goes through a separate API path). This means the pre-flight total is always higher than the runtime accumulator's achievable total for extraction costs, making a natural runtime abort impossible to trigger for small datasets where the judge estimate is accurate. This is conservative (safe direction — trips earlier at pre-flight, never under-counts) but means the runtime abort path can only fire when actual judge tokens significantly exceed the pre-flight estimate. **Not a bug per se** (conservative is correct for a safety control), but noted as a testability limitation.

3. **Banked 76%@20 result file missing.** The run_benchmark.py --scorer llm result that produced the banked 76%@20 is not on disk in `benchmarks/longmemeval/runs/` or elsewhere. The gate06_* files are from run_q3_async.py (different runner). This makes provenance verification impossible for the extraction model used. **Not actioned — read-only finding per scope.**

4. **Interrupted extraction jobs from session.** 3 extraction jobs were submitted to the API during an interrupted test run (smoke_q3.json --scorer llm --max-cost 0.04). These were processed by the async worker (not the benchmark process). Cost: ~$0.007. No orphaned processes resulted. **Noted for spend accounting.**
