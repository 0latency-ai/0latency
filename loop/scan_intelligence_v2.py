#!/usr/bin/env python3
"""
Loop Intelligence Scanner v2 - Comprehensive Edition
Monitors Reddit, HN, YouTube, Twitter, enterprise agent infrastructure
"""
import requests
import json
import os
from datetime import datetime, timedelta

SUPADATA_API_KEY = os.environ.get('SUPADATA_API_KEY', 'sd_0cd8dcc58cc1f4b60c6e42e4385e895d')

def scan_reddit():
    """Scan Reddit for agent memory discussions"""
    subreddits = ['ClaudeAI', 'ClaudeCode', 'AI_Agents', 'LocalLLaMA', 'OpenAI', 'MachineLearning']
    alerts = []
    
    keywords = ['memory', 'context', 'agent', 'remember', 'forget', 'persistence', 'stateful', 'MCP']
    
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
            headers = {'User-Agent': '0Latency Intelligence/2.0'}
            r = requests.get(url, headers=headers, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for post in data.get('data', {}).get('children', []):
                    p = post['data']
                    title_lower = p['title'].lower()
                    
                    # Check for relevant keywords
                    if any(kw in title_lower for kw in keywords):
                        # Extra priority for memory-specific posts
                        is_memory_focused = any(kw in title_lower for kw in ['memory', 'remember', 'forget', 'context'])
                        
                        alerts.append({
                            'source': f'r/{sub}',
                            'title': p['title'],
                            'url': f"https://reddit.com{p['permalink']}",
                            'score': p['score'],
                            'comments': p['num_comments'],
                            'priority': 'HIGH' if (is_memory_focused and p['score'] > 50) else 'MEDIUM',
                            'category': 'reddit'
                        })
        except Exception as e:
            print(f"Reddit r/{sub} error: {e}")
    
    return alerts

def scan_hn():
    """Scan Hacker News Algolia API"""
    alerts = []
    
    queries = [
        'agent memory',
        'AI context',
        'MCP',
        'agent deployment',
        'agent infrastructure',
        'persistent memory AI'
    ]
    
    for query in queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=10"
            r = requests.get(url, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for hit in data.get('hits', []):
                    title = hit.get('title', '')
                    points = hit.get('points', 0)
                    
                    # Dedupe by objectID
                    if not any(a.get('hn_id') == hit['objectID'] for a in alerts):
                        alerts.append({
                            'source': 'HN',
                            'title': title,
                            'url': f"https://news.ycombinator.com/item?id={hit['objectID']}",
                            'score': points,
                            'priority': 'HIGH' if points > 50 else 'MEDIUM',
                            'category': 'hn',
                            'hn_id': hit['objectID']
                        })
        except Exception as e:
            print(f"HN query '{query}' error: {e}")
    
    return alerts

def scan_youtube():
    """Check YouTube channels for recent agent/memory content"""
    alerts = []
    
    channels = {
        '@mreflow': 'Matt Wolfe',
        '@GregIsenberg': 'Greg Isenberg', 
        '@NateHerk': 'Nate Herk',
        '@AIRevolutionX': 'AI Revolution',
        '@swyx': 'Swyx',
        '@AnthropicAI': 'Anthropic',
        '@OpenAI': 'OpenAI',
        '@AIJasonZ': 'AI Jason'
    }
    
    for handle, name in channels.items():
        try:
            # Use YouTube RSS feed (no API key needed)
            url = f"https://www.youtube.com/feeds/videos.xml?user={handle.replace('@', '')}"
            r = requests.get(url, timeout=10)
            
            if r.status_code == 200 and 'entry' in r.text:
                # Parse basic XML (good enough for RSS)
                entries = r.text.split('<entry>')[1:6]  # Last 5 videos
                
                for entry in entries:
                    if '<title>' in entry and '<link' in entry:
                        title_start = entry.find('<title>') + 7
                        title_end = entry.find('</title>')
                        title = entry[title_start:title_end]
                        
                        # Extract video ID
                        vid_start = entry.find('watch?v=') + 8
                        vid_end = entry.find('"', vid_start)
                        video_id = entry[vid_start:vid_end]
                        
                        # Check if relevant
                        title_lower = title.lower()
                        keywords = ['agent', 'memory', 'ai', 'claude', 'mcp', 'automation', 'context']
                        
                        if any(kw in title_lower for kw in keywords):
                            alerts.append({
                                'source': f'YouTube - {name}',
                                'title': title,
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'priority': 'HIGH' if name in ['Greg Isenberg', 'Anthropic', 'Swyx'] else 'MEDIUM',
                                'category': 'youtube'
                            })
        except Exception as e:
            print(f"YouTube {name} error: {e}")
    
    return alerts

def scan_twitter_via_search():
    """Scan Twitter content via web search (no API needed)"""
    alerts = []
    
    queries = [
        'site:twitter.com OR site:x.com #aiagents memory',
        'site:twitter.com OR site:x.com #MCP agent',
        'site:twitter.com OR site:x.com agent deployment infrastructure',
        'site:twitter.com OR site:x.com "agent memory" OR "persistent context"'
    ]
    
    # Note: This will require calling out to brave_search or similar
    # For now, log that we need this capability
    print("Twitter scan: Would use web_search tool here (requires tool call)")
    
    return alerts

def scan_enterprise_infrastructure():
    """Search for enterprise agent deployment platforms and infrastructure"""
    alerts = []
    
    # Companies/platforms building agent infrastructure
    targets = [
        'ZeroClick agent platform',
        'agent deployment enterprise',
        'AI agent infrastructure retail',
        'conversational commerce agents',
        'agent-to-agent communication platforms',
        'multi-agent orchestration enterprise'
    ]
    
    print("Enterprise infrastructure scan: Would use web_search tool here")
    
    return alerts

def prioritize_alerts(alerts):
    """Enhanced prioritization logic"""
    for alert in alerts:
        title_lower = alert['title'].lower()
        
        # Upgrade to CRITICAL if:
        # - Mentions 0Latency competitors (Mem0, Zep, Hindsight)
        # - Enterprise agent deployment
        # - ZeroClick or similar platforms
        critical_keywords = ['mem0', 'zep', 'hindsight', 'zeroclick', 'agent deployment', 'enterprise agents']
        
        if any(kw in title_lower for kw in critical_keywords):
            alert['priority'] = 'CRITICAL'
        
        # Memory-focused content gets priority boost
        if any(kw in title_lower for kw in ['memory', 'remember', 'context', 'forget']):
            if alert['priority'] == 'MEDIUM':
                alert['priority'] = 'HIGH'
    
    return alerts

def write_alerts(alerts):
    """Write alerts to file with enhanced formatting"""
    if not alerts:
        with open('alerts-pending.txt', 'w') as f:
            f.write("NO_NEW_ALERTS\n")
        return
    
    alerts = prioritize_alerts(alerts)
    
    critical = [a for a in alerts if a.get('priority') == 'CRITICAL']
    high = [a for a in alerts if a.get('priority') == 'HIGH']
    medium = [a for a in alerts if a.get('priority') == 'MEDIUM']
    
    with open('alerts-pending.txt', 'w') as f:
        f.write(f"=== Loop Intelligence Scan {datetime.utcnow().isoformat()} ===\n\n")
        
        if critical:
            f.write("🚨 CRITICAL PRIORITY:\n")
            for a in critical[:3]:
                f.write(f"- [{a['source']}] {a['title']}\n")
                f.write(f"  {a['url']}")
                if 'score' in a:
                    f.write(f" (score: {a['score']})")
                f.write("\n\n")
        
        if high:
            f.write("HIGH PRIORITY:\n")
            for a in high[:5]:
                f.write(f"- [{a['source']}] {a['title']}\n")
                f.write(f"  {a['url']}")
                if 'score' in a:
                    f.write(f" (score: {a['score']})")
                f.write("\n\n")
        
        if medium:
            f.write("MEDIUM PRIORITY:\n")
            for a in medium[:5]:
                f.write(f"- [{a['source']}] {a['title']}\n")
                f.write(f"  {a['url']}\n\n")
        
        # Summary stats
        f.write(f"\n--- Scan Summary ---\n")
        f.write(f"Total alerts: {len(alerts)}\n")
        f.write(f"Critical: {len(critical)}, High: {len(high)}, Medium: {len(medium)}\n")
        f.write(f"Sources: Reddit ({len([a for a in alerts if a['category']=='reddit'])}), ")
        f.write(f"HN ({len([a for a in alerts if a['category']=='hn'])}), ")
        f.write(f"YouTube ({len([a for a in alerts if a['category']=='youtube'])})\n")

def main():
    print(f"Loop Intelligence Scan v2 starting: {datetime.utcnow()}")
    
    all_alerts = []
    
    # Run all scans
    all_alerts.extend(scan_reddit())
    all_alerts.extend(scan_hn())
    all_alerts.extend(scan_youtube())
    # Twitter and enterprise scans need tool calls - will be handled by wrapper
    
    # Dedupe by URL
    seen_urls = set()
    unique_alerts = []
    for alert in all_alerts:
        if alert['url'] not in seen_urls:
            seen_urls.add(alert['url'])
            unique_alerts.append(alert)
    
    # Sort by priority, then score
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}
    unique_alerts.sort(key=lambda x: (
        priority_order.get(x.get('priority', 'MEDIUM'), 2),
        -x.get('score', 0)
    ))
    
    write_alerts(unique_alerts)
    
    print(f"Scan complete: {len(unique_alerts)} unique alerts")
    print(f"  CRITICAL: {len([a for a in unique_alerts if a.get('priority')=='CRITICAL'])}")
    print(f"  HIGH: {len([a for a in unique_alerts if a.get('priority')=='HIGH'])}")
    print(f"  MEDIUM: {len([a for a in unique_alerts if a.get('priority')=='MEDIUM'])}")

if __name__ == '__main__':
    main()
