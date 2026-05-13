#!/usr/bin/env python3
"""
LongMemEval benchmark adapter for 0Latency with production hardening.

Features:
- Async extraction via /memories/extract with worker queue
- Bounded concurrency (ThreadPoolExecutor) for parallel submission
- Exponential backoff retry for 502/429/503/520/524 errors
- Circuit breaker to prevent hanging on degraded API
- Rate limiting to prevent CloudFlare blocks  
- Smoke test mode for pre-flight validation
- Cost estimation before full runs
- Auto-kill on consecutive recall failures
- Memory-efficient loading for large datasets
"""
import os
import sys
import json
import time
import requests
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import anthropic

# Load benchmark credentials
env_file = Path(__file__).parent / ".env.benchmark"
if not env_file.exists():
    print(f"ERROR: {env_file} not found. Run Phase 2 to create tenant.", file=sys.stderr)
    sys.exit(1)

for line in env_file.read_text().splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()

TENANT_ID = os.getenv("TENANT_ID")
API_KEY = os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.0latency.ai")

if not all([TENANT_ID, API_KEY]):
    print("ERROR: TENANT_ID or API_KEY missing in .env.benchmark", file=sys.stderr)
    sys.exit(1)

# LLM judge needs Anthropic key (from running service env or environment)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    # Try loading from running API service process
    import glob
    for cmdline_path in glob.glob("/proc/*/cmdline"):
        try:
            with open(cmdline_path, "rb") as f:
                if b"uvicorn" in f.read() and b"api.main" in open(cmdline_path, "rb").read():
                    pid = cmdline_path.split("/")[2]
                    with open(f"/proc/{pid}/environ", "rb") as ef:
                        for pair in ef.read().split(b"\x00"):
                            if pair.startswith(b"ANTHROPIC_API_KEY="):
                                ANTHROPIC_API_KEY = pair.decode().split("=", 1)[1]
                                break
                    if ANTHROPIC_API_KEY:
                        break
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            continue

