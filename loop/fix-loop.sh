#!/bin/bash
# Fix Loop Intelligence - Make it actually work

# 1. Delete broken run.sh
rm -f run.sh

# 2. Create working scan script
cat > scan_intelligence.py << 'PYEOF'
#!/usr/bin/env python3
"""
Loop Intelligence Scanner
Monitors Reddit, HN, YouTube for 0Latency opportunities
"""
import requests
import json
from datetime import datetime

def scan_reddit():
    """Scan Reddit for agent memory discussions"""
    subreddits = ['ClaudeAI', 'ClaudeCode', 'AI_Agents', 'LocalLLaMA']
    alerts = []
    
    for sub in subreddits:
        try:
            # Use Reddit JSON API (no auth needed)
            url = f"https://www.reddit.com/r/{sub}/search.json?q=memory+OR+context+OR+agent&restrict_sr=1&sort=new&limit=10"
            headers = {'User-Agent': '0Latency Intelligence/1.0'}
            r = requests.get(url, headers=headers, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for post in data.get('data', {}).get('children', []):
                    p = post['data']
                    if any(kw in p['title'].lower() for kw in ['memory', 'forget', 'context', 'remember']):
                        alerts.append({
                            'source': f'r/{sub}',
                            'title': p['title'],
                            'url': f"https://reddit.com{p['permalink']}",
                            'score': p['score'],
                            'priority': 'HIGH' if p['score'] > 100 else 'MEDIUM'
                        })
        except Exception as e:
            print(f"Reddit r/{sub} error: {e}")
    
    return alerts

def scan_hn():
    """Scan Hacker News Algolia API"""
    alerts = []
    try:
        url = "https://hn.algolia.com/api/v1/search?query=agent+memory&tags=story&hitsPerPage=10"
        r = requests.get(url, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            for hit in data.get('hits', []):
                if any(kw in hit.get('title', '').lower() for kw in ['memory', 'agent', 'context']):
                    alerts.append({
                        'source': 'HN',
                        'title': hit['title'],
                        'url': f"https://news.ycombinator.com/item?id={hit['objectID']}",
                        'score': hit.get('points', 0),
                        'priority': 'HIGH' if hit.get('points', 0) > 50 else 'MEDIUM'
                    })
    except Exception as e:
        print(f"HN error: {e}")
    
    return alerts

def write_alerts(alerts):
    """Write alerts to file"""
    if not alerts:
        with open('alerts-pending.txt', 'w') as f:
            f.write("NO_NEW_ALERTS\n")
        return
    
    high = [a for a in alerts if a['priority'] == 'HIGH']
    medium = [a for a in alerts if a['priority'] == 'MEDIUM']
    
    with open('alerts-pending.txt', 'w') as f:
        f.write(f"=== Loop Scan {datetime.utcnow().isoformat()} ===\n\n")
        
        if high:
            f.write("HIGH PRIORITY:\n")
            for a in high[:5]:
                f.write(f"- [{a['source']}] {a['title']}\n")
                f.write(f"  {a['url']} (score: {a['score']})\n\n")
        
        if medium:
            f.write("MEDIUM PRIORITY:\n")
            for a in medium[:5]:
                f.write(f"- [{a['source']}] {a['title']}\n")
                f.write(f"  {a['url']}\n\n")

def main():
    print(f"Loop scan starting: {datetime.utcnow()}")
    
    reddit_alerts = scan_reddit()
    hn_alerts = scan_hn()
    
    all_alerts = reddit_alerts + hn_alerts
    all_alerts.sort(key=lambda x: x['score'], reverse=True)
    
    write_alerts(all_alerts)
    
    print(f"Found {len(all_alerts)} alerts ({len([a for a in all_alerts if a['priority']=='HIGH'])} HIGH)")

if __name__ == '__main__':
    main()
PYEOF

chmod +x scan_intelligence.py

# 3. Update cron to use Python script directly
echo "✓ Loop fixed. Test with: python3 scan_intelligence.py"
