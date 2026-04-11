"""
RQ Worker for async memory extraction jobs.
This module defines the job function that gets executed by RQ workers.
"""
import os
import sys
import logging
from datetime import datetime, timezone
import redis
from rq import Queue
# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv("/root/.openclaw/workspace/memory-product/.env")
    logger_temp = logging.getLogger("zerolatency.worker.startup")
    logger_temp.info("Loaded .env file")
except ImportError:
    pass  # dotenv not installed


# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger("zerolatency.worker")

# Add src/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from extraction import extract_memories
from storage_multitenant import store_memories, track_api_usage

# Redis connection
redis_conn = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def process_extraction_job(job_id: str, content: str, agent_id: str, 
                          session_key: str, tenant_id: str):
    """
    Process a memory extraction job.
    This function is executed by RQ workers in the background.
    
    Args:
        job_id: Unique job identifier
        content: Content to extract memories from
        agent_id: Agent identifier
        session_key: Session key for grouping
        tenant_id: Tenant identifier
    """
    try:
        logger.info(f"Starting extraction job {job_id} for tenant {tenant_id}")
        
        # Update job status to processing
        redis_conn.hset(f"extract_job:{job_id}", mapping={
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        
        # Extract memories from content
        memories = extract_memories(
            human_message=content,
            agent_message="",
            agent_id=agent_id,
            session_key=session_key,
        )
        
        # Store memories if any were extracted
        if memories:
            memory_ids = store_memories(memories, tenant_id)
            redis_conn.hset(f"extract_job:{job_id}", mapping={
                "status": "complete",
                "memories_stored": len(memory_ids),
                "memory_ids": ",".join(memory_ids),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"Job {job_id} completed: {len(memory_ids)} memories stored")
        else:
            redis_conn.hset(f"extract_job:{job_id}", mapping={
                "status": "complete",
                "memories_stored": 0,
                "memory_ids": "",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"Job {job_id} completed: no memories extracted")
        
        # Track API usage
        track_api_usage(tenant_id, "/memories/extract", 
                       tokens_used=len(content), response_time_ms=0)
        
        # Set expiration on job data (24 hours)
        redis_conn.expire(f"extract_job:{job_id}", 86400)
        
        return {
            "job_id": job_id,
            "status": "complete",
            "memories_stored": len(memories) if memories else 0
        }
        
    except Exception as e:
        logger.error(f"Extraction job {job_id} failed: {e}", exc_info=True)
        redis_conn.hset(f"extract_job:{job_id}", mapping={
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        # Set expiration on failed job data (24 hours)
        redis_conn.expire(f"extract_job:{job_id}", 86400)
        raise
