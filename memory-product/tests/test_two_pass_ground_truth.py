#!/usr/bin/env python3
"""
Ground-truth test: Two-pass extraction must catch Business Administration degree
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/memory-product/src')

from extraction import extract_memories, extract_memories_two_pass

# Test case: Business Administration degree (from LongMemEval Q1)
human_msg = """I graduated with a degree in Business Administration, which has definitely helped me in my new role. Do you have any advice on how to stay organized when it comes to paperwork and documentation, especially when it comes to tracking expenses and reimbursements?"""

agent_msg = """Congratulations on your degree in Business Administration! That's a great foundation for your new role.

Staying organized with paperwork and documentation is crucial, especially when it comes to tracking expenses and reimbursements. Here are some tips to help you stay on top of it:

1. Create a filing system: Develop a consistent filing system, both physical and digital...
2. Digitize your documents: Scan or digitize paper documents to reduce clutter...
3. Expense tracking tools: Utilize expense tracking tools like Expensify, Concur, or Zoho Expense..."""

print("=== GROUND-TRUTH TEST: Business Administration Degree ===\n")

# Test Pass 1 (Haiku only)
print("Pass 1 (Haiku only):")
pass1_memories = extract_memories(
    human_message=human_msg,
    agent_message=agent_msg,
    agent_id="test-ground-truth",
    session_key="test",
    turn_id="test-001",
)

print(f"  Extracted {len(pass1_memories)} memories")
found_degree_pass1 = False
for mem in pass1_memories:
    headline = mem.get('headline', '')
    if 'Business Administration' in headline or ('degree' in headline.lower() and 'business' in headline.lower()):
        print(f"  ✓ Found degree: {headline}")
        found_degree_pass1 = True

if not found_degree_pass1:
    print("  ✗ Business Administration degree NOT found in Pass 1")

# Test Two-Pass (Haiku + Sonnet)
print("\nTwo-Pass (Haiku + Sonnet):")
two_pass_memories = extract_memories_two_pass(
    human_message=human_msg,
    agent_message=agent_msg,
    agent_id="test-ground-truth",
    session_key="test",
    turn_id="test-002",
)

print(f"  Extracted {len(two_pass_memories)} memories total")

# Count by pass
pass1_count = sum(1 for m in two_pass_memories if m.get('metadata', {}).get('extraction_pass') == 1)
pass2_count = sum(1 for m in two_pass_memories if m.get('metadata', {}).get('extraction_pass') == 2)
print(f"    Pass 1: {pass1_count} memories")
print(f"    Pass 2: {pass2_count} memories")

found_degree_two_pass = False
for mem in two_pass_memories:
    headline = mem.get('headline', '')
    mem_type = mem.get('memory_type', '')
    extraction_pass = mem.get('metadata', {}).get('extraction_pass', 1)
    
    if 'Business Administration' in headline or ('degree' in headline.lower() and 'business' in headline.lower()):
        print(f"  ✓ Found degree (Pass {extraction_pass}): [{mem_type}] {headline}")
        found_degree_two_pass = True

if not found_degree_two_pass:
    print("  ✗ Business Administration degree NOT found in Two-Pass")
    sys.exit(1)

print("\n✅ GROUND-TRUTH TEST PASSED")
print("Two-pass extraction successfully catches Business Administration degree")
