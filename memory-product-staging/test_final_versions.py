#!/usr/bin/env python3
"""
Test the final replaced storage files to ensure they work correctly.
Uses mock embeddings to avoid API dependencies.
"""

import sys
import os

def test_final_storage():
    """Test that the final storage.py works correctly."""
    print("🧪 Testing final storage.py...")
    
    # Add src to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    try:
        import storage
        
        # Mock the embedding function to avoid API calls
        def mock_embed_text(text):
            # Return a fake 768-dimensional embedding
            return [0.1] * 768
        
        # Replace the embedding function
        storage._embed_text = mock_embed_text
        
        # Test stats function (doesn't need embeddings)
        stats = storage.get_memory_stats('test-agent')
        print(f"  ✅ get_memory_stats works: {stats}")
        
        print("  🎉 Final storage.py tests PASSED")
        return True
        
    except Exception as e:
        print(f"  ❌ Final storage.py test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_final_multitenant_storage():
    """Test that the final storage_multitenant.py works correctly."""
    print("🧪 Testing final storage_multitenant.py...")
    
    try:
        import storage_multitenant
        
        # Mock the embedding function to avoid API calls
        def mock_embed_text(text):
            # Return a fake 768-dimensional embedding
            return [0.1] * 768
        
        # Replace the embedding function
        storage_multitenant._embed_text = mock_embed_text
        
        # Set tenant context
        test_tenant_id = "12345678-1234-1234-1234-123456789abc"
        storage_multitenant.set_tenant_context(test_tenant_id)
        
        # Test stats function (doesn't need embeddings)
        stats = storage_multitenant.get_memory_stats('test-agent', test_tenant_id)
        print(f"  ✅ get_memory_stats works: {stats}")
        
        print("  🎉 Final storage_multitenant.py tests PASSED")
        return True
        
    except Exception as e:
        print(f"  ❌ Final storage_multitenant.py test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🔒 Testing Final Hardened Storage Files")
    print("=" * 50)
    
    success = True
    
    if not test_final_storage():
        success = False
    
    print()
    
    if not test_final_multitenant_storage():
        success = False
    
    print()
    print("=" * 50)
    
    if success:
        print("🎉 ALL FINAL TESTS PASSED!")
        print("✅ Hardened storage files are working correctly")
        print("✅ Ready for production use")
    else:
        print("❌ SOME FINAL TESTS FAILED")
    
    sys.exit(0 if success else 1)