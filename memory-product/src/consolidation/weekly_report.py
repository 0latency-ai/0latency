#!/usr/bin/env python3
"""Phase 6 Weekly Report Generator
Implements §5: single SQL query, deterministic quality score, file + memory insert.
Constitution: /root/.openclaw/workspace/PHASE4-6-CONSTITUTION.md
"""
import os
import sys
import logging
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

# Setup logging
log_file = f"/root/logs/weekly-report-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s UTC | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DB_CONN = "postgresql://postgres.fuojxlabvhtmysbsixdn:jcYlwEhuHN9VcOuj@aws-1-us-east-1.pooler.supabase.com:5432/postgres"


def get_db_conn():
    """Get database connection."""
    return psycopg2.connect(DB_CONN)


def log_msg(msg: str):
    """Log with ISO timestamp."""
    ts = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'
    logger.info(f"{ts} | {msg}")


def run_report_query() -> dict:
    """§5.1 — Single query to get all metrics."""
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM memory_service.memories) AS total_memories,
                (SELECT COUNT(*) FROM memory_service.memories WHERE created_at > NOW() - INTERVAL '7 days') AS new_this_week,
                (SELECT COUNT(*) FROM memory_service.consolidation_queue WHERE status='processed' AND processed_at > NOW() - INTERVAL '7 days') AS merged_this_week,
                (SELECT COUNT(*) FROM memory_service.consolidation_queue WHERE consolidation_type='CONTRADICTION' AND created_at > NOW() - INTERVAL '7 days') AS contradictions_this_week,
                (SELECT COUNT(*) FROM memory_service.recall_telemetry WHERE created_at > NOW() - INTERVAL '7 days') AS recalls_this_week,
                (SELECT AVG(memories_returned) FROM memory_service.recall_telemetry WHERE created_at > NOW() - INTERVAL '7 days') AS avg_recall_results,
                (SELECT COUNT(*) FROM memory_service.recall_feedback WHERE feedback_type='used' AND created_at > NOW() - INTERVAL '7 days') AS memories_used,
                (SELECT COUNT(*) FROM memory_service.recall_feedback WHERE feedback_type='ignored' AND created_at > NOW() - INTERVAL '7 days') AS memories_ignored,
                (SELECT COUNT(*) FROM memory_service.recall_feedback WHERE feedback_type='miss' AND created_at > NOW() - INTERVAL '7 days') AS recall_misses;
        """)
        
        result = cur.fetchone()
        return dict(result)
    finally:
        cur.close()
        conn.close()


def calculate_quality_score(metrics: dict) -> int:
    """§5.2 — Deterministic quality score formula."""
    used = metrics['memories_used'] or 0
    ignored = metrics['memories_ignored'] or 0
    
    # usage_rate = used / MAX(used + ignored, 1)
    usage_rate = used / max(used + ignored, 1)
    
    # quality_score = INT(formula)
    # INT truncates, no rounding
    score = int(
        usage_rate * 40
        + min(metrics['merged_this_week'] / max(metrics['total_memories'] * 0.01, 1), 1) * 20
        + min(metrics['recalls_this_week'] / 100, 1) * 20
        + (1 - min(metrics['contradictions_this_week'] / 10, 1)) * 20
    )
    
    return score


def write_report_file(date_str: str, metrics: dict, score: int):
    """Write weekly report to file."""
    report_file = f"/root/logs/weekly-report-{date_str}.txt"
    
    content = f"""═══════════════════════════════════════════════════════════════
WEEKLY REPORT — {date_str}
Quality Score: {score}/100
═══════════════════════════════════════════════════════════════

METRICS (Last 7 Days):
  Total Memories: {metrics['total_memories']}
  New This Week: {metrics['new_this_week']}
  Merged (Consolidations): {metrics['merged_this_week']}
  Contradictions Detected: {metrics['contradictions_this_week']}
  Recall Operations: {metrics['recalls_this_week']}
  Avg Recall Results: {metrics['avg_recall_results']:.1f if metrics['avg_recall_results'] else 'N/A'}
  Memories Used (Feedback): {metrics['memories_used']}
  Memories Ignored (Feedback): {metrics['memories_ignored']}
  Recall Misses: {metrics['recall_misses']}

QUALITY SCORE BREAKDOWN:
  Usage Rate: {(metrics['memories_used'] / max(metrics['memories_used'] + metrics['memories_ignored'], 1) * 40):.1f} / 40
  Consolidation Activity: {(min(metrics['merged_this_week'] / max(metrics['total_memories'] * 0.01, 1), 1) * 20):.1f} / 20
  Recall Activity: {(min(metrics['recalls_this_week'] / 100, 1) * 20):.1f} / 20
  Contradiction Handling: {((1 - min(metrics['contradictions_this_week'] / 10, 1)) * 20):.1f} / 20
═══════════════════════════════════════════════════════════════
"""
    
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w') as f:
        f.write(content)
    
    log_msg(f"Report written to {report_file}")


def insert_report_memory(tenant_id: str, date_str: str, score: int, metrics: dict):
    """§5.3 — Insert report into memories table."""
    conn = get_db_conn()
    cur = conn.cursor()
    
    try:
        # Find a valid tenant_id from existing memories
        if not tenant_id:
            cur.execute("SELECT tenant_id FROM memory_service.memories LIMIT 1;")
            row = cur.fetchone()
            if row:
                tenant_id = row[0]
            else:
                # Fallback to a UUID if no memories exist
                tenant_id = str(uuid.uuid4())
        
        memory_id = str(uuid.uuid4())
        headline = f"Weekly Report {date_str} — Score {score}/100"
        content = f"""Weekly consolidation and recall metrics for {date_str}.
Merged {metrics['merged_this_week']} memories.
{metrics['recalls_this_week']} recall operations.
{metrics['memories_used']} memories used, {metrics['memories_ignored']} ignored.
Quality Score: {score}/100."""
        
        cur.execute("""
            INSERT INTO memory_service.memories
            (id, tenant_id, agent_id, headline, content, memory_type, importance, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW());
        """, (memory_id, tenant_id, 'system', headline, content, 'report', 0.7))
        
        conn.commit()
        log_msg(f"Report memory inserted: {memory_id}")
    except Exception as e:
        logger.error(f"Failed to insert report memory: {str(e)}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def main():
    """Main report generation."""
    log_msg("=== WEEKLY REPORT START ===")
    
    # Get metrics
    metrics = run_report_query()
    log_msg(f"Metrics retrieved: total_memories={metrics['total_memories']}, merged_this_week={metrics['merged_this_week']}")
    
    # Calculate score
    score = calculate_quality_score(metrics)
    log_msg(f"Quality score calculated: {score}/100")
    
    # Get date string
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    # Write file
    write_report_file(date_str, metrics, score)
    
    # Insert into memories
    insert_report_memory(None, date_str, score, metrics)
    
    log_msg(f"=== WEEKLY REPORT END (score={score}) ===")


if __name__ == '__main__':
    main()
