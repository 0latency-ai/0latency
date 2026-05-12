#!/usr/bin/env python3
"""
Q3 Single-Question Async Benchmark Runner

Submit-all-then-poll architecture eliminates thread starvation.

Runs against local API (localhost:8420) to bypass edge rate limiting.
For production smoke tests, override API_BASE_URL env var.
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Tuple
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
    
    def run(self, output_path: str = None):
        """Run Q3 benchmark with submit-all-then-poll pattern."""
        print(f"\\nRunning Q3 Async Benchmark...")
        print(f"API: {API_BASE_URL}")
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
            print(f"  Sessions: {len(haystack_sessions)}")
            
            # Extract all turns
            all_turns = self.extract_turns(haystack_sessions, question_id)
            print(f"  Total turns: {len(all_turns)}")
            
            # PHASE 1: Submit all jobs
            print(f"\\n  Phase 1: Submitting {len(all_turns)} jobs...")
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
            print(f"\\n  Phase 2: Polling {len(job_map)} jobs...")
            poll_start = time.time()
            
            results = []
            
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
            
            # PHASE 3: Aggregate and output
            succeeded = [r for r in results if r.get("status") == "complete"]
            failed = [r for r in results if r.get("status") != "complete"]
            
            # Calculate percentiles
            if succeeded:
                elapsed_times = sorted([r["elapsed"] for r in succeeded])
                p50 = elapsed_times[len(elapsed_times) // 2]
                p95 = elapsed_times[int(len(elapsed_times) * 0.95)]
            else:
                p50 = p95 = 0
            
            # Group by session
            sessions_results = {}
            for r in results:
                session_idx = r["session_idx"]
                if session_idx not in sessions_results:
                    sessions_results[session_idx] = []
                sessions_results[session_idx].append(r)
            
            print(f"\\n  Phase 3: Results")
            print(f"  Polling completed in {poll_elapsed:.1f}s")
            print(f"  Total wall-clock: {total_elapsed:.1f}s")
            print(f"  Succeeded: {len(succeeded)}/{len(results)}")
            print(f"  Failed: {len(failed)}")
            print(f"  Turn latency: p50={p50:.1f}s, p95={p95:.1f}s")
            
            # Write output
            if output_path:
                output_data = {
                    "question_id": question_id,
                    "question": question_text,
                    "total_sessions": len(haystack_sessions),
                    "total_turns": len(results),
                    "succeeded": len(succeeded),
                    "failed": len(failed),
                    "wall_clock_seconds": total_elapsed,
                    "submit_phase_seconds": submit_elapsed,
                    "poll_phase_seconds": poll_elapsed,
                    "turn_latency_p50": p50,
                    "turn_latency_p95": p95,
                    "sessions": sessions_results,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file, "w") as f:
                    json.dump(output_data, f, indent=2)
                
                print(f"\\n  Results written to: {output_file}")
            
            # Check for failure threshold
            failure_rate = len(failed) / len(results) if results else 1.0
            if failure_rate > 0.1:
                print(f"\\n✗ FAILED: High failure rate ({failure_rate*100:.1f}%)")
                sys.exit(1)
        
        print(f"\\n✓ Q3 benchmark completed successfully")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <dataset.json> [-o OUTPUT]")
        sys.exit(1)
    
    dataset_path = sys.argv[1]
    output_path = None
    
    if len(sys.argv) > 3 and sys.argv[2] == "-o":
        output_path = sys.argv[3]
    
    if not Path(dataset_path).exists():
        print(f"ERROR: Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)
    
    runner = BenchmarkRunner(dataset_path, max_workers=16)
    runner.run(output_path=output_path)
