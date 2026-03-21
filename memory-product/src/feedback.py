"""
Recall Feedback Loop — Self-Learning Memory
Tracks which recalled memories are actually used in responses vs ignored.
Reinforces useful memories, demotes ignored ones.

Also handles ephemeral memories (TTL-based expiration).
"""
import os
import sys
import subprocess
from datetime import datetime, timezone

DB_CONN = os.environ.get("MEMORY_DB_CONN",
    os.environ.get("MEMORY_DB_CONN", ""))


def _db_execute(query: str) -> list:
    result = subprocess.run(
        ["psql", DB_CONN, "-t", "-A", "-F", "|||", "-c", query],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "PGPASSWORD": os.environ.get("MEMORY_DB_PASSWORD", "")}
    )
    if result.returncode != 0:
        raise RuntimeError(f"DB error: {result.stderr}")
    return [line for line in result.stdout.strip().split("\n") if line]


def record_recall_usage(memory_ids_surfaced: list[str], memory_ids_used: list[str]):
    """
    After a response is generated, compare which recalled memories were
    actually referenced in the response vs. ignored.
    
    - Surfaced but used → reinforce (recall_used_count++, relevance boost)
    - Surfaced but ignored → demote (recall_ignored_count++, slight relevance drop)
    """
    used_set = set(memory_ids_used)
    
    for mid in memory_ids_surfaced:
        mid = mid.strip()
        if not mid:
            continue
            
        if mid in used_set:
            # Memory was useful — reinforce
            _db_execute(f"""
                UPDATE memory_service.memories
                SET recall_count = recall_count + 1,
                    recall_used_count = recall_used_count + 1,
                    relevance_score = LEAST(1.0, relevance_score + 0.05),
                    last_accessed = now()
                WHERE id = '{mid}'
            """)
        else:
            # Memory was surfaced but ignored — slight demotion
            _db_execute(f"""
                UPDATE memory_service.memories
                SET recall_count = recall_count + 1,
                    recall_ignored_count = recall_ignored_count + 1,
                    relevance_score = GREATEST(0.05, relevance_score - 0.02)
                WHERE id = '{mid}'
            """)


def get_recall_stats(agent_id: str) -> dict:
    """Get recall feedback statistics."""
    rows = _db_execute(f"""
        SELECT 
            COUNT(*) FILTER (WHERE recall_count > 0) as recalled_total,
            SUM(recall_used_count) as total_used,
            SUM(recall_ignored_count) as total_ignored,
            ROUND(AVG(CASE WHEN recall_count > 0 
                THEN recall_used_count::float / recall_count 
                ELSE NULL END)::numeric, 3) as avg_hit_rate
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}' AND superseded_at IS NULL
    """)
    
    if rows and rows[0]:
        parts = rows[0].split("|||")
        return {
            "recalled_total": int(parts[0] or 0),
            "total_used": int(parts[1] or 0),
            "total_ignored": int(parts[2] or 0),
            "avg_hit_rate": float(parts[3]) if parts[3] else 0.0,
        }
    return {}


def cleanup_expired(agent_id: str = None) -> int:
    """Remove expired ephemeral memories."""
    agent_filter = f"AND agent_id = '{agent_id}'" if agent_id else ""
    
    rows = _db_execute(f"""
        UPDATE memory_service.memories
        SET superseded_at = now()
        WHERE expires_at IS NOT NULL 
          AND expires_at < now()
          AND superseded_at IS NULL
          {agent_filter}
        RETURNING id
    """)
    
    count = len([r for r in rows if r.strip()])
    if count:
        print(f"Expired {count} ephemeral memories")
    return count


