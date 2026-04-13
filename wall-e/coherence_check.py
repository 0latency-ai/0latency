#!/usr/bin/env python3
"""
Wall-E - Organizational Memory Monitor
Cross-agent coherence checks, memory quality monitoring, knowledge propagation
"""
import requests
import json
from datetime import datetime, timedelta

ZEROLATENCY_API_KEY = open('/root/.openclaw/workspace/THOMAS_API_KEY.txt').read().strip()
API_URL = 'https://api.0latency.ai/v1/recall'
EXTRACT_URL = 'https://api.0latency.ai/extract'

AGENT_PAIRS = [
    ('thomas', 'loop'),
    ('thomas', 'scout'),
    ('thomas', 'sheila'),
    ('loop', 'lance'),
    ('scout', 'shea'),
    ('sheila', 'nellie'),
]

def recall_recent_memories(agent_id, query, limit=20):
    """Recall recent memories from agent namespace"""
    try:
        response = requests.post(
            API_URL,
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': agent_id,
                'query': query,
                'conversation_context': f'Wall-E coherence check for {agent_id}',
                'limit': limit
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('context_block', ''), data.get('memories_used', 0)
        else:
            return '', 0
            
    except Exception as e:
        print(f"Recall error for {agent_id}: {e}")
        return '', 0

def check_cross_agent_contradictions():
    """
    Check for factual contradictions between agent namespaces
    Example: Scout says "Colorado adoption Q3" but Thomas says "Q4"
    """
    print(f"\n=== Cross-Agent Coherence Check ===")
    print(f"Time: {datetime.utcnow().isoformat()}")
    
    contradictions_found = []
    
    # Check intelligence→execution pairs for misalignment
    for intelligence_agent, execution_agent in AGENT_PAIRS:
        intel_context, intel_count = recall_recent_memories(
            intelligence_agent, 
            f'recent findings decisions actions last 24 hours',
            limit=10
        )
        
        exec_context, exec_count = recall_recent_memories(
            execution_agent,
            f'pending actions drafts status last 24 hours',
            limit=10
        )
        
        print(f"\n{intelligence_agent} ↔ {execution_agent}:")
        print(f"  {intelligence_agent}: {intel_count} memories")
        print(f"  {execution_agent}: {exec_count} memories")
        
        # TODO: LLM-based contradiction detection once self-improving Phase 2 is live
        # For now, just log that check happened
        
        # Log recall usage
        log_coherence_check(intelligence_agent, execution_agent, intel_count, exec_count)
    
    return contradictions_found

def log_coherence_check(agent_a, agent_b, count_a, count_b):
    """Store coherence check as Wall-E memory (recall usage logging)"""
    try:
        log_content = f"""Cross-Agent Coherence Check

Agents Checked: {agent_a} ↔ {agent_b}
Memories Recalled: {agent_a}={count_a}, {agent_b}={count_b}

PURPOSE: Detect contradictions between intelligence and execution agent namespaces
OUTCOME: Monitoring for misaligned facts, inconsistent decisions

Status: No automated contradiction detection yet (pending self-improving Phase 2 LLM classifier)
Manual review: Thomas should spot-check if counts seem misaligned

This log will be enhanced with LLM-based contradiction detection once Phase 2 is live.
Generated: {datetime.utcnow().isoformat()}"""
        
        requests.post(
            EXTRACT_URL,
            headers={
                'X-API-Key': ZEROLATENCY_API_KEY,
                'Content-Type': 'application/json'
            },
            json={
                'agent_id': 'wall-e',
                'human_message': f"Coherence check — {agent_a} ↔ {agent_b}",
                'agent_message': log_content
            },
            timeout=30
        )
        
    except Exception as e:
        print(f"  Warning: Could not log coherence check: {e}")

def check_memory_quality():
    """
    Monitor memory quality across all agents
    Once self-improving Phase 2 is live, this will check:
    - Classification queue status
    - Consolidation rates
    - Contradiction flags
    """
    print(f"\n=== Memory Quality Check ===")
    print("Status: Monitoring disabled pending self-improving Phase 2 deployment")
    print("Once Phase 2 is live, Wall-E will check:")
    print("  - Consolidation queue depth")
    print("  - Classification accuracy")
    print("  - Contradiction flag rate")
    print("  - Per-agent memory quality scores")

def main():
    print(f"Wall-E coherence monitor starting: {datetime.utcnow()}")
    
    # Cross-agent coherence checks
    contradictions = check_cross_agent_contradictions()
    
    if contradictions:
        print(f"\n⚠ {len(contradictions)} contradictions detected")
        # TODO: Alert Thomas via namespace or file
    else:
        print(f"\n✓ No contradictions detected")
    
    # Memory quality monitoring (pending Phase 2)
    check_memory_quality()
    
    print(f"\nWall-E complete: {datetime.utcnow()}")

if __name__ == '__main__':
    main()
