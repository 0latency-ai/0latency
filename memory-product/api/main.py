"""
Zero Latency Memory API — Phase B  
FastAPI REST endpoints for multi-tenant agent memory with real authentication.
"""
import os
import sys
import time

# Load .env file for environment variables (Stripe keys, etc.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import hashlib
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Header, Request, Query, BackgroundTasks
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from api.analytics import track_posthog_event, is_first_api_call, is_first_memory_stored, is_first_memory_recalled, check_activation_milestone
from api.email_service import email_service
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger("zerolatency")

# Add src/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from extraction import extract_memories
from storage_multitenant import (
    store_memory, store_memories, set_tenant_context, 
    get_tenant_by_api_key, create_tenant, track_api_usage,
    _db_execute_rows,
)
from recall import recall_fixed as recall, recall_hybrid, recall_with_fallback, recall_cross_agent
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
from recall_telemetry import trigger_recall_telemetry
from graph import (
    get_entity_subgraph, list_entities, get_entity_memories, 
    find_path, upsert_entity, add_relationship,
)
from versioning import snapshot_version, get_history
from webhooks import register_webhook, list_webhooks, delete_webhook, trigger_event
from criteria import (
    create_criteria as _create_criteria, list_criteria as _list_criteria,
    delete_criteria as _delete_criteria,
)
from schemas import (
    create_schema as _create_schema, list_schemas as _list_schemas,
    delete_schema as _delete_schema, get_schema,
)
from synthesis.orchestrator import run_synthesis_for_tenant
import tier_gates
from org_memory import (
    create_organization, add_tenant_to_org, get_tenant_org,
    store_org_memory, recall_org_memories, list_org_memories,
    delete_org_memory, promote_to_org,
)

# Monitoring & Error Tracking
try:
    from api.monitoring import track_critical_errors
except ImportError:
    # If monitoring not available, create pass-through decorator
    def track_critical_errors(func):
        return func

# Initialize Sentry for error tracking
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

_sentry_dsn = os.environ.get('SENTRY_DSN')
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
        environment=os.environ.get('ENVIRONMENT', 'development'),
        attach_stacktrace=True,
        send_default_pii=False,
    )
    logger.info('✓ Sentry error tracking initialized')
else:
    logger.warning('⚠ SENTRY_DSN not set - error tracking disabled')

# --- App ---
app = FastAPI(
    title="Zero Latency Memory API",
    version="0.1.0",
    description="Structured memory extraction, storage, and recall for AI agents.",
)

_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "https://164.90.156.169,https://0latency.ai,https://www.0latency.ai,https://api.0latency.ai,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Global exception handler
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

# --- Auth Module ---

# Warm embedding cache on startup
from storage_multitenant import warm_embedding_cache, _get_local_model

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    warm_embedding_cache()
    
    # Sprint 4: Pre-warm local embedding model
    try:
        import time as _time
        print("[STARTUP] Pre-warming local embedding model...")
        _start = _time.time()
        model = _get_local_model()
        _load_time = _time.time() - _start
        print(f"[STARTUP] Local model ready in {_load_time:.2f}s")
    except Exception as e:
        print(f"[STARTUP] Warning: Failed to pre-warm local model: {e}")

from api.auth import router as auth_router
app.include_router(auth_router)

# --- Billing Module ---
from api.billing import router as billing_router
app.include_router(billing_router)

# --- Security Module (secret scanning) ---
from api.security import router as security_router, check_for_secrets
from api.checkpoint_validation import validate_session_checkpoint_metadata
app.include_router(security_router)

@app.middleware("http")
async def request_logging(request: Request, call_next):
    """Log every request with ID, tenant, endpoint, latency."""
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    latency_ms = int((time.time() - start) * 1000)
    tenant_id = getattr(request.state, "tenant_id", "anon") if hasattr(request, "state") else "anon"
    logger.info(f"req={request_id} method={request.method} path={request.url.path} status={response.status_code} latency={latency_ms}ms tenant={tenant_id}")
    response.headers["X-Request-ID"] = request_id
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# --- Security & Observability Middleware ---
try:
    from api.middleware_security import security_middleware
    app.middleware("http")(security_middleware)
    logger.info("Security middleware enabled")
except ImportError as e:
    logger.warning(f"Security middleware not available: {e}")

try:
    from api.metrics_middleware import metrics_middleware
    app.middleware("http")(metrics_middleware)
    logger.info("Metrics middleware enabled")
except ImportError as e:
    logger.warning(f"Metrics middleware not available: {e}")

# --- Configuration ---
def _admin_key(): return os.environ.get("MEMORY_ADMIN_KEY", "")

# --- Rate Limiting (Redis-backed, survives restarts) ---
import redis as _redis

_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            _redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
            _redis_client = _redis.from_url(_redis_url, decode_responses=True, socket_timeout=2)
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client

def _check_rate_limit(tenant_id: str, rate_limit_rpm: int):
    """Check if tenant has exceeded their rate limit. Redis-backed with in-memory fallback."""
    from fastapi.responses import JSONResponse
    r = _get_redis()
    if r:
        try:
            key = f"rl:{tenant_id}"
            count = r.incr(key)
            if count == 1:
                r.expire(key, 60)
            if count > rate_limit_rpm:
                ttl = max(r.ttl(key), 1)
                logger.warning(f"rate_limit_hit tenant={tenant_id} plan_rpm={rate_limit_rpm} count={count} retry_after={ttl}")
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"Rate limit exceeded ({rate_limit_rpm} requests/min). Retry after {ttl}s.",
                        "limit": rate_limit_rpm,
                        "retry_after": ttl,
                    },
                    headers={"Retry-After": str(ttl)},
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Redis rate-limit unavailable, falling back to in-memory: {e}")
    
    # In-memory fallback if Redis unavailable
    now = time.time()
    window = _rate_limits_fallback.setdefault(tenant_id, [])
    _rate_limits_fallback[tenant_id] = [t for t in window if now - t < 60]
    if len(_rate_limits_fallback[tenant_id]) >= rate_limit_rpm:
        logger.warning(f"rate_limit_hit tenant={tenant_id} plan_rpm={rate_limit_rpm} (in-memory fallback)")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded ({rate_limit_rpm} requests/min). Retry after 60s.",
                "limit": rate_limit_rpm,
                "retry_after": 60,
            },
            headers={"Retry-After": "60"},
        )
    _rate_limits_fallback[tenant_id].append(now)

_rate_limits_fallback: dict[str, list[float]] = {}

# --- Auth ---
# Tenant auth cache — avoids DB lookup on every request
_tenant_cache: dict[str, tuple[dict, float]] = {}
_TENANT_CACHE_TTL = 30  # 30 seconds

async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Multi-tenant auth via API key header with cached validation."""
    if not x_api_key or not x_api_key.startswith("zl_live_") or len(x_api_key) != 40:
        raise HTTPException(401, detail="Invalid API key format")
    
    api_key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    now = time.time()
    
    # Check for cross-worker cache invalidation
    _check_cache_bust()
    
    # Check cache first
    if api_key_hash in _tenant_cache:
        cached_tenant, cached_at = _tenant_cache[api_key_hash]
        if now - cached_at < _TENANT_CACHE_TTL:
            if not cached_tenant["active"]:
                raise HTTPException(401, detail="Account suspended")
            _check_rate_limit(cached_tenant["id"], cached_tenant["rate_limit_rpm"])
            set_tenant_context(cached_tenant["id"])
            return cached_tenant
        else:
            del _tenant_cache[api_key_hash]
    
    # DB lookup
    tenant = get_tenant_by_api_key(api_key_hash)
    if not tenant:
        raise HTTPException(401, detail="Invalid API key")
    
    if not tenant["active"]:
        raise HTTPException(401, detail="Account suspended")
    
    # Cache it
    _tenant_cache[api_key_hash] = (tenant, now)
    
    _check_rate_limit(tenant["id"], tenant["rate_limit_rpm"])
    set_tenant_context(tenant["id"])
    return tenant

def _invalidate_tenant_cache(tenant_id: str = None):
    """Clear tenant cache after key rotation/revocation.
    Also sets a Redis flag so other workers know to clear their cache."""
    _tenant_cache.clear()
    try:
        r = _get_redis()
        if r:
            # Signal all workers to clear cache
            r.set("zl:cache_bust", str(time.time()), ex=60)
    except Exception as e:
        logger.debug(f"Redis cache-bust signal failed: {e}")

def _check_cache_bust():
    """Check if another worker invalidated the cache."""
    try:
        r = _get_redis()
        if r:
            bust_time = r.get("zl:cache_bust")
            if bust_time:
                bust_ts = float(bust_time)
                for key in list(_tenant_cache.keys()):
                    _, cached_at = _tenant_cache[key]
                    if cached_at < bust_ts:
                        del _tenant_cache[key]
    except Exception as e:
        logger.debug(f"Redis cache-bust check failed: {e}")

def auto_resolve_agent_id(tenant_id: str, provided_agent_id: Optional[str] = None) -> str:
    """Auto-resolve agent_id when not provided. Returns the agent with the highest memory count."""
    if provided_agent_id:
        return provided_agent_id

    rows = _db_execute_rows("""
        SELECT a.agent_id, COUNT(m.id) as memory_count
        FROM (SELECT DISTINCT agent_id FROM memory_service.memories
              WHERE tenant_id = %s AND superseded_at IS NULL) a
        LEFT JOIN memory_service.memories m ON a.agent_id = m.agent_id
            AND m.tenant_id = %s AND m.superseded_at IS NULL
        GROUP BY a.agent_id ORDER BY memory_count DESC LIMIT 1
    """, (tenant_id, tenant_id), tenant_id=tenant_id)

    if not rows:
        raise HTTPException(status_code=404, detail="No agents found for this tenant")

    return rows[0][0]

async def require_admin_key(request: Request, x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """Admin authentication for tenant management. Restricted to localhost."""
    # IP allowlist: admin endpoints only accessible from localhost
    client_ip = request.client.host if request.client else "unknown"
    allowed_ips = {"127.0.0.1", "::1", "localhost"}
    if client_ip not in allowed_ips:
        raise HTTPException(403, detail="Admin endpoints are only accessible from localhost")
    
    if not _admin_key():
        raise HTTPException(500, detail="Admin endpoint not configured")
    
    if x_admin_key != _admin_key():
        raise HTTPException(401, detail="Invalid admin key")
    
    return True

# --- Models ---
from fastapi.responses import HTMLResponse

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, tenant=Depends(require_api_key)):
    """Tenant dashboard UI (requires API key)."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(dashboard_path) as f:
        return HTMLResponse(content=f.read())


