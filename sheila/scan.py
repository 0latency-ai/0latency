#!/usr/bin/env python3
"""
Sheila - Startup Smartup Intelligence Scanner
Monitors for reconnect opportunities and startup education market activity
"""
import requests
from datetime import datetime

def scan_reddit_startups():
    """Scan r/startups and r/Entrepreneur for reconnect triggers"""
    alerts = []
    subreddits = ['startups', 'Entrepreneur']
    
    keywords = ['first customer', 'validate idea', 'startup education', 'learning', 'founder journey']
    
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=20"
            headers = {'User-Agent': 'Sheila SS Intelligence/1.0'}
            r = requests.get(url, headers=headers, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for post in data.get('data', {}).get('children', []):
                    p = post['data']
                    title_lower = p['title'].lower()
                    selftext_lower = p.get('selftext', '').lower()
                    
                    # Look for posts about startup education, getting first customers
                    if any(kw in title_lower or kw in selftext_lower for kw in keywords):
                        alerts.append({
                            'source': f'r/{sub}',
                            'title': p['title'],
                            'url': f"https://reddit.com{p['permalink']}",
                            'author': p['author'],
                            'score': p['score'],
                            'type': 'community'
                        })
        except Exception as e:
            print(f"Reddit r/{sub} error: {e}")
    
    return alerts

def scan_indie_hackers():
    """
    Note: IndieHackers scraping requires web_search tool
    Flag for Thomas to handle
    """
    print("IndieHackers monitoring: Requires web_search tool - flagging for Thomas")
    return []

def write_alerts(alerts):
    """Write Sheila alerts to file"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    with open('/root/.openclaw/workspace/sheila/alerts-pending.txt', 'w') as f:
        f.write(f"=== Sheila Intelligence Scan - {timestamp} ===\n\n")
        
        if not alerts:
            f.write("NO_NEW_ALERTS - Market quiet\n")
            f.write("No significant Startup Smartup opportunities detected since last scan.\n")
            return
        
        community = [a for a in alerts if a.get('type') == 'community']
        
        if community:
            f.write("COMMUNITY ENGAGEMENT OPPORTUNITIES:\n")
            for a in community[:7]:
                f.write(f"- {a['source']}: {a['title']}\n")
                f.write(f"  {a['url']} (by u/{a['author']}, {a['score']} points)\n")
                f.write(f"  → Potential for Startup Smartup reconnect or Project Explore mention\n\n")
        
        f.write("\n--- NEEDS THOMAS ---\n")
        f.write("IndieHackers + ed-tech funding news requires web_search tool.\n")
        f.write("Thomas: Please run searches for:\n")
        f.write("- IndieHackers discussions about founder education, getting first customers\n")
        f.write("- Recent ed-tech startup funding announcements (Crunchbase, TechCrunch)\n")
        f.write("- YC batch companies in education/learning space\n")

def main():
    print(f"Sheila scan starting: {datetime.utcnow()}")
    
    all_alerts = []
    all_alerts.extend(scan_reddit_startups())
    # IndieHackers + other sources need web_search tool
    
    write_alerts(all_alerts)
    
    print(f"Found {len(all_alerts)} alerts")

if __name__ == '__main__':
    main()