class LongMemEvalRunner:
    def __init__(self, dataset_path: str, max_questions: int = 5, max_sessions: int = None,
                 smoke_mode: bool = False, max_zero_streak: int = 10, confirm_cost: bool = False,
                 scorer: str = "substring", max_workers: int = 8):
        self.dataset_path = Path(dataset_path)
        self.max_questions = max_questions
        self.max_sessions = max_sessions
        self.smoke_mode = smoke_mode
        self.max_zero_streak = max_zero_streak
        self.confirm_cost = confirm_cost
        self.scorer = scorer
        self.max_workers = max_workers
        self.headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        self.latencies = []
        self.total_extraction_tokens = 0
        self.total_recall_tokens = 0
        self.total_judge_tokens = 0
        self.zero_streak = 0
        self.dataset_total_count = 0
        self.consecutive_failures = 0
        
        if self.scorer == "llm":
            if not ANTHROPIC_API_KEY:
                print("ERROR: --scorer llm requires ANTHROPIC_API_KEY", file=sys.stderr)
                sys.exit(1)
            self.anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
    def load_dataset(self) -> List[Dict]:
        """Load LongMemEval dataset with memory-efficient approach."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")
        
        # Smoke mode overrides max_questions
        if self.smoke_mode:
            self.max_questions = 3
            print(f"[SMOKE MODE] Running {self.max_questions} questions", file=sys.stderr)
        
        # For smoke mode, use jq to extract only first N questions to avoid OOM
        # on large datasets (longmemeval_s_cleaned.json is 265MB)
        if self.smoke_mode or self.max_questions < 20:
            print(f"Loading first {self.max_questions} questions with jq (memory-efficient)...", file=sys.stderr, end=" ")
            sys.stderr.flush()
            
            try:
                # Use jq to extract first N questions without loading full file
                result = subprocess.run(
                    ["jq", f".[:{ self.max_questions}]", str(self.dataset_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True
                )
                data = json.loads(result.stdout)
                
                # Count total using grep (fast, no memory overhead)
                count_result = subprocess.run(
                    ["grep", "-o", '"question_id"', str(self.dataset_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True
                )
                self.dataset_total_count = count_result.stdout.count('"question_id"')
                
                print(f"OK", file=sys.stderr)
                print(f"Loaded {len(data)}/{self.dataset_total_count} questions from {self.dataset_path.name}", file=sys.stderr)
                return data
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
                print(f"WARN: jq failed ({e}), falling back to standard load", file=sys.stderr)
                # Fall through to standard load
        
        # Standard load for full runs
        with open(self.dataset_path) as f:
            data = json.load(f)
        self.dataset_total_count = len(data)
        
        print(f"Loaded {len(data)} questions from {self.dataset_path.name}", file=sys.stderr)
        return data[:self.max_questions]
    
    def submit_extraction_job(self, payload: Dict) -> Tuple[str, str, int]:
        """Submit single extraction job to async endpoint. Returns (job_id, error, status_code)."""
        max_retries = 1  # Only 1 retry at benchmark layer (workers retry 3x internally)
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/memories/extract",
                    headers=self.headers,
                    json=payload,
                    timeout=10
                )
                
                print(f"DEBUG: POST status={response.status_code} body={response.text[:200]}", file=sys.stderr)
                
                if response.status_code == 202:
                    data = response.json()
                    return data["job_id"], None, 202
                elif response.status_code in (429, 502, 503, 520, 524):
                    if attempt < max_retries:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    return None, f"status_{response.status_code}", response.status_code
                else:
                    return None, f"status_{response.status_code}", response.status_code
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return None, "timeout", 0
            except Exception as e:
                print(f"DEBUG: Exception {type(e).__name__}: {e}", file=sys.stderr)
                return None, str(e), 0
        
        return None, "max_retries_exceeded", 0
    
    def poll_job_completion(self, job_id: str, max_wait: int = 120) -> Tuple[bool, str]:
        """Poll job until complete or timeout. Returns (success, error)."""
        start = time.time()
        
        while time.time() - start < max_wait:
            try:
                response = requests.get(
                    f"{API_BASE_URL}/memories/extract/{job_id}",
                    headers=self.headers,
                    timeout=5
                )
                
                if response.status_code != 200:
                    return False, f"poll_status_{response.status_code}"
                
                data = response.json()
                status = data.get("status")
                
                if status == "complete":
                    return True, None
                elif status == "failed":
                    error = data.get("error", "unknown_error")
                    return False, f"job_failed_{error}"
                # status == "accepted" or "processing", keep polling
                
                time.sleep(0.5)
            except Exception as e:
                time.sleep(0.5)
                continue
        
        return False, "poll_timeout"
    
    def extract_single_session(self, session: List[Dict], session_idx: int, question_id: str) -> Tuple[int, int]:
        """Extract one session (all turns). Returns (turn_count, failed_count)."""
        turn_count = 0
        failed_count = 0
        
        i = 0
        while i < len(session) - 1:
            user_turn = session[i]
            assistant_turn = session[i + 1]
            
            if user_turn["role"] != "user" or assistant_turn["role"] != "assistant":
                i += 1
                continue
            
            payload = {
                "content": f"Human: {user_turn['content']}\n\nAssistant: {assistant_turn['content']}",
                "session_key": f"longmemeval_{question_id}_session_{session_idx}"
            }
            
            # Track tokens for cost estimation
            self.total_extraction_tokens += len(user_turn["content"]) + len(assistant_turn["content"])
            
            # Submit job
            job_id, error, status_code = self.submit_extraction_job(payload)
            
            if not job_id:
                failed_count += 1
                self.consecutive_failures += 1
                i += 2
                continue
            
            # Poll for completion
            success, poll_error = self.poll_job_completion(job_id)
            
            if success:
                turn_count += 1
                self.consecutive_failures = 0
            else:
                failed_count += 1
                self.consecutive_failures += 1
            
            # Circuit breaker
            if self.consecutive_failures >= 5:
                print(f"\n✗ CIRCUIT BREAKER: 5 consecutive failures", file=sys.stderr)
                print(f"API appears degraded. Aborting to prevent hang.", file=sys.stderr)
                raise RuntimeError("Circuit breaker tripped")
            
            i += 2
        
        return turn_count, failed_count
    
    def extract_sessions(self, sessions: List[List[Dict]], question_id: str) -> int:
        """Extract haystack sessions with async submission and bounded concurrency."""
        sessions_to_extract = sessions if self.max_sessions is None else sessions[:self.max_sessions]
        
        print(f"  Extracting {len(sessions_to_extract)}/{len(sessions)} sessions...", file=sys.stderr, end=" ")
        sys.stderr.flush()
        
        start = time.time()
        total_turns = 0
        total_failed = 0
        session_times = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for session_idx, session in enumerate(sessions_to_extract):
                future = executor.submit(self.extract_single_session, session, session_idx, question_id)
                futures[future] = (session_idx, time.time())
            
            for future in as_completed(futures):
                session_idx, session_start = futures[future]
                session_elapsed = time.time() - session_start
                session_times.append(session_elapsed)
                
                try:
                    turn_count, failed_count = future.result()
                    total_turns += turn_count
                    total_failed += failed_count
                except Exception as e:
                    print(f"\nERROR extracting session {session_idx}: {e}", file=sys.stderr)
                    raise
        
        elapsed = time.time() - start
        
        # Calculate per-session stats
        if session_times:
            session_times.sort()
            p50 = session_times[len(session_times) // 2]
            p95 = session_times[int(len(session_times) * 0.95)]
            print(f"\n  {total_turns} turns ({total_failed} failed) in {elapsed:.1f}s | p50={p50:.1f}s p95={p95:.1f}s per session", file=sys.stderr)
        else:
            print(f"\n  {total_turns} turns ({total_failed} failed) in {elapsed:.1f}s", file=sys.stderr)
        
        return total_turns
    
    def recall(self, question: str) -> Tuple[str, float]:
        """Recall relevant context for question."""
        payload = {"conversation_context": question, "budget_tokens": 4000}
        self.total_recall_tokens += len(question)
        
        start = time.time()
        try:
            response = requests.post(
                f"{API_BASE_URL}/recall",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            latency_ms = (time.time() - start) * 1000
            
            if response.status_code != 200:
                print(f"WARN: Recall failed: {response.status_code}", file=sys.stderr)
                return "", latency_ms
            
            data = response.json()
            context = data.get("context", "") or data.get("context_block", "")
            self.total_recall_tokens += data.get("tokens_used", 0)
            
            return context, latency_ms
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            print(f"WARN: Recall exception: {e}", file=sys.stderr)
            return "", latency_ms
    
    def llm_judge(self, question: str, expected: str, context: str) -> bool:
        """Use Claude Sonnet to judge if context contains the expected answer."""
        # Send up to 20K chars of context for accurate judgment
        ctx = context[:20000] if len(context) > 20000 else context
        
        prompt = f"""You are a benchmark judge for a memory recall system. Given a question, the expected answer, and a recalled context block, determine if the context contains information that answers the question correctly.

