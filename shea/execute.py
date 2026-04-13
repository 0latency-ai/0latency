#!/usr/bin/env python3
"""
Shea - PFL Academy Outreach Execution Agent (Memory-First Architecture)
Reads lead briefs from Scout, validates emails, drafts outreach, stores in namespace ONLY
"""
import os
import glob
import requests
from datetime import datetime

ZEROLATENCY_API_KEY = open('/root/.openclaw/workspace/THOMAS_API_KEY.txt').read().strip()
WORKSPACE = '/root/.openclaw/workspace/shea'
PENDING_DIR = f'{WORKSPACE}/leads-pending'

def store_draft_to_namespace(brief_filename, lead, draft, zerobounce_status):
    """Store draft in Shea's namespace with status=pending_validation_and_approval"""
    try:
        content = f"""State: {lead['state']}
Contact: {lead['contact']}
Email: {lead['email']}
ZeroBounce Status: {zerobounce_status}
Priority: {lead['priority']}
Status: pending_validation_and_approval
Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

DRAFT EMAIL:
{draft}

---
Intelligence Source: Scout brief {brief_filename}
Context: {lead['context'][:200]}
Standards Alignment: {lead['standards'][:200]}
Approval Required: {lead['approval']}

CRITICAL CHECKS BEFORE SENDING:
- Email must be ZeroBounce validated
- No Oklahoma Standard 15 references outside OK
- Correct state standards used
- Send ramp limits not exceeded (25/day days 1-5)
- Approved sender domain used

Awaiting ZeroBounce validation + Thomas/Justin approval before sending.
"""
        
        response = requests.post(
            'https://api.0latency.ai/extract',
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'shea',
                'human_message': f"Draft PFL outreach for {lead['state']} — {lead['contact']}",
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

def read_lead_brief(brief_path):
    """Parse lead brief from Scout"""
    with open(brief_path, 'r') as f:
        content = f.read()
    
    lead = {
        'state': '',
        'contact': '',
        'email': '',
        'context': '',
        'standards': '',
        'suggested_email': '',
        'priority': '',
        'approval': ''
    }
    
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        if line.startswith('**State:**'):
            lead['state'] = line.replace('**State:**', '').strip()
        elif line.startswith('**Contact:**'):
            lead['contact'] = line.replace('**Contact:**', '').strip()
        elif line.startswith('**Email:**'):
            lead['email'] = line.replace('**Email:**', '').strip()
        elif line.startswith('### Context'):
            current_section = 'context'
        elif line.startswith('### Standards Alignment'):
            current_section = 'standards'
        elif line.startswith('### Suggested Email'):
            current_section = 'suggested_email'
        elif line.startswith('### Send Priority'):
            current_section = 'priority'
        elif line.startswith('### Approval Required'):
            current_section = 'approval'
        elif line.startswith('###') or line.startswith('**'):
            current_section = None
        elif current_section and line.strip() and not line.startswith('---'):
            if current_section in lead:
                lead[current_section] += line.strip() + ' '
    
    return lead

def validate_email(email):
    """Validate email via ZeroBounce (placeholder)"""
    if not email or email == 'TBD' or 'needs research' in email.lower():
        return 'missing'
    return 'needs_validation'  # TODO: Implement actual ZeroBounce API call

def draft_email(lead):
    """Draft personalized PFL Academy outreach"""
    # CRITICAL: Check for Oklahoma Standard 15 outside Oklahoma
    if lead['state'] != 'Oklahoma' and 'Standard 15' in lead['standards']:
        return f"[ERROR: Draft references Standard 15 but state is {lead['state']}, not Oklahoma. Scout must correct.]"
    
    if lead['suggested_email'].strip() and '[Shea:' not in lead['suggested_email']:
        return lead['suggested_email'].strip()
    
    # Default template
    return f"""Subject: Financial Literacy Curriculum for {lead['state']}

Hi {lead['contact'] if lead['contact'] and lead['contact'] != 'TBD' else 'there'},

I noticed your interest in financial literacy curriculum{' on Reddit' if 'reddit' in lead.get('context', '').lower() else ''}.

We built PFL Academy specifically for {lead['state']} schools - it's aligned with {lead['standards'].strip() if lead['standards'].strip() else 'state standards'} and designed to be teacher-friendly (no prep time needed).

{lead['context'][:200] if lead['context'] else 'Students work through real-world scenarios at their own pace, and teachers get full curriculum coverage with minimal effort.'}

Would you be open to a quick demo? Happy to show you how it works.

Best,
Justin Ghiglia
Founder, PFL Academy
justin@pflacademy.co
"""

def process_leads():
    """Main execution loop - memory-first architecture"""
    leads = glob.glob(f'{PENDING_DIR}/*.md')
    
    if not leads:
        print("No pending lead briefs from Scout")
        return 0
    
    print(f"Processing {len(leads)} lead briefs...")
    stored_count = 0
    validation_needed = 0
    
    for lead_path in leads:
        lead_filename = os.path.basename(lead_path)
        print(f"  Processing: {lead_filename}")
        
        try:
            lead = read_lead_brief(lead_path)
            zerobounce_status = validate_email(lead['email'])
            
            if zerobounce_status == 'missing':
                print(f"    ⚠ Email missing - needs research before drafting")
                continue
            elif zerobounce_status == 'needs_validation':
                validation_needed += 1
            
            draft = draft_email(lead)
            
            # Store ONLY to namespace (no filesystem drafts)
            memory_id = store_draft_to_namespace(lead_filename, lead, draft, zerobounce_status)
            
            if memory_id:
                stored_count += 1
                print(f"    ✓ Stored to namespace: memory_id={memory_id}")
                os.rename(lead_path, f"{PENDING_DIR}/../leads-processed/{lead_filename}")
            else:
                print(f"    ✗ Failed to store to namespace")
            
        except Exception as e:
            print(f"    ✗ Error processing {lead_filename}: {e}")
    
    return stored_count

def main():
    print(f"Shea execution starting: {datetime.utcnow()}")
    
    os.makedirs(f'{WORKSPACE}/leads-processed', exist_ok=True)
    
    stored = process_leads()
    print(f"\nShea complete: {stored} drafts stored to namespace with status=pending_validation_and_approval")
    print("Thomas/Justin will review during heartbeat by querying Shea's namespace.")

if __name__ == '__main__':
    main()
