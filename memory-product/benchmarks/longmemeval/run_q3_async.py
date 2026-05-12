#!/usr/bin/env python3
"""
Q3 Single-Question Async Benchmark Runner

Runs against local API (localhost:8420) to bypass edge rate limiting.
For production smoke tests, override API_BASE_URL env var.

Features:
- Async /memories/extract endpoint with job polling
- Sequential processing (no concurrency for simplicity)
- Circuit breaker for degraded API
- Retry logic for transient errors
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8420")
API_KEY = os.getenv("API_KEY")
TENANT_ID = os.getenv("TENANT_ID")

if not API_KEY or not TENANT_ID:
    print("ERROR: Set API_KEY and TENANT_ID environment variables", file=sys.stderr)
    print("  export API_KEY=zl_live_...", file=sys.stderr)
    print("  export TENANT_ID=...", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}

class BenchmarkRunner:
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.consecutive_failures = 0
        self.total_turns = 0
        self.total_failed = 0
        
    def load_dataset(self) -> List[Dict]:
        """Load Q3 dataset."""
        with open(self.dataset_path) as f:
            data = json.load(f)
        print(f"Loaded {len(data)} questions from {self.dataset_path.name}")
        return data
    
    def submit_extraction_job(self, payload: Dict) -> Tuple[str, str, int]:
        """Submit extraction job to async endpoint. Returns (job_id, error, status_code)."""
        max_retries = 3
        
        for attempt in range(max_retries):
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
                elif response.status_code in (429, 502, 503, 520, 524):
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    return None, f"status_{response.status_code}", response.status_code
                else:
                    return None, f"status_{response.status_code}", response.status_code
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                return None, "timeout", 0
            except Exception as e:
                return None, str(e), 0
        
        return None, "max_retries_exceeded", 0
    
    def poll_job_completion(self, job_id: str, max_wait: int = 120) -> Tuple[bool, str]:
        """Poll job until complete or timeout. Returns (success, error)."""
        start = time.time()
        
        while time.time() - start < max_wait:
            try:
                response = requests.get(
                    f"{API_BASE_URL}/memories/extract/{job_id}",
                    headers=HEADERS,
                    timeout=5
                )
                
                if response.status_code != 200:
                    return False, f"poll_status_{response.status_code}"
                
                data = response.json()
                status = data.get("status")
                
                if status == "complete":
                    return True, None
                elif status == "failed":
                    return False, f"job_failed: {data.get(error, unknown)}"
                
                # Still processing, wait before next poll
                time.sleep(1)
            except Exception as e:
                return False, str(e)
        
        return False, "timeout"
    
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
                "content": f"Human: {user_turn['content']}\\n\\nAssistant: {assistant_turn['content']}",
                "session_key": f"longmemeval_{question_id}_session_{session_idx}"
            }
            
            # Submit job
            job_id, error, status_code = self.submit_extraction_job(payload)
            
            if not job_id:
                failed_count += 1
                self.consecutive_failures += 1
                print(f"  WARN: Failed to submit job: {error}", file=sys.stderr)
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
                print(f"  WARN: Job {job_id} failed: {poll_error}", file=sys.stderr)
            
            # Circuit breaker
            if self.consecutive_failures >= 5:
                print(f"\\n✗ CIRCUIT BREAKER: 5 consecutive failures", file=sys.stderr)
                print(f"API appears degraded. Aborting to prevent hang.", file=sys.stderr)
                raise RuntimeError("Circuit breaker tripped")
            
            i += 2
        
        return turn_count, failed_count
    
    def run(self):
        """Run Q3 benchmark."""
        print(f"\\nRunning Q3 Async Benchmark...")
        print(f"API: {API_BASE_URL}")
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
            
            for session_idx, session in enumerate(haystack_sessions):
                try:
                    turn_count, failed_count = self.extract_session(session, session_idx, question_id)
                    self.total_turns += turn_count
                    self.total_failed += failed_count
                    
                    if (session_idx + 1) % 10 == 0 or session_idx == len(haystack_sessions) - 1:
                        print(f"  Progress: {session_idx + 1}/{len(haystack_sessions)} sessions", file=sys.stderr)
                except RuntimeError as e:
                    print(f"  ERROR: {e}", file=sys.stderr)
                    sys.exit(1)
            
            elapsed = time.time() - start
            print(f"\\n  Extracted {len(haystack_sessions)} sessions in {elapsed:.1f}s")
            print(f"  Total turns: {self.total_turns}, Failed: {self.total_failed}")
            
            if self.total_failed > 0:
                failure_rate = (self.total_failed / (self.total_turns + self.total_failed)) * 100
                print(f"  Failure rate: {failure_rate:.1f}%")
            
            if self.total_failed > len(haystack_sessions) * 0.1:
                print(f"\\n✗ FAILED: Too many extraction failures ({self.total_failed})")
                sys.exit(1)
        
        print(f"\\n✓ Q3 benchmark completed successfully")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <dataset.json>")
        print(f"Example: {sys.argv[0]} single_q3.json")
        sys.exit(1)
    
    dataset_path = sys.argv[1]
    
    if not Path(dataset_path).exists():
        print(f"ERROR: Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)
    
    runner = BenchmarkRunner(dataset_path)
    runner.run()
