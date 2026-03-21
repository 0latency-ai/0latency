"""
Memory Compaction — Summarization Layers for Scale
When memory count exceeds thresholds, cluster related memories and create summaries.
Individual memories remain accessible, but the recall layer can use cluster summaries
to stay within token budgets at scale.

Strategy:
1. Cluster memories by entity/scope overlap using the entity graph
2. Generate summaries for each cluster using Gemini
3. Store cluster summaries with centroid embeddings
4. Recall layer checks clusters first for broad context, then drills into individual memories

Triggers:
- When total active memories > 500: first compaction pass
- When total active memories > 1000: aggressive compaction
- Run as daily cron alongside decay
"""

import os
import sys
import json
import subprocess
import requests
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
DB_CONN = os.environ.get("MEMORY_DB_CONN", "")


def _db_execute(query: str) -> list:
    result = subprocess.run(
        ["psql", DB_CONN, "-t", "-A", "-F", "|||", "-c", query],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "PGPASSWORD": os.environ.get("MEMORY_DB_PASSWORD", "")}
    )
    if result.returncode != 0:
        raise RuntimeError(f"DB error: {result.stderr}")
    return [line for line in result.stdout.strip().split("\n") if line]


def _call_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    resp = requests.post(
        url,
        params={"key": GOOGLE_API_KEY},
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
        params={"key": GOOGLE_API_KEY},
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
    # Get all active memories with their scopes and entities
    rows = _db_execute(f"""
        SELECT id, headline, context, scope, entities::text, importance
        FROM memory_service.memories
        WHERE agent_id = '{agent_id}'
          AND superseded_at IS NULL
          AND memory_type NOT IN ('correction')
        ORDER BY scope, importance DESC
    """)
    
    if not rows:
        return []
    
    # Group by top-level scope
    scope_groups = defaultdict(list)
    for row in rows:
        parts = row.split("|||")
        if len(parts) < 6:
            continue
        
        mem_id = parts[0]
        headline = parts[1]
        context = parts[2]
        scope = parts[3] or "/"
        entities_raw = parts[4]
        importance = float(parts[5] or 0.5)
        
        # Use top two scope levels as cluster key
        scope_parts = [p for p in scope.split("/") if p]
        cluster_key = "/".join(scope_parts[:2]) if scope_parts else "general"
        
        scope_groups[cluster_key].append({
            "id": mem_id,
            "headline": headline,
            "context": context,
            "scope": scope,
            "importance": importance,
        })
    
    # Filter to clusters with enough members
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
    headlines = [m["headline"] for m in cluster["members"][:20]]  # Cap at 20
    contexts = [m["context"] for m in cluster["members"][:10]]    # Cap at 10
    
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
    """
    Run memory compaction. Creates/updates cluster summaries.
    
    Only runs if:
    - force=True, OR
    - Active memory count > 200 (early compaction for testing)
    """
    # Check memory count
    rows = _db_execute(f"""
        SELECT COUNT(*) FROM memory_service.memories
        WHERE agent_id = '{agent_id}' AND superseded_at IS NULL
    """)
    
    total = int(rows[0]) if rows else 0
    print(f"Active memories for {agent_id}: {total}")
    
    if total < 200 and not force:
        print("Below compaction threshold (200). Use --force to compact anyway.")
        return
    
    # Build clusters
    clusters = build_clusters(agent_id)
    print(f"Found {len(clusters)} clusters")
    
    if not clusters:
        print("No clusters large enough for compaction.")
        return
    
    # Process each cluster
    for cluster in clusters:
        print(f"\nCluster: {cluster['cluster_key']} ({cluster['count']} members)")
        
        # Generate summary
        try:
            summary = summarize_cluster(cluster)
            print(f"  Summary: {summary[:100]}...")
        except Exception as e:
            print(f"  ERROR generating summary: {e}")
            continue
        
        # Generate centroid embedding from summary
        try:
            embedding = _embed_text(summary)
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        except Exception as e:
            print(f"  ERROR generating embedding: {e}")
            embedding_str = None
        
        # Calculate average importance
        avg_importance = sum(m["importance"] for m in cluster["members"]) / len(cluster["members"])
        
        # Member IDs as Postgres array
        member_ids = [m["id"] for m in cluster["members"]]
        member_array = "ARRAY[" + ",".join(f"'{mid}'::uuid" for mid in member_ids) + "]"
        
        cluster_name = cluster["cluster_key"].replace("'", "''")
        summary_escaped = summary.replace("'", "''")
        
        # Upsert cluster
        try:
            embed_clause = f", centroid_embedding = '{embedding_str}'::extensions.vector" if embedding_str else ""
            
            _db_execute(f"""
                INSERT INTO memory_service.memory_clusters 
                    (agent_id, cluster_name, summary, member_memory_ids, member_count, 
                     importance_avg{', centroid_embedding' if embedding_str else ''})
                VALUES 
                    ('{agent_id}', '{cluster_name}', '{summary_escaped}', 
                     {member_array}, {len(member_ids)}, {avg_importance}
                     {f", '{embedding_str}'::extensions.vector" if embedding_str else ''})
                ON CONFLICT DO NOTHING
            """)
            print(f"  ✅ Cluster stored: {cluster_name}")
        except Exception as e:
            print(f"  ERROR storing cluster: {e}")
    
    print(f"\nCompaction complete for {agent_id}")


def get_cluster_summaries(agent_id: str) -> list[dict]:
    """Get all cluster summaries for an agent (used by recall for broad context)."""
    rows = _db_execute(f"""
        SELECT cluster_name, summary, member_count, importance_avg
        FROM memory_service.memory_clusters
        WHERE agent_id = '{agent_id}'
        ORDER BY importance_avg DESC
    """)
    
    results = []
    for row in rows:
        parts = row.split("|||")
        if len(parts) >= 4:
            results.append({
                "cluster": parts[0],
                "summary": parts[1],
                "members": int(parts[2]),
                "importance": float(parts[3]),
            })
    return results


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
