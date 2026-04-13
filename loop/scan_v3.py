#!/usr/bin/env python3
"""
Loop Intelligence Scanner v3 - Orchestration Edition
Now stores findings in loop namespace + writes action briefs to Lance
"""
import requests
import json
import os
from datetime import datetime

SUPADATA_API_KEY = os.environ.get('SUPADATA_API_KEY', 'sd_0cd8dcc58cc1f4b60c6e42e4385e895d')
ZEROLATENCY_API_KEY = os.environ.get('ZEROLATENCY_API_KEY', 
    open('/root/.openclaw/workspace/THOMAS_API_KEY.txt').read().strip())

def recall_past_outcomes():
    """
    Self-improvement: Recall past 7 days of findings and check outcomes
    Returns priority adjustments based on what converted vs what was ignored
    """
    try:
        # Recall Loop's past findings
        loop_response = requests.post(
            'https://api.0latency.ai/v1/recall',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'loop',
                'query': 'past intelligence findings last 7 days',
                'conversation_context': 'reviewing past findings to learn conversion patterns',
                'limit': 100
            },
            timeout=30
        )
        
        # Recall Lance's actions to see what converted
        lance_response = requests.post(
            'https://api.0latency.ai/v1/recall',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'lance',
                'query': 'approved sent actions outcomes engagement',
                'conversation_context': 'checking which Loop findings led to successful engagement',
                'limit': 50
            },
            timeout=30
        )
        
        # TODO: Parse responses and build priority adjustment map
        # For now, log that recall happened
        loop_memories = loop_response.json().get('memories_used', 0) if loop_response.status_code == 200 else 0
        lance_memories = lance_response.json().get('memories_used', 0) if lance_response.status_code == 200 else 0
        
        print(f"  Self-improvement: Recalled {loop_memories} past findings, {lance_memories} Lance actions")
        
        # RECALL USAGE LOGGING (prep for Phase 3 /feedback integration)
        # Store what we recalled and what we'll do with it
        recall_usage = f"""Recall Usage Log
        
Query: "past intelligence findings last 7 days + Lance action outcomes"
Loop memories recalled: {loop_memories}
Lance action memories recalled: {lance_memories}

PURPOSE: Self-improvement priority adjustment
OUTCOME: Learning which types of findings convert to actual engagement

Next step: Parse recall results to identify conversion patterns
- High-engagement findings → boost similar content priority
- Ignored findings → lower similar content priority

This log will inform /feedback endpoint calls once Phase 3 is live.
Generated: {datetime.utcnow().isoformat()}"""
        
        # Store recall usage as memory
        store_to_namespace('loop', 
            f"Recall Usage — Self-Improvement Check ({datetime.utcnow().strftime('%Y-%m-%d %H:%M')})",
            recall_usage,
            importance=0.4)
        
        # Return empty adjustments for now - in production, this would return:
        # { 'mcp_threads': +0.2, 'show_hn': +0.1, 'reddit_casual': -0.1 }
        return {}
        
    except Exception as e:
        print(f"  Recall error (non-fatal): {e}")
        return {}

def store_to_namespace(agent_id, headline, content, importance=0.5):
    """Store finding in Loop's 0Latency namespace"""
    try:
        response = requests.post(
            'https://api.0latency.ai/extract',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': agent_id,
                'human_message': f"New intelligence finding: {headline}",
                'agent_message': content
            },
            timeout=30
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Namespace storage error: {e}")
        return False

