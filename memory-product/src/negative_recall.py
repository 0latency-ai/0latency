"""
Negative Recall — Know What You DON'T Know
Tracks topic coverage to prevent hallucinated fill-in details.

SECURITY HARDENED: psycopg2 parameterized queries, no hardcoded credentials.
"""
import os
import sys
import json
import requests
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from config import get_google_api_key
from db import execute, execute_one, execute_modify


def _call_gemini(prompt: str) -> str:
    raise NotImplementedError("Gemini removed 2026-04-21; reintegrate with Anthropic/OpenAI when needed")


def update_topic_coverage(agent_id: str, memories: list[dict]):
    """
    Update the topic coverage map based on newly extracted memories.
    Called after each extraction batch.
    """
    topics_seen = {}

    for mem in memories:
        scope = mem.get("scope", "/")
        project = mem.get("project", "")
        categories = mem.get("categories", [])

        if project:
            topics_seen[project.lower()] = scope
        for cat in categories:
            if cat and len(cat) > 2:
                topics_seen[cat.lower()] = scope
        scope_parts = [p for p in scope.split("/") if p]
        if scope_parts:
            topics_seen[scope_parts[0].lower()] = scope

    for topic, scope in topics_seen.items():
        try:
            execute_modify("""
                INSERT INTO memory_service.topic_coverage (agent_id, topic, scope)
                VALUES (%s, %s, %s)
                ON CONFLICT (agent_id, topic) DO UPDATE SET
                    last_discussed = now(),
                    discussion_count = memory_service.topic_coverage.discussion_count + 1,
                    depth = CASE
                        WHEN memory_service.topic_coverage.discussion_count >= 5 THEN 'deep'
                        WHEN memory_service.topic_coverage.discussion_count >= 2 THEN 'moderate'
                        ELSE 'shallow'
                    END
            """, (agent_id, topic, scope))
        except Exception:
            pass


def detect_gaps(agent_id: str, query: str) -> dict:
    """
    Given a conversational query, detect what the agent KNOWS vs DOESN'T KNOW
    about the topics involved.
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
        query_topics = [w.lower() for w in query.split() if len(w) > 3][:5]

    known = []
    unknown = []
    shallow = []

    for topic in query_topics:
        rows = execute("""
            SELECT topic, discussion_count, depth, last_discussed
            FROM memory_service.topic_coverage
            WHERE agent_id = %s
              AND (topic ILIKE %s OR %s ILIKE '%%' || topic || '%%')
            LIMIT 3
        """, (agent_id, f"%{topic}%", topic))

        if rows:
            for row in rows:
                depth = row["depth"]
                if depth == "shallow":
                    shallow.append({"topic": topic, "depth": depth, "matched": row["topic"]})
                else:
                    known.append({"topic": topic, "depth": depth, "matched": row["topic"]})
        else:
            unknown.append(topic)

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
    return execute("""
        SELECT topic, scope, discussion_count, depth,
               first_discussed, last_discussed
        FROM memory_service.topic_coverage
        WHERE agent_id = %s
        ORDER BY discussion_count DESC
        LIMIT 50
    """, (agent_id,))


if __name__ == "__main__":
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
