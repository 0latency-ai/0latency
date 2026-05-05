#!/usr/bin/env python3
"""One-shot backfill of metadata.cluster_id for existing synthesis rows."""
import os
import hashlib
import psycopg2
from psycopg2.extras import Json

def cluster_id(parent_ids):
    """Derive deterministic cluster_id from parent memory IDs."""
    sorted_ids = sorted(parent_ids)
    return hashlib.sha256(",".join(sorted_ids).encode()).hexdigest()[:16]

def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    
    # Find all synthesis rows without cluster_id
    cur.execute("""
        SELECT id, metadata
        FROM memory_service.memories
        WHERE memory_type = 'synthesis'
          AND (metadata->>'cluster_id' IS NULL OR metadata->>'cluster_id' = '')
    """)
    rows = cur.fetchall()
    
    updated = 0
    skipped = 0
    
    for memory_id, metadata in rows:
        parents = metadata.get("parent_memory_ids") or []
        if not parents:
            skipped += 1
            continue
        
        cid = cluster_id(parents)
        new_metadata = {**metadata, "cluster_id": cid}
        
        cur.execute(
            "UPDATE memory_service.memories SET metadata = %s WHERE id = %s",
            (Json(new_metadata), memory_id)
        )
        updated += 1
    
    conn.commit()
    print(f"Backfilled cluster_id on {updated} synthesis rows (skipped {skipped} rows without parents)")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