def write_action_brief(alert, analysis):
    """Write action brief to Lance's workspace"""
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    source_clean = alert['source'].replace('/', '-').replace(' ', '-').lower()
    filename = f"/root/.openclaw/workspace/lance/actions-pending/{timestamp}-{source_clean}.md"
    
    with open(filename, 'w') as f:
        f.write(f"""## Engagement Brief

**Source:** {alert['url']}
**Platform:** {alert['source']}
**Priority:** {alert['priority']}
**Found:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

### Thread Summary
{alert['title']}

Score: {alert.get('score', 'N/A')} points
{f"Comments: {alert.get('comments', 'N/A')}" if 'comments' in alert else ""}

### Why We Should Engage
{analysis.get('relevance', 'High relevance to 0Latency positioning and agent memory use cases.')}

### Engagement Opportunity
{analysis.get('engagement_type', 'comment')}

### Suggested Response
{analysis.get('suggested_response', '[Lance: Draft response based on thread context]')}

### Tone
{analysis.get('tone', 'helpful-technical')}

### CTA
{analysis.get('cta', 'Link to 0latency.ai/docs if relevant')}

### Deadline
{analysis.get('deadline', '~24 hours (discussions move fast)')}

---
**Status:** pending_review
**Assigned To:** lance
""")
    return filename

def analyze_alert(alert):
    """Determine if alert warrants action brief to Lance"""
    title_lower = alert['title'].lower()
    
    # Auto-generate analysis based on content
    analysis = {
        'relevance': '',
        'engagement_type': 'comment',
        'suggested_response': '[Draft helpful technical response]',
        'tone': 'helpful-technical',
        'cta': '0latency.ai',
        'deadline': '24 hours'
    }
    
    # Memory-focused = high relevance
    if any(kw in title_lower for kw in ['memory', 'context', 'forget', 'remember']):
        analysis['relevance'] = "Direct discussion of agent memory/context management — core 0Latency use case."
        analysis['engagement_type'] = 'comment'
    
    # MCP discussions
    elif 'mcp' in title_lower:
        analysis['relevance'] = "MCP ecosystem discussion — 0Latency integrates with MCP servers for persistent memory."
        analysis['engagement_type'] = 'comment'
    
    # Agent deployment platforms
    elif any(kw in title_lower for kw in ['agent deployment', 'agent infrastructure', 'multi-agent']):
        analysis['relevance'] = "Enterprise agent deployment platform — exact target market for 0Latency (agents at scale need persistent memory)."
        analysis['engagement_type'] = 'comment or DM to founder'
    
    # Show HN = opportunity to engage with builder
    if 'show hn' in title_lower:
        analysis['tone'] = 'supportive-technical'
        analysis['cta'] = 'Offer to help with memory layer if relevant'
    
    return analysis

