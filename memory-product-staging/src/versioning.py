"""
Memory Versioning — Full changelog per memory.
Feature gap #3 vs mem0: Memory history/versioning with audit trail.
"""

import json
from datetime import datetime, timezone
from typing import Optional
from storage_multitenant import _db_execute_rows


def snapshot_version(memory_id: str, tenant_id: str, changed_by: str = "system",
                     change_reason: str = None) -> Optional[int]:
    """
    Snapshot the current state of a memory before it changes.
    Call this BEFORE updating a memory to preserve its previous state.
    Returns the version number.
    """
    # Get current state (including sentiment fields)
    rows = _db_execute_rows("""
        SELECT headline, context, full_content, memory_type, importance, confidence, version,
               sentiment, sentiment_score
        FROM memory_service.memories
        WHERE id = %s::UUID AND tenant_id = %s::UUID
    """, (memory_id, tenant_id), tenant_id=tenant_id)
    
    if not rows:
        return None
    
    current = rows[0]
    version = int(current[6]) if current[6] else 1
    
    # Insert version record
    _db_execute_rows("""
        INSERT INTO memory_service.memory_versions 
            (tenant_id, memory_id, version_number, headline, context, full_content,
             memory_type, importance, confidence, changed_by, change_reason)
        VALUES (%s::UUID, %s::UUID, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        tenant_id, memory_id, version,
        str(current[0]), str(current[1]) if current[1] else None,
        str(current[2]) if current[2] else None,
        str(current[3]), float(current[4]) if current[4] else 0.5,
        float(current[5]) if current[5] else 0.8,
        changed_by, change_reason
    ), tenant_id=tenant_id, fetch_results=False)
    
    # Increment version on the memory
    _db_execute_rows("""
        UPDATE memory_service.memories SET version = version + 1
        WHERE id = %s::UUID AND tenant_id = %s::UUID
    """, (memory_id, tenant_id), tenant_id=tenant_id, fetch_results=False)
    
    return version


def get_history(memory_id: str, tenant_id: str, limit: int = 20) -> list[dict]:
    """Get version history for a memory."""
    rows = _db_execute_rows("""
        SELECT version_number, headline, context, full_content, memory_type,
               importance, confidence, changed_by, change_reason, created_at, diff_summary
        FROM memory_service.memory_versions
        WHERE memory_id = %s::UUID AND tenant_id = %s::UUID
        ORDER BY version_number DESC
        LIMIT %s
    """, (memory_id, tenant_id, limit), tenant_id=tenant_id)
    
    versions = []
    for r in (rows or []):
        versions.append({
            "version": int(r[0]),
            "headline": str(r[1]),
            "context": str(r[2]) if r[2] else None,
            "full_content": str(r[3]) if r[3] else None,
            "memory_type": str(r[4]) if r[4] else None,
            "importance": float(r[5]) if r[5] else None,
            "confidence": float(r[6]) if r[6] else None,
            "changed_by": str(r[7]) if r[7] else "system",
            "change_reason": str(r[8]) if r[8] else None,
            "created_at": str(r[9]),
            "diff_summary": str(r[10]) if r[10] else None,
        })
    
    # Also get current state
    current = _db_execute_rows("""
        SELECT headline, memory_type, importance, version
        FROM memory_service.memories
        WHERE id = %s::UUID AND tenant_id = %s::UUID
    """, (memory_id, tenant_id), tenant_id=tenant_id)
    
    current_version = None
    if current:
        current_version = {
            "version": int(current[0][3]) if current[0][3] else 1,
            "headline": str(current[0][0]),
            "memory_type": str(current[0][1]),
            "importance": float(current[0][2]) if current[0][2] else 0.5,
            "is_current": True,
        }
    
    return {
        "memory_id": memory_id,
        "current": current_version,
        "history": versions,
        "total_versions": len(versions) + (1 if current_version else 0),
    }


def compute_diff_summary(old: dict, new: dict) -> str:
    """Generate human-readable diff between two memory states."""
    diffs = []
    
    if old.get("headline") != new.get("headline"):
        diffs.append(f"headline: '{old.get('headline', '')}' → '{new.get('headline', '')}'")
    
    if old.get("memory_type") != new.get("memory_type"):
        diffs.append(f"type: {old.get('memory_type')} → {new.get('memory_type')}")
    
    old_imp = old.get("importance", 0.5)
    new_imp = new.get("importance", 0.5)
    if abs(old_imp - new_imp) > 0.01:
        diffs.append(f"importance: {old_imp:.2f} → {new_imp:.2f}")
    
    old_conf = old.get("confidence", 0.8)
    new_conf = new.get("confidence", 0.8)
    if abs(old_conf - new_conf) > 0.01:
        diffs.append(f"confidence: {old_conf:.2f} → {new_conf:.2f}")
    
    if old.get("context") != new.get("context"):
        diffs.append("context updated")
    
    if old.get("full_content") != new.get("full_content"):
        diffs.append("full_content updated")
    
    return "; ".join(diffs) if diffs else "no changes"
