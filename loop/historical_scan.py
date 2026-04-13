#!/usr/bin/env python3
"""
Loop Intelligence - Historical HN Scan (Past 14 Days)
"""
import requests
import json
from datetime import datetime, timedelta

def scan_hn_past_14_days():
    """Scan HN for past 14 days of agent/memory discussions"""
    # Calculate timestamp for 14 days ago
    cutoff = int((datetime.utcnow() - timedelta(days=14)).timestamp())
    
    alerts = []
    queries = [
        "agent memory",
        "AI memory",
        "context management",
        "persistent memory",
        "agent context",
        "LLM memory"
    ]
    
    seen_ids = set()
    
    for query in queries:
        try:
            # HN Algolia API with date filter
            url = f"https://hn.algolia.com/api/v1/search?query={query.replace(' ', '+')}&tags=story&hitsPerPage=50&numericFilters=created_at_i>{cutoff}"
            r = requests.get(url, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for hit in data.get('hits', []):
                    obj_id = hit['objectID']
                    if obj_id in seen_ids:
                        continue
                    seen_ids.add(obj_id)
                    
                    title = hit.get('title', '')
                    points = hit.get('points', 0)
                    created = datetime.fromtimestamp(hit.get('created_at_i', 0))
                    
                    # Filter for relevant keywords
                    if any(kw in title.lower() for kw in [
                        'memory', 'agent', 'context', 'llm', 'ai', 
                        'claude', 'gpt', 'recall', 'forget', 'persistent'
                    ]):
                        alerts.append({
                            'id': obj_id,
                            'title': title,
                            'url': f"https://news.ycombinator.com/item?id={obj_id}",
                            'points': points,
                            'created': created.strftime('%Y-%m-%d'),
                            'age_days': (datetime.utcnow() - created).days,
                            'priority': 'HIGH' if points > 50 else 'MEDIUM' if points > 20 else 'LOW'
                        })
        except Exception as e:
            print(f"Error scanning '{query}': {e}")
    
    # Sort by points descending
    alerts.sort(key=lambda x: x['points'], reverse=True)
    return alerts

def main():
    print(f"=== Loop Historical HN Scan (Past 14 Days) ===")
    print(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    
    alerts = scan_hn_past_14_days()
    
    # Write to file
    with open('historical-hn-scan.md', 'w') as f:
        f.write(f"# Loop Intelligence - HN Scan (Past 14 Days)\n\n")
        f.write(f"**Scan Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  \n")
        f.write(f"**Total Threads:** {len(alerts)}  \n\n")
        
        f.write("---\n\n")
        
        # Group by priority
        high = [a for a in alerts if a['priority'] == 'HIGH']
        medium = [a for a in alerts if a['priority'] == 'MEDIUM']
        low = [a for a in alerts if a['priority'] == 'LOW']
        
        if high:
            f.write(f"## HIGH PRIORITY ({len(high)} threads)\n\n")
            for a in high:
                f.write(f"### {a['title']}\n")
                f.write(f"- **URL:** {a['url']}\n")
                f.write(f"- **Points:** {a['points']}\n")
                f.write(f"- **Posted:** {a['created']} ({a['age_days']} days ago)\n\n")
        
        if medium:
            f.write(f"## MEDIUM PRIORITY ({len(medium)} threads)\n\n")
            for a in medium:
                f.write(f"- [{a['points']} pts] **{a['title']}**  \n")
                f.write(f"  {a['url']} • {a['created']}\n\n")
        
        if low:
            f.write(f"## LOW PRIORITY ({len(low)} threads)\n\n")
            for a in low:
                f.write(f"- [{a['points']} pts] {a['title']}  \n")
                f.write(f"  {a['url']}\n\n")
    
    print(f"Found {len(alerts)} threads:")
    print(f"  HIGH: {len(high)}")
    print(f"  MEDIUM: {len(medium)}")
    print(f"  LOW: {len(low)}")
    print(f"\nResults written to: historical-hn-scan.md")

if __name__ == '__main__':
    main()