def scan_reddit():
    """Scan Reddit for agent memory discussions"""
    alerts = []
    subreddits = ['ClaudeAI', 'ClaudeCode', 'AI_Agents', 'LocalLLaMA', 'OpenAI', 'MachineLearning']
    keywords = ['memory', 'context', 'agent', 'remember', 'forget', 'persistence', 'stateful', 'MCP']
    
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
            headers = {'User-Agent': '0Latency Intelligence/3.0'}
            r = requests.get(url, headers=headers, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for post in data.get('data', {}).get('children', []):
                    p = post['data']
                    title_lower = p['title'].lower()
                    
                    if any(kw in title_lower for kw in keywords):
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
    """Scan Hacker News"""
    alerts = []
    queries = ['agent memory', 'AI context', 'MCP', 'agent deployment', 'persistent memory AI']
    
    for query in queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=10"
            r = requests.get(url, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for hit in data.get('hits', []):
                    if not any(a.get('hn_id') == hit['objectID'] for a in alerts):
                        points = hit.get('points', 0)
                        alerts.append({
                            'source': 'HN',
                            'title': hit.get('title', ''),
                            'url': f"https://news.ycombinator.com/item?id={hit['objectID']}",
                            'score': points,
                            'priority': 'CRITICAL' if 'deployment' in query else ('HIGH' if points > 50 else 'MEDIUM'),
                            'category': 'hn',
                            'hn_id': hit['objectID']
                        })
        except Exception as e:
            print(f"HN query '{query}' error: {e}")
    
    return alerts

def scan_youtube():
    """Check YouTube channels via RSS"""
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
            url = f"https://www.youtube.com/feeds/videos.xml?user={handle.replace('@', '')}"
            r = requests.get(url, timeout=10)
            
            if r.status_code == 200 and 'entry' in r.text:
                entries = r.text.split('<entry>')[1:6]
                
                for entry in entries:
                    if '<title>' in entry and '<link' in entry:
                        title_start = entry.find('<title>') + 7
                        title_end = entry.find('</title>')
                        title = entry[title_start:title_end]
                        
                        vid_start = entry.find('watch?v=') + 8
                        vid_end = entry.find('"', vid_start)
                        video_id = entry[vid_start:vid_end]
                        
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

def prioritize_and_store(alerts):
    """Enhanced prioritization + namespace storage"""
    # Upgrade critical items
    for alert in alerts:
        title_lower = alert['title'].lower()
        
        critical_keywords = ['mem0', 'zep', 'hindsight', 'zeroclick', 'agent deployment', 'enterprise agents']
        if any(kw in title_lower for kw in critical_keywords):
            alert['priority'] = 'CRITICAL'
        
        # Memory-focused gets priority boost
        if any(kw in title_lower for kw in ['memory', 'remember', 'context', 'forget']):
            if alert['priority'] == 'MEDIUM':
                alert['priority'] = 'HIGH'
    
    # Store each finding in Loop's namespace
    action_briefs_written = 0
    for alert in alerts:
        # Build memory content
        content = f"""
Source: {alert['source']}
Title: {alert['title']}
URL: {alert['url']}
Priority: {alert['priority']}
Score: {alert.get('score', 'N/A')}
Category: {alert['category']}
Relevance: {"High - direct agent memory discussion" if alert['priority'] in ['CRITICAL', 'HIGH'] else "Medium - general agent ecosystem"}
"""
        
        # Store to namespace
        importance = {'CRITICAL': 0.9, 'HIGH': 0.7, 'MEDIUM': 0.5, 'LOW': 0.3}.get(alert['priority'], 0.5)
        store_to_namespace('loop', alert['title'], content, importance)
        
        # Write action brief for HIGH/CRITICAL items
        if alert['priority'] in ['CRITICAL', 'HIGH'] and alert.get('score', 0) > 20:
            analysis = analyze_alert(alert)
            brief_file = write_action_brief(alert, analysis)
            action_briefs_written += 1
            print(f"  → Action brief: {brief_file}")
    
    return action_briefs_written

def main():
    print(f"Loop Intelligence Scan v3 starting: {datetime.utcnow()}")
    
    all_alerts = []
    all_alerts.extend(scan_reddit())
    all_alerts.extend(scan_hn())
    all_alerts.extend(scan_youtube())
    
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
    
    # Store to namespace + write action briefs
    action_briefs = prioritize_and_store(unique_alerts)
    
    # Write summary file for Thomas
    critical = [a for a in unique_alerts if a.get('priority') == 'CRITICAL']
    high = [a for a in unique_alerts if a.get('priority') == 'HIGH']
    medium = [a for a in unique_alerts if a.get('priority') == 'MEDIUM']
    
    with open('/root/.openclaw/workspace/loop/alerts-pending.txt', 'w') as f:
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
        
        f.write(f"\n--- Scan Summary ---\n")
        f.write(f"Total alerts: {len(unique_alerts)}\n")
        f.write(f"Stored to namespace: {len(unique_alerts)} memories\n")
        f.write(f"Action briefs for Lance: {action_briefs}\n")
        f.write(f"Critical: {len(critical)}, High: {len(high)}, Medium: {len(medium)}\n")
    
    print(f"Scan complete: {len(unique_alerts)} alerts")
    print(f"  Stored to loop namespace: {len(unique_alerts)} memories")
    print(f"  Action briefs for Lance: {action_briefs}")
    print(f"  CRITICAL: {len(critical)} | HIGH: {len(high)} | MEDIUM: {len(medium)}")

if __name__ == '__main__':
    main()