class SeedFact(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    category: Optional[str] = Field(None, max_length=64, deprecated=True, description="Deprecated: use memory_type instead")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_type: Optional[str] = Field(None, max_length=64, description="Memory type (fact, preference, event, instruction, etc.)")
    metadata: Optional[dict] = Field(default_factory=dict, description="Optional metadata as JSONB object")

class SeedRequest(BaseModel):
    agent_id: Optional[str] = Field(None, min_length=1, max_length=128)
    facts: list[SeedFact] = Field(..., min_length=1, max_length=500)

class SeedResponse(BaseModel):
    memories_stored: int
    memory_ids: list[str]
    deduplicated_count: int = 0
    new_count: int = 0


class ExtractRequest(BaseModel):
    agent_id: Optional[str] = Field(None, min_length=1, max_length=128)
    human_message: str = Field(..., min_length=1, max_length=50000)
    agent_message: str = Field(..., min_length=1, max_length=50000)
    session_key: Optional[str] = Field(None, max_length=256)
    turn_id: Optional[str] = Field(None, max_length=256)

class AsyncExtractRequest(BaseModel):
    agent_id: Optional[str] = Field(None, min_length=1, max_length=128)
    content: str = Field(..., min_length=1, max_length=100000)
    session_key: Optional[str] = Field(None, max_length=256)


# CP7b Phase 2: Checkpoint models
class CheckpointRequest(BaseModel):
    project_id: Optional[str] = Field(None, description="Project UUID")
    thread_id: str = Field(..., description="Thread UUID")
    turn_range: List[int] = Field(..., description="[start_turn, end_turn]")
    parent_memory_ids: List[str] = Field(..., description="UUIDs of atoms to summarize")
    parent_checkpoint_id: Optional[str] = Field(None, description="Previous checkpoint UUID")
    thread_title: Optional[str] = None
    project_name: Optional[str] = None
    agent_id: str = Field(..., min_length=1, max_length=128)
    source: Optional[str] = Field("server_job", description="Checkpoint source: server_job | agent | extension")

class CheckpointResponse(BaseModel):
    checkpoint_id: str
    job_id: Optional[str] = None
    deduplicated: bool = False

class ResumeRequest(BaseModel):
    agent_id: str
    project_id: str  # UUID
    project_name: Optional[str] = None
    thread_id: str  # new thread's UUID
    thread_title: Optional[str] = None

class ResumeResponse(BaseModel):
    resume_checkpoint_id: Optional[str]  # None if no prior checkpoints exist
    status: str  # "written" | "no_prior_context" | "deduplicated"
    prior_checkpoints_used: int
    tail_recoveries_written: List[str]  # IDs of any tail_recovery checkpoints written this call
    tail_recoveries_deferred: int  # Count of eligible orphans skipped due to cap

class ExtractResponse(BaseModel):
    memories_stored: int
    memory_ids: list[str]
    raw_turn_id: Optional[str] = None
    deduplicated_count: int = 0
    new_count: int = 0
    entities_extracted: int = 0
    relationships_created: int = 0
    sentiment_analyzed: bool = False
    tier_features_used: list[str] = []

class RecallRequest(BaseModel):
    agent_id: Optional[str] = Field(None, min_length=1, max_length=128)
    conversation_context: str = Field(..., min_length=1, max_length=50000)
    budget_tokens: int = Field(default=4000, ge=500, le=16000)
    cross_agent: bool = Field(default=False, description="Enable cross-agent namespace search")
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Min confidence before cross-agent fallback")
    dynamic_budget: bool = False

class RecallResponse(BaseModel):
    context_block: str
    memories_used: int
    tokens_used: int
    memory_ids: List[str] = []

class FeedbackRequest(BaseModel):
    agent_id: Optional[str] = Field(None, min_length=1, max_length=128, description="Agent namespace (auto-resolved if not provided)")
    memory_id: Optional[str] = Field(None, description="UUID of specific memory (required for used/ignored/contradicted)")
    feedback_type: str = Field(..., description="One of: used, ignored, contradicted, miss")
    context: Optional[str] = Field(None, max_length=1000, description="Optional context (required for miss type)")

class FeedbackResponse(BaseModel):
    status: str

class MemoryItem(BaseModel):
    id: str
    headline: str
    memory_type: str
    importance: float
    created_at: str

class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    plan: str = Field(default="free", pattern="^(free|pro|enterprise)$")

class CreateTenantResponse(BaseModel):
    tenant_id: str
    name: str
    api_key: str
    plan: str
    created_at: str
    memory_limit: int
    rate_limit_rpm: int

class TenantInfo(BaseModel):
    id: str
    name: str
    plan: str
    memory_limit: int
    rate_limit_rpm: int
    api_calls_count: int

class AgentCount(BaseModel):
    agent_id: str
    memory_count: int
    last_active: Optional[datetime] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    memories_total: Optional[int] = None
    db_pool: Optional[dict] = None
    redis: Optional[str] = None

# --- Endpoints ---
@app.post("/extract", response_model=ExtractResponse)
@track_critical_errors
async def extract_endpoint(req: ExtractRequest, tenant: dict = Depends(require_api_key)):
    """Extract memories from a conversation turn."""
    # Secret scanning — reject if secrets detected in inbound content
    check_for_secrets(req.human_message, "human_message")
    check_for_secrets(req.agent_message, "agent_message")
    
    # Resolve agent_id default: use tenant_id if not provided
    agent_id = req.agent_id or tenant["id"]
    
    start_time = time.time()
    try:
        # Enforce memory limit
        count_rows = _db_execute_rows("""
            SELECT COUNT(*) FROM memory_service.memories
            WHERE tenant_id = %s::UUID AND superseded_at IS NULL
        """, (tenant["id"],), tenant_id=tenant["id"])
        current_count = int(count_rows[0][0]) if count_rows else 0
        if current_count >= tenant["memory_limit"]:
            raise HTTPException(429, detail=f"Memory limit reached ({tenant['memory_limit']}). Upgrade plan or delete old memories.")
        
        # Fetch recent headlines for dedup context
        existing_context = ""
        try:
            recent = _db_execute_rows("""
                SELECT headline FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
                ORDER BY created_at DESC LIMIT 20
            """, (agent_id, tenant["id"]), tenant_id=tenant["id"])
            if recent:
                existing_context = "\n".join(f"- {row[0]}" for row in recent)
        except Exception as e:
            logger.warning(f"Failed to load existing context for dedup: {e}")
        
        memories, raw_turn_id = extract_memories(
            human_message=req.human_message,
            agent_message=req.agent_message,
            agent_id=agent_id,
            session_key=req.session_key,
            turn_id=req.turn_id,
            existing_context=existing_context,
            tenant_id=tenant["id"],
            source="api",
        )
        if not memories:
            response = ExtractResponse(memories_stored=0, memory_ids=[], raw_turn_id=None)
        else:
            result = store_memories(memories, tenant["id"])
            ids = result["ids"]
            
            # Tier-based auto-enablement of premium features
            entities_extracted = 0
            relationships_created = 0
            sentiment_analyzed = False
            tier_features_used = []
            
            if tenant.get("plan") in ["pro", "scale", "enterprise"]:
                try:
                    # Auto-extract entities and build graph for paid tiers
                    from src.graph import extract_relationships_from_memory
                    
                    for i, memory_id in enumerate(ids):
                        # Get the memory object that was stored
                        memory_dict = memories[i] if i < len(memories) else None
                        if not memory_dict:
                            continue
                        
                        # Add the ID to the memory dict for relationship extraction
                        memory_dict["id"] = memory_id
                        
                        # Extract entities and relationships using existing graph function
                        extract_relationships_from_memory(memory_dict, agent_id, tenant_id=tenant["id"])
                        
                        # Count entities for response
                        entity_count = len(memory_dict.get("entities", []))
                        entities_extracted += entity_count
                        
                        # Count relationships (rough estimate: n*(n-1)/2 for n entities)
                        if entity_count >= 2:
                            relationships_created += (entity_count * (entity_count - 1)) // 2
                    
                    if entities_extracted > 0:
                        tier_features_used.append("entity_extraction")
                    if relationships_created > 0:
                        tier_features_used.append("graph_relationships")
                    
                    # Sentiment is already extracted in extract_memories()
                    # Just flag that it was used for paid tiers
                    sentiment_analyzed = True
                    tier_features_used.append("sentiment_analysis")
                    
                except Exception as e:
                    logger.warning(f"Tier features auto-enablement failed (non-critical): {e}")
            
            response = ExtractResponse(
                memories_stored=len(ids), 
                memory_ids=ids,
                entities_extracted=entities_extracted,
                relationships_created=relationships_created,
                sentiment_analyzed=sentiment_analyzed,
                tier_features_used=list(set(tier_features_used)),  # dedup
                raw_turn_id=raw_turn_id
            )
        
        # Track usage
        response_time = int((time.time() - start_time) * 1000)
        track_api_usage(tenant["id"], "/extract",
                       tokens_used=len(req.human_message + req.agent_message),
                       response_time_ms=response_time)
        
        # Track PostHog events
        if is_first_api_call(tenant["id"]):
            track_posthog_event(
                tenant_id=tenant["id"],
                event_name="first_api_call",
                properties={"endpoint": "/extract"}
            )
        
        if is_first_memory_stored(tenant["id"]):
            track_posthog_event(
                tenant_id=tenant["id"],
                event_name="first_memory_stored",
                properties={"input_length": len(req.human_message + req.agent_message)}
            )
        return response
    except HTTPException:
        raise  # Re-raise HTTP exceptions (429, 401, etc.) as-is
    except Exception as e:
        track_api_usage(tenant["id"], "/extract", response_time_ms=int((time.time() - start_time) * 1000), status_code=500)
        raise HTTPException(500, detail="Extraction failed. Please check your input and try again.")


@app.post("/memories/seed", response_model=SeedResponse)
@track_critical_errors
async def seed_endpoint(req: SeedRequest, tenant: dict = Depends(require_api_key)):
    """Seed memories directly from raw facts, bypassing the extraction pipeline.
    
    Use this to bulk-load known facts, preferences, or context into an agent's
    memory without requiring conversation-format input. Each fact becomes a
    memory with its own embedding.
    """
    start_time = time.time()
    try:
        # Secret scanning on each fact
        for i, fact in enumerate(req.facts):
            check_for_secrets(fact.text, f"facts[{i}].text")
        
        # CP7b Phase 1: Validate session_checkpoint metadata
        for i, fact in enumerate(req.facts):
            validate_session_checkpoint_metadata(
                fact.metadata or {},
                fact.memory_type or fact.category or "fact"
            )
        
        # Resolve agent_id default: use tenant_id if not provided
        agent_id = req.agent_id or tenant["id"]

        # Enforce memory limit
        count_rows = _db_execute_rows("""
            SELECT COUNT(*) FROM memory_service.memories
            WHERE tenant_id = %s::UUID AND superseded_at IS NULL
        """, (tenant["id"],), tenant_id=tenant["id"])
        current_count = int(count_rows[0][0]) if count_rows else 0
        remaining = tenant["memory_limit"] - current_count
        if remaining <= 0:
            raise HTTPException(429, detail=f"Memory limit reached ({tenant['memory_limit']}). Upgrade plan or delete old memories.")
        if len(req.facts) > remaining:
            raise HTTPException(429, detail=f"Would exceed memory limit. {remaining} slots remaining, {len(req.facts)} facts submitted.")

        # Build memory dicts from facts and store them
        memories = []
        for fact in req.facts:
            categories = [fact.category] if fact.category else []
            memories.append({
                "agent_id": agent_id,
                "headline": fact.text,
                "context": fact.text,
                "full_content": fact.text,
                "memory_type": fact.memory_type or fact.category or "fact",
                "importance": fact.importance,
                "confidence": 0.9,
                "entities": [],
                "categories": categories,
                "scope": "/",
                "source_session": "seed",
                "source_turn": None,
                "metadata": {**(fact.metadata or {}), "source": (fact.metadata or {}).get("source", "seed_api")},
            })

        result = store_memories(memories, tenant["id"])
        response = SeedResponse(
            memories_stored=len(result["ids"]),
            memory_ids=result["ids"],
            deduplicated_count=len(result["deduplicated_ids"]),
            new_count=len(result["new_ids"])
        )

        # Track usage
        response_time = int((time.time() - start_time) * 1000)
        track_api_usage(tenant["id"], "/memories/seed",
                       tokens_used=sum(len(f.text) for f in req.facts),
                       response_time_ms=response_time)
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        track_api_usage(tenant["id"], "/memories/seed",
                       response_time_ms=int((time.time() - start_time) * 1000),
                       status_code=500)
        logger.error(f"Seed endpoint failed: {e}")
        raise HTTPException(500, detail="Seed failed. Please check your input and try again.")


# --- Async Extraction Job Store (in-memory for now, Redis-backed in production) ---
_extract_jobs: dict[str, dict] = {}

@app.post("/memories/extract", status_code=202)
async def async_extract_endpoint(req: AsyncExtractRequest, tenant: dict = Depends(require_api_key)):
    """Async memory extraction. Accepts instantly (202), processes in background.
    
    This is the preferred extraction path. Recall is always sync and fast.
    Extraction accepts instantly and processes in the background.
    Partial results beat blocking.
    """
    # Secret scanning — reject if secrets detected in inbound content
    check_for_secrets(req.content, "content")
    
    # Resolve agent_id default: use tenant_id if not provided
    agent_id = req.agent_id or tenant["id"]
    
    import threading
    
    job_id = str(uuid.uuid4())
    _extract_jobs[job_id] = {
        "job_type": "extract",
        "status": "accepted",
        "tenant_id": tenant["id"],
        "agent_id": agent_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "memories_stored": 0,
        "memory_ids": [],
    }
    
    def _process_extraction():
        try:
            # Split content into human/agent turns or treat as raw content
            memories, raw_turn_id = extract_memories(
                human_message=req.content,
                agent_message="",
                agent_id=agent_id,
                tenant_id=tenant["id"],
                source="api",
                session_key=req.session_key,
            )
            if memories:
                result = store_memories(memories, tenant["id"])
                ids = result["ids"]
                _extract_jobs[job_id].update({
                    "status": "complete",
                    "memories_stored": len(ids),
                    "memory_ids": ids,
                    "raw_turn_id": raw_turn_id,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
            else:
                _extract_jobs[job_id].update({
                    "status": "complete",
                    "memories_stored": 0,
                    "memory_ids": [],
                    "raw_turn_id": None,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
            
            track_api_usage(tenant["id"], "/memories/extract", 
                           tokens_used=len(req.content), response_time_ms=0)
        except Exception as e:
            logger.error(f"Async extraction failed for job {job_id}: {e}")
            _extract_jobs[job_id].update({
                "status": "failed",
                "error": "extraction_failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
    
    thread = threading.Thread(target=_process_extraction, daemon=True)
    thread.start()
    
    return {"job_id": job_id, "status": "accepted"}


@app.get("/memories/extract/{job_id}")
async def get_extract_job(job_id: str, tenant: dict = Depends(require_api_key)):
    """Check status of an async job (extract or resume). Job type indicated by job_type field."""
    job = _extract_jobs.get(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job["tenant_id"] != tenant["id"]:
        raise HTTPException(404, detail="Job not found")
    return {k: v for k, v in job.items() if k != "tenant_id"}



@app.post("/memories/checkpoint", response_model=CheckpointResponse)
async def create_checkpoint(req: CheckpointRequest, tenant: dict = Depends(require_api_key)):
    """
    CP7b Phase 2: Mid-thread rollup checkpoint creation.
    Dedup guard → Haiku summarization → session_checkpoint memory write.
    """
    import threading
    import requests

    # Dedup guard: check for existing checkpoint with overlapping turn_range
    try:
        existing = _db_execute_rows(f"""
            SELECT id, metadata
            FROM memory_service.memories
            WHERE tenant_id = %s::UUID
              AND agent_id = %s
              AND memory_type = 'session_checkpoint'
              AND metadata->>'thread_id' = %s
              AND (metadata->>'turn_range')::jsonb IS NOT NULL
        """, (tenant["id"], req.agent_id, req.thread_id), tenant_id=tenant["id"])

        # Check for range overlap: [a,b] overlaps [c,d] if a <= d AND c <= b
        for row in existing:
            existing_range = row[1].get("turn_range", [])
            if len(existing_range) == 2:
                if req.turn_range[0] <= existing_range[1] and existing_range[0] <= req.turn_range[1]:
                    logger.info(f"Dedup: checkpoint for thread {req.thread_id} range {req.turn_range} already exists")
                    return CheckpointResponse(
                        checkpoint_id=str(row[0]),
                        job_id=None,
                        deduplicated=True
                    )
    except Exception as e:
        logger.warning(f"Dedup check failed (continuing): {e}")

    # Fetch parent atoms
    try:
        parent_atoms = _db_execute_rows(f"""
            SELECT id, context AS content, metadata, created_at
            FROM memory_service.memories
            WHERE id = ANY(%s::UUID[])
            ORDER BY created_at ASC
        """, (req.parent_memory_ids,), tenant_id=tenant["id"])
    except Exception as e:
        logger.error(f"Failed to fetch parent atoms: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch parent memories")

    if not parent_atoms:
        raise HTTPException(status_code=400, detail="No parent memories found")

    # Assemble turns_text
    turns_text = ""
    for i, atom in enumerate(parent_atoms):
        # Infer role from position (alternating user/assistant)
        role = "user" if i % 2 == 0 else "assistant"
        content = atom[1]  # content field
        turns_text += f"{role}: {content}\n\n"

    # Fetch prior checkpoint if provided
    prior_rollup_text = ""
    if req.parent_checkpoint_id:
        try:
            prior = _db_execute_rows(f"""
                SELECT full_content FROM memory_service.memories
                WHERE id = %s::UUID AND tenant_id = %s::UUID
            """, (req.parent_checkpoint_id, tenant["id"]), tenant_id=tenant["id"])
            if prior:
                prior_content = prior[0][0]
                # Truncate to ≤200 tokens (rough: ~4 chars/token)
                if len(prior_content) > 800:
                    half = 400
                    prior_content = prior_content[:half] + "\n\n[...]\n\n" + prior_content[-half:]
                prior_rollup_text = f"Prior rollup:\n{prior_content}\n\n---\n\n"
        except Exception as e:
            logger.warning(f"Failed to fetch prior checkpoint: {e}")

    # Build prompt from CP7b-OPUS-PROMPTS.md section 1
    system_prompt = """You are a summarization engine for 0Latency's session_checkpoint memory type. Your job is to compress a window of turns from an ongoing AI-assistant conversation into one dense, structured record that a future agent — possibly in a different session — can read to reconstruct what happened and pick up work cleanly.

You are writing for another AI, not for a human reader. Favor information density over prose polish. No hedging, no throat-clearing, no meta-commentary about the summary itself. Every sentence must carry a fact, a decision, or an open question that would cost the next agent time to recover from raw turns.

You receive a slice of conversation — typically 20 turns — from somewhere in the middle of a longer thread. Earlier context may exist but is not shown. Do not speculate about what came before. Do not invent continuity. Summarize only what is present.

Output exactly four labeled sections, in this order, in plain markdown. No preamble. No closing line. If a section has nothing worth recording, write "None in this window." — do not omit the section.

**topic** — One to two sentences naming what this window was actually about. Not "the user and assistant discussed X" — just the subject and the frame (e.g., "Debugging a 504 on the /memories/checkpoint endpoint; traced to uvicorn worker timeout, not DB.").

**decisions** — Bullet list of concrete decisions made in this window. A decision is a commitment to an approach, a value, a name, a deferral, or a rejection. Include the reasoning clause when it's short ("Chose N=20 over N=10 because..."). Skip decisions that were revisited and reversed in the same window — record only the final state.

**open_questions** — Bullet list of unresolved items explicitly raised and not closed. Include who or what the resolution depends on when stated ("Waiting on Denis for Supabase RLS check"). Do not manufacture questions from absence — only record questions the turns actually raised.

**next_steps** — Bullet list of actions either committed to or clearly implied as immediate next moves. Include ownership when stated. If a step has a gate or dependency, note it inline ("Kick off migration after vector-phase subinstrumentation — gate is DB ≥1,500ms").

Constraints:
- Total output ≤500 tokens. Bias toward ≤350.
- Never quote verbatim from the turns unless the exact wording is the point (a name, an ID, a command). Paraphrase everything else.
- Proper nouns, file paths, commit hashes, identifiers, and numeric thresholds are load-bearing — reproduce them exactly.
- Use past tense for decisions and discussion, future tense for next_steps, present tense for open_questions.
- No apologies, no caveats about summary limitations, no "based on the provided turns" framing."""

    user_prompt = f"""Summarize the following conversation window.

Thread: {req.thread_title or "(untitled)"}
Project: {req.project_name or "(none)"}
Turn range: {req.turn_range[0]}–{req.turn_range[1]} of this thread
Prior checkpoint in this thread: {"present" if req.parent_checkpoint_id else "none — this is the first rollup"}

{prior_rollup_text}Turns:
{turns_text}"""

    # Call Haiku (reuse extraction pattern)
    def _get_anthropic_key():
        key = os.environ.get("ANTHROPIC_API_KEY")
        return key.strip('"\'') if key else ""

    # checkpoint_id will be returned by store_memory
    job_id = None  # Synchronous operation

    def _process_checkpoint():
        try:
            # Call Haiku
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": _get_anthropic_key(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            body = {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 2048,
                "temperature": 0.1,
                "messages": [
                    {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
                ]
            }

            resp = requests.post(url, headers=headers, json=body, timeout=60)
            resp.raise_for_status()
            result = resp.json()
            summary_content = result["content"][0]["text"]

            # Validate output shape (must have 4 headers)
            required_headers = ["**topic**", "**decisions**", "**open_questions**", "**next_steps**"]
            has_all_headers = all(h in summary_content for h in required_headers)
            prompt_retry = False

            if not has_all_headers:
                logger.warning(f"Checkpoint summary missing headers, retrying once")
                resp = requests.post(url, headers=headers, json=body, timeout=60)
                resp.raise_for_status()
                result = resp.json()
                summary_content = result["content"][0]["text"]
                has_all_headers = all(h in summary_content for h in required_headers)
                prompt_retry = True

                if not has_all_headers:
                    logger.warning(f"Checkpoint summary still malformed after retry, proceeding anyway")

            # Compute checkpoint_sequence
            try:
                seq_result = _db_execute_rows(f"""
                    SELECT COALESCE(MAX((metadata->>'checkpoint_sequence')::int), 0)
                    FROM memory_service.memories
                    WHERE tenant_id = %s::UUID
                      AND agent_id = %s
                      AND metadata->>'thread_id' = %s
                      AND memory_type = 'session_checkpoint'
                """, (tenant["id"], req.agent_id, req.thread_id), tenant_id=tenant["id"])
                checkpoint_sequence = (seq_result[0][0] if seq_result and seq_result[0][0] else 0) + 1
            except Exception as e:
                logger.warning(f"Failed to compute checkpoint_sequence: {e}, defaulting to 1")
                checkpoint_sequence = 1

            # Compute time_span_seconds
            time_span_seconds = 0
            if len(parent_atoms) >= 2:
                try:
                    first_ts = parent_atoms[0][3]  # created_at
                    last_ts = parent_atoms[-1][3]
                    time_span_seconds = int((last_ts - first_ts).total_seconds())
                except Exception as e:
                    logger.warning(f"Failed to compute time_span: {e}")

            # Build metadata
            metadata = {
                "level": 1,
                "thread_id": req.thread_id,
                "project_id": req.project_id,
                "thread_title": req.thread_title,
                "project_name": req.project_name,
                "checkpoint_sequence": checkpoint_sequence,
                "checkpoint_type": "mid_thread",
                "turn_range": req.turn_range,
                "turn_count": req.turn_range[1] - req.turn_range[0] + 1,
                "time_span_seconds": time_span_seconds,
                "parent_memory_ids": req.parent_memory_ids,
                "child_memory_ids": [],
                "parent_checkpoint_id": req.parent_checkpoint_id,
                "source": req.source or "server_job",
                "prompt_version": "mid_thread_v1",
            }
            if prompt_retry:
                metadata["prompt_retry"] = True

            # Write checkpoint memory
            from api.checkpoint_validation import validate_session_checkpoint_metadata
            validate_session_checkpoint_metadata(metadata, "session_checkpoint")

            checkpoint_mem = {
                "memory_type": "session_checkpoint",
                "headline": f"Mid-thread rollup {req.turn_range[0]}-{req.turn_range[1]}: {req.thread_title or '(untitled)'}",
                "context": summary_content[:500],  # First 500 chars as summary
                "full_content": summary_content,  # Full summary content
                "agent_id": req.agent_id,
                "importance": 0.7,
                "confidence": 0.9,
                "entities": [],
                "categories": ["checkpoint", "mid_thread"],
                "project": req.project_id,
                "scope": "/",
                "source_session": req.thread_id,
                "source_turn": None,
                "metadata": metadata,
            # NEW top-level scope fields:
            "thread_id": req.thread_id,
            "project_id": req.project_id,
            "thread_title": req.thread_title,
            "project_name": req.project_name,
            }

            result = store_memory(checkpoint_mem, tenant["id"])
            actual_checkpoint_id = result["id"]
            logger.info(f"Checkpoint {actual_checkpoint_id} created for thread {req.thread_id} range {req.turn_range}")
            return actual_checkpoint_id

        except Exception as e:
            logger.error(f"Checkpoint creation failed: {e}")
            import traceback
            traceback.print_exc()

    # Run synchronously to ensure DB commit before returning
    try:
        actual_checkpoint_id = _process_checkpoint()
        return CheckpointResponse(
            checkpoint_id=actual_checkpoint_id,
            job_id=None,  # Completed synchronously
            deduplicated=False
        )
    except Exception as e:
        logger.error(f"Synchronous checkpoint creation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Checkpoint creation failed: {str(e)}")



# ======================================================================
# Resume checkpoint - shared logic
# ======================================================================

def _do_resume_work(req: ResumeRequest, tenant: dict) -> ResumeResponse:
    """
    CP7b Phase 4: Auto-resume meta-summary - pure logic extraction.
    Called by both sync and async endpoints.
    
    Orchestrates tail recovery on orphaned prior threads, then generates
    a meta-summary checkpoint across all end_of_thread checkpoints in the project.
    """
    # Load env config
    orphan_threshold_hours = int(os.getenv("CP7B_ORPHAN_THRESHOLD_HOURS", "24"))
    max_tail_recoveries = int(os.getenv("CP7B_RESUME_MAX_TAIL_RECOVERIES", "3"))
    max_prior_checkpoints = int(os.getenv("CP7B_RESUME_MAX_PRIOR_CHECKPOINTS", "10"))
    input_token_cap = int(os.getenv("CP7B_RESUME_INPUT_TOKEN_CAP", "8000"))
    
    
    from api.resume_helpers import write_tail_recovery
    
    # Nested helper (mirrors checkpoint pattern)
    def _get_anthropic_key():
        key = os.environ.get("ANTHROPIC_API_KEY")
        return key.strip('"' + "'") if key else ""
    
    # ===== STEP A: ORPHAN DETECTION AND TAIL RECOVERY =====
    
    # A.1: Query for orphaned threads (exclude those with end_of_thread OR tail_recovery)
    orphan_query = f"""
        WITH threads_with_activity AS (
            SELECT DISTINCT thread_id, MAX(created_at) AS last_activity
            FROM memory_service.memories
            WHERE tenant_id = %s::UUID
              AND project_id = %s
              AND thread_id IS NOT NULL
              AND thread_id != %s
              AND (
                  memory_type IN ('fact', 'task', 'decision', 'preference', 'identity', 'event')
                  OR (memory_type = 'session_checkpoint' AND metadata->>'checkpoint_type' = 'mid_thread')
              )
            GROUP BY thread_id
        ),
        threads_with_prior_closure AS (
            SELECT DISTINCT thread_id
            FROM memory_service.memories
            WHERE memory_type = 'session_checkpoint'
              AND metadata->>'checkpoint_type' IN ('end_of_thread', 'tail_recovery')
              AND thread_id IS NOT NULL
        )
        SELECT t.thread_id, t.last_activity
        FROM threads_with_activity t
        LEFT JOIN threads_with_prior_closure c ON t.thread_id = c.thread_id
        WHERE c.thread_id IS NULL
          AND t.last_activity < NOW() - INTERVAL '{orphan_threshold_hours} hours'
        ORDER BY t.last_activity DESC;
    """
    
    orphan_rows = _db_execute_rows(
        orphan_query,
        (tenant["id"], req.project_id, req.thread_id),
        tenant_id=tenant["id"]
    )
    
    total_eligible_orphans = len(orphan_rows)
    tail_recovery_ids = []
    
    # A.2: Process top N orphans by recency (cap at max_tail_recoveries)
    orphans_to_process = orphan_rows[:max_tail_recoveries]
    
    for orphan_row in orphans_to_process:
        orphan_thread_id = orphan_row[0]
        
        # Fetch thread metadata for this orphan
        meta_query = """
            SELECT DISTINCT project_name, thread_title
            FROM memory_service.memories
            WHERE tenant_id = %s::UUID AND thread_id = %s
            LIMIT 1;
        """
        meta_rows = _db_execute_rows(meta_query, (tenant["id"], orphan_thread_id), tenant_id=tenant["id"])
        project_name_orphan = meta_rows[0][0] if meta_rows and len(meta_rows[0]) > 0 else req.project_name
        thread_title_orphan = meta_rows[0][1] if meta_rows and len(meta_rows[0]) > 1 else None
        
        try:
            result = write_tail_recovery(
                thread_id=orphan_thread_id,
                project_id=req.project_id,
                agent_id=req.agent_id,
                thread_title=thread_title_orphan,
                project_name=project_name_orphan,
                tenant_id=tenant["id"]
            )
            if result.get("written"):
                tail_recovery_ids.append(result["checkpoint_id"])
                logger.info(f"Tail recovery {result['checkpoint_id']} written for thread {orphan_thread_id}")
        except Exception as e:
            # Fault-tolerant: log warning, skip this orphan, continue
            logger.warning(f"Tail recovery failed for thread {orphan_thread_id}: {e}")
            continue
    
    tail_recoveries_deferred = total_eligible_orphans - len(tail_recovery_ids)
    
    # ===== STEP B: META-SUMMARY GENERATION =====
    
    # B.1: Query prior checkpoints (all end_of_thread/tail_recovery + mid_thread from most recent prior thread)
    
    # First, find the most recent prior thread (excluding the resuming thread)
    recent_thread_query = """
        SELECT thread_id, MAX(created_at) as last_activity
        FROM memory_service.memories
        WHERE tenant_id = %s::UUID
          AND project_id = %s
          AND thread_id IS NOT NULL
          AND thread_id != %s
        GROUP BY thread_id
        ORDER BY last_activity DESC
        LIMIT 1;
    """
    recent_thread_rows = _db_execute_rows(
        recent_thread_query,
        (tenant["id"], req.project_id, req.thread_id),
        tenant_id=tenant["id"]
    )
    most_recent_prior_thread = recent_thread_rows[0][0] if recent_thread_rows else None
    
    # Build checkpoint query
    if most_recent_prior_thread:
        checkpoint_query = """
            SELECT id, full_content, created_at, thread_id, thread_title,
                   metadata->>'checkpoint_type' AS checkpoint_type,
                   metadata->>'turn_range' AS turn_range
            FROM memory_service.memories
            WHERE tenant_id = %s::UUID
              AND project_id = %s
              AND memory_type = 'session_checkpoint'
              AND (
                  metadata->>'checkpoint_type' IN ('end_of_thread', 'tail_recovery')
                  OR (metadata->>'checkpoint_type' = 'mid_thread' AND thread_id = %s)
              )
            ORDER BY created_at DESC;
        """
        checkpoint_rows = _db_execute_rows(
            checkpoint_query,
            (tenant["id"], req.project_id, most_recent_prior_thread),
            tenant_id=tenant["id"]
        )
    else:
        # No prior threads - just get end_of_thread/tail_recovery
        checkpoint_query = """
            SELECT id, full_content, created_at, thread_id, thread_title,
                   metadata->>'checkpoint_type' AS checkpoint_type,
                   metadata->>'turn_range' AS turn_range
            FROM memory_service.memories
            WHERE tenant_id = %s::UUID
              AND project_id = %s
              AND memory_type = 'session_checkpoint'
              AND metadata->>'checkpoint_type' IN ('end_of_thread', 'tail_recovery')
            ORDER BY created_at DESC;
        """
        checkpoint_rows = _db_execute_rows(
            checkpoint_query,
            (tenant["id"], req.project_id),
            tenant_id=tenant["id"]
        )
    
    # B.2: If zero prior checkpoints, return no_prior_context
    if not checkpoint_rows:
        return ResumeResponse(
            resume_checkpoint_id=None,
            status="no_prior_context",
            prior_checkpoints_used=0,
            tail_recoveries_written=tail_recovery_ids,
            tail_recoveries_deferred=tail_recoveries_deferred
        )
    
    # Parse checkpoints
    parsed_checkpoints = []
    for row in checkpoint_rows:
        parsed_checkpoints.append({
            'id': row[0],
            'content': row[1],
            'created_at': row[2],
            'thread_id': row[3],
            'thread_title': row[4] or "(untitled)",
            'checkpoint_type': row[5],
            'turn_range': row[6] or "unknown"
        })
    
    # B.1 (cont): Token-based filtering with preservation rules
    # Estimate tokens as chars // 4
    selected_checkpoints = []
    total_tokens = 0
    
    # Always preserve: end_of_thread, tail_recovery, and checkpoints from most_recent_prior_thread
    preserved = []
    droppable = []
    
    for ckpt in parsed_checkpoints:
        if ckpt['checkpoint_type'] in ('end_of_thread', 'tail_recovery'):
            preserved.append(ckpt)
        elif most_recent_prior_thread and ckpt['thread_id'] == most_recent_prior_thread:
            preserved.append(ckpt)
        else:
            droppable.append(ckpt)
    
    # Add preserved first
    for ckpt in preserved:
        estimated_tokens = len(ckpt['content']) // 4
        total_tokens += estimated_tokens
        selected_checkpoints.append(ckpt)
    
    # Add droppable if budget allows
    for ckpt in droppable:
        estimated_tokens = len(ckpt['content']) // 4
        if total_tokens + estimated_tokens <= input_token_cap and len(selected_checkpoints) < max_prior_checkpoints:
            total_tokens += estimated_tokens
            selected_checkpoints.append(ckpt)
    
    # Hard ceiling fallback
    if len(selected_checkpoints) > max_prior_checkpoints:
        selected_checkpoints = selected_checkpoints[:max_prior_checkpoints]
    
    # B.3: Build checkpoints_text for prompt (newest first, but chronological within-thread)
    checkpoints_by_thread = {}
    for ckpt in selected_checkpoints:
        tid = ckpt['thread_id']
        if tid not in checkpoints_by_thread:
            checkpoints_by_thread[tid] = []
        checkpoints_by_thread[tid].append(ckpt)
    
    # Sort each thread's checkpoints chronologically (oldest first within thread)
    for tid in checkpoints_by_thread:
        checkpoints_by_thread[tid].sort(key=lambda c: c['created_at'])
    
    # Now build text: threads in reverse chronological order (newest thread first)
    thread_order = sorted(
        checkpoints_by_thread.keys(),
        key=lambda tid: max(c['created_at'] for c in checkpoints_by_thread[tid]),
        reverse=True
    )
    
    checkpoints_text_lines = []
    for tid in thread_order:
        for ckpt in checkpoints_by_thread[tid]:
            thread_id_short = ckpt['thread_id'][:8]
            created_str = str(ckpt['created_at'])[:19] if ckpt['created_at'] else "unknown"
            header = f"## Checkpoint [{ckpt['thread_title']} | {thread_id_short}] — {ckpt['checkpoint_type']} — {ckpt['turn_range']} — {created_str}"
            checkpoints_text_lines.append(header)
            checkpoints_text_lines.append(ckpt['content'])
            checkpoints_text_lines.append("")
    
    checkpoints_text = "\n".join(checkpoints_text_lines)
    
    # B.4: Content-hash dedup
    hash_input = req.thread_id + "\n" + "\n".join(f"{c['id']}:{c['content']}" for c in selected_checkpoints)
    content_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    # Check for existing resume checkpoint with same hash in 60s window
    dedup_query = """
        SELECT id FROM memory_service.memories
        WHERE tenant_id = %s::UUID
          AND thread_id = %s
          AND memory_type = 'session_checkpoint'
          AND metadata->>'checkpoint_type' = 'auto_resume_meta'
          AND metadata->>'content_hash' = %s
          AND created_at > NOW() - INTERVAL '60 seconds'
        LIMIT 1;
    """
    dedup_rows = _db_execute_rows(dedup_query, (tenant["id"], req.thread_id, content_hash), tenant_id=tenant["id"])
    
    if dedup_rows:
        existing_id = dedup_rows[0][0]
        logger.info(f"Resume checkpoint deduplicated: {existing_id}")
        return ResumeResponse(
            resume_checkpoint_id=existing_id,
            status="deduplicated",
            prior_checkpoints_used=len(selected_checkpoints),
            tail_recoveries_written=tail_recovery_ids,
            tail_recoveries_deferred=tail_recoveries_deferred
        )
    
    # B.5: Call Haiku with prompt § 2
    system_prompt = """You are a session-resumption engine for 0Latency. A new conversation thread has just opened in a project that already has prior activity. Your job is to produce the single most useful piece of context that could appear at the top of the new thread — a briefing that lets the next agent pick up work without re-interrogating the user.

This is not a summary of summaries. It is a handoff document. The reader is an AI assistant about to receive its first real user turn in this new thread. What does it need to know to not waste the user's time?

You receive, in order:
1. The sequence of mid-thread and end-of-thread checkpoints from the project's prior threads, newest first.
2. Optionally: a tail-recovery block — turns from the most recent prior thread that ended without an end-of-thread checkpoint.
3. Project metadata (name, current thread title if set).

Output exactly four labeled sections, in this order, in plain markdown. No preamble. No closing line.

**project_arc** — Two to four sentences. What is this project fundamentally about, based on the pattern of work across prior threads? Not a restatement of the project name — the actual arc of intent. Example: "Justin is building the context layer for agents and is currently shipping CP7b — the session_checkpoint memory type that replaces hand-written handoff docs. Prior sprints closed CP7a (memory_write) and the MCP codebase unification."

**recent_context** — Bullet list. The state of things as of the end of the most recent prior thread. Blend the end-of-thread checkpoint (if present) with the tail-recovery block (if present) into one coherent view. Prefer concrete: what shipped, what broke, what's mid-flight, what commit or file matters. Reproduce identifiers, paths, and numbers exactly. If the prior thread ended abruptly, say so ("Prior thread ended mid-decision on X").

**open_threads** — Bullet list. Unresolved questions, waiting-ons, and decisions pending across the project as a whole — not just the last thread. Dedup across checkpoints: if the same question has been open for three threads, list it once and note how long. Include external dependencies by name when stated (Denis, Palmer, Stripe, etc.).

**likely_next_steps** — Bullet list. What the user most plausibly wants to do in this new thread, inferred from the pattern. Rank by likelihood, highest first. If the pattern is ambiguous, say so and list the top two branches. Do not invent goals the prior checkpoints don't support.

Constraints:
- Total output ≤800 tokens. Bias toward 500–650.
- You are synthesizing across threads. If two prior checkpoints contradict each other, the newer one wins and you note the contradiction briefly in recent_context ("Earlier approach X was abandoned; current is Y").
- Reproduce proper nouns, file paths, commit hashes, identifiers, and numeric thresholds exactly.
- No apologies about summary limitations. No "based on the provided checkpoints" framing. Write as if you were the previous agent handing off directly.
- If there is exactly one prior checkpoint and no tail-recovery, the arc section may be thin — that's fine, don't manufacture depth. Lean heavier on recent_context."""
    
    tail_recovery_included = "yes" if tail_recovery_ids else "no"
    
    user_prompt = f"""Produce an auto-resume briefing for a new thread.

Project: {req.project_name or "(none)"}
New thread: {req.thread_title or "(untitled)"}
Prior checkpoints in this project: {len(selected_checkpoints)}
Tail recovery included: {tail_recovery_included}

---

Prior checkpoints (newest first):

{checkpoints_text}"""
    
    # Call Haiku
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": _get_anthropic_key(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2048,
        "temperature": 0.1,
        "messages": [
            {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
        ]
    }
    
    try:
        import requests
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        meta_content = result["content"][0]["text"]
        
        # Validate output shape (must have 4 headers)
        required_headers = ["**project_arc**", "**recent_context**", "**open_threads**", "**likely_next_steps**"]
        has_all_headers = all(h in meta_content for h in required_headers)
        
        if not has_all_headers:
            logger.warning(f"Meta-summary missing headers, retrying once")
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            resp.raise_for_status()
            result = resp.json()
            meta_content = result["content"][0]["text"]
            has_all_headers = all(h in meta_content for h in required_headers)
            
            if not has_all_headers:
                logger.error(f"Meta-summary still malformed after retry")
                raise HTTPException(status_code=503, detail={"detail": "resume_generation_failed", "error": "Malformed output after retry"})
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Haiku call failed for resume meta-summary: {e}")
        raise HTTPException(status_code=503, detail={"detail": "resume_generation_failed", "error": str(e)})
    
    # B.6: Write checkpoint via store_memory
    parent_ids = [c['id'] for c in selected_checkpoints]
    
    metadata = {
        "level": 1,
        "checkpoint_type": "auto_resume_meta",
        "parent_memory_ids": parent_ids,
        "child_memory_ids": [],
        "source": "resume_endpoint",
        "prompt_version": "auto_resume_meta_v1",
        "content_hash": content_hash,
        "prior_checkpoints_count": len(selected_checkpoints),
        "tail_recoveries_count": len(tail_recovery_ids),
    }
    
    resume_mem = {
        "memory_type": "session_checkpoint",
        "headline": f"Auto-resume briefing: {req.project_name or '(project)'} → {req.thread_title or '(new thread)'}",
        "context": meta_content[:500],
        "full_content": meta_content,
        "agent_id": req.agent_id,
        "importance": 0.8,
        "confidence": 0.9,
        "entities": [],
        "categories": ["checkpoint", "auto_resume_meta"],
        "project": req.project_id,
        "scope": "/",
        "source_session": req.thread_id,
        "source_turn": None,
        "metadata": metadata,
        # Top-level scope fields for P1 dual-write
        "thread_id": req.thread_id,
        "project_id": req.project_id,
        "thread_title": req.thread_title,
        "project_name": req.project_name,
    }
    
    result = store_memory(resume_mem, tenant["id"])
    resume_checkpoint_id = result["id"]
    
    logger.info(f"Resume checkpoint {resume_checkpoint_id} created for thread {req.thread_id}, {len(selected_checkpoints)} prior checkpoints, {len(tail_recovery_ids)} tail recoveries")
    
    # B.7: Return response
    return ResumeResponse(
        resume_checkpoint_id=resume_checkpoint_id,
        status="written",
        prior_checkpoints_used=len(selected_checkpoints),
        tail_recoveries_written=tail_recovery_ids,
        tail_recoveries_deferred=tail_recoveries_deferred
    )



@app.post("/memories/resume", response_model=ResumeResponse)
async def create_resume_checkpoint(req: ResumeRequest, tenant: dict = Depends(require_api_key)):
    """
    CP7b Phase 4: Auto-resume meta-summary endpoint (SYNC).
    For long-running resume operations, use POST /memories/resume/async instead.
    """
    return _do_resume_work(req, tenant)


@app.post("/memories/resume/async", status_code=202)
async def async_resume_endpoint(req: ResumeRequest, tenant: dict = Depends(require_api_key)):
    """
    CP7b Phase 4: Auto-resume meta-summary endpoint (ASYNC).
    Returns job_id immediately (202), processes in background.
    Poll GET /memories/extract/{job_id} for status.
    """
    import threading
    
    job_id = str(uuid.uuid4())
    _extract_jobs[job_id] = {
        "job_type": "resume",
        "status": "accepted",
        "tenant_id": tenant["id"],
        "agent_id": req.agent_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resume_checkpoint_id": None,
        "prior_checkpoints_used": 0,
        "tail_recoveries_written": [],
        "tail_recoveries_deferred": 0,
    }
    
    def _process_resume():
        try:
            result = _do_resume_work(req, tenant)
            _extract_jobs[job_id].update({
                "status": "complete" if result.status == "written" else result.status,
                "resume_checkpoint_id": result.resume_checkpoint_id,
                "prior_checkpoints_used": result.prior_checkpoints_used,
                "tail_recoveries_written": result.tail_recoveries_written,
                "tail_recoveries_deferred": result.tail_recoveries_deferred,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.error(f"Async resume failed for job {job_id}: {e}")
            _extract_jobs[job_id].update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
    
    thread = threading.Thread(target=_process_resume, daemon=True)
    thread.start()
    
    return {"job_id": job_id, "status": "accepted"}


def _analytics_fire_and_forget(func, *args):
    """Submit analytics task to background executor — don't wait, returns immediately"""
    try:
        _analytics_executor.submit(func, *args)
    except Exception:
        pass  # Executor full or other error — silently skip


@app.post("/recall", response_model=RecallResponse)
@track_critical_errors
async def recall_endpoint(req: RecallRequest, tenant: dict = Depends(require_api_key), background_tasks: BackgroundTasks = BackgroundTasks()):
    """Recall relevant memories for a conversation context.
    
    Supports multi-agent orchestration via cross-agent recall:
    - Set cross_agent=true for automatic fallback to cross-agent search
    - Adjust confidence_threshold (default 0.6) to tune fallback sensitivity
    """
    start_time = time.time()
    try:
        # Auto-resolve agent_id if not provided
        _t0 = time.time()
        agent_id = auto_resolve_agent_id(tenant["id"], req.agent_id)
        _t1 = time.time()

        # Choose recall strategy based on cross_agent parameter
        if req.cross_agent:
            # Use recall_with_fallback for automatic cross-agent search
            result = recall_with_fallback(
                agent_id=agent_id,
                conversation_context=req.conversation_context,
                budget_tokens=req.budget_tokens,
                confidence_threshold=req.confidence_threshold,
                tenant_id=tenant["id"]
            )
        else:
            # Standard single-agent recall
            result = recall_hybrid(
                agent_id=agent_id,
                conversation_context=req.conversation_context,
                budget_tokens=req.budget_tokens,
                tenant_id=tenant["id"]
            )

        _t2 = time.time()

        # Extract memory_ids from recall_details
        memory_ids = []
        if result.get("recall_details"):
            memory_ids = [detail.get("id") for detail in result["recall_details"] if detail.get("id")]

        response = RecallResponse(
            context_block=result["context_block"],
            memories_used=result["memories_used"],
            tokens_used=result["tokens_used"],
            memory_ids=memory_ids,
        )

        # Phase 1: Log recall telemetry (non-blocking)
        try:
            trigger_recall_telemetry(
                tenant["id"],
                agent_id,
                req.conversation_context,
                memory_ids,
                int((time.time() - start_time) * 1000)
            )
        except Exception:
            pass  # Fire-and-forget, don't break on telemetry failure
        
        # Track usage — run after response is sent (was blocking ~800ms on sync DB writes)
        response_time = int((time.time() - start_time) * 1000)
        background_tasks.add_task(track_api_usage, tenant["id"], "/recall",
                                  tokens_used=result["tokens_used"],
                                  response_time_ms=response_time)

        # Fire activation check in background (executor) — has genuine side effect
        _analytics_fire_and_forget(check_activation_milestone, tenant["id"])

        _t3 = time.time()
        _phases = {
            "agent_resolve_ms": round((_t1 - _t0) * 1000, 1),
            "recall_exec_ms": round((_t2 - _t1) * 1000, 1),
            "telemetry_ms": round((_t3 - _t2) * 1000, 1),
            "total_ms": round((_t3 - start_time) * 1000, 1),
        }
        # Merge inner timing from recall_hybrid
        _inner = result.get("_timing", {})
        _phases["bm25_ms"] = round(_inner.get("bm25_ms", 0), 1) if isinstance(_inner.get("bm25_ms"), (int, float)) else 0
        _phases["vector_ms"] = round(_inner.get("vector_ms", 0), 1) if isinstance(_inner.get("vector_ms"), (int, float)) else 0
        _phases["path"] = _inner.get("path", "unknown")
        logger.info(f"[RECALL PHASES] agent_resolve={_phases['agent_resolve_ms']:.0f}ms recall_exec={_phases['recall_exec_ms']:.0f}ms bm25={_phases['bm25_ms']:.0f}ms vector={_phases['vector_ms']:.0f}ms telemetry={_phases['telemetry_ms']:.0f}ms total={_phases['total_ms']:.0f}ms path={_phases['path']}")
        return response
    except Exception as e:
        background_tasks.add_task(track_api_usage, tenant["id"], "/recall", response_time_ms=int((time.time() - start_time) * 1000), status_code=500)
        raise HTTPException(500, detail="Recall failed. Please check your input and try again.")




@app.post("/feedback", response_model=FeedbackResponse)
@track_critical_errors
async def feedback_endpoint(req: FeedbackRequest, tenant: dict = Depends(require_api_key)):
    """Submit feedback on recalled memories.
    
    Feedback types:
    - used: Memory was recalled and used by agent
    - ignored: Memory was recalled but not used
    - contradicted: Memory conflicts with agent's current knowledge
    - miss: Agent needed information that wasn't recalled (memory_id optional)
    
    This data powers importance score adjustments for self-improvement.
    """
    from storage_multitenant import _get_connection_pool
    
    # Validate feedback_type
    valid_types = {'used', 'ignored', 'contradicted', 'miss'}
    if req.feedback_type not in valid_types:
        raise HTTPException(400, f"feedback_type must be one of {valid_types}")
    
    # For non-miss feedback, memory_id is required
    if req.feedback_type != 'miss' and not req.memory_id:
        raise HTTPException(400, f"memory_id required for feedback_type={req.feedback_type}")
    
    # For miss feedback, context is required
    if req.feedback_type == 'miss' and not req.context:
        raise HTTPException(400, "context required for feedback_type=miss")
    
    # Auto-resolve agent_id if not provided
    agent_id = auto_resolve_agent_id(tenant["id"], req.agent_id)
    
    try:
        pool = _get_connection_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            
            # Find the most recent telemetry entry for this agent (within last 5 minutes)
            # to link feedback to a specific recall operation
            cur.execute("""
                SELECT id FROM memory_service.recall_telemetry
                WHERE agent_id = %s AND tenant_id = %s
                AND created_at > NOW() - INTERVAL '5 minutes'
                ORDER BY created_at DESC LIMIT 1
            """, (agent_id, tenant["id"]))
            
            row = cur.fetchone()
            telemetry_id = row[0] if row else None
            
            # Insert feedback (telemetry_id can be NULL for miss feedback)
            cur.execute("""
                INSERT INTO memory_service.recall_feedback 
                (telemetry_id, tenant_id, agent_id, memory_id, feedback_type, context)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (telemetry_id, tenant["id"], agent_id, 
                    req.memory_id, req.feedback_type, req.context))
            
            conn.commit()
            cur.close()
            
            # Track usage analytics
            track_api_usage(tenant["id"], "feedback")
            
            logger.info(f"Feedback recorded: agent={agent_id} type={req.feedback_type} memory={req.memory_id}")
            
            return FeedbackResponse(status="ok")
            
        finally:
            pool.putconn(conn)
            
    except Exception as e:
        logger.error(f"Feedback endpoint failed: {e}")
        raise HTTPException(500, f"Failed to record feedback: {str(e)}")

@app.get("/memories", response_model=list[MemoryItem])
async def list_memories(
    agent_id: Optional[str] = Query(None, min_length=1, max_length=128),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    memory_type: Optional[str] = Query(None, max_length=32),
    tenant: dict = Depends(require_api_key),
):
    """List memories for an agent with pagination."""
    start_time = time.time()
    try:
        tenant_id = tenant["id"]

        # Auto-resolve agent_id if not provided
        agent_id = auto_resolve_agent_id(tenant_id, agent_id)

        if memory_type:
            rows = _db_execute_rows("""
                SELECT id, headline, memory_type, importance, created_at
                FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s AND superseded_at IS NULL AND memory_type = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (agent_id, tenant_id, memory_type, limit, offset), tenant_id=tenant_id)
        else:
            rows = _db_execute_rows("""
                SELECT id, headline, memory_type, importance, created_at
                FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s AND superseded_at IS NULL
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (agent_id, tenant_id, limit, offset), tenant_id=tenant_id)
        
        items = []
        for row in (rows or []):
            items.append(MemoryItem(
                id=str(row[0]),
                headline=str(row[1]),
                memory_type=str(row[2]),
                importance=float(row[3]) if row[3] is not None else 0.5,
                created_at=str(row[4]),
            ))
        
        # Track usage
        response_time = int((time.time() - start_time) * 1000)
        track_api_usage(tenant["id"], "/memories", response_time_ms=response_time)
        
        return items
    except Exception as e:
        track_api_usage(tenant["id"], "/memories", response_time_ms=int((time.time() - start_time) * 1000), status_code=500)
        raise HTTPException(500, detail="Failed to list memories. Please try again.")


@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str, tenant: dict = Depends(require_api_key)):
    """Delete a specific memory. Tenant-isolated."""
    try:
        rows = _db_execute_rows("""
            DELETE FROM memory_service.memories
            WHERE id = %s::UUID AND tenant_id = %s::UUID
            RETURNING id
        """, (memory_id, tenant["id"]), tenant_id=tenant["id"])
        if not rows:
            raise HTTPException(404, detail="Memory not found")
        
        # Clean up entity index and edges
        _db_execute_rows("""
            DELETE FROM memory_service.entity_index WHERE memory_id = %s
        """, (memory_id,), tenant_id=tenant["id"], fetch_results=False)
        _db_execute_rows("""
            DELETE FROM memory_service.memory_edges 
            WHERE source_memory_id = %s OR target_memory_id = %s
        """, (memory_id, memory_id), tenant_id=tenant["id"], fetch_results=False)
        
        # Audit log
        _db_execute_rows("""
            INSERT INTO memory_service.memory_audit_log (tenant_id, agent_id, action, memory_id, details)
            VALUES (%s::UUID, 'api', 'delete', %s, '{"source":"api"}'::jsonb)
        """, (tenant["id"], memory_id), tenant_id=tenant["id"], fetch_results=False)
        
        logger.info(f"Memory deleted: {memory_id} tenant={tenant['id']}")
        return {"deleted": memory_id}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, detail="Failed to delete memory.")


@app.get("/memories/search")
async def search_memories(
    agent_id: Optional[str] = Query(None, min_length=1, max_length=128),
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=100),
    tenant: dict = Depends(require_api_key),
):
    """Search memories by keyword. Tenant-isolated."""
    try:
        # Auto-resolve agent_id if not provided
        agent_id = auto_resolve_agent_id(tenant["id"], agent_id)

        pattern = f"%{q}%"
        rows = _db_execute_rows("""
            SELECT id, headline, memory_type, importance, created_at, context
            FROM memory_service.memories
            WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
              AND (headline ILIKE %s OR context ILIKE %s)
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
        """, (agent_id, tenant["id"], pattern, pattern, limit), tenant_id=tenant["id"])
        
        results = []
        for row in (rows or []):
            results.append({
                "id": str(row[0]),
                "headline": str(row[1]),
                "memory_type": str(row[2]),
                "importance": float(row[3]) if row[3] is not None else 0.5,
                "created_at": str(row[4]),
                "context": str(row[5]) if row[5] else "",
            })
        return results
    except Exception:
        raise HTTPException(500, detail="Search failed.")


class BatchExtractItem(BaseModel):
    agent_id: Optional[str] = Field(None, min_length=1, max_length=128)
    human_message: str = Field(..., min_length=1, max_length=50000)
    agent_message: str = Field(..., min_length=1, max_length=50000)
    session_key: Optional[str] = Field(None, max_length=256)
    turn_id: Optional[str] = Field(None, max_length=256)

class BatchExtractRequest(BaseModel):
    turns: list[BatchExtractItem] = Field(..., min_length=1, max_length=50)

@app.post("/extract/batch")
async def batch_extract(req: BatchExtractRequest, tenant: dict = Depends(require_api_key)):
    """Extract memories from multiple conversation turns in one request."""
    import traceback as _tb
    logger.info(f"[BATCH DEBUG] /extract/batch called with {len(req.turns)} turns, tenant={tenant['id']}")

    # Secret scanning — reject entire batch if any turn contains secrets
    for i, turn in enumerate(req.turns):
        check_for_secrets(turn.human_message, f"turns[{i}].human_message")
        check_for_secrets(turn.agent_message, f"turns[{i}].agent_message")
    
    start_time = time.time()
    total_stored = 0
    all_ids = []
    errors = []
    
    for i, turn in enumerate(req.turns):
        logger.info(f"[BATCH DEBUG] Turn {i}: agent_id={turn.agent_id!r}, human_len={len(turn.human_message)}, agent_len={len(turn.agent_message)}, session_key={turn.session_key!r}")
        
        # Resolve agent_id default for this turn
        agent_id = turn.agent_id or tenant["id"]
        try:
            # Fetch existing headlines for dedup (matches /extract behavior)
            existing_context = ""
            try:
                recent = _db_execute_rows("""
                    SELECT headline FROM memory_service.memories
                    WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
                    ORDER BY created_at DESC LIMIT 20
                """, (agent_id, tenant["id"]), tenant_id=tenant["id"])
                if recent:
                    existing_context = "\n".join(f"- {row[0]}" for row in recent)
                    logger.info(f"[BATCH DEBUG] Turn {i}: loaded {len(recent)} existing headlines for dedup")
            except Exception as ctx_err:
                logger.warning(f"[BATCH DEBUG] Turn {i}: failed to load dedup context: {ctx_err}")

            memories, raw_turn_id = extract_memories(
                human_message=turn.human_message,
                agent_message=turn.agent_message,
                agent_id=agent_id,
                session_key=turn.session_key,
                turn_id=turn.turn_id,
                existing_context=existing_context,
                tenant_id=tenant["id"],
                source="api",
            )
            logger.info(f"[BATCH DEBUG] Turn {i}: extract_memories returned {len(memories) if memories else 0} memories")
            if memories:
                for j, mem in enumerate(memories):
                    logger.info(f"[BATCH DEBUG]   mem[{j}]: type={mem.get('memory_type')}, headline={mem.get('headline', '')[:80]!r}")
                result = store_memories(memories, tenant["id"])
                ids = result["ids"]
                logger.info(f"[BATCH DEBUG] Turn {i}: store_memories returned {len(ids)} ids: {ids}")
                total_stored += len(ids)
                all_ids.extend(ids)
            else:
                logger.warning(f"[BATCH DEBUG] Turn {i}: extract_memories returned empty/None — no memories to store")
        except Exception as e:
            logger.error(f"[BATCH DEBUG] Turn {i}: EXCEPTION: {type(e).__name__}: {e}")
            logger.error(f"[BATCH DEBUG] Turn {i}: traceback:\n{_tb.format_exc()}")
            errors.append({"turn": i, "error": f"extraction failed: {type(e).__name__}: {str(e)[:200]}"})
    
    response_time = int((time.time() - start_time) * 1000)
    track_api_usage(tenant["id"], "/extract/batch", 
                   tokens_used=sum(len(t.human_message + t.agent_message) for t in req.turns),
                   response_time_ms=response_time)
    
    resp = {
        "turns_processed": len(req.turns),
        "memories_stored": total_stored,
        "memory_ids": all_ids,
        "errors": errors if errors else None,
    }
    logger.info(f"[BATCH DEBUG] Final response: turns_processed={resp['turns_processed']}, memories_stored={resp['memories_stored']}, errors={resp['errors']}")
    return resp


# === BULK IMPORT & THREAD IMPORT ENDPOINTS ===

class BulkImportRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=128)
    content: str = Field(..., min_length=1, max_length=204800)  # 200KB
    source: Optional[str] = Field(None, max_length=256)

class ConversationTurn(BaseModel):
    role: str = Field(..., pattern="^(human|assistant|user|system)$")
    content: str = Field(..., min_length=1, max_length=100000)

class ThreadImportRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=128)
    conversation: list[ConversationTurn] = Field(..., min_length=1, max_length=500)
    source: Optional[str] = Field(None, max_length=256)


def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks of ~chunk_size characters."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            # Look for paragraph break first
            para_break = text.rfind("\n\n", start + chunk_size // 2, end + 200)
            if para_break > start:
                end = para_break
            else:
                # Look for sentence break
                for sep in [". ", ".\n", "! ", "? ", "\n"]:
                    sent_break = text.rfind(sep, start + chunk_size // 2, end + 100)
                    if sent_break > start:
                        end = sent_break + len(sep)
                        break
        chunks.append(text[start:end].strip())
        start = end - overlap  # overlap for context continuity
        if start >= len(text):
            break
    return [c for c in chunks if c]  # filter empty


@app.post("/memories/import")
@track_critical_errors
async def bulk_import_endpoint(req: BulkImportRequest, tenant: dict = Depends(require_api_key)):
    """Bulk import: accepts a large text document, chunks it, extracts memories from each chunk.
    
    Use this to import project briefs, wiki pages, documentation, or any large text block.
    Content is chunked into ~2000 char segments with overlap, and each chunk is run through
    the extraction pipeline.
    """
    # Secret scanning on full content
    check_for_secrets(req.content, "content")
    
    start_time = time.time()
    
    # Enforce memory limit
    count_rows = _db_execute_rows("""
        SELECT COUNT(*) FROM memory_service.memories
        WHERE tenant_id = %s::UUID AND superseded_at IS NULL
    """, (tenant["id"],), tenant_id=tenant["id"])
    current_count = int(count_rows[0][0]) if count_rows else 0
    if current_count >= tenant["memory_limit"]:
        raise HTTPException(429, detail=f"Memory limit reached ({tenant['memory_limit']}). Upgrade plan or delete old memories.")
    
    # Chunk the content
    chunks = _chunk_text(req.content)
    
    total_stored = 0
    all_ids = []
    
    # Fetch recent headlines for dedup context
    existing_context = ""
    try:
        recent = _db_execute_rows("""
            SELECT headline FROM memory_service.memories
            WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
            ORDER BY created_at DESC LIMIT 30
        """, (req.agent_id, tenant["id"]), tenant_id=tenant["id"])
        if recent:
            existing_context = "\n".join(f"- {row[0]}" for row in recent)
    except Exception as e:
        logger.warning(f"Failed to load existing context for dedup: {e}")
    
    for chunk in chunks:
        # Check memory limit per chunk to avoid overshooting
        if current_count + total_stored >= tenant["memory_limit"]:
            logger.warning(f"Memory limit reached during import for tenant {tenant['id']}")
            break
        
        try:
            memories, raw_turn_id = extract_memories(
                human_message=chunk,
                agent_message="",
                agent_id=req.agent_id,
                session_key=req.source or "bulk-import",
                existing_context=existing_context,
                tenant_id=tenant["id"],
                source="api",
            )
            if memories:
                result = store_memories(memories, tenant["id"])
                ids = result["ids"]
                total_stored += len(ids)
                all_ids.extend(ids)
                # Update dedup context with new headlines
                for mem in memories:
                    existing_context += f"\n- {mem['headline']}"
        except Exception as e:
            logger.error(f"Chunk extraction failed during import: {e}")
    
    response_time = int((time.time() - start_time) * 1000)
    track_api_usage(tenant["id"], "/memories/import",
                   tokens_used=len(req.content),
                   response_time_ms=response_time)
    
    return {
        "memories_stored": total_stored,
        "memory_ids": all_ids,
        "chunks_processed": len(chunks),
    }


@app.post("/memories/import-thread")
async def thread_import_endpoint(req: ThreadImportRequest, tenant: dict = Depends(require_api_key)):
    """Thread import: accepts a conversation export and extracts memories from each turn pair.
    
    Use this to import Claude Desktop exports, ChatGPT exports, or any conversation in
    [{role, content}] format. Human+assistant messages are paired and each pair is processed
    through the extraction pipeline.
    """
    # Secret scanning on all content
    for i, turn in enumerate(req.conversation):
        check_for_secrets(turn.content, f"conversation[{i}].content")
    
    start_time = time.time()
    
    # Enforce memory limit
    count_rows = _db_execute_rows("""
        SELECT COUNT(*) FROM memory_service.memories
        WHERE tenant_id = %s::UUID AND superseded_at IS NULL
    """, (tenant["id"],), tenant_id=tenant["id"])
    current_count = int(count_rows[0][0]) if count_rows else 0
    if current_count >= tenant["memory_limit"]:
        raise HTTPException(429, detail=f"Memory limit reached ({tenant['memory_limit']}). Upgrade plan or delete old memories.")
    
    # Pair human+assistant turns
    turns_processed = 0
    total_stored = 0
    all_ids = []
    
    # Fetch recent headlines for dedup context
    existing_context = ""
    try:
        recent = _db_execute_rows("""
            SELECT headline FROM memory_service.memories
            WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
            ORDER BY created_at DESC LIMIT 30
        """, (req.agent_id, tenant["id"]), tenant_id=tenant["id"])
        if recent:
            existing_context = "\n".join(f"- {row[0]}" for row in recent)
    except Exception as e:
        logger.warning(f"Failed to load existing context for dedup: {e}")
    
    # Build turn pairs: collect consecutive human/assistant pairs
    i = 0
    recent_pairs: list[tuple[str, str]] = []
    while i < len(req.conversation):
        human_msg = ""
        assistant_msg = ""
        
        # Collect human message(s)
        if req.conversation[i].role in ("human", "user"):
            human_msg = req.conversation[i].content
            i += 1
            # Check if next is assistant
            if i < len(req.conversation) and req.conversation[i].role == "assistant":
                assistant_msg = req.conversation[i].content
                i += 1
        elif req.conversation[i].role == "assistant":
            # Standalone assistant message — use as agent_message with empty human
            assistant_msg = req.conversation[i].content
            i += 1
        else:
            # Skip system messages
            i += 1
            continue
        
        if not human_msg and not assistant_msg:
            continue
        
        # Check memory limit per turn
        if current_count + total_stored >= tenant["memory_limit"]:
            logger.warning(f"Memory limit reached during thread import for tenant {tenant['id']}")
            break
        
        try:
            memories, raw_turn_id = extract_memories(
                human_message=human_msg,
                agent_message=assistant_msg,
                agent_id=req.agent_id,
                session_key=req.source or "thread-import",
                existing_context=existing_context,
                recent_turns=recent_pairs[-4:] if recent_pairs else None,
                tenant_id=tenant["id"],
                source="api",
            )
            if memories:
                result = store_memories(memories, tenant["id"])
                ids = result["ids"]
                total_stored += len(ids)
                all_ids.extend(ids)
                for mem in memories:
                    existing_context += f"\n- {mem['headline']}"
        except Exception as e:
            logger.error(f"Turn extraction failed during thread import: {e}")
        
        recent_pairs.append((human_msg, assistant_msg))
        turns_processed += 1
    
    response_time = int((time.time() - start_time) * 1000)
    track_api_usage(tenant["id"], "/memories/import-thread",
                   tokens_used=sum(len(t.content) for t in req.conversation),
                   response_time_ms=response_time)
    return {
        "memories_stored": total_stored,
        "memory_ids": all_ids,
        "turns_processed": turns_processed,
    }


@app.get("/memories/export")
async def export_memories(
    agent_id: str = Query(..., min_length=1, max_length=128),
    tenant: dict = Depends(require_api_key),
):
    """Export all memories for an agent as JSON. For data portability and GDPR compliance."""
    rows = _db_execute_rows("""
        SELECT id, headline, context, full_content, memory_type, 
               importance, confidence, entities, project, categories, scope,
               created_at, reinforcement_count, access_count
        FROM memory_service.memories
        WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
        ORDER BY created_at ASC
    """, (agent_id, tenant["id"]), tenant_id=tenant["id"])
    
    memories = []
    for row in rows:
        memories.append({
            "id": str(row[0]),
            "headline": str(row[1]),
            "context": str(row[2]) if row[2] else "",
            "full_content": str(row[3]) if row[3] else "",
            "memory_type": str(row[4]),
            "importance": float(row[5]) if row[5] is not None else 0.5,
            "confidence": float(row[6]) if row[6] is not None else 0.8,
            "entities": list(row[7]) if row[7] else [],
            "project": str(row[8]) if row[8] else None,
            "categories": list(row[9]) if row[9] else [],
            "scope": str(row[10]) if row[10] else "/",
            "created_at": str(row[11]),
            "reinforcement_count": int(row[12]) if row[12] else 0,
            "access_count": int(row[13]) if row[13] else 0,
        })
    
    track_api_usage(tenant["id"], "/memories/export", response_time_ms=0)
    
    return {
        "agent_id": agent_id,
        "tenant_id": tenant["id"],
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_memories": len(memories),
        "memories": memories,
    }


# === PUBLIC DEMO ENDPOINT (no auth, rate-limited by IP) ===

class DemoExtractRequest(BaseModel):
    content: str = Field(..., min_length=10, max_length=2000)

def _check_demo_rate_limit(client_ip: str, max_per_hour: int = 5):
    """Rate limit demo endpoint by IP: max_per_hour requests per hour."""
    r = _get_redis()
    if r:
        try:
            key = f"demo_rl:{client_ip}"
            count = r.incr(key)
            if count == 1:
                r.expire(key, 3600)
            if count > max_per_hour:
                ttl = max(r.ttl(key), 1)
                raise HTTPException(
                    status_code=429,
                    detail=f"Demo rate limit exceeded ({max_per_hour} requests/hour). Try again in {ttl}s.",
                    headers={"Retry-After": str(ttl)},
                )
            return
        except HTTPException:
            raise
        except Exception:
            pass
    # In-memory fallback
    now = time.time()
    window = _demo_rate_limits.setdefault(client_ip, [])
    _demo_rate_limits[client_ip] = [t for t in window if now - t < 3600]
    if len(_demo_rate_limits[client_ip]) >= max_per_hour:
        raise HTTPException(429, detail=f"Demo rate limit exceeded ({max_per_hour} requests/hour). Try again later.")
    _demo_rate_limits[client_ip].append(now)

_demo_rate_limits: dict[str, list[float]] = {}

@app.post("/demo/extract")
async def demo_extract_endpoint(req: DemoExtractRequest, request: Request):
    """Public demo endpoint — extracts memories from text without authentication.
    Rate limited to 5 requests per IP per hour. Max 2000 chars input.
    """
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
    _check_demo_rate_limit(client_ip)
    
    start_time = time.time()
    try:
        memories, raw_turn_id = extract_memories(
            human_message=req.content,
            agent_message="",
            agent_id="demo",
            session_key="demo-playground",
            tenant_id=None,
            source="demo",
        )
        
        results = []
        for mem in (memories or []):
            results.append({
                "text": mem.get("headline", ""),
                "category": mem.get("memory_type", "fact"),
                "importance": round(mem.get("importance", 0.5), 2),
                "entities": mem.get("entities", []),
            })
        
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"demo_extract ip={client_ip} memories={len(results)} latency={latency_ms}ms")
        
        return {
            "memories": results,
            "count": len(results),
            "latency_ms": latency_ms,
        }
    except Exception as e:
        logger.error(f"Demo extraction failed: {e}")
        raise HTTPException(500, detail="Extraction failed. Please try again.")


@app.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
async def health_check():
    """Health check — no auth required. Verifies DB connectivity and pool status."""
    try:
        from storage_multitenant import _get_connection_pool
        
        rows = _db_execute_rows(
            "SELECT COUNT(*) FROM memory_service.memories WHERE superseded_at IS NULL",
            tenant_id="00000000-0000-0000-0000-000000000000"
        )
        total = int(rows[0][0]) if rows else 0
        
        # Pool stats
        pool_info = {}
        try:
            pool = _get_connection_pool()
            pool_info = {
                "pool_min": pool.minconn,
                "pool_max": pool.maxconn,
            }
        except Exception as e:
            logger.debug(f"Pool info unavailable: {e}")
        
        # Redis status
        redis_ok = False
        try:
            r = _get_redis()
            if r:
                redis_ok = r.ping()
        except Exception as e:
            logger.debug(f"Redis health check failed: {e}")
        
        return {
            "status": "ok",
            "version": "0.1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "memories_total": total,
            "db_pool": pool_info,
            "redis": "connected" if redis_ok else "unavailable",
        }
    except Exception:
        return {
            "status": "degraded",
            "version": "0.1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "memories_total": None,
            "db_pool": {},
            "redis": "unknown",
        }


@app.get("/metrics")
async def metrics_endpoint():
    """Performance metrics — no auth required. Shows request rates, latency percentiles, error rates."""
    try:
        from api.metrics_middleware import get_metrics_summary
        return get_metrics_summary()
    except Exception as e:
        return {"error": "Metrics not available", "detail": str(e)}


@app.get("/observability/anomalies")
async def anomalies_endpoint(
    hours: int = Query(24, ge=1, le=168),
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$")
):
    """Recent anomalies detected by statistical analysis. Public endpoint for status page."""
    try:
        from observability import get_recent_anomalies
        return {
            "anomalies": get_recent_anomalies(hours=hours, severity=severity),
            "hours": hours,
            "severity_filter": severity
        }
    except Exception as e:
        return {"error": "Anomaly detection not available", "detail": str(e)}


@app.get("/observability/anomalies/summary")
async def anomalies_summary_endpoint():
    """Summary of recent anomaly detection activity. Public endpoint."""
    try:
        from observability import get_anomaly_summary
        return get_anomaly_summary()
    except Exception as e:
        return {"error": "Anomaly detection not available", "detail": str(e)}


@app.get("/observability/errors/stats")
async def error_stats_endpoint(hours: int = Query(24, ge=1, le=168)):
    """Error statistics for monitoring. Public endpoint."""
    try:
        from observability import get_error_stats
        return get_error_stats(hours=hours)
    except Exception as e:
        return {"error": "Error tracking not available", "detail": str(e)}


# === GRAPH MEMORY ENDPOINTS ===

@app.get("/graph/entity")
async def graph_entity_endpoint(
    agent_id: str = Query(..., min_length=1, max_length=128),
    entity: str = Query(..., min_length=1, max_length=256),
    depth: int = Query(2, ge=1, le=4),
    tenant: dict = Depends(require_api_key),
):
    """Get knowledge graph around an entity with multi-hop traversal."""
    try:
        result = get_entity_subgraph(agent_id, entity, depth=depth, tenant_id=tenant["id"])
        track_api_usage(tenant["id"], "/graph/entity", response_time_ms=0)
        return result
    except Exception as e:
        logger.error(f"Graph query failed: {e}")
        raise HTTPException(500, detail="Graph query failed. Check agent_id and entity name.")


@app.get("/graph/entities")
async def graph_entities_endpoint(
    agent_id: str = Query(..., min_length=1, max_length=128),
    entity_type: Optional[str] = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=200),
    tenant: dict = Depends(require_api_key),
):
    """List all known entities for an agent."""
    try:
        return list_entities(agent_id, entity_type=entity_type, limit=limit, tenant_id=tenant["id"])
    except Exception as e:
        raise HTTPException(500, detail="Failed to list entities.")


@app.get("/graph/entity/memories")
async def graph_entity_memories_endpoint(
    agent_id: str = Query(..., min_length=1, max_length=128),
    entity: str = Query(..., min_length=1, max_length=256),
    limit: int = Query(20, ge=1, le=100),
    tenant: dict = Depends(require_api_key),
):
    """Get all memories associated with an entity."""
    try:
        return get_entity_memories(agent_id, entity, limit=limit, tenant_id=tenant["id"])
    except Exception as e:
        raise HTTPException(500, detail="Failed to retrieve entity memories.")


@app.get("/graph/path")
async def graph_path_endpoint(
    agent_id: str = Query(..., min_length=1, max_length=128),
    source: str = Query(..., min_length=1, max_length=256),
    target: str = Query(..., min_length=1, max_length=256),
    max_depth: int = Query(4, ge=1, le=6),
    tenant: dict = Depends(require_api_key),
):
    """Find shortest path between two entities in the knowledge graph."""
    try:
        path = find_path(agent_id, source, target, max_depth=max_depth, tenant_id=tenant["id"])
        return {"source": source, "target": target, "path": path, "hops": len(path) - 1 if path else 0}
    except Exception as e:
        raise HTTPException(500, detail="Path query failed.")


# === MEMORY VERSIONING ENDPOINTS ===

@app.get("/memories/{memory_id}/history")
async def memory_history_endpoint(
    memory_id: str,
    tenant: dict = Depends(require_api_key),
):
    """Get full version history for a memory."""
    try:
        return get_history(memory_id, tenant["id"])
    except Exception as e:
        raise HTTPException(500, detail="Failed to retrieve memory history.")


def _fetch_memory_row(memory_id: str, tenant_id: str) -> Optional[dict]:
    """Fetch a single memory row for source resolution, tenant-isolated. Returns None if not found."""
    rows = _db_execute_rows("""
        SELECT id, memory_type, full_content, metadata
        FROM memory_service.memories
        WHERE id = %s::UUID AND tenant_id = %s::UUID
    """, (memory_id, tenant_id), tenant_id=tenant_id)
    if not rows:
        return None
    row = rows[0]
    meta = row[3]
    if not isinstance(meta, dict):
        try:
            import json as _json
            meta = _json.loads(meta) if meta else {}
        except Exception:
            meta = {}
    return {"id": str(row[0]), "memory_type": row[1], "full_content": row[2], "metadata": meta}


def _resolve_source_chain(
    memory_id: str, tenant_id: str, visited: set, depth: int, max_depth: int = 5
) -> tuple:
    """Recursively resolve source chain from parent_memory_ids.
    Returns (source_chain, raw_turn_ids, max_depth_reached, truncated)."""
    if memory_id in visited:
        return ([], [], depth, False)
    if depth > max_depth:
        return ([], [], max_depth, True)
    visited.add(memory_id)

    row = _fetch_memory_row(memory_id, tenant_id)
    if not row:
        return ([], [], depth, False)

    if row["memory_type"] == "raw_turn":
        return (
            [{"memory_id": row["id"], "memory_type": "raw_turn", "source_text": row["full_content"]}],
            [row["id"]],
            depth,
            False,
        )

    parent_ids = (row["metadata"] or {}).get("parent_memory_ids") or []
    chain: list = []
    raw_turn_ids: list = []
    max_depth_reached = depth
    truncated = False

    for parent_id in parent_ids:
        sub_chain, sub_raw, sub_depth, sub_trunc = _resolve_source_chain(
            parent_id, tenant_id, visited, depth + 1, max_depth
        )
        chain.extend(sub_chain)
        raw_turn_ids.extend(sub_raw)
        if sub_depth > max_depth_reached:
            max_depth_reached = sub_depth
        if sub_trunc:
            truncated = True

    return (chain, raw_turn_ids, max_depth_reached, truncated)


@app.get("/memories/{memory_id}/source")
async def get_memory_source(memory_id: str, tenant: dict = Depends(require_api_key)):
    """Return verbatim source text for a memory, resolving parent_memory_ids chain for derived types."""
    try:
        uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(422, detail="memory_id must be a valid UUID")

    tenant_id = tenant["id"]
    row = _fetch_memory_row(memory_id, tenant_id)
    if not row:
        logger.warning(f"Memory source not found: {memory_id} tenant={tenant_id}")
        raise HTTPException(404, detail="Memory not found")

    if row["memory_type"] == "raw_turn":
        logger.info(f"Memory source fetched (verbatim): {memory_id} tenant={tenant_id}")
        return {
            "memory_id": memory_id,
            "memory_type": "raw_turn",
            "source_type": "verbatim",
            "source_text": row["full_content"],
            "trace": {"raw_turn_ids": [memory_id], "depth": 0},
        }

    parent_ids = (row["metadata"] or {}).get("parent_memory_ids") or []
    visited = {memory_id}
    source_chain: list = []
    raw_turn_ids: list = []
    max_depth_reached = 0
    truncated = False

    for parent_id in parent_ids:
        sub_chain, sub_raw, sub_depth, sub_trunc = _resolve_source_chain(
            parent_id, tenant_id, visited, 1
        )
        source_chain.extend(sub_chain)
        raw_turn_ids.extend(sub_raw)
        if sub_depth > max_depth_reached:
            max_depth_reached = sub_depth
        if sub_trunc:
            truncated = True

    seen: set = set()
    deduped_raw_turn_ids = []
    for rid in raw_turn_ids:
        if rid not in seen:
            seen.add(rid)
            deduped_raw_turn_ids.append(rid)

    trace: dict = {"raw_turn_ids": deduped_raw_turn_ids, "depth": max_depth_reached}
    if truncated:
        trace["truncated"] = True

    logger.info(f"Memory source fetched (derived): {memory_id} chain_len={len(source_chain)} tenant={tenant_id}")
    return {
        "memory_id": memory_id,
        "memory_type": row["memory_type"],
        "source_type": "derived",
        "source_chain": source_chain,
        "trace": trace,
    }


@app.put("/memories/{memory_id}")
async def update_memory_endpoint(
    memory_id: str,
    request: Request,
    tenant: dict = Depends(require_api_key),
):
    """Update a memory. Automatically creates a version snapshot before updating."""
    try:
        body = await request.json()
        
        # Snapshot current state before update
        snapshot_version(memory_id, tenant["id"], changed_by="api", change_reason="manual_update")
        
        # Build update query from provided fields
        allowed_fields = {"headline", "context", "full_content", "memory_type", "importance", "confidence"}
        updates = []
        params = []
        for field in allowed_fields:
            if field in body:
                updates.append(f"{field} = %s")
                params.append(body[field])
        
        if not updates:
            raise HTTPException(400, detail="No valid fields to update")
        
        params.extend([memory_id, tenant["id"]])
        query = f"""
            UPDATE memory_service.memories 
            SET {', '.join(updates)}
            WHERE id = %s::UUID AND tenant_id = %s::UUID
            RETURNING id
        """
        rows = _db_execute_rows(query, tuple(params), tenant_id=tenant["id"])
        
        if not rows:
            raise HTTPException(404, detail="Memory not found")
        
        # Trigger webhook
        trigger_event(tenant["id"], "memory.updated", {
            "memory_id": memory_id,
            "fields_updated": list(body.keys()),
        })
        
        return {"updated": memory_id, "version": "incremented"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail="Memory update failed.")


# === WEBHOOK ENDPOINTS ===

class WebhookRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)
    events: list[str] = Field(..., min_length=1, max_length=10)
    secret: Optional[str] = Field(None, max_length=256)

@app.post("/webhooks")
async def create_webhook_endpoint(req: WebhookRequest, tenant: dict = Depends(require_api_key)):
    """Register a webhook for memory events."""
    try:
        return register_webhook(tenant["id"], req.url, req.events, req.secret)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail="Webhook creation failed.")


@app.get("/webhooks")
async def list_webhooks_endpoint(tenant: dict = Depends(require_api_key)):
    """List all webhooks for the current tenant."""
    return list_webhooks(tenant["id"])


@app.delete("/webhooks/{webhook_id}")
async def delete_webhook_endpoint(webhook_id: str, tenant: dict = Depends(require_api_key)):
    """Delete a webhook."""
    if delete_webhook(tenant["id"], webhook_id):
        return {"deleted": webhook_id}
    raise HTTPException(404, detail="Webhook not found")


# === CRITERIA ENDPOINTS ===

class CriteriaRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=64)
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    description: Optional[str] = Field(None, max_length=500)
    scoring_prompt: Optional[str] = Field(None, max_length=2000)

@app.post("/criteria")
async def create_criteria_endpoint(req: CriteriaRequest, tenant: dict = Depends(require_api_key)):
    """Create a custom recall scoring criteria."""
    try:
        return _create_criteria(tenant["id"], req.agent_id, req.name, req.weight,
                               req.description, req.scoring_prompt)
    except Exception as e:
        raise HTTPException(500, detail="Criteria creation failed.")


@app.get("/criteria")
async def list_criteria_endpoint(
    agent_id: str = Query(..., min_length=1, max_length=128),
    tenant: dict = Depends(require_api_key),
):
    """List all criteria for an agent."""
    return _list_criteria(tenant["id"], agent_id)


@app.delete("/criteria/{criteria_id}")
async def delete_criteria_endpoint(criteria_id: str, tenant: dict = Depends(require_api_key)):
    """Delete a criteria."""
    if _delete_criteria(tenant["id"], criteria_id):
        return {"deleted": criteria_id}
    raise HTTPException(404, detail="Criteria not found")


# === SCHEMA ENDPOINTS ===

class SchemaRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    schema_definition: dict = Field(..., alias="schema")
    extraction_prompt: Optional[str] = Field(None, max_length=2000)
    
    class Config:
        populate_by_name = True

@app.post("/schemas")
async def create_schema_endpoint(req: SchemaRequest, tenant: dict = Depends(require_api_key)):
    """Create a custom extraction schema."""
    try:
        return _create_schema(tenant["id"], req.name, req.schema_definition, req.extraction_prompt)
    except Exception as e:
        raise HTTPException(500, detail="Schema creation failed.")


@app.get("/schemas")
async def list_schemas_endpoint(tenant: dict = Depends(require_api_key)):
    """List all schemas for the current tenant."""
    return _list_schemas(tenant["id"])


@app.delete("/schemas/{schema_id}")
async def delete_schema_endpoint(schema_id: str, tenant: dict = Depends(require_api_key)):
    """Delete a schema."""
    if _delete_schema(tenant["id"], schema_id):
        return {"deleted": schema_id}
    raise HTTPException(404, detail="Schema not found")


# === BATCH OPERATION ENDPOINTS ===

class BatchDeleteRequest(BaseModel):
    memory_ids: list[str] = Field(..., min_length=1, max_length=100)

@app.post("/memories/batch-delete")
async def batch_delete_endpoint(req: BatchDeleteRequest, tenant: dict = Depends(require_api_key)):
    """Delete multiple memories in one request."""
    deleted = []
    errors = []
    for mid in req.memory_ids:
        try:
            rows = _db_execute_rows("""
                DELETE FROM memory_service.memories
                WHERE id = %s::UUID AND tenant_id = %s::UUID
                RETURNING id
            """, (mid, tenant["id"]), tenant_id=tenant["id"])
            if rows:
                deleted.append(mid)
                trigger_event(tenant["id"], "memory.deleted", {"memory_id": mid})
            else:
                errors.append({"id": mid, "error": "not found"})
        except Exception as e:
            errors.append({"id": mid, "error": "delete failed"})
    
    return {"deleted": deleted, "errors": errors if errors else None}


class BatchSearchRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=128)
    queries: list[str] = Field(..., min_length=1, max_length=20)
    limit_per_query: int = Field(default=10, ge=1, le=50)

@app.post("/memories/batch-search")
async def batch_search_endpoint(req: BatchSearchRequest, tenant: dict = Depends(require_api_key)):
    """Search with multiple queries in one request."""
    results = {}
    for query in req.queries:
        try:
            pattern = f"%{query}%"
            rows = _db_execute_rows("""
                SELECT id, headline, memory_type, importance, created_at
                FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s::UUID AND superseded_at IS NULL
                  AND (headline ILIKE %s OR context ILIKE %s)
                ORDER BY importance DESC
                LIMIT %s
            """, (req.agent_id, tenant["id"], pattern, pattern, req.limit_per_query),
                tenant_id=tenant["id"])
            
            results[query] = [{
                "id": str(r[0]),
                "headline": str(r[1]),
                "memory_type": str(r[2]),
                "importance": float(r[3]) if r[3] else 0.5,
                "created_at": str(r[4]),
            } for r in (rows or [])]
        except Exception as e:
            results[query] = {"error": "search failed"}
    
    return {"results": results}


# === ORG MEMORY ENDPOINTS ===

class OrgMemoryRequest(BaseModel):
    headline: str = Field(..., min_length=1, max_length=500)
    context: Optional[str] = Field(None, max_length=2000)
    full_content: Optional[str] = Field(None, max_length=10000)
    memory_type: str = Field(default="fact", max_length=32)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    entities: Optional[list[str]] = None
    categories: Optional[list[str]] = None

@app.post("/org/memories")
async def store_org_memory_endpoint(req: OrgMemoryRequest, tenant: dict = Depends(require_api_key)):
    """Store an organization-level shared memory."""
    org_id = get_tenant_org(tenant["id"])
    if not org_id:
        raise HTTPException(403, detail="Tenant not part of an organization. Contact admin to set up org.")
    
    try:
        mem_id = store_org_memory(
            org_id=org_id,
            headline=req.headline,
            context=req.context,
            full_content=req.full_content,
            memory_type=req.memory_type,
            importance=req.importance,
            entities=req.entities,
            categories=req.categories,
            created_by=tenant["id"],
        )
        return {"id": mem_id, "org_id": org_id}
    except Exception as e:
        raise HTTPException(500, detail="Failed to store org memory.")


@app.get("/org/memories")
async def list_org_memories_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant: dict = Depends(require_api_key),
):
    """List org-level memories."""
    org_id = get_tenant_org(tenant["id"])
    if not org_id:
        raise HTTPException(403, detail="Tenant not part of an organization")
    return list_org_memories(org_id, limit=limit, offset=offset)


@app.get("/org/memories/recall")
async def recall_org_memories_endpoint(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(10, ge=1, le=50),
    tenant: dict = Depends(require_api_key),
):
    """Recall relevant org-level memories by semantic search."""
    org_id = get_tenant_org(tenant["id"])
    if not org_id:
        raise HTTPException(403, detail="Tenant not part of an organization")
    return recall_org_memories(org_id, query=q, limit=limit)


@app.post("/memories/{memory_id}/promote")
async def promote_to_org_endpoint(memory_id: str, tenant: dict = Depends(require_api_key)):
    """Promote an agent memory to organization level."""
    try:
        org_mem_id = promote_to_org(tenant["id"], memory_id)
        return {"promoted": memory_id, "org_memory_id": org_mem_id}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail="Memory promotion failed.")


@app.delete("/org/memories/{memory_id}")
async def delete_org_memory_endpoint(memory_id: str, tenant: dict = Depends(require_api_key)):
    """Delete an org memory."""
    org_id = get_tenant_org(tenant["id"])
    if not org_id:
        raise HTTPException(403, detail="Tenant not part of an organization")
    if delete_org_memory(org_id, memory_id):
        return {"deleted": memory_id}
    raise HTTPException(404, detail="Org memory not found")


# === EXISTING ENDPOINTS ===

@app.get("/tenant-info", response_model=TenantInfo)
async def get_tenant_info(tenant: dict = Depends(require_api_key)):
    """Get current tenant information."""
    return TenantInfo(
        id=tenant["id"],
        name=tenant["name"],
        plan=tenant["plan"],
        memory_limit=tenant["memory_limit"],
        rate_limit_rpm=tenant["rate_limit_rpm"],
        api_calls_count=tenant["api_calls_count"]
    )





class TenantKeyRotateResponse(BaseModel):
    new_api_key: str
    rotated_at: str
    revoke_at: str
    message: str


@app.post("/tenant/keys/rotate", response_model=TenantKeyRotateResponse)
async def rotate_tenant_key(tenant: dict = Depends(require_api_key)):
    """Rotate the tenant's API key.

    - Generates new zl_live_* key, hashes, inserts as 'active' in api_keys.
    - Existing 'active' row(s) for this tenant transition to 'rotating' with
      revoke_at = now() + 24 hours.
    - Updates tenants.api_key_live (trigger 024 will auto-recompute api_key_hash).
    - Returns new key in body. ONE-TIME RETURN — never echoed again.
    - Invalidates the auth cache so the new key takes effect immediately.

    The current API key remains valid for 24 hours (grace window).
    """
    import secrets as _secrets
    import hashlib as _hashlib

    # Generate new key (40-char total: 8-char prefix + 32-char body)
    new_key_body = "".join(_secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(32))
    new_key = f"zl_live_{new_key_body}"
    new_key_hash = _hashlib.sha256(new_key.encode()).hexdigest()

    tenant_id = tenant["id"]
    from storage_multitenant import _db_execute_rows

    try:
        # 1) Mark all existing active keys for this tenant as 'rotating' with 24h grace
        _db_execute_rows(
            """
            UPDATE memory_service.api_keys
            SET status = 'rotating',
                rotated_at = now(),
                revoke_at = now() + interval '24 hours'
            WHERE tenant_id = %s::uuid AND status = 'active'
            """,
            (tenant_id,),
            tenant_id=tenant_id,
        )

        # 2) Insert new active key
        _db_execute_rows(
            """
            INSERT INTO memory_service.api_keys (tenant_id, key_hash, status, created_at)
            VALUES (%s::uuid, %s, 'active', now())
            """,
            (tenant_id, new_key_hash),
            tenant_id=tenant_id,
        )

        # 3) Update tenants.api_key_live (trigger 024 recomputes api_key_hash automatically)
        # IMPORTANT: do NOT pass api_key_hash — the trigger handles it.
        _db_execute_rows(
            "UPDATE memory_service.tenants SET api_key_live = %s WHERE id = %s::uuid",
            (new_key, tenant_id),
            tenant_id=tenant_id,
        )

        # 4) Invalidate auth cache so new key works immediately
        _invalidate_tenant_cache(tenant_id)

        rotated_at = datetime.now(timezone.utc).isoformat()
        revoke_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

        return TenantKeyRotateResponse(
            new_api_key=new_key,
            rotated_at=rotated_at,
            revoke_at=revoke_at,
            message="Old key remains valid for 24 hours. Update your integration before then. This key is shown once — store it securely.",
        )
    except Exception as e:
        logger.error(f"Key rotation failed for tenant={tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Key rotation failed. Try again or contact support.")



@app.get("/agents", response_model=list[AgentCount])
async def list_agents(tenant: dict = Depends(require_api_key)):
    """List all distinct agent_id values for the authenticated tenant with memory counts."""
    start_time = time.time()
    try:
        tenant_id = tenant["id"]
        
        rows = _db_execute_rows("""
            SELECT agent_id, COUNT(*) as memory_count,
                   MAX(GREATEST(created_at, COALESCE(last_accessed, created_at))) as last_active
            FROM memory_service.memories
            WHERE tenant_id = %s::UUID AND superseded_at IS NULL
            GROUP BY agent_id
            ORDER BY memory_count DESC
        """, (tenant_id,), tenant_id=tenant_id)
        
        agents = []
        for row in (rows or []):
            agents.append(AgentCount(
                agent_id=str(row[0]),
                memory_count=int(row[1]),
                last_active=row[2]
            ))
        
        # Track usage
        response_time = int((time.time() - start_time) * 1000)
        track_api_usage(tenant["id"], "/agents", response_time_ms=response_time)
        
        return agents
    except Exception as e:
        track_api_usage(tenant["id"], "/agents", response_time_ms=int((time.time() - start_time) * 1000), status_code=500)
        raise HTTPException(500, detail="Failed to list agents. Please try again.")

@app.get("/usage")
async def get_usage(
    days: int = Query(7, ge=1, le=90),
    tenant: dict = Depends(require_api_key),
):
    """Get API usage stats for current tenant."""
    tenant_id = tenant["id"]
    
    # Summary stats
    rows = _db_execute_rows("""
        SELECT endpoint, COUNT(*) as calls, 
               COALESCE(SUM(tokens_used), 0) as total_tokens,
               COALESCE(AVG(response_time_ms)::int, 0) as avg_latency_ms,
               COUNT(*) FILTER (WHERE status_code >= 400) as errors
        FROM memory_service.api_usage
        WHERE tenant_id = %s::UUID AND timestamp > now() - make_interval(days => %s)
        GROUP BY endpoint
        ORDER BY calls DESC
    """, (tenant_id, days), tenant_id=tenant_id)
    
    endpoints = []
    for row in (rows or []):
        endpoints.append({
            "endpoint": str(row[0]),
            "calls": int(row[1]),
            "total_tokens": int(row[2]),
            "avg_latency_ms": int(row[3]),
            "errors": int(row[4]),
        })
    
    # Memory count for this tenant
    mem_rows = _db_execute_rows("""
        SELECT COUNT(*) FROM memory_service.memories
        WHERE tenant_id = %s::UUID AND superseded_at IS NULL
    """, (tenant_id,), tenant_id=tenant_id)
    memory_count = int(mem_rows[0][0]) if mem_rows else 0
    
    return {
        "tenant_id": tenant_id,
        "period_days": days,
        "total_api_calls": tenant["api_calls_count"],
        "memories_stored": memory_count,
        "memory_limit": tenant["memory_limit"],
        "memory_usage_pct": round(memory_count / tenant["memory_limit"] * 100, 1) if tenant["memory_limit"] > 0 else 0,
        "endpoints": endpoints,
    }


# --- Admin Endpoints ---
@app.post("/api-keys", response_model=CreateTenantResponse)
async def create_api_key(req: CreateTenantRequest, admin: bool = Depends(require_admin_key)):
    """Create a new tenant and API key. Requires admin authentication."""
    try:
        tenant = create_tenant(req.name, req.plan)
        
        # Track API key creation
        track_posthog_event(
            tenant_id=tenant["tenant_id"],
            event_name="api_key_created",
            properties={
                "method": "admin_create",
                "name": req.name
            }
        )
        return CreateTenantResponse(**tenant)
    except Exception as e:
        raise HTTPException(500, detail="Failed to create tenant.")


class RotateKeyResponse(BaseModel):
    tenant_id: str
    new_api_key: str
    message: str

@app.post("/admin/rotate-key/{tenant_id}", response_model=RotateKeyResponse)
async def rotate_api_key(tenant_id: str, admin: bool = Depends(require_admin_key)):
    """Rotate API key for a tenant. Old key is immediately invalidated."""
    import secrets
    try:
        from storage_multitenant import _db_execute
        # Generate new key
        new_key = f"zl_live_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
        new_hash = hashlib.sha256(new_key.encode()).hexdigest()
        
        # Update tenant with new key hash
        rows = _db_execute("""
            UPDATE memory_service.tenants 
            SET api_key_hash = %s, api_key_live = %s
            WHERE id = %s::UUID AND active = true
            RETURNING id
        """, (new_hash, new_key, tenant_id), tenant_id="00000000-0000-0000-0000-000000000000")
        
        if not rows:
            raise HTTPException(404, detail="Tenant not found or inactive")
        
        _invalidate_tenant_cache(tenant_id)
        logger.info(f"API key rotated for tenant {tenant_id}")
        return RotateKeyResponse(
            tenant_id=tenant_id,
            new_api_key=new_key,
            message="Key rotated. Old key is immediately invalid."
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, detail="Failed to rotate key.")


@app.post("/admin/revoke-key/{tenant_id}")
async def revoke_api_key(tenant_id: str, admin: bool = Depends(require_admin_key)):
    """Revoke API key by deactivating tenant. Immediate effect."""
    try:
        from storage_multitenant import _db_execute
        rows = _db_execute("""
            UPDATE memory_service.tenants 
            SET active = false
            WHERE id = %s::UUID
            RETURNING id
        """, (tenant_id,), tenant_id="00000000-0000-0000-0000-000000000000")
        
        if not rows:
            raise HTTPException(404, detail="Tenant not found")
        
        _invalidate_tenant_cache(tenant_id)
        logger.info(f"API key revoked (tenant deactivated) for {tenant_id}")
        return {"tenant_id": tenant_id, "status": "revoked", "message": "Tenant deactivated. API key no longer valid."}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, detail="Failed to revoke key.")


@app.post("/admin/reactivate/{tenant_id}")
async def reactivate_tenant(tenant_id: str, admin: bool = Depends(require_admin_key)):
    """Reactivate a previously revoked tenant."""
    try:
        from storage_multitenant import _db_execute
        rows = _db_execute("""
            UPDATE memory_service.tenants 
            SET active = true
            WHERE id = %s::UUID
            RETURNING id
        """, (tenant_id,), tenant_id="00000000-0000-0000-0000-000000000000")
        
        if not rows:
            raise HTTPException(404, detail="Tenant not found")
        
        _invalidate_tenant_cache(tenant_id)
        logger.info(f"Tenant reactivated: {tenant_id}")
        return {"tenant_id": tenant_id, "status": "active"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, detail="Failed to reactivate tenant.")


@app.get("/admin/tenants")
async def list_tenants(admin: bool = Depends(require_admin_key)):
    """List all tenants. Admin only."""
    try:
        rows = _db_execute_rows("""
            SELECT id, name, plan, memory_limit, rate_limit_rpm, active, api_calls_count, created_at
            FROM memory_service.tenants 
            ORDER BY created_at DESC
        """, tenant_id="00000000-0000-0000-0000-000000000000")
        
        tenants = []
        for row in (rows or []):
            tenants.append({
                "id": str(row[0]),
                "name": str(row[1]),
                "plan": str(row[2]),
                "memory_limit": int(row[3]),
                "rate_limit_rpm": int(row[4]),
                "active": bool(row[5]),
                "api_calls_count": int(row[6] or 0),
                "created_at": str(row[7])
            })
        return {"tenants": tenants}
    except Exception as e:
        raise HTTPException(500, detail="Failed to list tenants.")

# Temporary admin endpoint to delete a user
@app.delete("/admin/delete-user/{email}")

# Temporary admin endpoint to delete a user  
@app.delete("/admin/delete-user/{email}")
async def admin_delete_user(email: str):
    """ADMIN: Delete user by email"""
    from api.auth import _db_exec
    
    try:
        result = _db_exec(
            "DELETE FROM memory_service.users WHERE email = %s RETURNING id",
            (email,)
        )
        deleted = len(result)
        return {"deleted": deleted, "email": email}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# Fix GitHub tenant API key
# ──────────────────────────────────────────────────────────────────────────────
# CP8 Phase 2 — Synthesis Trigger Endpoint
# ──────────────────────────────────────────────────────────────────────────────

class SynthesisRunRequest(BaseModel):
    agent_id: str = Field(..., description="Agent namespace to run synthesis for")
    max_clusters: Optional[int] = Field(None, ge=1, le=10, description="Max clusters to synthesize (capped at 10)")
    force: Optional[bool] = Field(False, description="Skip cooldown check")
    role_scope: Optional[str] = Field("public", description="Role tag for synthesis memories")

@app.post("/synthesis/run")
def synthesis_run(req: SynthesisRunRequest, tenant=Depends(require_api_key)):
    """
    Manual synthesis trigger endpoint.
    Free tier: blocked (403).
    Pro+ tiers: rate-limited by tier_gates.
    """
    try:
        # Check quota first
        from storage_multitenant import _get_connection_pool
        pool = _get_connection_pool()
        conn = pool.getconn()
        try:
            allowed, reason = tier_gates.check_synthesis_quota(
                tenant_id=tenant["id"],
                kind="manual_run",
                conn=conn,
                amount=1,
            )
        finally:
            pool.putconn(conn)

        if not allowed:
            # Determine status code based on tier
            from tier_gates import get_tier
            conn2 = pool.getconn()
            try:
                tier = get_tier(tenant["id"], conn2)
            finally:
                pool.putconn(conn2)
            
            if tier == "free":
                raise HTTPException(status_code=403, detail=reason)
            else:
                raise HTTPException(status_code=429, detail=reason)
        # Run synthesis via orchestrator
        max_clusters = min(req.max_clusters or 5, 10)  # Cap at 10
        result = run_synthesis_for_tenant(
            tenant_id=tenant["id"],
            agent_id=req.agent_id,
            role_scope=req.role_scope,
            force=req.force,
            max_clusters=max_clusters,
            triggered_by="manual_api",
        )
        
        track_api_usage(tenant["id"], "synthesis_run")
        logger.info(f"Synthesis run: tenant={tenant['id']} status={result['status']}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Synthesis run failed: {e}")
        raise HTTPException(status_code=500, detail="Synthesis failed")


@app.post("/admin/fix-github-tenant")
async def fix_github_tenant():
    """ADMIN: Generate API key for GitHub tenant"""
    from api.auth import _db_exec
    import secrets
    import hashlib
    
    tenant_id = "677cd129-7f9c-4556-93be-f10bf8c54a73"
    api_key = f"zl_live_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    _db_exec(
        "UPDATE memory_service.tenants SET api_key_live = %s, api_key_hash = %s WHERE id = %s::UUID",
        (api_key, api_key_hash, tenant_id),
        fetch=False
    )
    
    return {"fixed": True, "tenant_id": tenant_id, "api_key": api_key}
