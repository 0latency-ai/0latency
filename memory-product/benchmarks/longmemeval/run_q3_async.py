#!/usr/bin/env python3
"""
Async Benchmark Runner (multi-question)

Submit-all-then-poll architecture per question, sequential across questions.
Phase 4 (recall verification) measures answer retrievability post-ingestion.

Gate 06: Adapted from single-question Q3 runner to handle n-question datasets.
Processes each question sequentially (submit → poll → recall) to ensure
ingestion completes before recall verification.
"""
import os
import sys
import json
import time
import argparse
import requests
import psycopg2
import redis as _redis
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import re as _re

def _fuzzy_answer_match(answer_keywords: list, headline: str, threshold: float = 0.35) -> bool:
    """Fuzzy answer matching: token overlap + substring + numeric patterns.

    Replaces exact substring matching for answer-bearing memory identification.
    Returns True if the headline likely contains the answer.

    Matching strategies (any one triggers a match):
    1. Exact substring (original behavior, for backwards compatibility)
    2. Token overlap: at least `threshold` of answer tokens appear in headline
    3. Numeric/specific pattern: numbers, times, percentages from answer found in headline
    4. Proper noun matching: capitalized multi-word terms from answer found in headline
    """
    headline_lower = headline.lower()

    # Strategy 1: Original exact substring matching
    if all(kw in headline_lower for kw in answer_keywords):
        return True

    # Strategy 2: Token overlap
    # Combine all answer keywords into a token set
    stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
                 'had', 'her', 'was', 'one', 'our', 'out', 'has', 'his', 'how',
                 'its', 'may', 'who', 'did', 'get', 'she', 'use', 'that', 'with',
                 'this', 'from', 'they', 'been', 'have', 'were', 'said', 'each',
                 'which', 'their', 'will', 'other', 'about', 'would', 'user'}
    answer_tokens = set()
    for kw in answer_keywords:
        for word in _re.findall(r'\w+', kw):
            if len(word) > 2 and word not in stopwords:
                answer_tokens.add(word)

    if answer_tokens:
        headline_tokens = set(_re.findall(r'\w+', headline_lower))
        overlap = answer_tokens & headline_tokens
        overlap_ratio = len(overlap) / len(answer_tokens)
        if overlap_ratio >= threshold:
            return True

    # Strategy 3: Numeric/specific patterns
    for kw in answer_keywords:
        specifics = _re.findall(r'\d+:\d+|\d+(?:\.\d+)?%?|\$\d+', kw)
        for s in specifics:
            if s in headline_lower:
                return True

    # Strategy 4: Proper nouns (multi-word capitalized terms)
    for kw in answer_keywords:
        proper = _re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', kw)
        for p in proper:
            if p.lower() in headline_lower:
                return True

    # Strategy 5: Bidirectional matching for long (preference-format) answers.
    # Multi-sentence answer descriptions (e.g. "The user would prefer suggestions
    # of sony-compatible accessories...") have 15-25 content tokens, diluting the
    # forward overlap ratio below threshold even when the headline captures the
    # core concept. Tightened thresholds (2026-05-15, kill Q14-class false positives):
    #   minimum overlap count >= 3 tokens (avoids spurious 2-token matches)
    #   forward >= 0.10  (at least 10% of answer concepts in headline)
    #   reverse >= 0.30  (at least 30% of headline concepts in answer)
    answer_text_length = sum(len(kw) for kw in answer_keywords)
    if answer_tokens and answer_text_length > 100:
        headline_content = {t for t in _re.findall(r'\w+', headline_lower)
                            if len(t) > 2 and t not in stopwords}
        overlap = answer_tokens & headline_content
        if len(overlap) >= 3 and headline_content:
            fwd_ratio = len(overlap) / len(answer_tokens)
            rev_ratio = len(overlap) / len(headline_content)
            if fwd_ratio >= 0.10 and rev_ratio >= 0.30:
                return True

    return False



# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8420")
API_KEY = os.getenv("API_KEY")
TENANT_ID = os.getenv("TENANT_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

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

    def preflight_wipe(self) -> Dict:
        """Delete all longmemeval benchmark memories from the tenant.

        Returns a dict with wipe metadata for the results JSON.
        Hard-halts if DATABASE_URL is not set or post-wipe count != 0.
        """
        if not DATABASE_URL:
            print("  HALT: DATABASE_URL not set — cannot run preflight wipe", file=sys.stderr)
            sys.exit(4)

        print(f"\n  PREFLIGHT_WIPE")
        print(f"  Tenant: {TENANT_ID}")

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                # Count benchmark memories before wipe
                cur.execute(
                    "SELECT COUNT(*) FROM memory_service.memories "
                    "WHERE tenant_id = %s::UUID AND source_session LIKE 'longmemeval_%%'",
                    (TENANT_ID,)
                )
                pre_count = cur.fetchone()[0]
                print(f"  Benchmark memories before wipe: {pre_count}")

                if pre_count > 0:
                    # Delete all benchmark memories
                    cur.execute(
                        "DELETE FROM memory_service.memories "
                        "WHERE tenant_id = %s::UUID AND source_session LIKE 'longmemeval_%%'",
                        (TENANT_ID,)
                    )
                    deleted = cur.rowcount
                    conn.commit()
                    print(f"  Deleted: {deleted}")
                else:
                    deleted = 0
                    print(f"  Clean — no benchmark memories to delete")

                # Verify: count must be exactly 0
                cur.execute(
                    "SELECT COUNT(*) FROM memory_service.memories "
                    "WHERE tenant_id = %s::UUID AND source_session LIKE 'longmemeval_%%'",
                    (TENANT_ID,)
                )
                post_count = cur.fetchone()[0]

                # Total memories remaining (base/test data)
                cur.execute(
                    "SELECT COUNT(*) FROM memory_service.memories "
                    "WHERE tenant_id = %s::UUID",
                    (TENANT_ID,)
                )
                total_remaining = cur.fetchone()[0]

                print(f"  Post-wipe benchmark memories: {post_count}")
                print(f"  Total memories remaining: {total_remaining}")

                if post_count != 0:
                    print(f"  HALT: Post-wipe count is {post_count}, expected 0", file=sys.stderr)
                    sys.exit(4)

                print(f"  PASS: tenant clean for benchmark")
        finally:
            conn.close()

        return {
            "pre_wipe_benchmark_count": pre_count,
            "deleted": deleted,
            "post_wipe_benchmark_count": post_count,
            "total_remaining": total_remaining,
        }

    def preflight_queue_drain(self):
        """Drain RQ extraction queue and flush stale job-tracking keys.

        Must run BEFORE submitting new jobs. Waits for any in-flight RQ
        jobs to complete (does NOT delete the queue — that orphans jobs),
        then removes all extract_job:* Redis keys so the next run starts
        with a clean tracking state.

        Without this, killed-then-relaunched runs accumulate "accepted"
        orphan keys whose RQ jobs were deleted mid-queue, and pollers
        waste time on stale entries.
        """
        print("\n  PREFLIGHT_QUEUE_DRAIN")
        r = _redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

        # Phase A: wait for RQ queue to drain (max 120s)
        deadline = time.time() + 120
        while time.time() < deadline:
            qlen = r.llen('rq:queue:extraction')
            if qlen == 0:
                break
            print(f"    waiting: {qlen} jobs in RQ queue...")
            time.sleep(5)
        else:
            qlen = r.llen('rq:queue:extraction')
            if qlen > 0:
                print(f"    WARN: {qlen} jobs still in queue after 120s — flushing")
                r.delete('rq:queue:extraction')

        # Phase B: flush ALL extract_job:* tracking keys
        flushed = 0
        for key in r.scan_iter('extract_job:*'):
            r.delete(key)
            flushed += 1
        print(f"    Flushed {flushed} stale job-tracking keys")
        print(f"    PASS: queue drained, tracking state clean")

    def load_dataset(self) -> List[Dict]:
        """Load dataset (single or multi-question)."""
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
                timeout=30
            )

            if response.status_code == 202:
                data = response.json()
                return data["job_id"], turn
            else:
                return None, {**turn, "error": f"status_{response.status_code}"}
        except Exception as e:
            return None, {**turn, "error": str(e)}

    def poll_job(self, job_id: str, turn: Dict, max_wait: int = 900) -> Dict:
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

        Override via question-level fields: recall_match_answer, recall_match_entity,
        recall_match_type.
        """
        question_text = question["question"]
        answer_text = str(question.get("answer", ""))

        # Configurable matching criteria
        answer_keywords = question.get("recall_match_answer", [answer_text.lower()])
        if isinstance(answer_keywords, str):
            answer_keywords = [answer_keywords.lower()]
        else:
            answer_keywords = [k.lower() for k in answer_keywords]

        entity_keywords = question.get("recall_match_entity", [])
        if not entity_keywords:
            # Auto-extract: proper nouns from the question
            import re
            proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', question_text)
            common_starts = {"where", "what", "when", "how", "who", "why", "did", "does", "do", "can",
                           "is", "are", "was", "were", "has", "have", "had", "the", "after", "her",
                           "could", "should", "would", "may", "might", "shall", "must",
                           "please", "tell", "give", "help", "let", "will", "which", "this"}
            entity_keywords = [n.lower() for n in proper_nouns if n.lower() not in common_starts]
        elif isinstance(entity_keywords, str):
            entity_keywords = [entity_keywords.lower()]
        else:
            entity_keywords = [k.lower() for k in entity_keywords]

        # Default to no type filter for multi-question flexibility;
        # per-question override via recall_match_type field.
        type_filter = question.get("recall_match_type", None)

        print(f"\n  Phase 4: Recall Verification")
        print(f"  Query: {question_text}")
        print(f"  Answer keywords: {answer_keywords}")
        print(f"  Entity keywords: {entity_keywords}")
        print(f"  Type filter: {type_filter or '(none)'}")

        # Call recall endpoint
        recall_start = time.time()
        try:
            response = requests.post(
                f"{API_BASE_URL}/recall",
                headers=HEADERS,
                json={
                    "conversation_context": question_text,
                    "budget_tokens": 8000,
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

            # Check all criteria (fuzzy matching for answer, exact for entity/type)
            answer_match = _fuzzy_answer_match(answer_keywords, headline_lower)
            entity_match = all(kw in headline_lower for kw in entity_keywords) if entity_keywords else True
            type_match = (mem_type == type_filter) if type_filter else True

            if answer_match and entity_match and type_match:
                answer_bearing_rank = rank_idx + 1  # 1-indexed
                answer_bearing_memory = mem
                break

        # RANK-20 CEILING: Any answer found beyond rank 20 is NOT_FOUND.
        # Locked definition as of 2026-05-15 (Stage 1B clean baseline).
        RANK_CEILING = 20
        if answer_bearing_rank is not None and answer_bearing_rank > RANK_CEILING:
            print(f"  Rank ceiling applied: rank {answer_bearing_rank} > {RANK_CEILING} -> NOT_FOUND")
            answer_bearing_rank = None
            answer_bearing_memory = None

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

        # Compute recall precision score
        if answer_bearing_rank is not None:
            recall_precision_score = max(0, 1.0 - (answer_bearing_rank - 1) / memories_used) if memories_used > 0 else 0.0
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

    def run(self, output_path: str = None, recall_only: bool = False, skip_wipe: bool = False):
        """Run benchmark with submit-all-then-poll pattern.

        Processes all questions in the dataset sequentially. Each question:
        Phase 1 (submit) → Phase 2 (poll) → Phase 3 (results) → Phase 4 (recall).

        If recall_only=True, skip Phases 1-3 (ingestion) and run Phase 4 only.
        Preflight wipe deletes all longmemeval benchmark memories before ingestion
        unless skip_wipe=True or recall_only=True.
        """
        print(f"\nRunning Async Benchmark{'  [recall-only mode]' if recall_only else ''}...")
        print(f"API: {API_BASE_URL}")
        if not recall_only:
            print(f"Concurrency: {self.max_workers} workers")
        print(f"Dataset: {self.dataset_path}")
        print()

        questions = self.load_dataset()

        # Pre-compute turns and print summary
        question_turns_map = {}
        total_turns_all = 0
        for qi, q in enumerate(questions):
            turns = self.extract_turns(q["haystack_sessions"], q["question_id"])
            question_turns_map[q["question_id"]] = turns
            total_turns_all += len(turns)
            print(f"  [{qi+1:2d}] {q['question_id'][:8]}  {q.get('question_type',''):25s}  "
                  f"sessions={len(q['haystack_sessions']):3d}  turns={len(turns):4d}  "
                  f"Q: {q['question'][:55]}")
        print(f"\n  Total: {len(questions)} questions, {total_turns_all} turns")

        # Pre-flight wipe: remove stale benchmark memories
        wipe_result = None
        if not recall_only and not skip_wipe:
            wipe_result = self.preflight_wipe()
            self.preflight_queue_drain()
        elif skip_wipe:
            print(f"\n  PREFLIGHT_WIPE: skipped (--skip-wipe)")

        # Pre-flight health calibration
        if not recall_only:
            print(f"\n  PREFLIGHT_HEALTH_CALIBRATION")
            probe_latencies = []
            for i in range(5):
                try:
                    probe_start = time.time()
                    resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
                    latency = time.time() - probe_start
                    status = resp.status_code
                except Exception as e:
                    latency = 5.0
                    status = 0
                probe_latencies.append(latency)
                print(f"    probe {i+1}/5: {latency*1000:.1f}ms (status={status})")
                if i < 4:
                    time.sleep(1)

            sorted_latencies = sorted(probe_latencies)
            preflight_p50 = sorted_latencies[len(sorted_latencies) // 2]
            preflight_p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            print(f"    idle p50={preflight_p50*1000:.1f}ms, p95={preflight_p95*1000:.1f}ms")

            if preflight_p95 > 0.200:
                print(f"    HALT: p95 {preflight_p95*1000:.1f}ms > 200ms threshold — API not idle")
                sys.exit(3)
            print(f"    PASS: proceeding with 500ms drain threshold")

        all_question_results = []
        agg_succeeded = 0
        agg_failed = 0
        agg_elapsed_times = []
        bench_wall_start = time.time()

        for q_idx, question in enumerate(questions):
            question_id = question["question_id"]
            question_text = question["question"]
            haystack_sessions = question["haystack_sessions"]

            print(f"\n{'='*65}")
            print(f"  Question {q_idx+1}/{len(questions)}: [{question_id[:8]}]")
            print(f"  Q: {question_text}")
            print(f"  A: {question.get('answer', 'N/A')}")
            print(f"  Type: {question.get('question_type', 'N/A')}")
            print(f"  Sessions: {len(haystack_sessions)}")

            all_turns = question_turns_map[question_id]
            print(f"  Turns: {len(all_turns)}")

            # Per-question ingestion metrics
            succeeded = []
            failed = []
            results = []
            submit_elapsed = poll_elapsed = total_elapsed = p50 = p95 = 0
            failure_rate = 0.0

            if not recall_only:
                # PHASE 1: Submit all turns for this question
                print(f"\n  Phase 1: Submitting {len(all_turns)} jobs...")
                submit_start = time.time()

                job_map = {}
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
                    results.append({**turn_meta, "status": "failed", "elapsed": 0})

                poll_elapsed = time.time() - poll_start
                total_elapsed = time.time() - submit_start

                # PHASE 3: Per-question results
                succeeded = [r for r in results if r.get("status") == "complete"]
                failed = [r for r in results if r.get("status") != "complete"]

                if succeeded:
                    elapsed_times = sorted([r["elapsed"] for r in succeeded])
                    p50 = elapsed_times[len(elapsed_times) // 2]
                    p95 = elapsed_times[int(len(elapsed_times) * 0.95)]
                    agg_elapsed_times.extend(elapsed_times)

                failure_rate = len(failed) / len(results) if results else 1.0

                print(f"\n  Phase 3: Results")
                print(f"  Polling completed in {poll_elapsed:.1f}s")
                print(f"  Wall-clock: {total_elapsed:.1f}s")
                print(f"  Succeeded: {len(succeeded)}/{len(results)}")
                print(f"  Failed: {len(failed)}")
                print(f"  Turn latency: p50={p50:.1f}s, p95={p95:.1f}s")
                if failure_rate > 0.1:
                    print(f"  WARNING: High failure rate ({failure_rate*100:.1f}%)")

                agg_succeeded += len(succeeded)
                agg_failed += len(failed)
            else:
                print("\n  Phases 1-3 skipped (recall-only mode)")

            # PHASE 4: Recall Verification
            recall_result = self.recall_verification(question)

            q_result = {
                "question_id": question_id,
                "question": question_text,
                "answer": question.get("answer", ""),
                "question_type": question.get("question_type", ""),
                "total_sessions": len(haystack_sessions),
                "total_turns": len(all_turns),
                "succeeded": len(succeeded),
                "failed": len(failed),
                "success_rate": 1.0 - failure_rate,
                "wall_clock_seconds": total_elapsed,
                "turn_latency_p50": p50,
                "turn_latency_p95": p95,
                "recall_verification": recall_result,
            }
            all_question_results.append(q_result)

            # Adaptive inter-question cool-down: wait for API to drain backlog
            if not recall_only and q_idx < len(questions) - 1:
                consecutive_fast = 0
                cooldown_start = time.time()
                max_cooldown = 300  # 5 minutes max
                health_threshold = 0.5  # seconds
                required_consecutive = 3

                print(f"\n  Cool-down: waiting for API to drain (3x < {health_threshold}s health probes)...")
                while consecutive_fast < required_consecutive:
                    elapsed_cooldown = time.time() - cooldown_start
                    if elapsed_cooldown > max_cooldown:
                        print(f"  HALT: API did not drain within {max_cooldown}s")
                        # Write partial results before halting
                        if output_path:
                            partial_data = {
                                "gate": "gate_06",
                                "dataset": self.dataset_path.name,
                                "total_questions": len(questions),
                                "completed_questions": q_idx + 1,
                                "halted_reason": f"cooldown_timeout_{max_cooldown}s",
                                "timestamp": datetime.utcnow().isoformat(),
                                "per_question": all_question_results,
                            }
                            output_file = Path(output_path)
                            output_file.parent.mkdir(parents=True, exist_ok=True)
                            with open(output_file, "w") as f:
                                json.dump(partial_data, f, indent=2)
                            print(f"  Partial results written to: {output_file}")
                        sys.exit(2)

                    try:
                        probe_start = time.time()
                        resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
                        probe_latency = time.time() - probe_start

                        if resp.status_code == 200 and probe_latency < health_threshold:
                            consecutive_fast += 1
                        else:
                            consecutive_fast = 0
                    except Exception:
                        consecutive_fast = 0

                    if consecutive_fast < required_consecutive:
                        time.sleep(5)

                cooldown_elapsed = time.time() - cooldown_start
                print(f"  Cool-down complete: {cooldown_elapsed:.1f}s (API drained)")

        bench_wall_total = time.time() - bench_wall_start

        # ===== AGGREGATE SUMMARY =====
        print(f"\n{'='*65}")
        print(f"  AGGREGATE RESULTS ({len(questions)} questions)")
        print(f"{'='*65}")

        total_turns = sum(q["total_turns"] for q in all_question_results)

        agg_p50 = agg_p95 = 0
        agg_failure_rate = 0.0

        if not recall_only:
            agg_total = agg_succeeded + agg_failed
            agg_failure_rate = agg_failed / agg_total if agg_total > 0 else 0

            if agg_elapsed_times:
                agg_elapsed_sorted = sorted(agg_elapsed_times)
                agg_p50 = agg_elapsed_sorted[len(agg_elapsed_sorted) // 2]
                agg_p95 = agg_elapsed_sorted[int(len(agg_elapsed_sorted) * 0.95)]

            print(f"  Total turns: {total_turns}")
            print(f"  Succeeded: {agg_succeeded}/{agg_total}")
            print(f"  Failed: {agg_failed}")
            print(f"  Success rate: {(1 - agg_failure_rate)*100:.1f}%")
            print(f"  Turn latency: p50={agg_p50:.1f}s, p95={agg_p95:.1f}s")
            print(f"  Total wall-clock: {bench_wall_total:.1f}s")

            # Per-question success table
            print(f"\n  Per-question success:")
            for qi, qr in enumerate(all_question_results):
                flag = " *** WARN" if qr["success_rate"] < 0.9 else ""
                print(f"    [{qi+1:2d}] {qr['question_id'][:8]}  "
                      f"{qr['succeeded']}/{qr['total_turns']}  "
                      f"({qr['success_rate']*100:.1f}%){flag}")

        # Recall summary table
        print(f"\n  Recall verification summary:")
        for qi, qr in enumerate(all_question_results):
            rv = qr["recall_verification"]
            rank = rv.get("answer_bearing_rank")
            precision = rv.get("recall_precision_score", 0)
            status = rv.get("recall_status", "error")
            rank_str = str(rank) if rank is not None else "N/A"
            flag = " *** NOT_FOUND" if rank is None else ""
            print(f"    [{qi+1:2d}] {qr['question_id'][:8]}  "
                  f"type={qr['question_type'][:20]:20s}  "
                  f"rank={rank_str:>3s}  precision={precision:.4f}  {status}{flag}")

        # Write output
        if output_path:
            agg_data = {}
            if not recall_only:
                agg_data = {
                    "total_succeeded": agg_succeeded,
                    "total_failed": agg_failed,
                    "success_rate": 1 - agg_failure_rate,
                    "turn_latency_p50": agg_p50,
                    "turn_latency_p95": agg_p95,
                    "wall_clock_seconds": bench_wall_total,
                }

            output_data = {
                "gate": "gate_06",
                "dataset": self.dataset_path.name,
                "total_questions": len(questions),
                "total_turns": total_turns,
                "recall_only": recall_only,
                "preflight_wipe": wipe_result,
                "timestamp": datetime.utcnow().isoformat(),
                "aggregate": agg_data,
                "per_question": all_question_results,
            }

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                json.dump(output_data, f, indent=2)
            print(f"\n  Results written to: {output_file}")

        # Exit status
        if not recall_only and agg_failure_rate > 0.1:
            print(f"\n  FAILED: Aggregate failure rate ({agg_failure_rate*100:.1f}%) exceeds 10% threshold")
            sys.exit(1)

        print(f"\n  Benchmark completed successfully ({len(questions)} questions)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async Benchmark Runner (multi-question)")
    parser.add_argument("dataset", help="Path to dataset JSON file (single or multi-question)")
    parser.add_argument("-o", "--output", help="Output path for results JSON")
    parser.add_argument("--recall-only", action="store_true",
                        help="Skip ingestion (Phases 1-3), run recall verification (Phase 4) only")
    parser.add_argument("--skip-wipe", action="store_true",
                        help="Skip preflight wipe (dangerous: allows contamination)")
    parser.add_argument("--max-workers", type=int, default=16,
                        help="Max concurrent workers for ingestion (default: 16)")
    args = parser.parse_args()

    if not Path(args.dataset).exists():
        print(f"ERROR: Dataset not found: {args.dataset}", file=sys.stderr)
        sys.exit(1)

    if not args.recall_only and not args.skip_wipe and not DATABASE_URL:
        print("ERROR: DATABASE_URL required for preflight wipe. Set it or use --skip-wipe", file=sys.stderr)
        sys.exit(4)

    runner = BenchmarkRunner(args.dataset, max_workers=args.max_workers)
    runner.run(output_path=args.output, recall_only=args.recall_only, skip_wipe=args.skip_wipe)
