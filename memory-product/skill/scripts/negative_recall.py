"""
Negative Recall — Know What You DON'T Know
Tracks topic coverage to prevent hallucinated fill-in details.

Core idea: if the agent has never discussed "Justin's college education" but knows
his name and businesses, it should flag that as a gap rather than guessing.

Two mechanisms:
1. Topic coverage map — auto-updated during extraction, tracks discussed topics + depth
2. Gap detection — given a query, identifies what ISN'T in memory vs what IS
"""

import os
import sys
import json
import subprocess
import requests
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
                "temperature": 0.1,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json"
            }
        },
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def update_topic_coverage(agent_id: str, memories: list[dict]):
    """
    Update the topic coverage map based on newly extracted memories.
    Called after each extraction batch.
    
    Extracts topics from memory scopes, entities, and categories,
    then upserts into the coverage table.
    """
    topics_seen = {}
    
    for mem in memories:
        # Extract topics from scope, project, categories, entities
        scope = mem.get("scope", "/")
        project = mem.get("project", "")
        categories = mem.get("categories", [])
        entities = mem.get("entities", [])
        
        # Build topic list from this memory
        if project:
            topics_seen[project.lower()] = scope
        for cat in categories:
            if cat and len(cat) > 2:
                topics_seen[cat.lower()] = scope
        # Top-level scope as topic
        scope_parts = [p for p in scope.split("/") if p]
        if scope_parts:
            topics_seen[scope_parts[0].lower()] = scope
    
    # Upsert each topic
    for topic, scope in topics_seen.items():
        topic_clean = topic.replace("'", "''")
        scope_clean = scope.replace("'", "''")
        try:
            _db_execute(f"""
                INSERT INTO memory_service.topic_coverage (agent_id, topic, scope)
                VALUES ('{agent_id}', '{topic_clean}', '{scope_clean}')
                ON CONFLICT (agent_id, topic) DO UPDATE SET
                    last_discussed = now(),
                    discussion_count = memory_service.topic_coverage.discussion_count + 1,
                    depth = CASE 
                        WHEN memory_service.topic_coverage.discussion_count >= 5 THEN 'deep'
                        WHEN memory_service.topic_coverage.discussion_count >= 2 THEN 'moderate'
                        ELSE 'shallow'
                    END
            """)
        except Exception:
            pass


def detect_gaps(agent_id: str, query: str) -> dict:
    """
    Given a conversational query, detect what the agent KNOWS vs DOESN'T KNOW
    about the topics involved.
    
    Returns:
        {
            "known_topics": [...],      # Topics we have coverage on
            "unknown_topics": [...],    # Topics in the query we have NO coverage on
            "shallow_topics": [...],    # Topics with minimal coverage (might be unreliable)
            "gap_warning": str or None  # Human-readable warning for the agent
        }
    """
    # Extract topics from the query using Gemini
    try:
        prompt = f"""Extract the main topics/subjects from this query. Return a JSON array of topic strings (lowercase, short phrases).

Query: "{query}"

Examples of topics: "college education", "family members", "health insurance", "python programming", "favorite movies"

JSON array:"""
        
        raw = _call_gemini(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        query_topics = json.loads(cleaned)
        if not isinstance(query_topics, list):
            query_topics = [query_topics]
    except Exception:
        # Fallback: split query into rough topics
        query_topics = [w.lower() for w in query.split() if len(w) > 3][:5]
    
    # Check each topic against coverage map
    known = []
    unknown = []
    shallow = []
    
    for topic in query_topics:
        topic_clean = topic.replace("'", "''")
        rows = _db_execute(f"""
            SELECT topic, discussion_count, depth, last_discussed
            FROM memory_service.topic_coverage
            WHERE agent_id = '{agent_id}'
              AND (topic ILIKE '%{topic_clean}%' OR '{topic_clean}' ILIKE '%' || topic || '%')
            LIMIT 3
        """)
        
        if rows:
            for row in rows:
                parts = row.split("|||")
                if len(parts) >= 3:
                    depth = parts[2]
                    if depth == "shallow":
                        shallow.append({"topic": topic, "depth": depth, "matched": parts[0]})
                    else:
                        known.append({"topic": topic, "depth": depth, "matched": parts[0]})
        else:
            unknown.append(topic)
    
    # Build warning
    warning = None
    if unknown:
        warning = f"⚠ No memory coverage for: {', '.join(unknown)}. Do not guess or fill in details about these topics."
    elif shallow:
        topics_str = ', '.join(s['topic'] for s in shallow)
        warning = f"⚠ Shallow coverage only for: {topics_str}. Information may be incomplete — verify before stating as fact."
    
    return {
        "known_topics": known,
        "unknown_topics": unknown,
        "shallow_topics": shallow,
        "gap_warning": warning,
    }


def get_coverage_summary(agent_id: str) -> list[dict]:
    """Get full topic coverage summary for an agent."""
    rows = _db_execute(f"""
        SELECT topic, scope, discussion_count, depth, 
               first_discussed, last_discussed
        FROM memory_service.topic_coverage
        WHERE agent_id = '{agent_id}'
        ORDER BY discussion_count DESC
        LIMIT 50
    """)
    
    results = []
    for row in rows:
        parts = row.split("|||")
        if len(parts) >= 4:
            results.append({
                "topic": parts[0],
                "scope": parts[1],
                "discussion_count": int(parts[2]),
                "depth": parts[3],
            })
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "gaps":
        agent = "thomas"
        query = " ".join(sys.argv[2:])
        result = detect_gaps(agent, query)
        print(json.dumps(result, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "coverage":
        agent = sys.argv[2] if len(sys.argv) > 2 else "thomas"
        results = get_coverage_summary(agent)
        for r in results:
            print(f"  [{r['depth']}] {r['topic']} ({r['discussion_count']}x)")
    else:
        print("Usage:")
        print("  python negative_recall.py gaps <query>   — Detect knowledge gaps")
        print("  python negative_recall.py coverage [agent] — Show topic coverage")