def memory_health(agent_id: str) -> dict:
    """Memory health dashboard — quick system health check."""
    rows = _db_execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE superseded_at IS NULL) as active,
            COUNT(*) FILTER (WHERE superseded_at IS NOT NULL) as superseded,
            COUNT(*) FILTER (WHERE relevance_score < 0.1 AND superseded_at IS NULL) as low_relevance,
            COUNT(*) FILTER (WHERE metadata->>'correction_cascade' = 'true' AND superseded_at IS NULL) as cascade_flagged,
            COUNT(*) FILTER (WHERE expires_at IS NOT NULL AND superseded_at IS NULL) as ephemeral,
            COUNT(*) FILTER (WHERE recall_count > 0 AND superseded_at IS NULL) as recalled,
            ROUND(AVG(relevance_score) FILTER (WHERE superseded_at IS NULL)::numeric, 3) as avg_relevance,
            ROUND(AVG(importance) FILTER (WHERE superseded_at IS NULL)::numeric, 3) as avg_importance,
            MAX(created_at) as newest_memory,
            COUNT(DISTINCT memory_type) FILTER (WHERE superseded_at IS NULL) as type_diversity
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
    """)
    
    health = {}
    if rows and rows[0]:
        parts = rows[0].split("|||")
        health = {
            "total": int(parts[0] or 0),
            "active": int(parts[1] or 0),
            "superseded": int(parts[2] or 0),
            "low_relevance": int(parts[3] or 0),
            "cascade_flagged": int(parts[4] or 0),
            "ephemeral": int(parts[5] or 0),
            "recalled": int(parts[6] or 0),
            "avg_relevance": float(parts[7] or 0),
            "avg_importance": float(parts[8] or 0),
            "newest_memory": parts[9] if parts[9] else "none",
            "type_diversity": int(parts[10] or 0),
        }
    
    # Add topic coverage stats
    topic_rows = _db_execute(f"""
        SELECT COUNT(*), 
               COUNT(*) FILTER (WHERE depth = 'deep'),
               COUNT(*) FILTER (WHERE depth = 'moderate'),
               COUNT(*) FILTER (WHERE depth = 'shallow')
        FROM memory_service.topic_coverage
        WHERE agent_id = '{agent_id}'
    """)
    
    if topic_rows and topic_rows[0]:
        tp = topic_rows[0].split("|||")
        health["topics_total"] = int(tp[0] or 0)
        health["topics_deep"] = int(tp[1] or 0)
        health["topics_moderate"] = int(tp[2] or 0)
        health["topics_shallow"] = int(tp[3] or 0)
    
    # Add cluster stats
    cluster_rows = _db_execute(f"""
        SELECT COUNT(*), SUM(member_count)
        FROM memory_service.memory_clusters
        WHERE agent_id = '{agent_id}'
    """)
    
    if cluster_rows and cluster_rows[0]:
        cp = cluster_rows[0].split("|||")
        health["clusters"] = int(cp[0] or 0)
        health["clustered_memories"] = int(cp[1] or 0)
    
    # Add edge stats
    edge_rows = _db_execute(f"""
        SELECT COUNT(*) FROM memory_service.memory_edges
        WHERE agent_id = '{agent_id}'
    """)
    
    if edge_rows:
        health["entity_edges"] = int(edge_rows[0] or 0)
    
    # Recall feedback
    feedback = get_recall_stats(agent_id)
    health.update(feedback)
    
    return health


if __name__ == "__main__":
    import json
    
    if len(sys.argv) > 1 and sys.argv[1] == "health":
        agent = sys.argv[2] if len(sys.argv) > 2 else "thomas"
        h = memory_health(agent)
        print(f"\n🧠 Memory Health Dashboard — {agent}")
        print(f"{'='*50}")
        print(f"📦 Total: {h.get('total', 0)} | Active: {h.get('active', 0)} | Superseded: {h.get('superseded', 0)}")
        print(f"📊 Avg Relevance: {h.get('avg_relevance', 0)} | Avg Importance: {h.get('avg_importance', 0)}")
        print(f"🏷️ Type Diversity: {h.get('type_diversity', 0)} types")
        print(f"⚠️ Low Relevance: {h.get('low_relevance', 0)} | Cascade Flagged: {h.get('cascade_flagged', 0)}")
        print(f"⏳ Ephemeral: {h.get('ephemeral', 0)}")
        print(f"🔍 Recalled: {h.get('recalled', 0)} | Used: {h.get('total_used', 0)} | Ignored: {h.get('total_ignored', 0)}")
        print(f"📚 Topics: {h.get('topics_total', 0)} (deep: {h.get('topics_deep', 0)}, moderate: {h.get('topics_moderate', 0)}, shallow: {h.get('topics_shallow', 0)})")
        print(f"🔗 Clusters: {h.get('clusters', 0)} | Entity Edges: {h.get('entity_edges', 0)}")
        print(f"🕐 Newest: {h.get('newest_memory', 'none')}")
    elif len(sys.argv) > 1 and sys.argv[1] == "expire":
        agent = sys.argv[2] if len(sys.argv) > 2 else None
        cleanup_expired(agent)
    else:
        print("Usage:")
        print("  python feedback.py health [agent]  — Memory health dashboard")
        print("  python feedback.py expire [agent]  — Cleanup expired memories")
