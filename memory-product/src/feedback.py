"""
Recall Feedback Loop — Self-Learning Memory
Tracks which recalled memories are actually used in responses vs ignored.
Reinforces useful memories, demotes ignored ones.

Also handles ephemeral memories (TTL-based expiration).

SECURITY HARDENED: psycopg2 parameterized queries, no hardcoded credentials.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from db import execute, execute_one, execute_scalar, execute_modify


def record_recall_usage(memory_ids_surfaced: list[str], memory_ids_used: list[str]):
    """
    After a response is generated, compare which recalled memories were
    actually referenced in the response vs. ignored.
    """
    used_set = set(memory_ids_used)

    for mid in memory_ids_surfaced:
        mid = mid.strip()
        if not mid:
            continue

        if mid in used_set:
            execute_modify("""
                UPDATE memory_service.memories
                SET recall_count = recall_count + 1,
                    recall_used_count = recall_used_count + 1,
                    relevance_score = LEAST(1.0, relevance_score + 0.05),
                    last_accessed = now()
                WHERE id = %s
            """, (mid,))
        else:
            execute_modify("""
                UPDATE memory_service.memories
                SET recall_count = recall_count + 1,
                    recall_ignored_count = recall_ignored_count + 1,
                    relevance_score = GREATEST(0.05, relevance_score - 0.02)
                WHERE id = %s
            """, (mid,))


def get_recall_stats(agent_id: str) -> dict:
    """Get recall feedback statistics."""
    row = execute_one("""
        SELECT
            COUNT(*) FILTER (WHERE recall_count > 0) as recalled_total,
            SUM(recall_used_count) as total_used,
            SUM(recall_ignored_count) as total_ignored,
            ROUND(AVG(CASE WHEN recall_count > 0
                THEN recall_used_count::float / recall_count
                ELSE NULL END)::numeric, 3) as avg_hit_rate
        FROM memory_service.memories
        WHERE agent_id = %s AND superseded_at IS NULL
    """, (agent_id,))

    if row:
        return {
            "recalled_total": int(row["recalled_total"] or 0),
            "total_used": int(row["total_used"] or 0),
            "total_ignored": int(row["total_ignored"] or 0),
            "avg_hit_rate": float(row["avg_hit_rate"]) if row["avg_hit_rate"] else 0.0,
        }
    return {}


def cleanup_expired(agent_id: str = None) -> int:
    """Remove expired ephemeral memories."""
    if agent_id:
        count = execute_modify("""
            UPDATE memory_service.memories
            SET superseded_at = now()
            WHERE expires_at IS NOT NULL
              AND expires_at < now()
              AND superseded_at IS NULL
              AND agent_id = %s
        """, (agent_id,))
    else:
        count = execute_modify("""
            UPDATE memory_service.memories
            SET superseded_at = now()
            WHERE expires_at IS NOT NULL
              AND expires_at < now()
              AND superseded_at IS NULL
        """)

    if count:
        print(f"Expired {count} ephemeral memories")
    return count


def memory_health(agent_id: str) -> dict:
    """Memory health dashboard — quick system health check."""
    row = execute_one("""
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
        WHERE agent_id = %s
    """, (agent_id,))

    health = {}
    if row:
        health = {
            "total": int(row["total"] or 0),
            "active": int(row["active"] or 0),
            "superseded": int(row["superseded"] or 0),
            "low_relevance": int(row["low_relevance"] or 0),
            "cascade_flagged": int(row["cascade_flagged"] or 0),
            "ephemeral": int(row["ephemeral"] or 0),
            "recalled": int(row["recalled"] or 0),
            "avg_relevance": float(row["avg_relevance"] or 0),
            "avg_importance": float(row["avg_importance"] or 0),
            "newest_memory": str(row["newest_memory"]) if row["newest_memory"] else "none",
            "type_diversity": int(row["type_diversity"] or 0),
        }

    # Topic coverage
    topic_row = execute_one("""
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE depth = 'deep') as deep,
               COUNT(*) FILTER (WHERE depth = 'moderate') as moderate,
               COUNT(*) FILTER (WHERE depth = 'shallow') as shallow
        FROM memory_service.topic_coverage
        WHERE agent_id = %s
    """, (agent_id,))

    if topic_row:
        health["topics_total"] = int(topic_row["total"] or 0)
        health["topics_deep"] = int(topic_row["deep"] or 0)
        health["topics_moderate"] = int(topic_row["moderate"] or 0)
        health["topics_shallow"] = int(topic_row["shallow"] or 0)

    # Clusters
    cluster_row = execute_one("""
        SELECT COUNT(*) as cnt, COALESCE(SUM(member_count), 0) as members
        FROM memory_service.memory_clusters
        WHERE agent_id = %s
    """, (agent_id,))

    if cluster_row:
        health["clusters"] = int(cluster_row["cnt"] or 0)
        health["clustered_memories"] = int(cluster_row["members"] or 0)

    # Edges
    edge_count = execute_scalar("""
        SELECT COUNT(*) FROM memory_service.memory_edges WHERE agent_id = %s
    """, (agent_id,))
    health["entity_edges"] = int(edge_count or 0)

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
