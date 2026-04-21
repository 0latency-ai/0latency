"""
Graph Memory — Lightweight knowledge graph using Postgres recursive CTEs.
Provides entity tracking, relationship mapping, and multi-hop traversal
without requiring Neo4j or any external graph database.

Feature gap #1 vs mem0: Graph memory with entity relationships and traversal.
"""

import json
from datetime import datetime, timezone
from typing import Optional
from storage_multitenant import _db_execute, _db_execute_rows, _embed_text


def upsert_entity(agent_id: str, entity_name: str, entity_type: str = "unknown",
                  summary: str = None, tenant_id: str = None) -> str:
    """Create or update an entity node. Returns entity node ID."""
    rows = _db_execute_rows("""
        INSERT INTO memory_service.entity_nodes 
            (tenant_id, agent_id, entity_name, entity_type, summary)
        VALUES (%s::UUID, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, agent_id, entity_name) DO UPDATE
        SET entity_type = COALESCE(EXCLUDED.entity_type, memory_service.entity_nodes.entity_type),
            summary = COALESCE(EXCLUDED.summary, memory_service.entity_nodes.summary),
            last_seen = now(),
            mention_count = memory_service.entity_nodes.mention_count + 1
        RETURNING id
    """, (tenant_id, agent_id, entity_name, entity_type, summary), tenant_id=tenant_id)
    return str(rows[0][0]) if rows else None


def add_relationship(agent_id: str, source: str, target: str, relationship: str,
                     strength: float = 0.5, evidence_memory_id: str = None,
                     tenant_id: str = None) -> str:
    """Add or strengthen a relationship between two entities."""
    # Ensure both entities exist
    upsert_entity(agent_id, source, tenant_id=tenant_id)
    upsert_entity(agent_id, target, tenant_id=tenant_id)
    
    rows = _db_execute_rows("""
        INSERT INTO memory_service.entity_relationships
            (tenant_id, agent_id, source_entity, target_entity, relationship, 
             strength, evidence_memory_id)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, agent_id, source_entity, target_entity, relationship) DO UPDATE
        SET strength = LEAST(1.0, memory_service.entity_relationships.strength + 0.1),
            updated_at = now(),
            evidence_memory_id = COALESCE(EXCLUDED.evidence_memory_id, 
                                          memory_service.entity_relationships.evidence_memory_id)
        RETURNING id
    """, (tenant_id, agent_id, source, target, relationship, strength, evidence_memory_id),
        tenant_id=tenant_id)
    return str(rows[0][0]) if rows else None


def get_entity_subgraph(agent_id: str, entity_name: str, depth: int = 2,
                        tenant_id: str = None) -> dict:
    """
    Get the subgraph around an entity using recursive CTE.
    Returns nodes and edges within `depth` hops.
    This is our lightweight alternative to Neo4j — multi-hop traversal via SQL.
    """
    depth = min(depth, 4)  # Cap depth to prevent runaway queries
    
    rows = _db_execute_rows("""
        WITH RECURSIVE entity_graph AS (
            -- Base case: start from the target entity
            SELECT source_entity, target_entity, relationship, strength, 1 as hop
            FROM memory_service.entity_relationships
            WHERE agent_id = %s 
              AND (source_entity = %s OR target_entity = %s)
            
            UNION
            
            -- Recursive case: follow edges up to depth
            SELECT er.source_entity, er.target_entity, er.relationship, er.strength, eg.hop + 1
            FROM memory_service.entity_relationships er
            JOIN entity_graph eg ON (er.source_entity = eg.target_entity 
                                     OR er.target_entity = eg.source_entity
                                     OR er.source_entity = eg.source_entity
                                     OR er.target_entity = eg.target_entity)
            WHERE er.agent_id = %s AND eg.hop < %s
              AND er.source_entity != er.target_entity
        )
        SELECT DISTINCT source_entity, target_entity, relationship, strength, hop
        FROM entity_graph
        ORDER BY hop, strength DESC
        LIMIT 100
    """, (agent_id, entity_name, entity_name, agent_id, depth), tenant_id=tenant_id)
    
    # Build graph structure
    nodes = set()
    edges = []
    for row in (rows or []):
        source, target, rel, strength, hop = row
        nodes.add(str(source))
        nodes.add(str(target))
        edges.append({
            "source": str(source),
            "target": str(target),
            "relationship": str(rel),
            "strength": float(strength) if strength else 0.5,
            "hop": int(hop),
        })
    
    # Fetch node details
    node_details = {}
    for node_name in nodes:
        details = _db_execute_rows("""
            SELECT entity_name, entity_type, summary, mention_count, last_seen
            FROM memory_service.entity_nodes
            WHERE agent_id = %s AND entity_name = %s
        """, (agent_id, node_name), tenant_id=tenant_id)
        if details:
            d = details[0]
            node_details[node_name] = {
                "name": str(d[0]),
                "type": str(d[1]) if d[1] else "unknown",
                "summary": str(d[2]) if d[2] else None,
                "mention_count": int(d[3]) if d[3] else 1,
                "last_seen": str(d[4]) if d[4] else None,
            }
        else:
            node_details[node_name] = {"name": node_name, "type": "unknown"}
    
    return {
        "root": entity_name,
        "nodes": node_details,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }


