"""
Memory Compaction — Summarization Layers for Scale
When memory count exceeds thresholds, cluster related memories and create summaries.

SECURITY HARDENED: psycopg2 parameterized queries, no hardcoded credentials.
"""
import os
import sys
import json
import requests
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from config import get_google_api_key
from db import execute, execute_one, execute_scalar, execute_modify, get_conn


def _call_gemini(prompt: str) -> str:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    resp = requests.post(
        url,
        params={"key": get_google_api_key()},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            }
        },
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _embed_text(text: str) -> list[float]:
    model_name = "gemini-embedding-001"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent"
    resp = requests.post(
        url,
        params={"key": get_google_api_key()},
        json={
            "model": f"models/{model_name}",
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": 768
        },
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def build_clusters(agent_id: str, min_cluster_size: int = 3) -> list[dict]:
    """
    Build memory clusters using scope and entity overlap.
    Groups memories that share the same scope prefix or entities.
    """
    rows = execute("""
        SELECT id, headline, context, scope, entities::text, importance
        FROM memory_service.memories
        WHERE agent_id = %s
          AND superseded_at IS NULL
          AND memory_type NOT IN ('correction')
        ORDER BY scope, importance DESC
    """, (agent_id,))

    if not rows:
        return []

    scope_groups = defaultdict(list)
    for row in rows:
        scope = row["scope"] or "/"
        scope_parts = [p for p in scope.split("/") if p]
        cluster_key = "/".join(scope_parts[:2]) if scope_parts else "general"

        scope_groups[cluster_key].append({
            "id": str(row["id"]),
            "headline": row["headline"],
            "context": row["context"],
            "scope": scope,
            "importance": float(row["importance"] or 0.5),
        })

    clusters = []
    for key, members in scope_groups.items():
        if len(members) >= min_cluster_size:
            clusters.append({
                "cluster_key": key,
                "members": members,
                "count": len(members),
            })

    return clusters


def summarize_cluster(cluster: dict) -> str:
    """Generate a concise summary of a memory cluster using Gemini."""
    headlines = [m["headline"] for m in cluster["members"][:20]]
    contexts = [m["context"] for m in cluster["members"][:10]]

    prompt = f"""Summarize these related memories into a single concise paragraph (3-5 sentences).
Capture the key facts, decisions, and relationships. Be specific — include names, numbers, and dates.

Topic area: {cluster['cluster_key']}

Memory headlines:
{chr(10).join(f'- {h}' for h in headlines)}

Detailed context (subset):
{chr(10).join(f'- {c}' for c in contexts)}

Summary:"""

    return _call_gemini(prompt).strip()


def run_compaction(agent_id: str, force: bool = False):
    """Run memory compaction. Creates/updates cluster summaries."""
    total = execute_scalar("""
        SELECT COUNT(*) FROM memory_service.memories
        WHERE agent_id = %s AND superseded_at IS NULL
    """, (agent_id,))

    total = int(total or 0)
    print(f"Active memories for {agent_id}: {total}")

    if total < 200 and not force:
        print("Below compaction threshold (200). Use --force to compact anyway.")
        return

    clusters = build_clusters(agent_id)
    print(f"Found {len(clusters)} clusters")

    if not clusters:
        print("No clusters large enough for compaction.")
        return

    for cluster in clusters:
        print(f"\nCluster: {cluster['cluster_key']} ({cluster['count']} members)")

        try:
            summary = summarize_cluster(cluster)
            print(f"  Summary: {summary[:100]}...")
        except Exception as e:
            print(f"  ERROR generating summary: {e}")
            continue

        try:
            embedding = _embed_text(summary)
        except Exception as e:
            print(f"  ERROR generating embedding: {e}")
            embedding = None

        avg_importance = sum(m["importance"] for m in cluster["members"]) / len(cluster["members"])
        member_ids = [m["id"] for m in cluster["members"]]

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    if embedding:
                        cur.execute("""
                            INSERT INTO memory_service.memory_clusters
                                (agent_id, cluster_name, summary, member_memory_ids, member_count,
                                 importance_avg, centroid_embedding)
                            VALUES (%s, %s, %s, %s, %s, %s, %s::extensions.vector)
                            ON CONFLICT DO NOTHING
                        """, (agent_id, cluster["cluster_key"], summary,
                              member_ids, len(member_ids), avg_importance,
                              "[" + ",".join(str(v) for v in embedding) + "]"))
                    else:
                        cur.execute("""
                            INSERT INTO memory_service.memory_clusters
                                (agent_id, cluster_name, summary, member_memory_ids, member_count,
                                 importance_avg)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (agent_id, cluster["cluster_key"], summary,
                              member_ids, len(member_ids), avg_importance))
                    conn.commit()
            print(f"  ✅ Cluster stored: {cluster['cluster_key']}")
        except Exception as e:
            print(f"  ERROR storing cluster: {e}")

    print(f"\nCompaction complete for {agent_id}")


def get_cluster_summaries(agent_id: str) -> list[dict]:
    """Get all cluster summaries for an agent."""
    return execute("""
        SELECT cluster_name as cluster, summary, member_count as members, importance_avg as importance
        FROM memory_service.memory_clusters
        WHERE agent_id = %s
        ORDER BY importance_avg DESC
    """, (agent_id,))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "compact":
        agent = sys.argv[2] if len(sys.argv) > 2 else "thomas"
        force = "--force" in sys.argv
        run_compaction(agent, force=force)
    elif len(sys.argv) > 1 and sys.argv[1] == "clusters":
        agent = sys.argv[2] if len(sys.argv) > 2 else "thomas"
        clusters = get_cluster_summaries(agent)
        for c in clusters:
            print(f"\n[{c['cluster']}] ({c['members']} memories, importance: {c['importance']:.2f})")
            print(f"  {c['summary'][:200]}")
    else:
        print("Usage:")
        print("  python compaction.py compact [agent] [--force]  — Run compaction")
        print("  python compaction.py clusters [agent]            — Show cluster summaries")
