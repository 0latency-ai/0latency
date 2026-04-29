"""
Classification Report Generator - Phase 2
Generates human-readable summary of classification results.

Run: cd /root/.openclaw/workspace/memory-product && python3 -m src.consolidation.report
"""

import os
import datetime
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("report")

def _get_db_conn_str():
    return os.environ["MEMORY_DB_CONN"]


def generate_report():
    """Generate classification report."""
    conn = psycopg2.connect(_get_db_conn_str())
    cur = conn.cursor()
    
    # Get overall statistics
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'classified') as classified,
            COUNT(*) FILTER (WHERE consolidation_type = 'DUPLICATE') as duplicates,
            COUNT(*) FILTER (WHERE consolidation_type = 'UPDATE') as updates,
            COUNT(*) FILTER (WHERE consolidation_type = 'CONTRADICTION') as contradictions,
            COUNT(*) FILTER (WHERE consolidation_type = 'DISTINCT') as distinct_pairs,
            AVG(classification_confidence) FILTER (WHERE status = 'classified') as avg_confidence,
            AVG(similarity_score) as avg_similarity
        FROM memory_service.consolidation_queue
    """)
    
    stats = cur.fetchone()
    pending, classified, duplicates, updates, contradictions, distinct_pairs, avg_conf, avg_sim = stats
    
    # Format confidence and similarity with fallback
    conf_str = f"{avg_conf:.2f}" if avg_conf is not None else "N/A"
    sim_str = f"{avg_sim:.3f}" if avg_sim is not None else "N/A"
    
    # Build report header
    report = f"""
===================================================================
CONSOLIDATION CLASSIFICATION REPORT
===================================================================
Generated: {datetime.datetime.now().isoformat()}

QUEUE STATUS:
  Pending:        {pending or 0}
  Classified:     {classified or 0}
  Avg Confidence: {conf_str}
  Avg Similarity: {sim_str}

CLASSIFICATION BREAKDOWN:
  Duplicates:      {duplicates or 0}
  Updates:         {updates or 0}
  Contradictions:  {contradictions or 0}
  Distinct:        {distinct_pairs or 0}

"""
    
    # Get samples of each type for review
    for ctype in ['DUPLICATE', 'UPDATE', 'CONTRADICTION']:
        cur.execute("""
            SELECT cq.id, cq.similarity_score, cq.classification_confidence, 
                   cq.classification_reasoning,
                   ma.headline as headline_a, ma.context as content_a,
                   mb.headline as headline_b, mb.context as content_b
            FROM memory_service.consolidation_queue cq
            JOIN memory_service.memories ma ON cq.memory_id_a = ma.id
            JOIN memory_service.memories mb ON cq.memory_id_b = mb.id
            WHERE cq.consolidation_type = %s
            AND cq.status = 'classified'
            ORDER BY cq.classification_confidence DESC
            LIMIT 5
        """, (ctype,))
        
        rows = cur.fetchall()
        
        report += f"\n--- TOP {ctype} SAMPLES ---\n"
        
        if not rows:
            report += f"  (No {ctype.lower()} pairs found)\n"
        else:
            for row in rows:
                pair_id, sim, conf, reasoning, head_a, cont_a, head_b, cont_b = row
                content_a_preview = (cont_a or "")[:200] + ("..." if cont_a and len(cont_a) > 200 else "")
                content_b_preview = (cont_b or "")[:200] + ("..." if cont_b and len(cont_b) > 200 else "")
                report += f"""
  ID: {pair_id}
  Confidence: {conf:.2f} | Similarity: {sim:.3f}
  Memory A: {head_a or 'N/A'}
    {content_a_preview}
  Memory B: {head_b or 'N/A'}
    {content_b_preview}
  Reasoning: {reasoning or 'N/A'}
  ---
"""
    
    # Add agent breakdown
    cur.execute("""
        SELECT agent_id, 
               COUNT(*) as total,
               COUNT(*) FILTER (WHERE consolidation_type = 'DUPLICATE') as dupes,
               COUNT(*) FILTER (WHERE consolidation_type = 'UPDATE') as upds,
               AVG(similarity_score) as avg_sim
        FROM memory_service.consolidation_queue
        WHERE status = 'classified'
        GROUP BY agent_id
        ORDER BY total DESC
        LIMIT 10
    """)
    
    agent_rows = cur.fetchall()
    
    report += "\n--- AGENT BREAKDOWN ---\n"
    if agent_rows:
        for agent_id, total, dupes, upds, avg_sim_agent in agent_rows:
            report += f"  {agent_id}: {total} pairs (D:{dupes or 0} U:{upds or 0} sim:{avg_sim_agent:.3f})\n"
    else:
        report += "  (No agent data yet)\n"
    
    report += "\n===================================================================\n"
    
    # Write report
    report_path = f"/root/logs/classification-report-{datetime.date.today()}.txt"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)
    
    print(report)
    logger.info(f"Report written to: {report_path}")
    
    cur.close()
    conn.close()
    
    return report_path


if __name__ == "__main__":
    generate_report()
