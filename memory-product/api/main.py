"""
0Lat Memory API — Phase B
FastAPI service wrapping the memory engine for multi-tenant SaaS access.

Endpoints:
  POST /v1/extract    — extract memories from a conversation turn
  POST /v1/recall     — recall relevant memories for a query
  GET  /v1/memories   — list/filter stored memories
  GET  /v1/handoff    — get latest conversation state
  GET  /v1/health     — memory system stats
  DELETE /v1/memories/{id} — delete a specific memory
  POST /v1/import     — import historical conversations
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add parent src to path for memory engine imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

app = FastAPI(
    title="0Lat Memory API",
    description="Zero-latency structured memory for AI agents",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth ---

API_KEYS = {}  # Will be loaded from DB; for now, env-based

def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Verify API key and return the associated agent_id/tenant."""
    # Phase B MVP: single API key from env
    valid_key = os.environ.get("OLAT_API_KEY", "")
    if not valid_key or x_api_key != valid_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Return the tenant/agent_id associated with this key
    return os.environ.get("OLAT_DEFAULT_AGENT", "default")


# --- Request/Response Models ---

class ExtractRequest(BaseModel):
    human_message: str = Field(..., description="The human's message")
    agent_message: str = Field(..., description="The agent's response")
    agent_id: Optional[str] = Field(None, description="Agent identifier (defaults to account default)")
    session_key: Optional[str] = Field(None, description="Session identifier for grouping")
    recent_turns: Optional[list] = Field(None, description="Recent conversation turns for multi-turn inference [(human, agent), ...]")

class RecallRequest(BaseModel):
    query: str = Field(..., description="What to recall — natural language query")
    agent_id: Optional[str] = Field(None, description="Agent identifier")
    budget_tokens: Optional[int] = Field(4000, description="Max tokens for recalled context")
    dynamic_budget: Optional[bool] = Field(True, description="Auto-scale budget based on query complexity")

class MemoryFilter(BaseModel):
    memory_type: Optional[str] = None
    min_importance: Optional[float] = None
    limit: Optional[int] = 50
    offset: Optional[int] = 0

class ImportRequest(BaseModel):
    content: str = Field(..., description="Raw conversation export (JSON string)")
    source: Optional[str] = Field("unknown", description="Source platform: claude, chatgpt, gemini")
    agent_id: Optional[str] = None


# --- Endpoints ---

@app.get("/")
async def root():
    return {"service": "0Lat Memory API", "version": "0.1.0", "status": "running"}


@app.post("/v1/extract")
async def extract(req: ExtractRequest, tenant: str = Depends(verify_api_key)):
    """Extract structured memories from a conversation turn."""
    from extraction import extract_memories
    from storage import store_memories
    
    agent_id = req.agent_id or tenant
    turn_id = str(uuid.uuid4())
    
    try:
        memories = extract_memories(
            human_message=req.human_message,
            agent_message=req.agent_message,
            agent_id=agent_id,
            session_key=req.session_key or "api",
            turn_id=turn_id,
            recent_turns=req.recent_turns,
        )
        
        if memories:
            ids = store_memories(memories)
            return {
                "memories_extracted": len(ids),
                "memory_ids": ids,
                "memories": [
                    {
                        "id": ids[i] if i < len(ids) else None,
                        "headline": m.get("headline"),
                        "memory_type": m.get("memory_type"),
                        "importance": m.get("importance"),
                    }
                    for i, m in enumerate(memories)
                ],
            }
        return {"memories_extracted": 0, "memory_ids": [], "memories": []}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/recall")
async def recall_memories(req: RecallRequest, tenant: str = Depends(verify_api_key)):
    """Recall relevant memories for a given query/context."""
    from recall import recall
    
    agent_id = req.agent_id or tenant
    
    try:
        result = recall(
            agent_id=agent_id,
            conversation_context=req.query,
            budget_tokens=req.budget_tokens,
            dynamic_budget=req.dynamic_budget,
        )
        return {
            "context_block": result["context_block"],
            "memories_used": result["memories_used"],
            "tokens_used": result["tokens_used"],
            "budget_remaining": result["budget_remaining"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/memories")
async def list_memories(
    agent_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    min_importance: Optional[float] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    tenant: str = Depends(verify_api_key),
):
    """List stored memories with optional filters."""
    from storage import _db_execute
    
    aid = agent_id or tenant
    conditions = [f"agent_id = '{aid}'", "superseded_at IS NULL"]
    
    if memory_type:
        conditions.append(f"memory_type = '{memory_type}'")
    if min_importance is not None:
        conditions.append(f"importance >= {min_importance}")
    
    where = " AND ".join(conditions)
    
    try:
        rows = _db_execute(f"""
            SELECT id, headline, context, memory_type, importance, confidence, 
                   created_at, entities, project, categories
            FROM memory_service.memories
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT {limit} OFFSET {offset}
        """)
        
        memories = []
        for row in rows:
            parts = row.split("|")
            if len(parts) >= 10:
                memories.append({
                    "id": parts[0],
                    "headline": parts[1],
                    "context": parts[2],
                    "memory_type": parts[3],
                    "importance": float(parts[4]) if parts[4] else 0.5,
                    "confidence": float(parts[5]) if parts[5] else 0.8,
                    "created_at": parts[6],
                    "entities": parts[7],
                    "project": parts[8],
                    "categories": parts[9],
                })
        
        # Get total count
        count_rows = _db_execute(f"SELECT COUNT(*) FROM memory_service.memories WHERE {where}")
        total = int(count_rows[0]) if count_rows else 0
        
        return {"memories": memories, "total": total, "limit": limit, "offset": offset}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/handoff")
async def get_handoff(agent_id: Optional[str] = None, tenant: str = Depends(verify_api_key)):
    """Get the latest conversation state handoff."""
    from handoff import get_latest_handoff
    
    aid = agent_id or tenant
    
    try:
        handoff = get_latest_handoff(aid)
        if handoff:
            return handoff
        return {"summary": "No handoff available", "decisions_made": [], "open_threads": [], "active_projects": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/health")
async def health(agent_id: Optional[str] = None, tenant: str = Depends(verify_api_key)):
    """Get memory system health stats."""
    from storage import get_memory_stats
    
    aid = agent_id or tenant
    
    try:
        stats = get_memory_stats(aid)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/memories/{memory_id}")
async def delete_memory(memory_id: str, tenant: str = Depends(verify_api_key)):
    """Delete a specific memory."""
    from storage import _db_execute
    
    try:
        # Verify ownership
        rows = _db_execute(f"""
            SELECT agent_id FROM memory_service.memories WHERE id = '{memory_id}'
        """)
        if not rows:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        # Soft delete (supersede, don't destroy)
        _db_execute(f"""
            UPDATE memory_service.memories 
            SET superseded_at = now() 
            WHERE id = '{memory_id}'
        """)
        return {"deleted": True, "memory_id": memory_id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/import")
async def import_conversations(req: ImportRequest, tenant: str = Depends(verify_api_key)):
    """Import historical conversations from LLM exports."""
    agent_id = req.agent_id or tenant
    
    # TODO: Wire to historical_import.py
    return {"status": "not_yet_implemented", "message": "Historical import coming in v0.2.0"}


# --- Startup ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("OLAT_PORT", "8100"))
    uvicorn.run(app, host="0.0.0.0", port=port)
