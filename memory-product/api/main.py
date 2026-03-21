"""
Zero Latency Memory API — Phase B  
FastAPI REST endpoints for multi-tenant agent memory with real authentication.
"""
import os
import sys
import time
import hashlib
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, Request
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
    get_tenant_by_api_key, create_tenant, track_api_usage
)
from recall import recall_fixed as recall

# --- App ---
app = FastAPI(
    title="Zero Latency Memory API",
    version="0.1.0",
    description="Structured memory extraction, storage, and recall for AI agents.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return response

# --- Configuration ---
def _admin_key(): return os.environ.get("MEMORY_ADMIN_KEY", "")

# --- Rate Limiting (simple in-memory, replace with Redis for prod) ---
_rate_limits: dict[str, list[float]] = {}

def _check_rate_limit(tenant_id: str, rate_limit_rpm: int):
    """Check if tenant has exceeded their rate limit."""
    now = time.time()
    window = _rate_limits.setdefault(tenant_id, [])
    # Purge entries older than 60s
    _rate_limits[tenant_id] = [t for t in window if now - t < 60]
    if len(_rate_limits[tenant_id]) >= rate_limit_rpm:
        raise HTTPException(429, detail=f"Rate limit exceeded ({rate_limit_rpm}/min). Try again in 60 seconds.")
    _rate_limits[tenant_id].append(now)

# --- Auth ---
async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Multi-tenant auth via API key header with real validation."""
    if not x_api_key or not x_api_key.startswith("zl_live_") or len(x_api_key) != 40:
        raise HTTPException(401, detail="Invalid API key format")
    
    # Hash the API key to look up tenant
    api_key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    
    # Look up tenant by hashed key
    tenant = get_tenant_by_api_key(api_key_hash)
    if not tenant:
        raise HTTPException(401, detail="Invalid API key")
    
    if not tenant["active"]:
        raise HTTPException(401, detail="Account suspended")
    
    # Check rate limit
    _check_rate_limit(tenant["id"], tenant["rate_limit_rpm"])
    
    # Set tenant context for this request
    set_tenant_context(tenant["id"])
    
    # Store tenant_id on request state for logging middleware
    # (FastAPI doesn't give us request in Depends easily, so we use a thread-local approach)
    
    return tenant

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
class ExtractRequest(BaseModel):
    agent_id: str
    human_message: str
    agent_message: str
    session_key: Optional[str] = None
    turn_id: Optional[str] = None

class ExtractResponse(BaseModel):
    memories_stored: int
    memory_ids: list[str]

class RecallRequest(BaseModel):
    agent_id: str
    conversation_context: str
    budget_tokens: int = Field(default=4000, ge=500, le=16000)
    dynamic_budget: bool = False

class RecallResponse(BaseModel):
    context_block: str
    memories_used: int
    tokens_used: int

class MemoryItem(BaseModel):
    id: str
    headline: str
    memory_type: str
    importance: float
    created_at: str

class CreateTenantRequest(BaseModel):
    name: str
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

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    memories_total: Optional[int] = None

# --- Endpoints ---
@app.post("/extract", response_model=ExtractResponse)
async def extract_endpoint(req: ExtractRequest, tenant: dict = Depends(require_api_key)):
    """Extract memories from a conversation turn."""
    start_time = time.time()
    try:
        memories = extract_memories(
            human_message=req.human_message,
            agent_message=req.agent_message,
            agent_id=req.agent_id,
            session_key=req.session_key,
            turn_id=req.turn_id,
        )
        if not memories:
            response = ExtractResponse(memories_stored=0, memory_ids=[])
        else:
            ids = store_memories(memories, tenant["id"])
            response = ExtractResponse(memories_stored=len(ids), memory_ids=ids)
        
        # Track usage
        response_time = int((time.time() - start_time) * 1000)
        track_api_usage(tenant["id"], "/extract", 
                       tokens_used=len(req.human_message + req.agent_message), 
                       response_time_ms=response_time)
        
        return response
    except Exception as e:
        track_api_usage(tenant["id"], "/extract", response_time_ms=int((time.time() - start_time) * 1000), status_code=500)
        raise HTTPException(500, detail="Extraction failed. Please check your input and try again.")


@app.post("/recall", response_model=RecallResponse)
async def recall_endpoint(req: RecallRequest, tenant: dict = Depends(require_api_key)):
    """Recall relevant memories for a conversation context."""
    start_time = time.time()
    try:
        result = recall(
            agent_id=req.agent_id,
            conversation_context=req.conversation_context,
            budget_tokens=req.budget_tokens,
            # dynamic_budget=req.dynamic_budget,  # TODO: add to recall_fixed
        )
        response = RecallResponse(
            context_block=result["context_block"],
            memories_used=result["memories_used"],
            tokens_used=result["tokens_used"],
        )
        
        # Track usage
        response_time = int((time.time() - start_time) * 1000)
        track_api_usage(tenant["id"], "/recall", 
                       tokens_used=result["tokens_used"], 
                       response_time_ms=response_time)
        
        return response
    except Exception as e:
        track_api_usage(tenant["id"], "/recall", response_time_ms=int((time.time() - start_time) * 1000), status_code=500)
        raise HTTPException(500, detail="Recall failed. Please check your input and try again.")


@app.get("/memories", response_model=list[MemoryItem])
async def list_memories(
    agent_id: str,
    limit: int = 50,
    memory_type: Optional[str] = None,
    tenant: dict = Depends(require_api_key),
):
    """List memories for an agent."""
    start_time = time.time()
    try:
        from storage_multitenant import _db_execute
        
        tenant_id = tenant["id"]
        
        if memory_type:
            rows = _db_execute("""
                SELECT id, headline, memory_type, importance, created_at
                FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s AND superseded_at IS NULL AND memory_type = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (agent_id, tenant_id, memory_type, min(limit, 200)), tenant_id=tenant_id)
        else:
            rows = _db_execute("""
                SELECT id, headline, memory_type, importance, created_at
                FROM memory_service.memories
                WHERE agent_id = %s AND tenant_id = %s AND superseded_at IS NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (agent_id, tenant_id, min(limit, 200)), tenant_id=tenant_id)
        
        items = []
        for row in (rows or []):
            parts = row.split("|||")
            if len(parts) >= 5:
                items.append(MemoryItem(
                    id=parts[0].strip(),
                    headline=parts[1].strip(),
                    memory_type=parts[2].strip(),
                    importance=float(parts[3].strip()),
                    created_at=parts[4].strip(),
                ))
        
        # Track usage
        response_time = int((time.time() - start_time) * 1000)
        track_api_usage(tenant["id"], "/memories", response_time_ms=response_time)
        
        return items
    except Exception as e:
        track_api_usage(tenant["id"], "/memories", response_time_ms=int((time.time() - start_time) * 1000), status_code=500)
        raise HTTPException(500, detail="Failed to list memories. Please try again.")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check — no auth required. Verifies DB connectivity."""
    try:
        from storage_multitenant import _db_execute
        rows = _db_execute(
            "SELECT COUNT(*) FROM memory_service.memories WHERE superseded_at IS NULL",
            tenant_id="00000000-0000-0000-0000-000000000000"
        )
        total = int(rows[0].split("|||")[0]) if rows else 0
        return HealthResponse(
            status="ok",
            version="0.1.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            memories_total=total,
        )
    except Exception:
        return HealthResponse(
            status="degraded",
            version="0.1.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            memories_total=None,
        )


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


# --- Admin Endpoints ---
@app.post("/api-keys", response_model=CreateTenantResponse)
async def create_api_key(req: CreateTenantRequest, admin: bool = Depends(require_admin_key)):
    """Create a new tenant and API key. Requires admin authentication."""
    try:
        tenant = create_tenant(req.name, req.plan)
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
            SET api_key_hash = %s
            WHERE id = %s::UUID AND active = true
            RETURNING id
        """, (new_hash, tenant_id), tenant_id="00000000-0000-0000-0000-000000000000")
        
        if not rows:
            raise HTTPException(404, detail="Tenant not found or inactive")
        
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
        from storage_multitenant import _db_execute
        # Bypass RLS for admin query
        rows = _db_execute("""
            SELECT id, name, plan, memory_limit, rate_limit_rpm, active, api_calls_count, created_at
            FROM memory_service.tenants 
            ORDER BY created_at DESC
        """, tenant_id="00000000-0000-0000-0000-000000000000")
        
        tenants = []
        for row in (rows or []):
            parts = row.split("|||")
            if len(parts) >= 8:
                tenants.append({
                    "id": parts[0],
                    "name": parts[1],
                    "plan": parts[2],
                    "memory_limit": int(parts[3]),
                    "rate_limit_rpm": int(parts[4]),
                    "active": parts[5].lower() in ('t', 'true', '1'),
                    "api_calls_count": int(parts[6] or 0),
                    "created_at": parts[7]
                })
        return {"tenants": tenants}
    except Exception as e:
        raise HTTPException(500, detail="Failed to list tenants.")