def find_path(agent_id: str, source: str, target: str, max_depth: int = 4,
              tenant_id: str = None) -> list[dict]:
    """Find shortest path between two entities using recursive CTE."""
    max_depth = min(max_depth, 6)
    
    rows = _db_execute_rows("""
        WITH RECURSIVE paths AS (
            SELECT 
                source_entity, target_entity, relationship, strength,
                ARRAY[source_entity, target_entity] as path,
                1 as depth
            FROM memory_service.entity_relationships
            WHERE agent_id = %s AND source_entity = %s
            
            UNION ALL
            
            SELECT 
                er.source_entity, er.target_entity, er.relationship, er.strength,
                p.path || er.target_entity,
                p.depth + 1
            FROM memory_service.entity_relationships er
            JOIN paths p ON er.source_entity = p.target_entity
            WHERE er.agent_id = %s 
              AND p.depth < %s
              AND NOT er.target_entity = ANY(p.path)  -- prevent cycles
        )
        SELECT path, depth
        FROM paths
        WHERE target_entity = %s
        ORDER BY depth ASC
        LIMIT 1
    """, (agent_id, source, agent_id, max_depth, target), tenant_id=tenant_id)
    
    if not rows:
        return []
    
    path_entities = rows[0][0]  # postgres array
    return [str(e) for e in path_entities] if path_entities else []


def get_entity_memories(agent_id: str, entity_name: str, limit: int = 20,
                        tenant_id: str = None) -> list[dict]:
    """Get all memories associated with an entity."""
    rows = _db_execute_rows("""
        SELECT m.id, m.headline, m.context, m.memory_type, m.importance, m.created_at
        FROM memory_service.memories m
        JOIN memory_service.entity_index ei ON m.id = ei.memory_id
        WHERE ei.agent_id = %s AND ei.entity = %s AND m.superseded_at IS NULL
        ORDER BY m.importance DESC, m.created_at DESC
        LIMIT %s
    """, (agent_id, entity_name, limit), tenant_id=tenant_id)
    
    return [{
        "id": str(r[0]),
        "headline": str(r[1]),
        "context": str(r[2]) if r[2] else "",
        "memory_type": str(r[3]),
        "importance": float(r[4]) if r[4] else 0.5,
        "created_at": str(r[5]),
    } for r in (rows or [])]


def extract_relationships_from_memory(memory: dict, agent_id: str, tenant_id: str = None):
    """
    After storing a memory, auto-extract entity relationships from its content.
    Uses simple heuristics — no LLM call needed for basic relationships.
    """
    entities = memory.get("entities", [])
    if len(entities) < 2:
        return
    
    memory_id = memory.get("id")
    memory_type = memory.get("memory_type", "fact")
    
    # Infer relationship type from memory type
    rel_map = {
        "relationship": "related_to",
        "decision": "decided_with",
        "task": "works_on",
        "fact": "mentioned_with",
        "identity": "identified_as",
    }
    rel_type = rel_map.get(memory_type, "related_to")
    
    # Create pairwise relationships between all entities in this memory
    for i, source in enumerate(entities):
        # Upsert entity node
        entity_type = _infer_entity_type(source, memory)
        upsert_entity(agent_id, source, entity_type=entity_type, tenant_id=tenant_id)
        
        for target in entities[i+1:]:
            target_type = _infer_entity_type(target, memory)
            upsert_entity(agent_id, target, entity_type=target_type, tenant_id=tenant_id)
            add_relationship(agent_id, source, target, rel_type,
                           evidence_memory_id=memory_id, tenant_id=tenant_id)


def _infer_entity_type(entity: str, memory: dict) -> str:
    """Simple heuristic to infer entity type."""
    lower = entity.lower()
    content = (memory.get("full_content", "") + memory.get("headline", "")).lower()
    
    # Check context clues
    if any(w in content for w in [f"{lower} is a person", f"{lower} said", f"{lower} prefers"]):
        return "person"
    if any(w in lower for w in ["inc", "corp", "llc", "ltd", "company", "academy", "university"]):
        return "organization"
    if any(w in lower for w in ["project", "phase", "module"]):
        return "project"
    if any(w in content for w in [f"in {lower}", f"at {lower}", f"from {lower}"]):
        return "location"
    
    return "unknown"


def list_entities(agent_id: str, entity_type: str = None, limit: int = 50,
                  tenant_id: str = None) -> list[dict]:
    """List all known entities for an agent."""
    if entity_type:
        rows = _db_execute_rows("""
            SELECT entity_name, entity_type, summary, mention_count, first_seen, last_seen
            FROM memory_service.entity_nodes
            WHERE agent_id = %s AND entity_type = %s
            ORDER BY mention_count DESC, last_seen DESC
            LIMIT %s
        """, (agent_id, entity_type, limit), tenant_id=tenant_id)
    else:
        rows = _db_execute_rows("""
            SELECT entity_name, entity_type, summary, mention_count, first_seen, last_seen
            FROM memory_service.entity_nodes
            WHERE agent_id = %s
            ORDER BY mention_count DESC, last_seen DESC
            LIMIT %s
        """, (agent_id, limit), tenant_id=tenant_id)
    
    return [{
        "name": str(r[0]),
        "type": str(r[1]) if r[1] else "unknown",
        "summary": str(r[2]) if r[2] else None,
        "mention_count": int(r[3]) if r[3] else 1,
        "first_seen": str(r[4]) if r[4] else None,
        "last_seen": str(r[5]) if r[5] else None,
    } for r in (rows or [])]
