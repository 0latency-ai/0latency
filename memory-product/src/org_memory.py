"""
Organization / Team Memory — Shared memory across agents in an org.
Feature gap #5 vs mem0: Organization-scoped shared memory layer.
"""

import json
from typing import Optional
from storage_multitenant import _db_execute_rows, _embed_text


def create_organization(name: str, metadata: dict = None) -> dict:
    """Create a new organization."""
    rows = _db_execute_rows("""
        INSERT INTO memory_service.organizations (name, metadata)
        VALUES (%s, %s::jsonb)
        RETURNING id, created_at
    """, (name, json.dumps(metadata or {})),
        tenant_id="00000000-0000-0000-0000-000000000000")
    
    if rows:
        return {
            "id": str(rows[0][0]),
            "name": name,
            "created_at": str(rows[0][1]),
        }
    raise RuntimeError("Failed to create organization")


def add_tenant_to_org(tenant_id: str, org_id: str) -> bool:
    """Associate a tenant with an organization."""
    rows = _db_execute_rows("""
        UPDATE memory_service.tenants 
        SET org_id = %s::UUID
        WHERE id = %s::UUID
        RETURNING id
    """, (org_id, tenant_id), tenant_id="00000000-0000-0000-0000-000000000000")
    return bool(rows)


def get_tenant_org(tenant_id: str) -> Optional[str]:
    """Get the org_id for a tenant."""
    rows = _db_execute_rows("""
        SELECT org_id FROM memory_service.tenants WHERE id = %s::UUID
    """, (tenant_id,), tenant_id="00000000-0000-0000-0000-000000000000")
    
    if rows and rows[0][0]:
        return str(rows[0][0])
    return None


def store_org_memory(org_id: str, headline: str, context: str = None,
                     full_content: str = None, memory_type: str = "fact",
                     importance: float = 0.5, entities: list = None,
                     categories: list = None, created_by: str = None) -> str:
    """Store a memory at the organization level, visible to all org members."""
    # Generate embedding
    embed_text = f"{headline}. {context or ''}"
    embedding = _embed_text(embed_text)
    
    rows = _db_execute_rows("""
        INSERT INTO memory_service.org_memories 
            (org_id, headline, context, full_content, memory_type,
             importance, entities, categories, embedding, created_by)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s::UUID)
        RETURNING id
    """, (
        org_id, headline, context, full_content, memory_type,
        importance, entities or [], categories or [], embedding, created_by
    ), tenant_id="00000000-0000-0000-0000-000000000000")
    
    return str(rows[0][0]) if rows else None


def recall_org_memories(org_id: str, query: str, limit: int = 10) -> list[dict]:
    """Recall relevant organization-level memories."""
    embedding = _embed_text(query[:2000])
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    
    rows = _db_execute_rows("""
        SELECT id, headline, context, full_content, memory_type, importance,
               entities, categories, created_at,
               1 - (embedding <=> %s::vector) as similarity
        FROM memory_service.org_memories
        WHERE org_id = %s::UUID
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (embedding_str, org_id, embedding_str, limit),
        tenant_id="00000000-0000-0000-0000-000000000000")
    
    return [{
        "id": str(r[0]),
        "headline": str(r[1]),
        "context": str(r[2]) if r[2] else "",
        "full_content": str(r[3]) if r[3] else "",
        "memory_type": str(r[4]),
        "importance": float(r[5]) if r[5] else 0.5,
        "entities": list(r[6]) if r[6] else [],
        "categories": list(r[7]) if r[7] else [],
        "created_at": str(r[8]),
        "similarity": float(r[9]) if r[9] else 0,
    } for r in (rows or [])]


def list_org_memories(org_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    """List all org memories with pagination."""
    rows = _db_execute_rows("""
        SELECT id, headline, context, memory_type, importance, created_at
        FROM memory_service.org_memories
        WHERE org_id = %s::UUID
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (org_id, limit, offset),
        tenant_id="00000000-0000-0000-0000-000000000000")
    
    return [{
        "id": str(r[0]),
        "headline": str(r[1]),
        "context": str(r[2]) if r[2] else "",
        "memory_type": str(r[3]),
        "importance": float(r[4]) if r[4] else 0.5,
        "created_at": str(r[5]),
    } for r in (rows or [])]


def delete_org_memory(org_id: str, memory_id: str) -> bool:
    """Delete an org memory."""
    rows = _db_execute_rows("""
        DELETE FROM memory_service.org_memories
        WHERE id = %s::UUID AND org_id = %s::UUID
        RETURNING id
    """, (memory_id, org_id),
        tenant_id="00000000-0000-0000-0000-000000000000")
    return bool(rows)


def promote_to_org(tenant_id: str, memory_id: str) -> Optional[str]:
    """
    Promote an agent-level memory to org-level so all team members can see it.
    Returns the org memory ID.
    """
    org_id = get_tenant_org(tenant_id)
    if not org_id:
        raise ValueError("Tenant is not part of an organization")
    
    # Get the original memory
    rows = _db_execute_rows("""
        SELECT headline, context, full_content, memory_type, importance, entities, categories
        FROM memory_service.memories
        WHERE id = %s::UUID AND tenant_id = %s::UUID AND superseded_at IS NULL
    """, (memory_id, tenant_id), tenant_id=tenant_id)
    
    if not rows:
        raise ValueError("Memory not found")
    
    r = rows[0]
    return store_org_memory(
        org_id=org_id,
        headline=str(r[0]),
        context=str(r[1]) if r[1] else None,
        full_content=str(r[2]) if r[2] else None,
        memory_type=str(r[3]),
        importance=float(r[4]) if r[4] else 0.5,
        entities=list(r[5]) if r[5] else [],
        categories=list(r[6]) if r[6] else [],
        created_by=tenant_id,
    )
