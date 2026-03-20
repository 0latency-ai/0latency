#!/usr/bin/env python3
"""Memory Engine — Health Check"""

import os
import sys
import subprocess
import json

DB_CONN = os.environ.get("MEMORY_DB_CONN", "")
if not DB_CONN:
    print("❌ MEMORY_DB_CONN not set")
    sys.exit(1)

agent_id = sys.argv[1] if len(sys.argv) > 1 else "default"


def query(sql):
    password = ""
    try:
        from urllib.parse import urlparse
        password = urlparse(DB_CONN).password or ""
    except:
        pass
    env = {**os.environ}
    if password:
        env["PGPASSWORD"] = password
    r = subprocess.run(["psql", DB_CONN, "-t", "-A", "-F", "|", "-c", sql],
                       capture_output=True, text=True, timeout=15, env=env)
    if r.returncode != 0:
        return []
    return [l for l in r.stdout.strip().split("\n") if l]


print(f"🧠 Memory Engine Health — Agent: {agent_id}")
print("=" * 50)

# Total memories
rows = query(f"SELECT COUNT(*) FROM memory_service.memories WHERE agent_id = '{agent_id}'")
total = int(rows[0]) if rows else 0
print(f"📦 Total memories: {total}")

# By type
rows = query(f"SELECT memory_type, COUNT(*) FROM memory_service.memories WHERE agent_id = '{agent_id}' GROUP BY memory_type ORDER BY count DESC")
if rows:
    print("📊 By type:")
    for r in rows:
        parts = r.split("|")
        if len(parts) == 2:
            print(f"   {parts[0]}: {parts[1]}")

# Active vs superseded
rows = query(f"SELECT COUNT(*) FILTER (WHERE superseded_at IS NULL) as active, COUNT(*) FILTER (WHERE superseded_at IS NOT NULL) as superseded FROM memory_service.memories WHERE agent_id = '{agent_id}'")
if rows:
    parts = rows[0].split("|")
    if len(parts) == 2:
        print(f"✅ Active: {parts[0]} | 🔄 Superseded: {parts[1]}")

# Average importance
rows = query(f"SELECT ROUND(AVG(importance)::numeric, 3) FROM memory_service.memories WHERE agent_id = '{agent_id}' AND superseded_at IS NULL")
if rows and rows[0]:
    print(f"⚖️  Avg importance: {rows[0]}")

# Entity edges
rows = query(f"SELECT COUNT(*) FROM memory_service.memory_edges WHERE agent_id = '{agent_id}'")
print(f"🔗 Entity edges: {rows[0] if rows else 0}")

# Topics
rows = query(f"SELECT COUNT(*) FROM memory_service.topic_coverage WHERE agent_id = '{agent_id}'")
print(f"📚 Topics tracked: {rows[0] if rows else 0}")

# Clusters
rows = query(f"SELECT COUNT(*) FROM memory_service.memory_clusters WHERE agent_id = '{agent_id}'")
print(f"📁 Clusters: {rows[0] if rows else 0}")

# Latest memory
rows = query(f"SELECT created_at FROM memory_service.memories WHERE agent_id = '{agent_id}' ORDER BY created_at DESC LIMIT 1")
if rows:
    print(f"🕒 Latest memory: {rows[0]}")

# Latest handoff
rows = query(f"SELECT created_at, LEFT(summary, 80) FROM memory_service.session_handoffs WHERE agent_id = '{agent_id}' ORDER BY created_at DESC LIMIT 1")
if rows:
    parts = rows[0].split("|")
    print(f"📋 Latest handoff: {parts[0]}")
    if len(parts) > 1:
        print(f"   Summary: {parts[1]}...")

# Daemon status
import shutil
daemon_running = False
try:
    r = subprocess.run(["pgrep", "-f", "session_processor.py daemon"], capture_output=True, text=True)
    daemon_running = r.returncode == 0
except:
    pass
print(f"⚙️  Daemon: {'🟢 running' if daemon_running else '🔴 stopped'}")

print("=" * 50)
