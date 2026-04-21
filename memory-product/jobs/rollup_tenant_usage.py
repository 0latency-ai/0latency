#!/usr/bin/env python3
"""
Daily tenant usage rollup job for 0Latency admin analytics.

Computes per-tenant metrics for a given day and upserts into tenant_usage_daily.
Runs via cron at 01:00 UTC daily for yesterday's data.

Cost formula (documented rough estimates):
- extractions_today * 0.0002     (Haiku 4.5 avg per extraction)
- recalls_today * 0.00015         (Supabase vector read + local embed)
- memories_added_today * 0.00005  (write cost)
- (storage_bytes / 1e9) * 0.023 / 30  (storage prorated daily)

Usage:
  python3 rollup_tenant_usage.py                # Process yesterday
  python3 rollup_tenant_usage.py --backfill 30  # Process last 30 days
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import psycopg2
from psycopg2.extras import execute_values

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection from environment variable."""
    conn_str = os.environ.get('MEMORY_DB_CONN')
    if not conn_str:
        raise ValueError('MEMORY_DB_CONN environment variable not set')
    return psycopg2.connect(conn_str)


def get_tenant_usage_for_day(conn, target_date: date) -> List[Dict[str, Any]]:
    """
    Compute usage metrics for all tenants for a specific day.
    
    Returns list of dicts with keys:
    - tenant_id
    - day
    - memories_total
    - memories_added_today
    - recalls_today
    - extractions_today
    - api_calls_today
    - agents_active
    - storage_bytes
    - estimated_cost_usd
    - last_active_at
    """
    cursor = conn.cursor()
    
    # Convert date to timestamps for queries
    day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    
    logger.info(f"Computing usage for {target_date} ({day_start} to {day_end})")
    
    # Get all tenants (including inactive ones for historical data)
    cursor.execute("SELECT id FROM memory_service.tenants")
    tenant_ids = [row[0] for row in cursor.fetchall()]
    
    logger.info(f"Found {len(tenant_ids)} tenants to process")
    
    usage_data = []
    
    for tenant_id in tenant_ids:
        try:
            # 1. Memories total (cumulative as of end of day)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM memory_service.memories 
                WHERE tenant_id = %s AND created_at <= %s
            """, (tenant_id, day_end))
            memories_total = cursor.fetchone()[0] or 0
            
            # 2. Memories added today
            cursor.execute("""
                SELECT COUNT(*) 
                FROM memory_service.memories 
                WHERE tenant_id = %s 
                  AND created_at >= %s 
                  AND created_at <= %s
            """, (tenant_id, day_start, day_end))
            memories_added_today = cursor.fetchone()[0] or 0
            
            # 3. Recalls today (from recall_telemetry)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM memory_service.recall_telemetry 
                WHERE tenant_id = %s 
                  AND created_at >= %s 
                  AND created_at <= %s
            """, (tenant_id, day_start, day_end))
            recalls_today = cursor.fetchone()[0] or 0
            
            # 4. Extractions today (use memories created as proxy)
            extractions_today = memories_added_today
            
            # 5. API calls today (from audit_logs)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM memory_service.audit_logs 
                WHERE tenant_id = %s 
                  AND timestamp >= %s 
                  AND timestamp <= %s
            """, (tenant_id, day_start, day_end))
            api_calls_today = cursor.fetchone()[0] or 0
            
            # 6. Active agents today (distinct agent_ids from memories + recall_telemetry)
            cursor.execute("""
                SELECT COUNT(DISTINCT agent_id) FROM (
                    SELECT agent_id FROM memory_service.memories 
                    WHERE tenant_id = %s 
                      AND created_at >= %s 
                      AND created_at <= %s
                    UNION
                    SELECT agent_id FROM memory_service.recall_telemetry 
                    WHERE tenant_id = %s 
                      AND created_at >= %s 
                      AND created_at <= %s
                ) AS combined_agents
            """, (tenant_id, day_start, day_end, tenant_id, day_start, day_end))
            agents_active = cursor.fetchone()[0] or 0
            
            # 7. Storage bytes (rough estimate: sum of headline + full_content lengths)
            cursor.execute("""
                SELECT COALESCE(
                    SUM(
                        COALESCE(LENGTH(headline), 0) + 
                        COALESCE(LENGTH(full_content), 0)
                    ), 
                    0
                )
                FROM memory_service.memories 
                WHERE tenant_id = %s AND created_at <= %s
            """, (tenant_id, day_end))
            storage_bytes = cursor.fetchone()[0] or 0
            
            # 8. Last active timestamp today (from actual activity, not audit_logs)
            # Check both memory writes and recalls
            cursor.execute("""
                SELECT MAX(activity_time) FROM (
                    SELECT MAX(created_at) as activity_time
                    FROM memory_service.memories 
                    WHERE tenant_id = %s 
                      AND created_at >= %s 
                      AND created_at <= %s
                    UNION ALL
                    SELECT MAX(created_at) as activity_time
                    FROM memory_service.recall_telemetry 
                    WHERE tenant_id = %s 
                      AND created_at >= %s 
                      AND created_at <= %s
                ) AS combined_activity
            """, (tenant_id, day_start, day_end, tenant_id, day_start, day_end))
            last_active_at = cursor.fetchone()[0]
            
            # 9. Compute estimated cost (USD)
            # Formula from brief:
            # - extractions_today * 0.0002
            # - recalls_today * 0.00015
            # - memories_added_today * 0.00005
            # - (storage_bytes / 1e9) * 0.023 / 30
            
            extraction_cost = extractions_today * 0.0002
            recall_cost = recalls_today * 0.00015
            write_cost = memories_added_today * 0.00005
            storage_cost = (storage_bytes / 1e9) * 0.023 / 30 if storage_bytes > 0 else 0
            
            estimated_cost_usd = extraction_cost + recall_cost + write_cost + storage_cost
            
            # Only include tenants with any activity (or existing memories)
            if memories_total > 0 or api_calls_today > 0:
                usage_data.append({
                    'tenant_id': tenant_id,
                    'day': target_date,
                    'memories_total': memories_total,
                    'memories_added_today': memories_added_today,
                    'recalls_today': recalls_today,
                    'extractions_today': extractions_today,
                    'api_calls_today': api_calls_today,
                    'agents_active': agents_active,
                    'storage_bytes': storage_bytes,
                    'estimated_cost_usd': round(estimated_cost_usd, 4),
                    'last_active_at': last_active_at
                })
                
                if memories_added_today > 0 or recalls_today > 0 or api_calls_today > 0:
                    logger.debug(
                        f"  {tenant_id}: memories={memories_total} (+{memories_added_today}), "
                        f"recalls={recalls_today}, api={api_calls_today}, cost=${estimated_cost_usd:.4f}"
                    )
        
        except Exception as e:
            logger.error(f"Error processing tenant {tenant_id}: {e}")
            continue
    
    cursor.close()
    logger.info(f"Computed usage for {len(usage_data)} active tenants")
    return usage_data


def upsert_usage_data(conn, usage_data: List[Dict[str, Any]]):
    """Upsert usage data into tenant_usage_daily table."""
    if not usage_data:
        logger.warning("No usage data to upsert")
        return
    
    cursor = conn.cursor()
    
    # Prepare data for execute_values
    values = [
        (
            row['tenant_id'],
            row['day'],
            row['memories_total'],
            row['memories_added_today'],
            row['recalls_today'],
            row['extractions_today'],
            row['api_calls_today'],
            row['agents_active'],
            row['storage_bytes'],
            row['estimated_cost_usd'],
            row['last_active_at']
        )
        for row in usage_data
    ]
    
    # Upsert query with ON CONFLICT
    query = """
        INSERT INTO memory_service.tenant_usage_daily (
            tenant_id, day, memories_total, memories_added_today, recalls_today,
            extractions_today, api_calls_today, agents_active, storage_bytes,
            estimated_cost_usd, last_active_at
        ) VALUES %s
        ON CONFLICT (tenant_id, day) DO UPDATE SET
            memories_total = EXCLUDED.memories_total,
            memories_added_today = EXCLUDED.memories_added_today,
            recalls_today = EXCLUDED.recalls_today,
            extractions_today = EXCLUDED.extractions_today,
            api_calls_today = EXCLUDED.api_calls_today,
            agents_active = EXCLUDED.agents_active,
            storage_bytes = EXCLUDED.storage_bytes,
            estimated_cost_usd = EXCLUDED.estimated_cost_usd,
            last_active_at = EXCLUDED.last_active_at
    """
    
    execute_values(cursor, query, values)
    conn.commit()
    cursor.close()
    
    logger.info(f"Upserted {len(usage_data)} rows into tenant_usage_daily")


def main():
    parser = argparse.ArgumentParser(description='Rollup tenant usage data')
    parser.add_argument(
        '--backfill',
        type=int,
        metavar='DAYS',
        help='Backfill N days of historical data'
    )
    parser.add_argument(
        '--date',
        type=str,
        metavar='YYYY-MM-DD',
        help='Process specific date (default: yesterday)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        conn = get_db_connection()
        logger.info("Connected to database")
        
        # Determine which dates to process
        if args.backfill:
            # Backfill mode: process last N days
            end_date = date.today() - timedelta(days=1)  # Yesterday
            start_date = end_date - timedelta(days=args.backfill - 1)
            dates_to_process = [
                start_date + timedelta(days=i)
                for i in range((end_date - start_date).days + 1)
            ]
            logger.info(f"Backfill mode: processing {len(dates_to_process)} days from {start_date} to {end_date}")
        
        elif args.date:
            # Specific date mode
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
            dates_to_process = [target_date]
            logger.info(f"Processing specific date: {target_date}")
        
        else:
            # Default: process yesterday
            yesterday = date.today() - timedelta(days=1)
            dates_to_process = [yesterday]
            logger.info(f"Processing yesterday: {yesterday}")
        
        # Process each date
        for target_date in dates_to_process:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {target_date}")
            logger.info(f"{'='*60}")
            
            usage_data = get_tenant_usage_for_day(conn, target_date)
            upsert_usage_data(conn, usage_data)
        
        conn.close()
        logger.info("\n✓ Rollup completed successfully")
        
    except Exception as e:
        logger.error(f"Rollup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
