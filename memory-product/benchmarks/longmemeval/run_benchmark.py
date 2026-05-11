#!/usr/bin/env python3
"""
LongMemEval benchmark adapter for 0Latency.

Loads questions from longmemeval dataset, extracts haystack sessions via /extract,
recalls via /recall, and evaluates accuracy.
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any
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
    def __init__(self, dataset_path: str, max_questions: int = 5, max_sessions: int = None):
        self.dataset_path = Path(dataset_path)
        self.max_questions = max_questions
        self.max_sessions = max_sessions
        self.headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        self.latencies = []
        
    def load_dataset(self) -> List[Dict]:
        """Load LongMemEval dataset."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")
        
        with open(self.dataset_path) as f:
            data = json.load(f)
        
        print(f"Loaded {len(data)} questions from {self.dataset_path.name}", file=sys.stderr)
        return data[:self.max_questions]
    
    def extract_sessions(self, sessions: List[List[Dict]], question_id: str) -> int:
        """Extract haystack sessions into 0Latency memory store.
        
        The 0Latency /extract endpoint expects human_message and agent_message pairs.
        LongMemEval sessions are multi-turn conversations.
        
        Returns number of turns extracted.
        """
        sessions_to_extract = sessions if self.max_sessions is None else sessions[:self.max_sessions]
        
        print(f"  Extracting {len(sessions_to_extract)}/{len(sessions)} sessions...", file=sys.stderr, end=" ")
        sys.stderr.flush()
        
        start = time.time()
        turn_count = 0
        
        for session_idx, session in enumerate(sessions_to_extract):
            # Process session as turn pairs (user → assistant)
            i = 0
            while i < len(session) - 1:
                user_turn = session[i]
                assistant_turn = session[i + 1]
                
                # Skip if not a proper user-assistant pair
                if user_turn["role"] != "user" or assistant_turn["role"] != "assistant":
                    i += 1
                    continue
                
                # Extract this turn pair
                payload = {
                    "human_message": user_turn["content"],
                    "agent_message": assistant_turn["content"],
                    "session_key": f"longmemeval_{question_id}_session_{session_idx}"
                }
                
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/extract",
                        headers=self.headers,
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code not in (200, 202):
                        # Only log first few failures to avoid spam
                        if turn_count < 3:
                            print(f"\nWARNING: Turn extraction failed: {response.status_code}", file=sys.stderr)
                            print(response.text[:200], file=sys.stderr)
                    else:
                        turn_count += 1
                    
                except requests.exceptions.Timeout:
                    print(f"\nWARNING: Turn timed out", file=sys.stderr)
                
                i += 2  # Move to next user-assistant pair
        
        elapsed = time.time() - start
        print(f"{turn_count} turns in {elapsed:.1f}s", file=sys.stderr)
        
        return turn_count
    
    def recall(self, question: str) -> tuple[str, float]:
        """Recall relevant context for question.
        
        Returns (recalled_context, latency_ms).
        """
        payload = {
            "conversation_context": question,
            "budget_tokens": 4000
        }
        
        start = time.time()
        try:
            response = requests.post(
                f"{API_BASE_URL}/recall",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            latency_ms = (time.time() - start) * 1000
            
            if response.status_code != 200:
                print(f"WARNING: Recall failed: {response.status_code}", file=sys.stderr)
                print(response.text[:200], file=sys.stderr)
                return "", latency_ms
            
            data = response.json()
            context = data.get("context", "")
            
            return context, latency_ms
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            print(f"WARNING: Recall exception: {e}", file=sys.stderr)
            return "", latency_ms
    
    def answer_question(self, question: str, context: str) -> str:
        """Generate answer from recalled context.
        
        For now, just extract the answer from context using simple heuristics.
        In production, this would use an LLM.
        """
        # Simple extraction: return the context itself for now
        # The eval script will use GPT-4o to judge semantic equivalence
        if not context:
            return "I don't have enough information to answer that."
        
        # Return first 500 chars of context as the "answer"
        return context[:500]
    
    def run(self, output_path: str = None):
        """Run benchmark and save results."""
        questions = self.load_dataset()
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if output_path is None:
            output_path = f"dryrun-{timestamp}.json"
        
        results = []
        
        print(f"\nRunning LongMemEval benchmark (n={len(questions)})...", file=sys.stderr)
        print(f"Tenant: {TENANT_ID}", file=sys.stderr)
        print(f"API: {API_BASE_URL}", file=sys.stderr)
        print(f"Max sessions per question: {self.max_sessions or 'all'}", file=sys.stderr)
        print("", file=sys.stderr)
        
        for i, item in enumerate(questions, 1):
            question_id = item["question_id"]
            question = item["question"]
            expected_answer = item["answer"]
            haystack_sessions = item["haystack_sessions"]
            
            print(f"[{i}/{len(questions)}] {question_id}", file=sys.stderr)
            print(f"  Q: {question}", file=sys.stderr)
            
            # Extract sessions
            num_extracted = self.extract_sessions(haystack_sessions, question_id)
            
            # Recall
            print(f"  Recalling...", file=sys.stderr, end=" ")
            sys.stderr.flush()
            context, recall_latency_ms = self.recall(question)
            print(f"{recall_latency_ms:.0f}ms, {len(context)} chars", file=sys.stderr)
            self.latencies.append(recall_latency_ms)
            
            # Generate answer
            hypothesis = self.answer_question(question, context)
            
            # Simple match check (will be re-evaluated by GPT-4o)
            match = expected_answer.lower() in hypothesis.lower()
            
            results.append({
                "question_id": question_id,
                "question": question,
                "expected": expected_answer,
                "hypothesis": hypothesis[:200],  # Truncate for readability
                "context_chars": len(context),
                "match": match,
                "recall_latency_ms": int(recall_latency_ms),
                "num_turns_extracted": num_extracted,
                "num_sessions_total": len(haystack_sessions)
            })
            
            print(f"  Match: {match} | Latency: {recall_latency_ms:.0f}ms", file=sys.stderr)
            print("", file=sys.stderr)
        
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
                "api_base_url": API_BASE_URL
            },
            "aggregate": {
                "accuracy": accuracy,
                "p50_recall_latency_ms": int(latencies_sorted[p50_idx]) if latencies_sorted else 0,
                "p95_recall_latency_ms": int(latencies_sorted[p95_idx]) if latencies_sorted else 0,
                "n_questions": len(results)
            },
            "results": results
        }
        
        # Save results
        output_file = Path(__file__).parent / output_path
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
    parser.add_argument("-n", "--max-questions", type=int, default=5, help="Max questions to run")
    parser.add_argument("-s", "--max-sessions", type=int, default=None, help="Max sessions per question (default: all)")
    parser.add_argument("-o", "--output", default=None, help="Output file path")
    
    args = parser.parse_args()
    
    runner = LongMemEvalRunner(
        dataset_path=args.dataset,
        max_questions=args.max_questions,
        max_sessions=args.max_sessions
    )
    
    runner.run(output_path=args.output)
