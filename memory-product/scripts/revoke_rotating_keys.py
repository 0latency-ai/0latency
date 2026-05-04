"""Transition rotating api_keys past revoke_at to revoked. Run daily via cron.

Idempotent: only updates rows still in 'rotating' status with revoke_at <= now().
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import psycopg2

def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE memory_service.api_keys
            SET status = 'revoked', revoked_at = now()
            WHERE status = 'rotating' AND revoke_at IS NOT NULL AND revoke_at <= now()
            RETURNING id, tenant_id
        """)
        revoked = cur.fetchall()
        conn.commit()
        print(f"REVOKED count={len(revoked)}")
        for r in revoked:
            print(f"  id={r[0]} tenant_id={r[1]}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
