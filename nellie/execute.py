#!/usr/bin/env python3
"""
Nellie - Startup Smartup Outreach Execution Agent (Memory-First Architecture)
Reads reconnect briefs from Sheila, drafts warm messages, stores in namespace ONLY
"""
import os
import glob
import requests
from datetime import datetime

ZEROLATENCY_API_KEY = open('/root/.openclaw/workspace/THOMAS_API_KEY.txt').read().strip()
WORKSPACE = '/root/.openclaw/workspace/nellie'
PENDING_DIR = f'{WORKSPACE}/reconnect-pending'

def store_draft_to_namespace(brief_filename, reconnect, draft):
    """Store draft in Nellie's namespace with status=pending_approval"""
    try:
        content = f"""Contact: {reconnect['contact']}
Platform: {reconnect['platform']}
Channel: {reconnect['channel']}
Priority: {reconnect['priority']}
Status: pending_approval
Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

DRAFT MESSAGE:
{draft}

---
Intelligence Source: Sheila brief {brief_filename}
Context: {reconnect['context'][:200]}
Trigger: {reconnect['trigger'][:200]}

TONE CHECK:
- Warm and personal (not salesy)
- Relationship-focused (not transactional)
- Authentic (no corporate speak)

Awaiting Thomas approval before sending.
"""
        
        response = requests.post(
            'https://api.0latency.ai/extract',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'nellie',
                'human_message': f"Draft reconnect for {reconnect['contact']} — Startup Smartup",
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

def read_reconnect_brief(brief_path):
    """Parse reconnect brief from Sheila"""
    with open(brief_path, 'r') as f:
        content = f.read()
    
    reconnect = {
        'contact': '',
        'platform': '',
        'context': '',
        'trigger': '',
        'suggested_message': '',
        'channel': '',
        'priority': ''
    }
    
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        if line.startswith('**Contact:**'):
            reconnect['contact'] = line.replace('**Contact:**', '').strip()
        elif line.startswith('**Platform:**'):
            reconnect['platform'] = line.replace('**Platform:**', '').strip()
        elif line.startswith('### Context'):
            current_section = 'context'
        elif line.startswith('### Reconnect Trigger'):
            current_section = 'trigger'
        elif line.startswith('### Suggested Message'):
            current_section = 'suggested_message'
        elif line.startswith('### Channel'):
            current_section = 'channel'
        elif line.startswith('### Priority'):
            current_section = 'priority'
        elif line.startswith('###') or line.startswith('**'):
            current_section = None
        elif current_section and line.strip() and not line.startswith('---'):
            if current_section in reconnect:
                reconnect[current_section] += line.strip() + ' '
    
    return reconnect

def draft_message(reconnect):
    """Draft warm, personal reconnect message (Nellie's signature tone)"""
    channel = reconnect['channel'].strip().lower()
    contact = reconnect['contact']
    
    if 'reddit' in channel:
        draft = f"""Hey {contact}!

Saw your post about {reconnect['context'][:100] if reconnect['context'] else 'startup challenges'} and thought of you.

{reconnect['trigger'][:150] if reconnect['trigger'] else 'We actually built something that might help with this exact problem.'}

Would love to reconnect and share what we learned building Startup Smartup. No pitch, just genuinely think this could be useful.

Let me know if you're up for a quick chat!

Best,
Justin"""
    
    elif 'email' in channel or 'linkedin' in channel:
        draft = f"""Subject: Quick reconnect - {reconnect['trigger'][:50] if reconnect['trigger'] else 'thought of you'}

Hi {contact.replace('u/', '') if contact.startswith('u/') else contact}!

{reconnect['context'][:200] if reconnect['context'] else 'Hope you\'re doing well!'}

{reconnect['trigger'][:200] if reconnect['trigger'] else 'I saw you were working on [topic] and immediately thought of our conversation from [timeframe].'}

Would love to catch up and hear how things are going. We've been working on some stuff at Startup Smartup that might be relevant, but honestly just want to reconnect.

Coffee chat sometime? (Virtual or in-person, whatever works!)

Best,
Justin Ghiglia
Startup Smartup
justin@startupsmartup.com
"""
    else:
        draft = reconnect['suggested_message'].strip() if reconnect['suggested_message'].strip() and '[Nellie:' not in reconnect['suggested_message'] else f"""Hi {contact}!

{reconnect['context'][:150]}

{reconnect['trigger'][:150]}

Would love to reconnect - let me know if you're up for a quick chat!

Best,
Justin"""
    
    return draft

def process_reconnects():
    """Main execution loop - memory-first architecture"""
    briefs = glob.glob(f'{PENDING_DIR}/*.md')
    
    if not briefs:
        print("No pending reconnect briefs from Sheila")
        return 0
    
    print(f"Processing {len(briefs)} reconnect briefs...")
    stored_count = 0
    
    for brief_path in briefs:
        brief_filename = os.path.basename(brief_path)
        print(f"  Processing: {brief_filename}")
        
        try:
            reconnect = read_reconnect_brief(brief_path)
            draft = draft_message(reconnect)
            
            # Store ONLY to namespace (no filesystem drafts)
            memory_id = store_draft_to_namespace(brief_filename, reconnect, draft)
            
            if memory_id:
                stored_count += 1
                print(f"    ✓ Stored to namespace: memory_id={memory_id}")
                os.rename(brief_path, f"{PENDING_DIR}/../reconnect-processed/{brief_filename}")
            else:
                print(f"    ✗ Failed to store to namespace")
            
        except Exception as e:
            print(f"    ✗ Error processing {brief_filename}: {e}")
    
    return stored_count

def main():
    print(f"Nellie execution starting: {datetime.utcnow()}")
    
    os.makedirs(f'{WORKSPACE}/reconnect-processed', exist_ok=True)
    
    stored = process_reconnects()
    print(f"\nNellie complete: {stored} drafts stored to namespace with status=pending_approval")
    print("Thomas will review during heartbeat by querying Nellie's namespace.")

if __name__ == '__main__':
    main()
