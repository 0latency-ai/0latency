#!/usr/bin/env python3
"""
Sheila - Startup Smartup Intelligence Scanner v2 (Orchestration Edition)
Now stores findings in sheila namespace + writes reconnect briefs to Nellie
"""
import requests
import json
from datetime import datetime

ZEROLATENCY_API_KEY = open('/root/.openclaw/workspace/THOMAS_API_KEY.txt').read().strip()

def store_to_namespace(headline, content, importance=0.6):
    """Store finding in Sheila's namespace"""
    try:
        response = requests.post(
            'https://api.0latency.ai/extract',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'sheila',
                'human_message': f"New Startup Smartup opportunity: {headline}",
                'agent_message': content
            },
            timeout=30
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Namespace storage error: {e}")
        return False

def write_reconnect_brief(opportunity):
    """Write reconnect brief to Nellie's workspace"""
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    contact = opportunity.get('author', 'community').replace('/', '-').lower()
    filename = f"/root/.openclaw/workspace/nellie/reconnect-pending/{timestamp}-{contact}.md"
    
    with open(filename, 'w') as f:
        f.write(f"""## Reconnect Brief

**Contact:** {opportunity.get('contact', 'Reddit community member')}
**Platform:** {opportunity.get('source', 'Reddit')}
**Found:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

### Context
{opportunity.get('context', 'Startup founder discussing early-stage challenges relevant to Startup Smartup.')}

### Reconnect Trigger
{opportunity.get('trigger', 'Engaged in discussion about founder education / getting first customers')}

### Suggested Message
{opportunity.get('suggested_message', '[Nellie: Draft warm, personal message based on discussion context]')}

### Channel
{opportunity.get('channel', 'Reddit DM')}

### Priority
{opportunity.get('priority', 'NORMAL')}

---
**Status:** pending_review
**Assigned To:** nellie
""")
    return filename

def scan_reddit_startups():
    """Scan r/startups and r/Entrepreneur for reconnect triggers"""
    opportunities = []
    subreddits = ['startups', 'Entrepreneur']
    
    keywords = ['first customer', 'validate idea', 'startup education', 'learning', 'founder journey']
    
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=20"
            headers = {'User-Agent': 'Sheila SS Intelligence/2.0'}
            r = requests.get(url, headers=headers, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for post in data.get('data', {}).get('children', []):
                    p = post['data']
                    title_lower = p['title'].lower()
                    selftext_lower = p.get('selftext', '').lower()
                    
                    # Look for posts about startup education, first customers
                    if any(kw in title_lower or kw in selftext_lower for kw in keywords):
                        opp = {
                            'source': f'r/{sub}',
                            'title': p['title'],
                            'url': f"https://reddit.com{p['permalink']}",
                            'author': p['author'],
                            'score': p['score'],
                            'type': 'community',
                            'contact': f"u/{p['author']}",
                            'context': f"Founder discussing: {p['title'][:100]}",
                            'trigger': 'Engaged in startup education / first customer discussion',
                            'channel': 'Reddit DM',
                            'priority': 'HIGH' if p['score'] > 20 else 'NORMAL'
                        }
                        
                        # Store to namespace
                        content = f"""
Source: {opp['source']}
Author: u/{p['author']}
Post: {p['title']}
URL: {opp['url']}
Score: {p['score']} points
Context: Founder discussing startup education, validation, or first customers
Opportunity Type: Community engagement / Startup Smartup reconnect potential
Trigger: {opp['trigger']}
"""
                        store_to_namespace(f"{opp['source']} — {p['title'][:60]}", content, 0.6)
                        
                        # Write reconnect brief for high-engagement posts
                        if p['score'] > 15:
                            brief_file = write_reconnect_brief(opp)
                            print(f"  → Reconnect brief: {brief_file}")
                        
                        opportunities.append(opp)
        except Exception as e:
            print(f"Reddit r/{sub} error: {e}")
    
    return opportunities

def write_alerts(all_findings):
    """Write summary for Thomas"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    with open('/root/.openclaw/workspace/sheila/alerts-pending.txt', 'w') as f:
        f.write(f"=== Sheila Intelligence Scan - {timestamp} ===\n\n")
        
        community = [f for f in all_findings if f.get('type') == 'community']
        
        if not all_findings:
            f.write("NO_NEW_ALERTS - Market quiet\n")
            f.write("No significant Startup Smartup opportunities detected since last scan.\n")
            f.write("\n--- Stored to Namespace ---\n")
            f.write("0 new memories (no findings)\n")
            return
        
        if community:
            f.write("COMMUNITY ENGAGEMENT OPPORTUNITIES:\n")
            for opp in community[:7]:
                f.write(f"- {opp['source']}: {opp['title']}\n")
                f.write(f"  {opp['url']} (by u/{opp['author']}, {opp['score']} points)\n")
                f.write(f"  → Potential for Startup Smartup reconnect or Project Explore mention\n")
                if opp.get('score', 0) > 15:
                    f.write(f"  ✓ Reconnect brief written for Nellie\n")
                f.write("\n")
        
        f.write(f"\n--- Stored to Namespace ---\n")
        f.write(f"{len(all_findings)} findings stored in sheila namespace\n")
        f.write(f"{len([f for f in community if f.get('score', 0) > 15])} reconnect briefs written for Nellie\n")
        
        f.write("\n--- NEEDS WEB_SEARCH (Thomas) ---\n")
        f.write("IndieHackers + ed-tech funding news requires web_search tool.\n")
        f.write("Thomas: Run searches for:\n")
        f.write("- IndieHackers: founder education, first customers discussions\n")
        f.write("- Recent ed-tech startup funding (Crunchbase, TechCrunch)\n")
        f.write("- YC batch companies in education/learning space\n")

def main():
    print(f"Sheila scan starting: {datetime.utcnow()}")
    
    all_findings = []
    all_findings.extend(scan_reddit_startups())
    
    write_alerts(all_findings)
    
    print(f"Found {len(all_findings)} opportunities")
    print(f"  Stored to sheila namespace: {len(all_findings)} memories")
    print(f"  Reconnect briefs for Nellie: {len([f for f in all_findings if f.get('score', 0) > 15])}")

if __name__ == '__main__':
    main()
