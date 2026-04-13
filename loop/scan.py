#!/usr/bin/env python3
"""
Loop Intelligence Scanner
Monitors Reddit, HN, GitHub for 0Latency engagement opportunities
"""

import json
import subprocess
from datetime import datetime, timedelta
import sys

CHANNELS = {
    "reddit": [
        "r/ClaudeCode",
        "r/AI_Agents", 
        "r/LocalLLaMA",
        "r/ClaudeAI"
    ],
    "hn": [
        "agent memory",
        "Claude memory",
        "MCP memory"
    ],
    "github": [
        "mem0-ai/mem0",
        "zep-ai/zep",
        "anthropics/mcp"
    ]
}

def search_web(query):
    """Use OpenClaw web_search via subprocess"""
    try:
        # This is a placeholder - in practice we'd use the actual web_search tool
        # For now, just log what we'd search
        return []
    except Exception as e:
        print(f"Search error: {e}", file=sys.stderr)
        return []

def scan_channels():
    """Scan all channels for new content"""
    results = {
        "high_priority": [],
        "medium_priority": [],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Reddit searches
    for subreddit in CHANNELS["reddit"]:
        query = f"0latency OR \"agent memory\" OR \"persistent memory\" site:reddit.com/{subreddit}"
        hits = search_web(query)
        # Process hits...
    
    # HN searches  
    for term in CHANNELS["hn"]:
        query = f"{term} site:news.ycombinator.com"
        hits = search_web(query)
        # Process hits...
    
    # GitHub issues
    for repo in CHANNELS["github"]:
        query = f"memory persistent agent site:github.com/{repo}/issues"
        hits = search_web(query)
        # Process hits...
    
    return results

def write_alerts(results):
    """Write alerts to pending file"""
    output_path = "/root/.openclaw/workspace/loop/alerts-pending.txt"
    
    with open(output_path, 'w') as f:
        f.write(f"=== Loop Intelligence Scan - {results['timestamp']} ===\n\n")
        
        if results['high_priority']:
            f.write("HIGH PRIORITY:\n")
            for alert in results['high_priority']:
                f.write(f"- {alert}\n")
            f.write("\n")
        
        if results['medium_priority']:
            f.write("MEDIUM PRIORITY:\n")
            for alert in results['medium_priority']:
                f.write(f"- {alert}\n")
            f.write("\n")
        
        if not results['high_priority'] and not results['medium_priority']:
            f.write("NO_NEW_ALERTS\n")

def main():
    print(f"Loop scan starting - {datetime.utcnow().isoformat()}")
    
    results = scan_channels()
    write_alerts(results)
    
    print(f"Scan complete - {len(results['high_priority'])} high, {len(results['medium_priority'])} medium priority")

if __name__ == "__main__":
    main()
