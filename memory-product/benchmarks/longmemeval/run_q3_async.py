#!/usr/bin/env python3
"""
Q3 Single-Question Async Benchmark Runner

Runs against local API (localhost:8420) to bypass edge rate limiting.
For production smoke tests, override API_BASE_URL env var.

Thin client: Workers + API handle retry. Benchmark just submits and polls.
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    def __init__(self, dataset_path: str, max_workers: int = 8):
        self.dataset_path = Path(dataset_path)
        self.max_workers = max_workers
        self.total_turns = 0
        self.total_failed = 0
        self.job_times = []
        
    def load_dataset(self) -> List[Dict]:
        """Load Q3 dataset."""
        with open(self.dataset_path) as f:
            data = json.load(f)
        print(f"Loaded {len(data)} questions from {self.dataset_path.name}")
        return data
    
    def submit_extraction_job(self, payload: Dict) -> Tuple[str, str, int]:
        """Submit extraction job. Returns (job_id, error, status_code). No retry."""
        try:
            response = requests.post(
                f"{API_BASE_URL}/memories/extract",
                headers=HEADERS,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 202:
                data = response.json()
                return data["job_id"], None, 202
            else:
                return None, f"status_{response.status_code}", response.status_code
        except Exception as e:
            return None, str(e), 0
    
    def poll_job_completion(self, job_id: str, max_wait: int = 180) -> Tuple[bool, str, float]:
        """Poll job until complete or timeout. Returns (success, error, elapsed_seconds)."""
        start = time.time()
        
        while time.time() - start < max_wait:
            try:
                response = requests.get(
                    f"{API_BASE_URL}/memories/extract/{job_id}",
                    headers=HEADERS,
                    timeout=5
                )
                
                if response.status_code != 200:
                    elapsed = time.time() - start
                    return False, f"poll_status_{response.status_code}", elapsed
                
                data = response.json()
                status = data.get("status")
                
                if status == "complete":
                    elapsed = time.time() - start
                    return True, None, elapsed
                elif status == "failed":
                    elapsed = time.time() - start
                    return False, f"job_failed: {data.get('error', 'unknown')}", elapsed
                
                time.sleep(1)
            except Exception as e:
                elapsed = time.time() - start
                return False, str(e), elapsed
        
        elapsed = time.time() - start
        return False, "timeout", elapsed
    
    def extract_session(self, session: List[Dict], session_idx: int, question_id: str) -> Tuple[int, int]:
        """Extract memories from one session. Returns (turn_count, failed_count)."""
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
            
            # Submit job (no retry)
            job_id, error, status_code = self.submit_extraction_job(payload)
            
            if not job_id:
                failed_count += 1
                i += 2
                continue
            
            # Poll for completion (180s timeout)
            success, poll_error, elapsed = self.poll_job_completion(job_id)
            
            if success:
                turn_count += 1
                self.job_times.append(elapsed)
            else:
                failed_count += 1
            
            i += 2
        
        return turn_count, failed_count
    
    def run(self):
        """Run Q3 benchmark."""
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
            print(f"  Extracting {len(haystack_sessions)} haystack sessions...")
            
            start = time.time()
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                for session_idx, session in enumerate(haystack_sessions):
                    future = executor.submit(self.extract_session, session, session_idx, question_id)
                    futures[future] = session_idx
                
                for future in as_completed(futures):
                    session_idx = futures[future]
                    try:
                        turn_count, failed_count = future.result()
                        self.total_turns += turn_count
                        self.total_failed += failed_count
                    except Exception as e:
                        print(f"  ERROR session {session_idx}: {e}", file=sys.stderr)
                        self.total_failed += 1
            
            elapsed = time.time() - start
            
            # Calculate percentiles
            if self.job_times:
                sorted_times = sorted(self.job_times)
                p50 = sorted_times[len(sorted_times) // 2]
                p95 = sorted_times[int(len(sorted_times) * 0.95)]
            else:
                p50 = p95 = 0
            
            print(f"\\n  Extracted {len(haystack_sessions)} sessions in {elapsed:.1f}s")
            print(f"  Total turns: {self.total_turns}, Failed: {self.total_failed}")
            print(f"  Job latency: p50={p50:.1f}s, p95={p95:.1f}s")
            
            if self.total_failed > len(haystack_sessions) * 0.1:
                print(f"\\n✗ FAILED: Too many extraction failures ({self.total_failed})")
                sys.exit(1)
        
        print(f"\\n✓ Q3 benchmark completed successfully")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <dataset.json>")
        sys.exit(1)
    
    dataset_path = sys.argv[1]
    
    if not Path(dataset_path).exists():
        print(f"ERROR: Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)
    
    runner = BenchmarkRunner(dataset_path, max_workers=8)
    runner.run()
