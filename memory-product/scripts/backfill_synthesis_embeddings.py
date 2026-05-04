#!/usr/bin/env python3
"""
CP8 Chain B-3.5 Stage 00: Backfill local_embedding for synthesis memory_type rows.
Uses all-MiniLM-L6-v2 (384d) read-path model from src/storage_multitenant.py.
Idempotent: only updates rows where local_embedding IS NULL.
"""

import os
import sys
import psycopg2
import time
import numpy as np
from sentence_transformers import SentenceTransformer

def main():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('[ERROR] DATABASE_URL environment variable not set', file=sys.stderr)
        sys.exit(1)
    
    print('[INFO] Loading all-MiniLM-L6-v2 model...')
    start_load = time.time()
    model = SentenceTransformer('all-MiniLM-L6-v2')
    load_time = time.time() - start_load
    print(f'[INFO] Model loaded in {load_time:.2f}s')
    
    print('[INFO] Connecting to database...')
    conn = psycopg2.connect(db_url)
    
    # Count synthesis rows needing backfill
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM memory_service.memories 
            WHERE memory_type='synthesis' AND local_embedding IS NULL
        """)
        total_count = cur.fetchone()[0]
    
    print(f'[INFO] Found {total_count} synthesis rows with NULL local_embedding')
    
    if total_count == 0:
        print('[INFO] No synthesis rows to backfill. Exiting.')
        conn.close()
        return 0
    
    # Fetch all synthesis rows needing backfill
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, headline, full_content
            FROM memory_service.memories
            WHERE memory_type='synthesis' AND local_embedding IS NULL
            ORDER BY created_at
        """)
        rows = cur.fetchall()
    
    print(f'[INFO] Backfilling {len(rows)} synthesis rows...')
    
    start_time = time.time()
    for idx, (row_id, headline, full_content) in enumerate(rows, 1):
        # Generate embedding text (headline + full_content)
        embed_text = f"{headline or ''}. {full_content or ''}"
        
        # Generate embedding using local model
        embedding = model.encode(embed_text, convert_to_numpy=True, show_progress_bar=False)
        
        # Normalize for cosine similarity
        embedding = embedding / np.linalg.norm(embedding)
        
        # Convert to list for psycopg2
        embedding_list = embedding.tolist()
        
        # Update the row
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE memory_service.memories 
                   SET local_embedding = %s::vector 
                   WHERE id = %s""",
                (embedding_list, row_id)
            )
        conn.commit()
        
        if idx % 10 == 0 or idx == len(rows):
            elapsed = time.time() - start_time
            rate = idx / elapsed if elapsed > 0 else 0
            print(f'[PROGRESS] {idx}/{len(rows)} rows ({rate:.1f} rows/sec)')
    
    total_time = time.time() - start_time
    print(f'[DONE] Backfilled {len(rows)} synthesis rows in {total_time:.2f}s')
    
    conn.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
