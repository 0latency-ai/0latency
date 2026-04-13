#!/usr/bin/env python3
"""
Atlas - Chief Data Officer
Weekly snapshots, Monday briefings, agent performance metrics
"""
import requests
import json
from datetime import datetime, timedelta
import subprocess

ZEROLATENCY_API_KEY = open('/root/.openclaw/workspace/THOMAS_API_KEY.txt').read().strip()
API_URL = 'https://api.0latency.ai/v1/recall'
EXTRACT_URL = 'https://api.0latency.ai/extract'

# Supabase connection (atlas schema)
DB_CONN = "postgresql://postgres.fuojxlabvhtmysbsixdn:jcYlwEhuHN9VcOuj@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

AGENTS = ['thomas', 'loop', 'lance', 'scout', 'shea', 'sheila', 'nellie', 'wall-e', 'steve', 'reed']

def query_namespace_stats(agent_id):
    """Query agent namespace for activity stats"""
    try:
        response = requests.post(
            API_URL,
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': agent_id,
                'query': f'{agent_id} activity last 7 days memories actions outcomes',
                'conversation_context': 'Atlas weekly snapshot data collection',
                'limit': 50
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'memories_recalled': data.get('memories_used', 0),
                'context_size': len(data.get('context_block', '')),
                'status': 'active' if data.get('memories_used', 0) > 0 else 'idle'
            }
        else:
            return {'memories_recalled': 0, 'context_size': 0, 'status': 'error'}
            
    except Exception as e:
        print(f"  Error querying {agent_id}: {e}")
        return {'memories_recalled': 0, 'context_size': 0, 'status': 'error'}

def capture_weekly_snapshot():
    """
    Capture Sunday night snapshot of all agent activity
    Stores to atlas.weekly_snapshots table
    """
    print(f"\n=== Atlas Weekly Snapshot ===")
    print(f"Snapshot Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    
    snapshot_data = {}
    
    for agent in AGENTS:
        print(f"  Querying {agent}...")
        stats = query_namespace_stats(agent)
        snapshot_data[agent] = stats
        
        # Log recall usage for each agent query
        log_recall_usage(agent, stats)
    
    # Store snapshot to Supabase atlas schema
    store_snapshot(snapshot_data)
    
    return snapshot_data

def log_recall_usage(agent_id, stats):
    """Store Atlas's recall of agent data as memory (recall usage logging)"""
    try:
        log_content = f"""Weekly Snapshot Recall — {agent_id}

Memories Recalled: {stats['memories_recalled']}
Context Size: {stats['context_size']} chars
Agent Status: {stats['status']}

PURPOSE: Weekly performance snapshot for Monday briefing
OUTCOME: Data collection for agent activity metrics

This recall feeds Atlas's reporting infrastructure.
Generated: {datetime.utcnow().isoformat()}"""
        
        requests.post(
            EXTRACT_URL,
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'atlas',
                'human_message': f"Weekly snapshot recall — {agent_id}",
                'agent_message': log_content
            },
            timeout=30
        )
        
    except Exception as e:
        print(f"  Warning: Could not log recall usage for {agent_id}: {e}")

def store_snapshot(snapshot_data):
    """Store snapshot to Supabase atlas.weekly_snapshots table"""
    try:
        # Build JSON for snapshot
        snapshot_json = json.dumps(snapshot_data)
        week_ending = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Insert via psql (RPC functions preferred but direct SQL works)
        insert_sql = f"""
INSERT INTO atlas.weekly_snapshots (week_ending, snapshot_data, created_at)
VALUES ('{week_ending}', '{snapshot_json}'::jsonb, NOW())
ON CONFLICT (week_ending) DO UPDATE SET snapshot_data = EXCLUDED.snapshot_data;
"""
        
        result = subprocess.run(
            ['psql', DB_CONN, '-c', insert_sql],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"  ✓ Snapshot stored to atlas.weekly_snapshots")
        else:
            print(f"  ✗ Snapshot storage failed: {result.stderr}")
            
    except Exception as e:
        print(f"  ✗ Error storing snapshot: {e}")

def generate_monday_briefing(snapshot_data):
    """
    Generate Monday morning briefing from Sunday snapshot
    Stored to Atlas namespace + sent to Thomas via Telegram
    """
    print(f"\n=== Monday Briefing Generation ===")
    
    # Calculate activity summary
    active_agents = sum(1 for agent, stats in snapshot_data.items() if stats['status'] == 'active')
    idle_agents = sum(1 for agent, stats in snapshot_data.items() if stats['status'] == 'idle')
    
    total_memories = sum(stats['memories_recalled'] for stats in snapshot_data.values())
    
    briefing = f"""ATLAS MONDAY BRIEFING
Week Ending: {datetime.utcnow().strftime('%Y-%m-%d')}

AGENT ACTIVITY SUMMARY:
  Active: {active_agents} agents
  Idle: {idle_agents} agents
  Total Memories Recalled: {total_memories}

PER-AGENT BREAKDOWN:
"""
    
    for agent, stats in sorted(snapshot_data.items(), key=lambda x: x[1]['memories_recalled'], reverse=True):
        status_emoji = "✓" if stats['status'] == 'active' else "—"
        briefing += f"  {status_emoji} {agent:10s}: {stats['memories_recalled']:4d} memories, {stats['context_size']:6d} chars\n"
    
    briefing += f"""
KEY METRICS:
  Intelligence Agents (Loop, Scout, Sheila): [pending metric definitions]
  Execution Agents (Lance, Shea, Nellie): [pending metric definitions]
  Memory Quality (Wall-E): [pending Phase 2 integration]

This briefing will be enhanced with:
- Revenue metrics tracking
- Action conversion rates
- Memory quality scores
Once self-improving Phase 3+ and revenue tracking are live.

Generated: {datetime.utcnow().isoformat()}
"""
    
    # Store briefing to Atlas namespace
    try:
        requests.post(
            EXTRACT_URL,
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'atlas',
                'human_message': f"Monday briefing — {datetime.utcnow().strftime('%Y-%m-%d')}",
                'agent_message': briefing
            },
            timeout=30
        )
        print(f"  ✓ Briefing stored to Atlas namespace")
    except Exception as e:
        print(f"  ✗ Error storing briefing: {e}")
    
    # Write to file for Thomas to read during heartbeat
    briefing_path = f"/root/logs/atlas-briefing-{datetime.utcnow().strftime('%Y-%m-%d')}.txt"
    with open(briefing_path, 'w') as f:
        f.write(briefing)
    
    print(f"  ✓ Briefing written to {briefing_path}")
    print("\n" + briefing)
    
    return briefing

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'snapshot':
        # Sunday night snapshot
        snapshot = capture_weekly_snapshot()
        print(f"\nAtlas snapshot complete: {len(snapshot)} agents captured")
        
    elif len(sys.argv) > 1 and sys.argv[1] == 'briefing':
        # Monday briefing (reads most recent snapshot from DB)
        # For now, generate from fresh recall
        snapshot = capture_weekly_snapshot()
        briefing = generate_monday_briefing(snapshot)
        
    else:
        print("Usage:")
        print("  python weekly_snapshot.py snapshot   # Sunday night data capture")
        print("  python weekly_snapshot.py briefing   # Monday morning report")

if __name__ == '__main__':
    main()
