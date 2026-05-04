"""Backfill memory_service.api_keys from existing tenants.api_key_hash.

Idempotent: ON CONFLICT (key_hash) DO NOTHING. Safe to run multiple times.

Run: python3 scripts/backfill_api_keys.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import psycopg2

def main():
    db_url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO memory_service.api_keys (tenant_id, key_hash, status, created_at)
            SELECT id, api_key_hash, 'active', now()
            FROM memory_service.tenants
            WHERE active = true AND api_key_hash IS NOT NULL
            ON CONFLICT (key_hash) DO NOTHING
            RETURNING tenant_id
        """)
        inserted = cur.fetchall()
        conn.commit()
        print(f"BACKFILL_INSERTED count={len(inserted)}")

        cur.execute("""
            SELECT
              (SELECT count(*) FROM memory_service.api_keys WHERE status='active') AS keys_active,
              (SELECT count(*) FROM memory_service.tenants WHERE active=true AND api_key_hash IS NOT NULL) AS tenants_active
        """)
        ka, ta = cur.fetchone()
        print(f"BACKFILL_VERIFY keys_active={ka} tenants_active={ta}")
        if ka < ta:
            print(f"BACKFILL_INCOMPLETE missing={ta - ka}", file=sys.stderr)
            sys.exit(2)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
