"""
Sprint 3 Backfill: Populate local_embedding column for all existing memories.
Generates 384-dimensional embeddings using all-MiniLM-L6-v2 model.
Runs in batches of 100 with progress logging.
"""

import os
import psycopg2
import time
import numpy as np
from sentence_transformers import SentenceTransformer

# Database connection
MEMORY_DB_CONN = os.environ.get("MEMORY_DB_CONN", "")
if not MEMORY_DB_CONN:
    raise RuntimeError("MEMORY_DB_CONN environment variable must be set")

# Load model once at startup
print("[INFO] Loading all-MiniLM-L6-v2 model...")
start_load = time.time()
model = SentenceTransformer("all-MiniLM-L6-v2")
load_time = time.time() - start_load
print(f"[INFO] Model loaded in {load_time:.2f}s")

# Connect to database
print("[INFO] Connecting to database...")
conn = psycopg2.connect(MEMORY_DB_CONN)
cursor = conn.cursor()

# Get total count of memories needing backfill
print("[INFO] Counting memories with NULL local_embedding...")
cursor.execute("""
    SELECT COUNT(*) FROM memory_service.memories 
    WHERE local_embedding IS NULL
""")
total_count = cursor.fetchone()[0]
print(f"[INFO] Found {total_count} memories to backfill")

if total_count == 0:
    print("[INFO] No memories to backfill. Exiting.")
    cursor.close()
    conn.close()
    exit(0)

# Batch configuration
BATCH_SIZE = 100
batches_completed = 0
records_backfilled = 0
start_time = time.time()

try:
    while True:
        # Fetch next batch of memories needing backfill
        print(f"\n[FETCH] Batch {batches_completed + 1}: Fetching {BATCH_SIZE} memories...")
        cursor.execute("""
            SELECT id, headline, context 
            FROM memory_service.memories 
            WHERE local_embedding IS NULL
            LIMIT %s
        """, (BATCH_SIZE,))
        
        rows = cursor.fetchall()
        if not rows:
            print("[INFO] No more records to process. Backfill complete.")
            break
        
        batch_start = time.time()
        
        # Generate embeddings and prepare updates
        updates = []
        for memory_id, headline, context in rows:
            # Generate embedding from headline + context (same as write path)
            embed_text = f"{headline}. {context}"
            
            # Generate embedding using local model
            embedding = model.encode(embed_text, convert_to_numpy=True, show_progress_bar=False)
            
            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)
            
            # Convert to list for psycopg2
            embedding_list = embedding.tolist()
            
            updates.append((embedding_list, memory_id))
        
        # Batch update
        print(f"[UPDATE] Updating {len(updates)} records...")
        for embedding_list, memory_id in updates:
            cursor.execute("""
                UPDATE memory_service.memories 
                SET local_embedding = %s::extensions.vector
                WHERE id = %s
            """, (embedding_list, memory_id))
        
        conn.commit()
        
        batches_completed += 1
        records_backfilled += len(updates)
        batch_time = time.time() - batch_start
        
        # Progress report
        elapsed = time.time() - start_time
        rate = records_backfilled / elapsed if elapsed > 0 else 0
        eta_remaining = (total_count - records_backfilled) / rate if rate > 0 else 0
        
        print(f"[PROGRESS] {records_backfilled}/{total_count} ({100*records_backfilled/total_count:.1f}%)")
        print(f"[STATS] Batch time: {batch_time:.2f}s | Avg rate: {rate:.1f} rec/s | ETA: {eta_remaining/60:.1f}m")

except Exception as e:
    print(f"[ERROR] Backfill failed: {e}")
    conn.rollback()
    raise
finally:
    cursor.close()
    conn.close()

# Final report
total_time = time.time() - start_time
avg_rate = records_backfilled / total_time if total_time > 0 else 0

print("\n" + "="*60)
print("[COMPLETE] Backfill finished successfully!")
print("="*60)
print(f"Total records backfilled: {records_backfilled:,}")
print(f"Total time: {total_time/60:.2f} minutes ({total_time:.0f}s)")
print(f"Average rate: {avg_rate:.1f} records/second")
print(f"Batches processed: {batches_completed}")
print("="*60)
