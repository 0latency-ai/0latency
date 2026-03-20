"""
Zero Latency Memory API — Phase B
FastAPI REST endpoints for multi-tenant agent memory.
"""
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add src/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from extraction import extract_memories
from storage import store_memory, store_memories
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

# --- Rate Limiting (simple in-memory, replace with Redis for prod) ---
_rate_limits: dict[str, list[float]] = {}
RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "60"))

def _check_rate_limit(api_key: str):
    now = time.time()
    window = _rate_limits.setdefault(api_key, [])
    # Purge entries older than 60s
    _rate_limits[api_key] = [t for t in window if now - t < 60]
    if len(_rate_limits[api_key]) >= RATE_LIMIT_RPM:
        raise HTTPException(429, detail="Rate limit exceeded. Try again in 60 seconds.")
    _rate_limits[api_key].append(now)

# --- Auth ---
async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Multi-tenant auth via API key header. Stub: accepts any non-empty key."""
    # TODO: Validate against tenant table in Postgres
    if not x_api_key or len(x_api_key) < 8:
        raise HTTPException(401, detail="Invalid API key")
    _check_rate_limit(x_api_key)
    # Return tenant_id derived from key (stub: key IS the tenant)
    return x_api_key

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

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    memories_total: Optional[int] = None

# --- Endpoints ---
@app.post("/extract", response_model=ExtractResponse)
async def extract_endpoint(req: ExtractRequest, tenant: str = Depends(require_api_key)):
    """Extract memories from a conversation turn."""
    try:
        memories = extract_memories(
            human_message=req.human_message,
            agent_message=req.agent_message,
            agent_id=req.agent_id,
            session_key=req.session_key,
            turn_id=req.turn_id,
        )
        if not memories:
            return ExtractResponse(memories_stored=0, memory_ids=[])
        
        ids = store_memories(memories)
        return ExtractResponse(memories_stored=len(ids), memory_ids=ids)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/recall", response_model=RecallResponse)
async def recall_endpoint(req: RecallRequest, tenant: str = Depends(require_api_key)):
    """Recall relevant memories for a conversation context."""
    try:
        result = recall(
            agent_id=req.agent_id,
            conversation_context=req.conversation_context,
            budget_tokens=req.budget_tokens,
            dynamic_budget=req.dynamic_budget,
        )
        return RecallResponse(
            context_block=result["context_block"],
            memories_used=result["memories_used"],
            tokens_used=result["tokens_used"],
        )
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/memories", response_model=list[MemoryItem])
async def list_memories(
    agent_id: str,
    limit: int = 50,
    memory_type: Optional[str] = None,
    tenant: str = Depends(require_api_key),
):
    """List memories for an agent."""
    from storage import _db_execute
    
    type_filter = f"AND memory_type = '{memory_type}'" if memory_type else ""
    rows = _db_execute(f"""
        SELECT id, headline, memory_type, importance, created_at
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}' AND superseded_at IS NULL {type_filter}
        ORDER BY created_at DESC
        LIMIT {min(limit, 200)}
    """)
    
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
    return items


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check — no auth required."""
    from storage import _db_execute
    
    count = None
    try:
        rows = _db_execute("SELECT COUNT(*) FROM memory_service.memories WHERE superseded_at IS NULL")
        if rows:
            count = int(rows[0].strip())
    except Exception:
        pass
    
    return HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        memories_total=count,
    )
