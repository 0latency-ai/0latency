"""
Importance Adjuster - Phase 3 of Self-Improving Memory
Runs daily. Analyzes recall feedback and adjusts memory importance scores.
This is the core self-improvement mechanism.

Run manually: cd /root/.openclaw/workspace/memory-product && python3 -m src.consolidation.importance_adjuster
Cron: 0 4 * * * (run at 4 AM UTC daily)
"""

import os
import datetime
import logging
import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("importance_adjuster")

def _get_db_conn_str():
    return os.environ["MEMORY_DB_CONN"]


def adjust_importance_scores(conn):
    """
    Analyze feedback from the last 7 days and adjust importance scores.
    
    Rules:
    - Memory recalled and used 3+ times in 7 days: importance += 0.05 (cap at 1.0)
    - Memory recalled and ignored 3+ times with 0 uses: importance -= 0.05 (floor at 0.1)
    - Memory contradicted 2+ times: flag for review, do NOT auto-adjust
    - Never adjust identity memories
    - Never adjust memories less than 48 hours old (too new for pattern)
    - Maximum adjustment per cycle: 0.1 (prevents runaway scoring)
    
    Schema-agnostic: Works only on memory IDs and importance scores, not content format.
    """
    
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get feedback aggregates per memory for last 7 days
    cur.execute("""
        SELECT 
            memory_id,
            agent_id,
            tenant_id,
            COUNT(*) FILTER (WHERE feedback_type = 'used') as use_count,
            COUNT(*) FILTER (WHERE feedback_type = 'ignored') as ignore_count,
            COUNT(*) FILTER (WHERE feedback_type = 'contradicted') as contradict_count
        FROM memory_service.recall_feedback
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY memory_id, agent_id, tenant_id
        HAVING COUNT(*) >= 3
    """)
    
    feedback_stats = cur.fetchall()
    
    adjustments_made = 0
    contradictions_flagged = 0
    log_path = f"/root/logs/importance-adjuster-{datetime.date.today()}.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    with open(log_path, "w") as logf:
        logf.write(f"=== Importance Adjuster Run: {datetime.datetime.now().isoformat()} ===\n\n")
    
    for stat in feedback_stats:
        # Get current memory state (schema-agnostic: only need ID, importance, type, created_at)
        cur.execute("""
            SELECT id, importance, memory_type, created_at, tenant_id
            FROM memory_service.memories WHERE id = %s
        """, (stat['memory_id'],))
        
        memory = cur.fetchone()
        
        if not memory:
            continue
        
        # Skip identity memories and very new memories
        if memory['memory_type'] == 'identity':
            continue
        memory_age = datetime.datetime.now(datetime.timezone.utc) - memory['created_at']
        if memory_age < datetime.timedelta(hours=48):
            continue
        
        current_importance = memory['importance'] or 0.5
        adjustment = 0.0
        reason = ""
        
        # Contradicted memories get flagged for review, not auto-adjusted
        if stat['contradict_count'] >= 2:
            # Insert into consolidation queue as a self-contradiction flagged for review
            cur.execute("""
                INSERT INTO memory_service.consolidation_queue 
                (tenant_id, agent_id, memory_id_a, memory_id_b, similarity_score, 
                 consolidation_type, status, classification_reasoning)
                VALUES (%s, %s, %s, %s, 1.0, 'CONTRADICTION', 'classified',
                        'Auto-flagged: contradicted ' || %s || ' times in 7 days')
                
            """, (stat['tenant_id'], stat['agent_id'], stat['memory_id'], 
                  stat['memory_id'], stat['contradict_count']))
            reason = f"flagged_contradiction (count={stat['contradict_count']})"
            contradictions_flagged += 1
        
        # Frequently used = boost importance
        elif stat['use_count'] >= 3 and stat['ignore_count'] == 0:
            adjustment = min(0.05, 1.0 - current_importance)
            reason = f"boost (used={stat['use_count']}, ignored=0)"
        
        # Frequently ignored with zero uses = demote importance
        elif stat['ignore_count'] >= 3 and stat['use_count'] == 0:
            adjustment = max(-0.05, 0.1 - current_importance)
            reason = f"demote (used=0, ignored={stat['ignore_count']})"
        
        # Apply adjustment if needed
        if adjustment != 0:
            new_importance = round(current_importance + adjustment, 3)
            cur.execute("""
                UPDATE memory_service.memories SET importance = %s WHERE id = %s
            """, (new_importance, stat['memory_id']))
            adjustments_made += 1
        
        # Log to file
        with open(log_path, "a") as logf:
            logf.write(f"{datetime.datetime.now().isoformat()} | "
                      f"memory={stat['memory_id']} | "
                      f"agent={stat['agent_id']} | "
                      f"old_importance={current_importance} | "
                      f"adjustment={adjustment:+.3f} | "
                      f"new={round(current_importance + adjustment, 3) if adjustment else current_importance} | "
                      f"reason={reason}\n")
    
    conn.commit()
    
    # Log miss patterns — queries that returned nothing useful
    cur.execute("""
        SELECT context, agent_id, COUNT(*) as miss_count
        FROM memory_service.recall_feedback
        WHERE feedback_type = 'miss'
        AND created_at > NOW() - INTERVAL '7 days'
        AND context IS NOT NULL
        GROUP BY context, agent_id
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    
    misses = cur.fetchall()
    
    with open(log_path, "a") as logf:
        logf.write(f"\n=== TOP RECALL MISSES (gaps in memory) ===\n")
        if misses:
            for miss in misses:
                logf.write(f"  {miss['miss_count']}x [{miss['agent_id']}]: {miss['context']}\n")
        else:
            logf.write("  (No recurring misses found)\n")
        
        logf.write(f"\n=== SUMMARY ===\n")
        logf.write(f"Importance adjustments made: {adjustments_made}\n")
        logf.write(f"Contradictions flagged: {contradictions_flagged}\n")
    
    cur.close()
    
    logger.info(f"Importance adjuster complete: {adjustments_made} adjustments, {contradictions_flagged} contradictions flagged")
    
    return adjustments_made, contradictions_flagged


def main():
    """Main entry point for importance adjuster."""
    logger.info("Starting importance adjuster...")
    
    try:
        # Create database connection
        conn = psycopg2.connect(_get_db_conn_str())
        
        adjustments, contradictions = adjust_importance_scores(conn)
        
        logger.info(f"Run complete: {adjustments} importance scores adjusted, {contradictions} contradictions flagged")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Importance adjuster failed: {e}")
        raise


if __name__ == "__main__":
    main()
