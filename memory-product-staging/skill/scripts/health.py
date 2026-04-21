#!/usr/bin/env python3
"""Memory Engine — Health Check

SECURITY HARDENED: psycopg2 parameterized queries, no hardcoded credentials.
"""
import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(__file__))

import psycopg2
import psycopg2.extras

DB_CONN = os.environ.get("MEMORY_DB_CONN", "")
if not DB_CONN:
    print("❌ MEMORY_DB_CONN not set")
    sys.exit(1)

agent_id = sys.argv[1] if len(sys.argv) > 1 else "default"


def query(sql, params=None):
    """Execute a parameterized query and return rows as dicts."""
    try:
        conn = psycopg2.connect(DB_CONN)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"DB error: {e}")
        return []


def scalar(sql, params=None):
    """Return first column of first row."""
    rows = query(sql, params)
    if rows:
        return list(rows[0].values())[0]
    return None


print(f"🧠 Memory Engine Health — Agent: {agent_id}")
print("=" * 50)

# Total memories
total = scalar("SELECT COUNT(*) FROM memory_service.memories WHERE agent_id = %s", (agent_id,))
print(f"📦 Total memories: {total or 0}")

# By type
rows = query(
    "SELECT memory_type, COUNT(*) as cnt FROM memory_service.memories WHERE agent_id = %s GROUP BY memory_type ORDER BY cnt DESC",
    (agent_id,))
if rows:
    print("📊 By type:")
    for r in rows:
        print(f"   {r['memory_type']}: {r['cnt']}")

# Active vs superseded
row = query(
    """SELECT COUNT(*) FILTER (WHERE superseded_at IS NULL) as active,
              COUNT(*) FILTER (WHERE superseded_at IS NOT NULL) as superseded
       FROM memory_service.memories WHERE agent_id = %s""",
    (agent_id,))
if row:
    print(f"✅ Active: {row[0]['active']} | 🔄 Superseded: {row[0]['superseded']}")

# Average importance
avg_imp = scalar(
    "SELECT ROUND(AVG(importance)::numeric, 3) FROM memory_service.memories WHERE agent_id = %s AND superseded_at IS NULL",
    (agent_id,))
if avg_imp:
    print(f"⚖️  Avg importance: {avg_imp}")

# Entity edges
edges = scalar("SELECT COUNT(*) FROM memory_service.memory_edges WHERE agent_id = %s", (agent_id,))
print(f"🔗 Entity edges: {edges or 0}")

# Topics
topics = scalar("SELECT COUNT(*) FROM memory_service.topic_coverage WHERE agent_id = %s", (agent_id,))
print(f"📚 Topics tracked: {topics or 0}")

# Clusters
clusters = scalar("SELECT COUNT(*) FROM memory_service.memory_clusters WHERE agent_id = %s", (agent_id,))
print(f"📁 Clusters: {clusters or 0}")

# Latest memory
latest = scalar(
    "SELECT created_at FROM memory_service.memories WHERE agent_id = %s ORDER BY created_at DESC LIMIT 1",
    (agent_id,))
if latest:
    print(f"🕒 Latest memory: {latest}")

# Latest handoff
handoff_row = query(
    "SELECT created_at, LEFT(summary, 80) as summary FROM memory_service.session_handoffs WHERE agent_id = %s ORDER BY created_at DESC LIMIT 1",
    (agent_id,))
if handoff_row:
    print(f"📋 Latest handoff: {handoff_row[0]['created_at']}")
    if handoff_row[0].get('summary'):
        print(f"   Summary: {handoff_row[0]['summary']}...")

# Daemon status
daemon_running = False
try:
    r = subprocess.run(["pgrep", "-f", "session_processor.py daemon"], capture_output=True, text=True)
    daemon_running = r.returncode == 0
except:
    pass
print(f"⚙️  Daemon: {'🟢 running' if daemon_running else '🔴 stopped'}")

print("=" * 50)