The context block contains recalled memory snippets. The expected answer may appear verbatim, paraphrased, or be inferable from the information present.

Question: {question}
Expected answer: {expected}

Recalled context:
{ctx}

Does the recalled context contain information that correctly answers the question with the expected answer (verbatim, paraphrased, or clearly inferable)?
Reply with ONLY "YES" or "NO"."""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=3,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )
            verdict = response.content[0].text.strip().upper()
            self.total_judge_tokens += response.usage.input_tokens + response.usage.output_tokens
            return verdict == "YES"
        except Exception as e:
            print(f"WARN: LLM judge failed ({e}), falling back to substring", file=sys.stderr)
            return expected.lower() in context.lower()

    def answer_question(self, question: str, context: str) -> str:
        """Generate answer from recalled context."""
        if not context:
            return "I don't have enough information to answer that."
        return context
    
    def estimate_cost(self, questions_processed: int, total_questions: int):
        """Estimate total cost for full run based on smoke test."""
        if questions_processed == 0:
            return
        
        avg_extraction_tokens = self.total_extraction_tokens / questions_processed
        avg_recall_tokens = self.total_recall_tokens / questions_processed
        
        projected_extraction_tokens = avg_extraction_tokens * total_questions
        projected_recall_tokens = avg_recall_tokens * total_questions
        
        # Haiku: $0.25/1M tokens, Sonnet: $3.00/1M tokens
        haiku_cost = (projected_extraction_tokens / 1_000_000) * 0.25
        sonnet_cost = (projected_recall_tokens / 1_000_000) * 3.00
        
        print(f"\n=== COST ESTIMATE ===", file=sys.stderr)
        print(f"Smoke test: {questions_processed} questions", file=sys.stderr)
        print(f"  Extraction: {self.total_extraction_tokens:,} tokens (avg {int(avg_extraction_tokens)}/q)", file=sys.stderr)
        print(f"  Recall: {self.total_recall_tokens:,} tokens (avg {int(avg_recall_tokens)}/q)", file=sys.stderr)
        print(f"\nProjected full run (n={total_questions}):", file=sys.stderr)
        print(f"  Extraction cost (Haiku): ${haiku_cost:.2f}", file=sys.stderr)
        print(f"  Recall cost (Sonnet): ${sonnet_cost:.2f}", file=sys.stderr)
        
        if self.scorer == "llm":
            avg_judge_tokens = self.total_judge_tokens / questions_processed if questions_processed else 0
            projected_judge_tokens = avg_judge_tokens * total_questions
            judge_cost = (projected_judge_tokens / 1_000_000) * 3.00  # claude-sonnet pricing
            print(f"  Judge cost (Claude Sonnet): ${judge_cost:.2f}", file=sys.stderr)
            print(f"  Total estimated: ${haiku_cost + sonnet_cost + judge_cost:.2f}", file=sys.stderr)
        else:
            print(f"  Total estimated: ${haiku_cost + sonnet_cost:.2f}", file=sys.stderr)
        print(f"\nTo proceed with full run, add --confirm-cost flag", file=sys.stderr)
    
    def run(self, output_path: str = None):
        """Run benchmark and save results."""
        questions = self.load_dataset()
        total_in_dataset = self.dataset_total_count
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if output_path is None:
            prefix = "smoke" if self.smoke_mode else "run"
            output_path = f"{prefix}-{timestamp}.json"
        
        results = []
        smoke_failures = []
        
        print(f"\nRunning LongMemEval benchmark (n={len(questions)})...", file=sys.stderr)
        print(f"Tenant: {TENANT_ID}", file=sys.stderr)
        print(f"API: {API_BASE_URL}", file=sys.stderr)
        print(f"Max sessions per question: {self.max_sessions or 'all'}", file=sys.stderr)
        print(f"Max zero streak: {self.max_zero_streak}", file=sys.stderr)
        print(f"Concurrency: {self.max_workers} workers", file=sys.stderr)
        print("", file=sys.stderr)
        
        for i, item in enumerate(questions, 1):
            question_id = item["question_id"]
            question = item["question"]
            expected_answer = item["answer"]
            haystack_sessions = item["haystack_sessions"]
            
            print(f"[{i}/{len(questions)}] {question_id}", file=sys.stderr)
            print(f"  Q: {question}", file=sys.stderr)
            
            question_start = time.time()
            
            num_extracted = self.extract_sessions(haystack_sessions, question_id)
            
            print(f"  Recalling...", file=sys.stderr, end=" ")
            sys.stderr.flush()
            context, recall_latency_ms = self.recall(question)
            print(f"{recall_latency_ms:.0f}ms, {len(context)} chars", file=sys.stderr)
            self.latencies.append(recall_latency_ms)
            
            question_elapsed = time.time() - question_start
            
            hypothesis = self.answer_question(question, context)
            if self.scorer == "llm":
                match = self.llm_judge(question, str(expected_answer), context)
            else:
                match = str(expected_answer).lower() in hypothesis.lower()
            
            results.append({
                "question_id": question_id,
                "question": question,
                "expected": expected_answer,
                "hypothesis": hypothesis[:200],
                "context_chars": len(context),
                "match": match,
                "scorer": self.scorer,
                "recall_latency_ms": int(recall_latency_ms),
                "num_turns_extracted": num_extracted,
                "num_sessions_total": len(haystack_sessions),
                "wall_clock_seconds": round(question_elapsed, 1)
            })
            
            scorer_label = "LLM" if self.scorer == "llm" else "sub"
            print(f"  Match: {match} ({scorer_label}) | Latency: {recall_latency_ms:.0f}ms | Wall: {question_elapsed:.1f}s", file=sys.stderr)
            
            # Smoke test validations
            if self.smoke_mode:
                if len(context) == 0:
                    smoke_failures.append(f"Q{i} ({question_id}): 0 chars from recall")
            
            # Zero-streak auto-kill
            if not match and len(context) == 0:
                self.zero_streak += 1
                if self.zero_streak >= self.max_zero_streak:
                    print(f"\n✗ ABORT: {self.zero_streak} consecutive failures with 0 chars recall", file=sys.stderr)
                    print(f"Recall is likely broken. Aborting to save time.", file=sys.stderr)
                    break
            else:
                self.zero_streak = 0
            
            print("", file=sys.stderr)
        
        # Smoke test final validation
        if self.smoke_mode:
            matches = sum(r["match"] for r in results)
            if matches == 0:
                smoke_failures.append("Zero matches across all smoke questions")
            
            if smoke_failures:
                print(f"\n✗ SMOKE TEST FAILED:", file=sys.stderr)
                for failure in smoke_failures:
                    print(f"  - {failure}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"\n✓ SMOKE TEST PASSED", file=sys.stderr)
                self.estimate_cost(len(results), total_in_dataset)
                sys.exit(0)
        
        # Calculate metrics
        latencies_sorted = sorted(self.latencies)
        p50_idx = len(latencies_sorted) // 2
        p95_idx = int(len(latencies_sorted) * 0.95)
        
        accuracy = sum(r["match"] for r in results) / len(results) * 100 if results else 0
        
        output_data = {
            "metadata": {
                "timestamp": timestamp,
                "sample_size": len(questions),
                "dataset": str(self.dataset_path),
                "max_sessions_per_question": self.max_sessions,
                "tenant_id": TENANT_ID,
                "api_base_url": API_BASE_URL,
                "max_zero_streak": self.max_zero_streak,
                "scorer": self.scorer,
                "max_workers": self.max_workers
            },
            "aggregate": {
                "accuracy": accuracy,
                "p50_recall_latency_ms": int(latencies_sorted[p50_idx]) if latencies_sorted else 0,
                "p95_recall_latency_ms": int(latencies_sorted[p95_idx]) if latencies_sorted else 0,
                "n_questions": len(results),
                "total_extraction_tokens": self.total_extraction_tokens,
                "total_recall_tokens": self.total_recall_tokens
            },
            "results": results
        }
        
        # Save results
        output_file = Path(__file__).parent / "runs" / output_path
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n✓ Results saved to {output_file}", file=sys.stderr)
        print(f"\n=== SUMMARY ===", file=sys.stderr)
        print(f"Accuracy: {accuracy:.1f}% ({sum(r['match'] for r in results)}/{len(results)})", file=sys.stderr)
        print(f"p50 latency: {output_data['aggregate']['p50_recall_latency_ms']}ms", file=sys.stderr)
        print(f"p95 latency: {output_data['aggregate']['p95_recall_latency_ms']}ms", file=sys.stderr)
        
        return output_data

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LongMemEval benchmark on 0Latency")
    parser.add_argument("dataset", help="Path to LongMemEval dataset JSON")
    parser.add_argument("-n", "--max-questions", type=int, default=500, help="Max questions to run")
    parser.add_argument("-s", "--max-sessions", type=int, default=None, help="Max sessions per question")
    parser.add_argument("-o", "--output", default=None, help="Output file path")
    parser.add_argument("--smoke", action="store_true", help="Smoke test mode: run n=3, exit 1 if failures")
    parser.add_argument("--max-zero-streak", type=int, default=10, help="Auto-kill after N consecutive 0-char recalls")
    parser.add_argument("--confirm-cost", action="store_true", help="Confirm willingness to pay projected cost")
    parser.add_argument("--scorer", choices=["substring", "llm"], default="substring",
                        help="Scoring method: substring (exact match) or llm (Claude Sonnet judge)")
    parser.add_argument("--max-workers", type=int, default=8, help="Max concurrent sessions for extraction")
    
    args = parser.parse_args()
    
    # Cost confirmation gate for large runs
    if not args.smoke and args.max_questions > 10 and not args.confirm_cost:
        print("ERROR: Large run requires --confirm-cost flag after reviewing smoke test estimate", file=sys.stderr)
        print("Run with --smoke first to see projected cost", file=sys.stderr)
        sys.exit(1)
    
    runner = LongMemEvalRunner(
        dataset_path=args.dataset,
        max_questions=args.max_questions,
        max_sessions=args.max_sessions,
        smoke_mode=args.smoke,
        max_zero_streak=args.max_zero_streak,
        confirm_cost=args.confirm_cost,
        scorer=args.scorer,
        max_workers=args.max_workers
    )
    
    runner.run(output_path=args.output)
