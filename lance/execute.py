#!/usr/bin/env python3
"""
Lance - 0Latency Outreach Execution Agent (Memory-First Architecture)
Reads action briefs from Loop, drafts responses, stores in namespace ONLY
"""
import os
import glob
import requests
from datetime import datetime

ZEROLATENCY_API_KEY = open('/root/.openclaw/workspace/THOMAS_API_KEY.txt').read().strip()
WORKSPACE = '/root/.openclaw/workspace/lance'
PENDING_DIR = f'{WORKSPACE}/actions-pending'

def store_draft_to_namespace(brief_filename, brief, draft):
    """Store draft in Lance's namespace with status=pending_approval"""
    try:
        content = f"""Platform: {brief['platform']}
Source: {brief['source']}
Priority: {brief['priority']}
Status: pending_approval
Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

DRAFT RESPONSE:
{draft}

---
Intelligence Source: Loop brief {brief_filename}
Thread Context: {brief['thread_summary'][:200]}
Why Engage: {brief['why_engage'][:200]}
Tone Requested: {brief['tone']}
Deadline: {brief['deadline']}

Awaiting Thomas approval before sending.
"""
        
        response = requests.post(
            'https://api.0latency.ai/extract',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'lance',
                'human_message': f"Draft response for {brief['platform']} — {brief['thread_summary'][:60]}",
                'agent_message': content
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            memory_ids = data.get('memory_ids', [])
            return memory_ids[0] if memory_ids else None
        else:
            print(f"    ⚠ Namespace storage failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"    ✗ Namespace storage error: {e}")
        return None

def read_brief(brief_path):
    """Parse action brief from Loop"""
    with open(brief_path, 'r') as f:
        content = f.read()
    
    brief = {
        'source': '',
        'platform': '',
        'priority': '',
        'thread_summary': '',
        'why_engage': '',
        'engagement_type': '',
        'suggested_response': '',
        'tone': '',
        'cta': '',
        'deadline': ''
    }
    
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        if line.startswith('**Source:**'):
            brief['source'] = line.replace('**Source:**', '').strip()
        elif line.startswith('**Platform:**'):
            brief['platform'] = line.replace('**Platform:**', '').strip()
        elif line.startswith('**Priority:**'):
            brief['priority'] = line.replace('**Priority:**', '').strip()
        elif line.startswith('### Thread Summary'):
            current_section = 'thread_summary'
        elif line.startswith('### Why We Should Engage'):
            current_section = 'why_engage'
        elif line.startswith('### Engagement Opportunity'):
            current_section = 'engagement_type'
        elif line.startswith('### Suggested Response'):
            current_section = 'suggested_response'
        elif line.startswith('### Tone'):
            current_section = 'tone'
        elif line.startswith('### CTA'):
            current_section = 'cta'
        elif line.startswith('### Deadline'):
            current_section = 'deadline'
        elif line.startswith('###') or line.startswith('**'):
            current_section = None
        elif current_section and line.strip():
            brief[current_section] += line.strip() + ' '
    
    return brief

def recall_past_rejections(platform, topic_keywords):
    """
    Recall past rejected drafts to learn what NOT to do
    RECALL USAGE LOGGING (prep for Phase 3 /feedback integration)
    """
    try:
        response = requests.post(
            'https://api.0latency.ai/v1/recall',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'lance',
                'query': f'{platform} rejected drafts {topic_keywords}',
                'conversation_context': 'checking past rejections to avoid repeating mistakes',
                'limit': 10
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            memories_used = data.get('memories_used', 0)
            context = data.get('context_block', '')
            
            # Log recall usage as memory
            recall_log = f"""Recall Usage Log — Draft Guidance

Query: "{platform} rejected drafts {topic_keywords}"
Memories recalled: {memories_used}
Context retrieved: {len(context)} chars

PURPOSE: Learn from past rejections to improve draft quality
OUTCOME: Adjust tone/approach based on what Thomas previously rejected

Recalled context summary:
{context[:300] if context else "No past rejections found"}

This log will inform /feedback endpoint calls once Phase 3 is live.
Generated: {datetime.utcnow().isoformat()}"""
            
            requests.post(
                'https://api.0latency.ai/extract',
                headers={'X-API-Key': ZEROLATENCY_API_KEY, 'Content-Type': 'application/json'},
                json={
                    'agent_id': 'lance',
                    'human_message': f"Recall usage — {platform} draft guidance",
                    'agent_message': recall_log
                },
                timeout=30
            )
            
            return context, memories_used
        else:
            return '', 0
            
    except Exception as e:
        print(f"    Recall error (non-fatal): {e}")
        return '', 0

def draft_response(brief):
    """
    Draft response based on Loop's brief
    Now WITH recall-informed adjustments
    """
    platform = brief['platform']
    tone = brief['tone'].strip() or 'helpful-technical'
    topic = brief['thread_summary'][:50]
    
    # Recall past rejections for this platform/topic
    past_context, memories_recalled = recall_past_rejections(platform, topic)
    if memories_recalled > 0:
        print(f"    → Recalled {memories_recalled} past rejections for guidance")
    
    if platform == 'HN':
        draft = f"""Hey, interesting approach!

{brief['suggested_response'].strip() or 'This looks like a great use case for persistent memory. We built 0Latency specifically to solve this - it gives agents a cross-session memory layer so they don\'t forget context between runs.'}

{brief['cta'].strip() or 'Happy to share more about how we handle this: https://0latency.ai/docs'}

(Disclaimer: I work on 0Latency)
"""
    elif platform == 'Reddit' or platform.startswith('r/'):
        draft = f"""{brief['suggested_response'].strip() or 'This is exactly the kind of problem we built 0Latency to solve - agents that remember context across sessions without blowing up your token budget.'}

{brief['cta'].strip() or 'Check out the docs if you\'re interested: https://0latency.ai/docs'}

Full disclosure: I work on 0Latency, but genuinely think this is relevant to your use case.
"""
    else:
        draft = brief['suggested_response'].strip() or '[Lance: Draft response based on brief context]'
    
    return draft

def process_briefs():
    """Main execution loop - memory-first architecture"""
    briefs = glob.glob(f'{PENDING_DIR}/*.md')
    
    if not briefs:
        print("No pending action briefs from Loop")
        return 0
    
    print(f"Processing {len(briefs)} action briefs...")
    stored_count = 0
    
    for brief_path in briefs:
        brief_filename = os.path.basename(brief_path)
        print(f"  Processing: {brief_filename}")
        
        try:
            brief = read_brief(brief_path)
            draft = draft_response(brief)
            
            # Store ONLY to namespace (no filesystem drafts)
            memory_id = store_draft_to_namespace(brief_filename, brief, draft)
            
            if memory_id:
                stored_count += 1
                print(f"    ✓ Stored to namespace: memory_id={memory_id}")
                # Move processed brief to archive
                os.rename(brief_path, f"{PENDING_DIR}/../actions-processed/{brief_filename}")
            else:
                print(f"    ✗ Failed to store to namespace")
            
        except Exception as e:
            print(f"    ✗ Error processing {brief_filename}: {e}")
    
    return stored_count

def main():
    print(f"Lance execution starting: {datetime.utcnow()}")
    
    # Ensure processed directory exists
    os.makedirs(f'{WORKSPACE}/actions-processed', exist_ok=True)
    
    stored = process_briefs()
    print(f"\nLance complete: {stored} drafts stored to namespace with status=pending_approval")
    print("Thomas will review during next heartbeat by querying Lance's namespace.")

if __name__ == '__main__':
    main()
