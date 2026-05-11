#!/usr/bin/env python3
"""
LongMemEval benchmark adapter for 0Latency with production hardening.

Features:
- Exponential backoff retry for 502/429/503 errors
- Rate limiting to prevent CloudFlare blocks  
- Smoke test mode for pre-flight validation
- Cost estimation before full runs
- Auto-kill on consecutive recall failures
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

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

class LongMemEvalRunner:
    def __init__(self, dataset_path: str, max_questions: int = 5, max_sessions: int = None,
                 smoke_mode: bool = False, max_zero_streak: int = 10, confirm_cost: bool = False):
        self.dataset_path = Path(dataset_path)
        self.max_questions = max_questions
        self.max_sessions = max_sessions
        self.smoke_mode = smoke_mode
        self.max_zero_streak = max_zero_streak
        self.confirm_cost = confirm_cost
        self.headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        self.latencies = []
        self.total_extraction_tokens = 0
        self.total_recall_tokens = 0
        self.zero_streak = 0
        
    def load_dataset(self) -> List[Dict]:
        """Load LongMemEval dataset."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")
        
        with open(self.dataset_path) as f:
            data = json.load(f)
        
        # Smoke mode overrides max_questions
        if self.smoke_mode:
            self.max_questions = 3
            print(f"[SMOKE MODE] Running {self.max_questions} questions", file=sys.stderr)
        
        print(f"Loaded {len(data)} questions from {self.dataset_path.name}", file=sys.stderr)
        return data[:self.max_questions]
    
    def extract_sessions(self, sessions: List[List[Dict]], question_id: str) -> int:
        """Extract haystack sessions with exponential backoff retry logic."""
        sessions_to_extract = sessions if self.max_sessions is None else sessions[:self.max_sessions]
        
        print(f"  Extracting {len(sessions_to_extract)}/{len(sessions)} sessions...", file=sys.stderr, end=" ")
        sys.stderr.flush()
        
        start = time.time()
        turn_count = 0
        failed_count = 0
        
        for session_idx, session in enumerate(sessions_to_extract):
            i = 0
            while i < len(session) - 1:
                user_turn = session[i]
                assistant_turn = session[i + 1]
                
                if user_turn["role"] != "user" or assistant_turn["role"] != "assistant":
                    i += 1
                    continue
                
                payload = {
                    "human_message": user_turn["content"],
                    "agent_message": assistant_turn["content"],
                    "session_key": f"longmemeval_{question_id}_session_{session_idx}"
                }
                
                # Track tokens for cost estimation
                self.total_extraction_tokens += len(user_turn["content"]) + len(assistant_turn["content"])
                
                # Exponential backoff retry
                max_retries = 5
                retry_delay = 0.5
                
                for attempt in range(max_retries):
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/extract",
                            headers=self.headers,
                            json=payload,
                            timeout=90
                        )
                        
                        if response.status_code in (200, 202):
                            turn_count += 1
                            time.sleep(0.1)  # Rate limit
                            break
                        elif response.status_code in (429, 502, 503):
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            else:
                                failed_count += 1
                                if failed_count <= 3:
                                    print(f"\nWARN: Turn failed after {max_retries} retries: {response.status_code}", file=sys.stderr)
                                break
                        else:
                            failed_count += 1
                            if failed_count <= 3:
                                print(f"\nWARN: Turn extraction failed: {response.status_code}", file=sys.stderr)
                            break
                    except requests.exceptions.Timeout:
                        failed_count += 1
                        if failed_count <= 3:
                            print(f"\nWARN: Turn timed out", file=sys.stderr)
                        break
                    except Exception as e:
                        failed_count += 1
                        if failed_count <= 3:
                            print(f"\nWARN: Turn error: {e}", file=sys.stderr)
                        break
                
                i += 2
        
        elapsed = time.time() - start
        print(f"{turn_count} turns ({failed_count} failed) in {elapsed:.1f}s", file=sys.stderr)
        return turn_count
    
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
    
    def answer_question(self, question: str, context: str) -> str:
        """Generate answer from recalled context."""
        if not context:
            return "I don't have enough information to answer that."
        return context[:500]
    
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
        print(f"  Total estimated: ${haiku_cost + sonnet_cost:.2f}", file=sys.stderr)
        print(f"\nTo proceed with full run, add --confirm-cost flag", file=sys.stderr)
    
    def run(self, output_path: str = None):
        """Run benchmark and save results."""
        questions = self.load_dataset()
        total_in_dataset = len(json.load(open(self.dataset_path)))
        
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
            match = expected_answer.lower() in hypothesis.lower()
            
            results.append({
                "question_id": question_id,
                "question": question,
                "expected": expected_answer,
                "hypothesis": hypothesis[:200],
                "context_chars": len(context),
                "match": match,
                "recall_latency_ms": int(recall_latency_ms),
                "num_turns_extracted": num_extracted,
                "num_sessions_total": len(haystack_sessions),
                "wall_clock_seconds": round(question_elapsed, 1)
            })
            
            print(f"  Match: {match} | Latency: {recall_latency_ms:.0f}ms | Wall: {question_elapsed:.1f}s", file=sys.stderr)
            
            # Smoke test validations
            if self.smoke_mode:
                if len(context) == 0:
                    smoke_failures.append(f"Q{i} ({question_id}): 0 chars from recall")
                if question_elapsed > 60:
                    smoke_failures.append(f"Q{i} ({question_id}): {question_elapsed:.1f}s exceeds 60s limit")
            
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
                "max_zero_streak": self.max_zero_streak
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
        confirm_cost=args.confirm_cost
    )
    
    runner.run(output_path=args.output)
