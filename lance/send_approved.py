#!/usr/bin/env python3
"""
Lance - Send Approved Drafts
Queries namespace for approved items, sends to HN/Reddit, updates with outcome
"""
import requests
import json
import time
from datetime import datetime

ZEROLATENCY_API_KEY = open('/root/.openclaw/workspace/THOMAS_API_KEY.txt').read().strip()
API_URL = 'https://api.0latency.ai/v1/recall'

def query_approved_drafts():
    """Query lance namespace for approved drafts"""
    try:
        response = requests.post(
            API_URL,
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'lance',
                'query': 'status approved ready to send',
                'conversation_context': 'checking for approved drafts to send',
                'limit': 20
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('context_block', '')
        else:
            print(f"Error querying approved drafts: {response.status_code}")
            return ''
            
    except Exception as e:
        print(f"Error: {e}")
        return ''

def send_to_hn(url, comment_text):
    """
    Send comment to Hacker News
    TODO: Implement actual HN posting via browser automation
    For now, just simulate
    """
    print(f"  [SIMULATED] Posting to HN: {url}")
    print(f"  Comment: {comment_text[:100]}...")
    # In production, use browser tool or HN API
    return {
        'sent': True,
        'url': url,
        'timestamp': datetime.utcnow().isoformat(),
        'outcome_placeholder': 'Check back in 24-48h for engagement metrics'
    }

def send_to_reddit(url, comment_text):
    """
    Send comment to Reddit  
    TODO: Implement actual Reddit posting
    For now, just simulate
    """
    print(f"  [SIMULATED] Posting to Reddit: {url}")
    print(f"  Comment: {comment_text[:100]}...")
    return {
        'sent': True,
        'url': url,
        'timestamp': datetime.utcnow().isoformat(),
        'outcome_placeholder': 'Check back in 24-48h for engagement metrics'
    }

def update_sent_status(original_memory_summary, outcome):
    """Store sent status + outcome placeholder in lance namespace"""
    try:
        response = requests.post(
            'https://api.0latency.ai/extract',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'lance',
                'human_message': f"Draft sent: {original_memory_summary[:100]}",
                'agent_message': f"""SENT - Outcome tracking placeholder

Original draft: {original_memory_summary[:200]}

Status: sent
Sent at: {outcome['timestamp']}
URL: {outcome['url']}

OUTCOME PLACEHOLDER:
{outcome['outcome_placeholder']}

TODO: Update this memory in 24-48h with actual engagement metrics:
- HN: upvotes, replies, discussion quality
- Reddit: upvotes, replies
- Outcome will inform Loop's future priority scoring
"""
            },
            timeout=30
        )
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"Error updating sent status: {e}")
        return False

def main():
    print(f"Lance send_approved starting: {datetime.utcnow()}")
    
    # Query for approved drafts
    approved_context = query_approved_drafts()
    
    if not approved_context or 'No relevant' in approved_context:
        print("No approved drafts to send")
        return 0
    
    print("Found approved drafts. Processing...")
    
    # For now, just log that we found them
    # In production, parse approved_context to extract:
    # - Platform (HN/Reddit)
    # - URL
    # - Comment text
    # - Memory ID
    
    print("""
NOTE: Sending workflow is SIMULATED pending HN karma unlock.

Production workflow:
1. Parse approved items from context
2. Send to HN/Reddit using browser automation or API
3. Store sent status + outcome placeholder
4. After 24-48h, check engagement metrics and update

Current status: Waiting for Justin's HN karma to unlock commenting.
Once unlocked, this script will handle actual posting.
""")
    
    return 0

if __name__ == '__main__':
    main()
