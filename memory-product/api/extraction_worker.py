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
from storage_multitenant import store_memories, track_api_usage, _db_execute_rows


_ENTITY_RE = __import__("re").compile(r"\b[A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]+){0,3}\b")
_MONEY_RE = __import__("re").compile(r"\$[\d,]+(?:\.\d{1,2})?[KMB]?")


def _extract_search_terms(content: str) -> list:
    """Pull proper nouns and dollar amounts from the incoming turn so we can
    find prior memories about the same entity even when the 30-most-recent
    window has slid past. Crude but cheap — no NLP dependency.
    """
    terms = set()
    for m in _ENTITY_RE.findall(content):
        if len(m) > 2 and m.lower() not in {"human", "assistant", "remember", "today", "yesterday"}:
            terms.add(m)
    for m in _MONEY_RE.findall(content):
        terms.add(m)
    return list(terms)[:8]


def _load_existing_context(agent_id: str, tenant_id: str, content: str = "") -> str:
    """Fetch existing memories for dedup + contradiction targeting.

    Returns up to 50 lines combining:
      - 20 most-recent memories (catches recent topic continuity)
      - 30 memories whose headline contains an entity from the current turn
        (catches the 'Wells Fargo mentioned 50 sessions ago' case where recent
        window has slid past)

    Each line is `[id=<UUID>] <headline>` so the LLM can copy the UUID verbatim
    into `contradicts_id`.
    """
    rows_acc = {}
    try:
        recent_rows = _db_execute_rows(
            """
            SELECT id::text, headline FROM memory_service.memories
            WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
            ORDER BY created_at DESC LIMIT 20
            """,
            (agent_id, tenant_id),
            tenant_id=tenant_id,
        )
        for r in recent_rows or []:
            rows_acc[r[0]] = r[1]
    except Exception as e:
        logger.warning(f"Failed to load recent context for dedup: {e}")

    search_terms = _extract_search_terms(content) if content else []
    if search_terms:
        try:
            pattern = "|".join(__import__("re").escape(t) for t in search_terms)
            entity_rows = _db_execute_rows(
                """
                SELECT id::text, headline FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
                  AND (headline ~* %s OR context ~* %s)
                ORDER BY created_at DESC LIMIT 30
                """,
                (agent_id, tenant_id, pattern, pattern),
                tenant_id=tenant_id,
            )
            for r in entity_rows or []:
                rows_acc[r[0]] = r[1]
        except Exception as e:
            logger.warning(f"Failed to load entity-overlap context for dedup: {e}")

    if rows_acc:
        return "\n".join(f"[id={mid}] {headline}" for mid, headline in rows_acc.items())
    return ""

# Redis connection
redis_conn = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


def _split_content_roles(content: str) -> tuple:
    """Split 'Human: ...\n\nAssistant: ...' into (human, assistant).

    The async extract endpoint receives a single content field containing
    both roles. This function restores proper role separation so the
    extraction prompt can distinguish human vs assistant content.
    """
    # Try double-newline separator first, then single-newline
    sep_double = "\n\nAssistant: "
    sep_single = "\nAssistant: "
    for sep in [sep_double, sep_single]:
        idx = content.find(sep)
        if idx != -1:
            human = content[:idx]
            agent = content[idx + len(sep):]
            if human.startswith("Human: "):
                human = human[len("Human: "):]
            return human.strip(), agent.strip()
    # Fallback: no assistant portion found
    human = content
    if human.startswith("Human: "):
        human = human[len("Human: "):]
    return human.strip(), ""

def process_extraction_job(job_id: str, content: str, agent_id: str,
                          session_key: str, tenant_id: str,
                          session_timestamp: str = None):
    """
    Process a memory extraction job.
    This function is executed by RQ workers in the background.

    Args:
        job_id: Unique job identifier
        content: Content to extract memories from
        agent_id: Agent identifier
        session_key: Session key for grouping
        tenant_id: Tenant identifier
        session_timestamp: ISO 8601 date of this conversation (for event_at resolution)
    """
    try:
        logger.info(f"Starting extraction job {job_id} for tenant {tenant_id}")

        # Update job status to processing
        redis_conn.hset(f"extract_job:{job_id}", mapping={
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        # Split content into human/assistant roles for proper extraction
        human_msg, agent_msg = _split_content_roles(content)

        # Load existing memories for dedup + contradiction targeting.
        # Pass the incoming content so entity-overlap matching can find prior
        # memories about the same Wells Fargo / Rachel / commute / etc. even
        # when the 20-recent window has slid past them under parallel ingest.
        existing_context = _load_existing_context(agent_id, tenant_id, content=content)

        # Extract memories from content (set source=api_extract for proper source_type tracking)
        memories, raw_turn_id = extract_memories(
            human_message=human_msg,
            agent_message=agent_msg,
            agent_id=agent_id,
            session_key=session_key,
            existing_context=existing_context,
            tenant_id=tenant_id,
            source="api_extract",  # Track as API extraction, not conversation
            session_timestamp=session_timestamp,
        )
        
        # Store memories if any were extracted
        if memories:
            result = store_memories(memories, tenant_id)
            memory_ids = result["ids"]
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
