#!/usr/bin/env python3
"""Custom rq worker entry that preloads the embedder before entering the job loop.

Forked job children inherit the loaded model via Linux copy-on-write,
eliminating the ~7-8s cold load and ~450MB per-fork overhead.

Usage:
    python3 bin/zerolatency_rq_worker.py

Environment:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379)
"""
import os
import sys
import time

# Add project root and src/ to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from src.embedder import preload_embedder
from redis import Redis
from rq import Worker

if __name__ == "__main__":
    print("[WORKER STARTUP] Preloading SentenceTransformer...", flush=True)
    t = time.time()
    preload_embedder()
    elapsed = time.time() - t
    print(f"[WORKER STARTUP] Embedder preloaded in {elapsed:.2f}s", flush=True)

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    print(f"[WORKER STARTUP] Connecting to Redis: {redis_url}", flush=True)

    redis_conn = Redis.from_url(redis_url)
    print("[WORKER STARTUP] Starting worker for queue: extraction", flush=True)

    worker = Worker(["extraction"], connection=redis_conn)
    worker.work()
