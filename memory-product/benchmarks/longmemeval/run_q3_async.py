#!/usr/bin/env python3
"""
Q3 Single-Question Async Benchmark Runner

Submit-all-then-poll architecture eliminates thread starvation.
Phase 4 (recall verification) measures answer retrievability post-ingestion.

Runs against local API (localhost:8420) to bypass edge rate limiting.
For production smoke tests, override API_BASE_URL env var.
"""
import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8420")
API_KEY = os.getenv("API_KEY")
TENANT_ID = os.getenv("TENANT_ID")

if not API_KEY or not TENANT_ID:
    print("ERROR: Set API_KEY and TENANT_ID environment variables", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}

class BenchmarkRunner:
    def __init__(self, dataset_path: str, max_workers: int = 16):
        self.dataset_path = Path(dataset_path)
        self.max_workers = max_workers
        
    def load_dataset(self) -> List[Dict]:
        """Load Q3 dataset."""
        with open(self.dataset_path) as f:
            data = json.load(f)
        print(f"Loaded {len(data)} questions from {self.dataset_path.name}")
        return data
    
    def extract_turns(self, sessions: List[List[Dict]], question_id: str) -> List[Dict]:
        """Extract all turns from all sessions into flat list."""
        turns = []
        
        for session_idx, session in enumerate(sessions):
            i = 0
            turn_idx = 0
            while i < len(session) - 1:
                user_turn = session[i]
                assistant_turn = session[i + 1]
                
                if user_turn["role"] != "user" or assistant_turn["role"] != "assistant":
                    i += 1
                    continue
                
                turns.append({
                    "session_idx": session_idx,
                    "turn_idx": turn_idx,
                    "content": f"Human: {user_turn['content']}\\n\\nAssistant: {assistant_turn['content']}",
                    "session_key": f"longmemeval_{question_id}_session_{session_idx}"
                })
                
                turn_idx += 1
                i += 2
        
        return turns
    
    def submit_job(self, turn: Dict) -> Tuple[str, Dict]:
        """Submit one extraction job. Returns (job_id or None, turn_metadata)."""
        payload = {
            "content": turn["content"],
            "session_key": turn["session_key"]
        }
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/memories/extract",
                headers=HEADERS,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 202:
                data = response.json()
                return data["job_id"], turn
            else:
                return None, {**turn, "error": f"status_{response.status_code}"}
        except Exception as e:
            return None, {**turn, "error": str(e)}
    
    def poll_job(self, job_id: str, turn: Dict, max_wait: int = 180) -> Dict:
        """Poll job until complete or timeout. Returns result dict."""
        start = time.time()
        retries_5xx = 0
        max_retries_5xx = 3
        backoff_schedule = [1, 2, 4]
        
        while time.time() - start < max_wait:
            try:
                response = requests.get(
                    f"{API_BASE_URL}/memories/extract/{job_id}",
                    headers=HEADERS,
                    timeout=5
                )
                
                if response.status_code == 429:
                    # Rate limited - wait and retry
                    data = response.json()
                    retry_after = data.get("detail", {}).get("error", {}).get("retry_after", 5)
                    time.sleep(retry_after)
                    continue
                elif 500 <= response.status_code < 600:
                    # Transient server error — retry with exponential backoff
                    retries_5xx += 1
                    if retries_5xx > max_retries_5xx:
                        elapsed = time.time() - start
                        return {
                            **turn,
                            "job_id": job_id,
                            "status": "failed",
                            "error": f"poll_status_{response.status_code}_after_3_retries",
                            "elapsed": elapsed
                        }
                    delay = backoff_schedule[retries_5xx - 1]
                    time.sleep(delay)
                    continue
                elif response.status_code != 200:
                    elapsed = time.time() - start
                    return {
                        **turn,
                        "job_id": job_id,
                        "status": "failed",
                        "error": f"poll_status_{response.status_code}",
                        "elapsed": elapsed
                    }
                
                data = response.json()
                status = data.get("status")
                
                if status == "complete":
                    elapsed = time.time() - start
                    return {
                        **turn,
                        "job_id": job_id,
                        "status": "complete",
                        "memories_stored": data.get("memories_stored", 0),
                        "elapsed": elapsed
                    }
                elif status == "failed":
                    elapsed = time.time() - start
                    return {
                        **turn,
                        "job_id": job_id,
                        "status": "failed",
                        "error": data.get("error", "unknown"),
                        "elapsed": elapsed
                    }
                
                # Reset 5xx counter on successful poll (job still processing)
                retries_5xx = 0
                time.sleep(0.5)
            except Exception as e:
                elapsed = time.time() - start
                return {
                    **turn,
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(e),
                    "elapsed": elapsed
                }
        
        elapsed = time.time() - start
        return {
            **turn,
            "job_id": job_id,
            "status": "failed",
            "error": "timeout",
            "elapsed": elapsed
        }
    
    def recall_verification(self, question: Dict) -> Dict:
        """Phase 4: Post-ingestion recall verification.

        Issues POST /recall with the question text, finds the answer-bearing
        memory by configurable matching, and computes recall precision metrics.

        Answer-bearing memory identification (configurable per question):
        - answer_keywords: substrings that must appear in headline (from dataset answer field)
        - entity_keywords: entity names that must appear in headline (e.g. "Rachel")
        - memory_type_filter: required memory_type (e.g. "identity")

        For Q3 (default): answer="the suburbs", entity="Rachel", type=identity.
        Override via question-level fields: recall_match_answer, recall_match_entity,
        recall_match_type.
        """
        question_text = question["question"]
        answer_text = question.get("answer", "")

        # Configurable matching criteria
        answer_keywords = question.get("recall_match_answer", [answer_text.lower()])
        if isinstance(answer_keywords, str):
            answer_keywords = [answer_keywords.lower()]
        else:
            answer_keywords = [k.lower() for k in answer_keywords]

        entity_keywords = question.get("recall_match_entity", [])
        if not entity_keywords:
            # Auto-extract: for Q3 "the suburbs" + "Rachel", derive entity from question
            # Default heuristic: proper nouns from the question
            import re
            proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', question_text)
            # Filter out sentence starters (first word after sentence boundary)
            # Keep nouns that aren't common words
            common_starts = {"where", "what", "when", "how", "who", "why", "did", "does", "do",
                           "is", "are", "was", "were", "has", "have", "had", "the", "after", "her"}
            entity_keywords = [n.lower() for n in proper_nouns if n.lower() not in common_starts]
        elif isinstance(entity_keywords, str):
            entity_keywords = [entity_keywords.lower()]
        else:
            entity_keywords = [k.lower() for k in entity_keywords]

        type_filter = question.get("recall_match_type", "identity")

        print(f"\n  Phase 4: Recall Verification")
        print(f"  Query: {question_text}")
        print(f"  Answer keywords: {answer_keywords}")
        print(f"  Entity keywords: {entity_keywords}")
        print(f"  Type filter: {type_filter}")

        # Call recall endpoint
        recall_start = time.time()
        try:
            response = requests.post(
                f"{API_BASE_URL}/recall",
                headers=HEADERS,
                json={
                    "conversation_context": question_text,
                    "budget_tokens": 8000,  # Large budget to surface more candidates
                    "expand": "evidence",
                },
                timeout=30,
            )
            recall_elapsed = time.time() - recall_start

            if response.status_code != 200:
                print(f"  ERROR: recall returned {response.status_code}")
                return {
                    "recall_status": "error",
                    "recall_http_status": response.status_code,
                    "recall_elapsed": recall_elapsed,
                }

            recall_data = response.json()
        except Exception as e:
            recall_elapsed = time.time() - recall_start
            print(f"  ERROR: recall request failed: {e}")
            return {
                "recall_status": "error",
                "recall_error": str(e),
                "recall_elapsed": recall_elapsed,
            }

        details = recall_data.get("recall_details", [])
        memories_used = recall_data.get("memories_used", 0)
        tokens_used = recall_data.get("tokens_used", 0)

        print(f"  Recalled {memories_used} memories ({tokens_used} tokens) in {recall_elapsed:.2f}s")

        # Find answer-bearing memory
        answer_bearing_rank = None
        answer_bearing_memory = None

        for rank_idx, mem in enumerate(details):
            headline_lower = mem.get("headline", "").lower()
            mem_type = mem.get("memory_type", "")

            # Check all criteria
            answer_match = all(kw in headline_lower for kw in answer_keywords)
            entity_match = all(kw in headline_lower for kw in entity_keywords) if entity_keywords else True
            type_match = (mem_type == type_filter) if type_filter else True

            if answer_match and entity_match and type_match:
                answer_bearing_rank = rank_idx + 1  # 1-indexed
                answer_bearing_memory = mem
                break

        # Compute top-20 composite distribution
        top_20 = details[:20]
        top_20_composites = [m.get("composite", 0) for m in top_20]

        if top_20_composites:
            top_20_min = min(top_20_composites)
            top_20_max = max(top_20_composites)
            top_20_spread = top_20_max - top_20_min
            top_20_p50 = sorted(top_20_composites)[len(top_20_composites) // 2]
        else:
            top_20_min = top_20_max = top_20_spread = top_20_p50 = 0

        # Compute recall precision score:
        # 1.0 if answer is rank 1, decreasing linearly.
        # 0.0 if answer not found in recalled set.
        if answer_bearing_rank is not None:
            recall_precision_score = max(0, 1.0 - (answer_bearing_rank - 1) / memories_used)
        else:
            recall_precision_score = 0.0

        # Print top-10 with answer marker
        print(f"\n  Top 10 recalled memories:")
        for i, m in enumerate(details[:10]):
            marker = " <-- ANSWER" if m.get("id") == (answer_bearing_memory or {}).get("id") else ""
            print(f"    {i+1:2d}. [{m.get('composite', 0):.4f}] {m.get('memory_type', ''):12s} "
                  f"{m.get('headline', '')[:70]}{marker}")

        if answer_bearing_rank and answer_bearing_rank > 10:
            m = answer_bearing_memory
            print(f"    ...")
            print(f"    {answer_bearing_rank:2d}. [{m.get('composite', 0):.4f}] {m.get('memory_type', ''):12s} "
                  f"{m.get('headline', '')[:70]} <-- ANSWER")

        # Summary
        print(f"\n  Recall Verification Results:")
        print(f"  answer_bearing_memory_id: {answer_bearing_memory['id'][:8] if answer_bearing_memory else 'NOT_FOUND'}")
        print(f"  answer_bearing_rank: {answer_bearing_rank or 'NOT_FOUND'}")
        print(f"  top_20_composite_spread: {top_20_spread:.4f}")
        print(f"  top_20_composite_range: [{top_20_min:.4f}, {top_20_max:.4f}]")
        print(f"  recall_precision_score: {recall_precision_score:.4f}")

        result = {
            "recall_status": "ok",
            "recall_elapsed": recall_elapsed,
            "memories_used": memories_used,
            "tokens_used": tokens_used,
            "answer_bearing_memory_id": answer_bearing_memory["id"] if answer_bearing_memory else None,
            "answer_bearing_memory_headline": answer_bearing_memory.get("headline") if answer_bearing_memory else None,
            "answer_bearing_memory_type": answer_bearing_memory.get("memory_type") if answer_bearing_memory else None,
            "answer_bearing_memory_composite": answer_bearing_memory.get("composite") if answer_bearing_memory else None,
            "answer_bearing_rank": answer_bearing_rank,
            "recall_precision_score": recall_precision_score,
            "top_20_composite_distribution": {
                "min": top_20_min,
                "max": top_20_max,
                "p50": top_20_p50,
                "spread": top_20_spread,
                "values": top_20_composites,
            },
            "top_10_recalled": [
                {
                    "rank": i + 1,
                    "id": m.get("id", ""),
                    "headline": m.get("headline", ""),
                    "memory_type": m.get("memory_type", ""),
                    "composite": m.get("composite", 0),
                }
                for i, m in enumerate(details[:10])
            ],
            "match_criteria": {
                "answer_keywords": answer_keywords,
                "entity_keywords": entity_keywords,
                "type_filter": type_filter,
            },
        }

        return result

    def run(self, output_path: str = None, recall_only: bool = False):
        """Run Q3 benchmark with submit-all-then-poll pattern.

        If recall_only=True, skip Phases 1-3 (ingestion) and run Phase 4 only.
        """
        print(f"\nRunning Q3 Async Benchmark{'  [recall-only mode]' if recall_only else ''}...")
        print(f"API: {API_BASE_URL}")
        if not recall_only:
            print(f"Concurrency: {self.max_workers} workers")
        print(f"Dataset: {self.dataset_path}")
        print()

        questions = self.load_dataset()

        for question in questions[:1]:  # Q3 = first question only
            question_id = question["question_id"]
            question_text = question["question"]
            haystack_sessions = question["haystack_sessions"]

            print(f"[Q3] {question_id}")
            print(f"  Q: {question_text}")
            print(f"  A: {question.get('answer', 'N/A')}")
            print(f"  Sessions: {len(haystack_sessions)}")

            # Extract all turns
            all_turns = self.extract_turns(haystack_sessions, question_id)
            print(f"  Total turns: {len(all_turns)}")

            # Initialize ingestion metrics (may be skipped in recall-only mode)
            succeeded = []
            failed = []
            results = []
            sessions_results = {}
            submit_elapsed = poll_elapsed = total_elapsed = p50 = p95 = 0

            if not recall_only:
                # PHASE 1: Submit all jobs
                print(f"\n  Phase 1: Submitting {len(all_turns)} jobs...")
                submit_start = time.time()

                job_map = {}  # {job_id: turn_metadata}
                failed_submissions = []

                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {executor.submit(self.submit_job, turn): turn for turn in all_turns}

                    for future in as_completed(futures):
                        job_id, turn_meta = future.result()
                        if job_id:
                            job_map[job_id] = turn_meta
                        else:
                            failed_submissions.append(turn_meta)

                submit_elapsed = time.time() - submit_start
                print(f"  Submitted: {len(job_map)} jobs in {submit_elapsed:.1f}s")
                if failed_submissions:
                    print(f"  Failed to submit: {len(failed_submissions)}")

                # PHASE 2: Poll all jobs
                print(f"\n  Phase 2: Polling {len(job_map)} jobs...")
                poll_start = time.time()

                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {executor.submit(self.poll_job, job_id, turn_meta): job_id
                              for job_id, turn_meta in job_map.items()}

                    for future in as_completed(futures):
                        result = future.result()
                        results.append(result)

                # Add failed submissions to results
                for turn_meta in failed_submissions:
                    results.append({
                        **turn_meta,
                        "status": "failed",
                        "elapsed": 0
                    })

                poll_elapsed = time.time() - poll_start
                total_elapsed = time.time() - submit_start

                # PHASE 3: Aggregate
                succeeded = [r for r in results if r.get("status") == "complete"]
                failed = [r for r in results if r.get("status") != "complete"]

                # Calculate percentiles
                if succeeded:
                    elapsed_times = sorted([r["elapsed"] for r in succeeded])
                    p50 = elapsed_times[len(elapsed_times) // 2]
                    p95 = elapsed_times[int(len(elapsed_times) * 0.95)]

                # Group by session
                for r in results:
                    session_idx = r["session_idx"]
                    if session_idx not in sessions_results:
                        sessions_results[session_idx] = []
                    sessions_results[session_idx].append(r)

                print(f"\n  Phase 3: Results")
                print(f"  Polling completed in {poll_elapsed:.1f}s")
                print(f"  Total wall-clock: {total_elapsed:.1f}s")
                print(f"  Succeeded: {len(succeeded)}/{len(results)}")
                print(f"  Failed: {len(failed)}")
                print(f"  Turn latency: p50={p50:.1f}s, p95={p95:.1f}s")

                # Check for failure threshold
                failure_rate = len(failed) / len(results) if results else 1.0
                if failure_rate > 0.1:
                    print(f"\n  FAILED: High failure rate ({failure_rate*100:.1f}%)")
                    sys.exit(1)
            else:
                print("\n  Phases 1-3 skipped (recall-only mode)")

            # PHASE 4: Recall Verification
            recall_result = self.recall_verification(question)

            # Write output
            if output_path:
                output_data = {
                    "question_id": question_id,
                    "question": question_text,
                    "answer": question.get("answer", ""),
                    "total_sessions": len(haystack_sessions),
                    "total_turns": len(all_turns),
                    "recall_only": recall_only,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                # Ingestion metrics (Phases 1-3)
                if not recall_only:
                    output_data.update({
                        "succeeded": len(succeeded),
                        "failed": len(failed),
                        "wall_clock_seconds": total_elapsed,
                        "submit_phase_seconds": submit_elapsed,
                        "poll_phase_seconds": poll_elapsed,
                        "turn_latency_p50": p50,
                        "turn_latency_p95": p95,
                        "sessions": sessions_results,
                    })

                # Recall verification metrics (Phase 4)
                output_data["recall_verification"] = recall_result

                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)

                with open(output_file, "w") as f:
                    json.dump(output_data, f, indent=2)

                print(f"\n  Results written to: {output_file}")

        print(f"\n  Q3 benchmark completed successfully")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Q3 Single-Question Async Benchmark Runner")
    parser.add_argument("dataset", help="Path to dataset JSON file")
    parser.add_argument("-o", "--output", help="Output path for results JSON")
    parser.add_argument("--recall-only", action="store_true",
                        help="Skip ingestion (Phases 1-3), run recall verification (Phase 4) only")
    parser.add_argument("--max-workers", type=int, default=16,
                        help="Max concurrent workers for ingestion (default: 16)")
    args = parser.parse_args()

    if not Path(args.dataset).exists():
        print(f"ERROR: Dataset not found: {args.dataset}", file=sys.stderr)
        sys.exit(1)

    runner = BenchmarkRunner(args.dataset, max_workers=args.max_workers)
    runner.run(output_path=args.output, recall_only=args.recall_only)
