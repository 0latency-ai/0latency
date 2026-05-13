#!/usr/bin/env python3
"""F1: Batch re-embed memories with Voyage voyage-3-large.

Idempotent: skips rows where embedding_voyage IS NOT NULL.
Rate-limited: 300 RPM (batch 128, ~2.3 batches/sec max).
Progress logging: prints count/total, no memory content.

Usage:
    export DATABASE_URL=...
    export VOYAGE_API_KEY=...
    python3 scripts/reembed_voyage.py [--tenant TENANT_ID] [--batch-size 128] [--dry-run]
"""
import argparse
import os
import sys
import time

import psycopg2


def get_voyage_embeddings(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed texts via Voyage API. Imported lazily to avoid top-level SDK dep."""
    import voyageai
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise RuntimeError("VOYAGE_API_KEY not set")
    client = voyageai.Client(api_key=api_key)
    result = client.embed(texts=texts, model="voyage-3-large", input_type=input_type, truncation=True)
    return result.embeddings


def main():
    parser = argparse.ArgumentParser(description="Batch re-embed memories with Voyage voyage-3-large")
    parser.add_argument("--tenant", help="Tenant ID to re-embed (default: all tenants)")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size (default 128)")
    parser.add_argument("--dry-run", action="store_true", help="Count rows but don't embed")
    parser.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = all)")
    parser.add_argument("--rpm", type=int, default=290, help="Max requests per minute (default 290, use 2 for free tier)")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    # Count pending rows
    tenant_filter = "AND tenant_id = %s::UUID" if args.tenant else ""
    count_params = (args.tenant,) if args.tenant else ()

    cur.execute(
        f"SELECT count(*) FROM memory_service.memories "
        f"WHERE embedding_voyage IS NULL {tenant_filter}",
        count_params,
    )
    total_pending = cur.fetchone()[0]

    cur.execute(
        f"SELECT count(*) FROM memory_service.memories "
        f"WHERE embedding_voyage IS NOT NULL {tenant_filter}",
        count_params,
    )
    already_done = cur.fetchone()[0]

    print(f"Pending: {total_pending}, Already embedded: {already_done}")

    if args.dry_run:
        print("Dry run — exiting.")
        cur.close()
        conn.close()
        return

    if total_pending == 0:
        print("Nothing to do.")
        cur.close()
        conn.close()
        return

    # Process in batches
    processed = 0
    errors = 0
    batch_num = 0
    rpm_window_start = time.time()
    rpm_count = 0
    MAX_RPM = args.rpm

    while True:
        if args.limit and processed >= args.limit:
            print(f"Reached --limit={args.limit}, stopping.")
            break

        # Rate limiting: fixed sleep between batches based on RPM
        min_interval = 60.0 / MAX_RPM  # seconds between requests
        if batch_num > 0:
            elapsed_since_last = time.time() - rpm_window_start
            if elapsed_since_last < min_interval:
                sleep_time = min_interval - elapsed_since_last + 0.5
                print(f"  Rate limit: sleeping {sleep_time:.1f}s...")
                time.sleep(sleep_time)

        # Fetch batch of rows needing embedding
        fetch_limit = min(args.batch_size, args.limit - processed) if args.limit else args.batch_size
        cur.execute(
            f"SELECT id::text, headline, context "
            f"FROM memory_service.memories "
            f"WHERE embedding_voyage IS NULL {tenant_filter} "
            f"ORDER BY created_at DESC "
            f"LIMIT %s",
            count_params + (fetch_limit,),
        )
        rows = cur.fetchall()
        if not rows:
            break

        batch_num += 1
        ids = [r[0] for r in rows]
        texts = [f"{r[1]}. {r[2]}" for r in rows]

        try:
            t0 = time.time()
            embeddings = get_voyage_embeddings(texts, input_type="document")
            api_ms = (time.time() - t0) * 1000
            rpm_window_start = time.time()  # Mark last successful request time

            # Batch update
            for mem_id, emb in zip(ids, embeddings):
                cur.execute(
                    "UPDATE memory_service.memories SET embedding_voyage = %s::vector WHERE id = %s::uuid",
                    (emb, mem_id),
                )

            processed += len(rows)
            print(f"  Batch {batch_num}: {len(rows)} rows, {api_ms:.0f}ms API, {processed}/{total_pending} done")

        except Exception as e:
            err_str = str(e)
            if "rate limit" in err_str.lower() or "RPM" in err_str or "TPM" in err_str:
                # Rate limit — wait a full minute and retry (don't count as permanent error)
                print(f"  Batch {batch_num}: rate-limited, waiting 62s...")
                time.sleep(62)
                rpm_window_start = time.time()
                batch_num -= 1  # Retry same batch
            else:
                errors += 1
                print(f"  Batch {batch_num}: ERROR - {e}", file=sys.stderr)
                if errors > 10:
                    print("Too many errors, aborting.", file=sys.stderr)
                    break
                time.sleep(2)

    print(f"\nDone. Processed: {processed}, Errors: {errors}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
