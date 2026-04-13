#!/usr/bin/env python3
"""
Scout - PFL Academy Intelligence Scanner
Monitors for school district opportunities, RFPs, procurement postings
"""
import requests
from datetime import datetime

def scan_reddit_teachers():
    """Scan r/teachers for financial literacy discussions"""
    alerts = []
    try:
        url = "https://www.reddit.com/r/teachers/search.json?q=financial+literacy+OR+economics+OR+personal+finance&restrict_sr=1&sort=new&limit=15"
        headers = {'User-Agent': 'Scout PFL Intelligence/1.0'}
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            for post in data.get('data', {}).get('children', []):
                p = post['data']
                # Look for posts about curriculum, resources, or teaching PFL
                if any(kw in p['title'].lower() or kw in p.get('selftext', '').lower() 
                       for kw in ['curriculum', 'lesson', 'resource', 'teach', 'class']):
                    alerts.append({
                        'source': 'r/teachers',
                        'title': p['title'],
                        'url': f"https://reddit.com{p['permalink']}",
                        'author': p['author'],
                        'score': p['score'],
                        'type': 'community_engagement'
                    })
    except Exception as e:
        print(f"Reddit r/teachers error: {e}")
    
    return alerts

def search_state_doe_activity():
    """
    Note: State DOE searches require web_search tool (not available in pure Python)
    This function logs that manual/Thomas-driven search is needed
    """
    print("State DOE monitoring: Requires web_search tool - flagging for Thomas")
    return []

def check_email_alerts():
    """Check if email monitoring has flagged anything"""
    alerts = []
    try:
        with open('/root/scripts/email_alerts_pending.txt', 'r') as f:
            content = f.read().strip()
            if content and content != 'NO_NEW_ALERTS':
                alerts.append({
                    'source': 'Email Monitor',
                    'title': 'New email alerts detected',
                    'url': '/root/scripts/email_alerts_pending.txt',
                    'type': 'email_alert'
                })
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Email check error: {e}")
    
    return alerts

def write_alerts(alerts):
    """Write Scout alerts to file"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    with open('/root/.openclaw/workspace/scout/alerts-pending.txt', 'w') as f:
        f.write(f"=== Scout Intelligence Scan - {timestamp} ===\n\n")
        
        if not alerts:
            f.write("NO_NEW_ALERTS\n")
            f.write("No new PFL Academy opportunities detected since last scan.\n")
            return
        
        community = [a for a in alerts if a.get('type') == 'community_engagement']
        email = [a for a in alerts if a.get('type') == 'email_alert']
        
        if email:
            f.write("🚨 EMAIL ALERTS:\n")
            for a in email:
                f.write(f"- Check {a['url']} for details\n\n")
        
        if community:
            f.write("COMMUNITY ENGAGEMENT OPPORTUNITIES:\n")
            for a in community[:5]:
                f.write(f"- r/teachers: {a['title']}\n")
                f.write(f"  {a['url']} (by u/{a['author']}, {a['score']} points)\n")
                f.write(f"  → Could engage with PFL Academy resources\n\n")
        
        f.write("\n--- NEEDS THOMAS ---\n")
        f.write("State DOE monitoring (CO, KY, TX, FL) requires web_search tool.\n")
        f.write("Thomas: Please run targeted searches for:\n")
        f.write("- Colorado DOE procurement + RFPs\n")
        f.write("- Kentucky Dept of Education financial literacy initiatives\n")
        f.write("- Texas TEA curriculum updates\n")
        f.write("- Florida DOE ed-tech contracts\n")

def main():
    print(f"Scout scan starting: {datetime.utcnow()}")
    
    all_alerts = []
    all_alerts.extend(scan_reddit_teachers())
    all_alerts.extend(check_email_alerts())
    # State DOE searches need web_search tool - handled by Thomas
    
    write_alerts(all_alerts)
    
    print(f"Found {len(all_alerts)} alerts")

if __name__ == '__main__':
    main()
