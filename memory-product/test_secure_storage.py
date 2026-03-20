#!/usr/bin/env python3
"""
Test script for the hardened storage modules.
Verifies that basic operations work with parameterized queries.
"""

import sys
import os
import traceback

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_non_multitenant():
    """Test the non-multitenant secure storage."""
    print("🧪 Testing non-multitenant secure storage...")
    
    try:
        import storage_secure as storage
        
        # Test memory creation
        test_memory = {
            'agent_id': 'test-agent',
            'headline': 'Test security fix implemented',
            'context': 'SQL injection vulnerabilities have been patched',
            'full_content': 'The storage layer now uses parameterized queries with psycopg2 instead of subprocess calls to psql with f-string formatting.',
            'memory_type': 'fact',
            'entities': ['security', 'SQL injection', 'psycopg2'],
            'categories': ['security', 'development'],
            'importance': 0.9,
            'confidence': 1.0,
            'metadata': {'test': True, 'hardening_date': '2026-03-20'}
        }
        
        # Store a test memory
        print("  📝 Storing test memory...")
        memory_id = storage.store_memory(test_memory)
        print(f"  ✅ Stored memory with ID: {memory_id}")
        
        # Get stats
        print("  📊 Getting memory stats...")
        stats = storage.get_memory_stats('test-agent')
        print(f"  ✅ Stats: {stats}")
        
        # Test handoff storage
        print("  📋 Storing test handoff...")
        test_handoff = {
            'agent_id': 'test-agent',
            'session_key': 'test-session-123',
            'summary': 'Security hardening test completed',
            'decisions_made': ['Use psycopg2', 'Implement connection pooling'],
            'open_threads': ['Performance testing'],
            'active_projects': ['Memory API hardening']
        }
        
        handoff_id = storage.store_handoff(test_handoff)
        print(f"  ✅ Stored handoff with ID: {handoff_id}")
        
        print("  🎉 Non-multitenant storage tests PASSED")
        return True
        
    except Exception as e:
        print(f"  ❌ Non-multitenant storage tests FAILED: {e}")
        traceback.print_exc()
        return False


def test_multitenant():
    """Test the multitenant secure storage."""
    print("🧪 Testing multitenant secure storage...")
    
    try:
        import storage_multitenant_secure as storage
        
        # Set tenant context
        test_tenant_id = "12345678-1234-1234-1234-123456789abc"
        storage.set_tenant_context(test_tenant_id)
        
        # Test memory creation
        test_memory = {
            'agent_id': 'test-agent-mt',
            'headline': 'Multitenant security fix implemented', 
            'context': 'SQL injection vulnerabilities patched in multitenant version',
            'full_content': 'The multitenant storage layer now uses parameterized queries with psycopg2 and proper tenant isolation.',
            'memory_type': 'fact',
            'entities': ['multitenant', 'security', 'SQL injection'],
            'categories': ['security', 'development'],
            'importance': 0.9,
            'confidence': 1.0,
            'metadata': {'test': True, 'tenant_test': True}
        }
        
        # Store a test memory
        print("  📝 Storing test memory with tenant context...")
        memory_id = storage.store_memory(test_memory, test_tenant_id)
        print(f"  ✅ Stored memory with ID: {memory_id}")
        
        # Get stats
        print("  📊 Getting memory stats...")
        stats = storage.get_memory_stats('test-agent-mt', test_tenant_id)
        print(f"  ✅ Stats: {stats}")
        
        # Test handoff storage
        print("  📋 Storing test handoff...")
        test_handoff = {
            'agent_id': 'test-agent-mt',
            'session_key': 'test-session-mt-123',
            'summary': 'Multitenant security hardening test completed',
            'decisions_made': ['Use psycopg2 with tenant isolation'],
            'open_threads': ['RLS verification'],
            'active_projects': ['Multitenant Memory API hardening']
        }
        
        handoff_id = storage.store_handoff(test_handoff, test_tenant_id)
        print(f"  ✅ Stored handoff with ID: {handoff_id}")
        
        print("  🎉 Multitenant storage tests PASSED")
        return True
        
    except Exception as e:
        print(f"  ❌ Multitenant storage tests FAILED: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🔒 Testing Hardened Storage Modules")
    print("=" * 50)
    
    success = True
    
    # Test non-multitenant version
    if not test_non_multitenant():
        success = False
    
    print()
    
    # Test multitenant version  
    if not test_multitenant():
        success = False
    
    print()
    print("=" * 50)
    
    if success:
        print("🎉 ALL TESTS PASSED - Hardened storage is working correctly!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Check the errors above")
        sys.exit(1)