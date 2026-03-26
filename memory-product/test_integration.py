#!/usr/bin/env python3
"""Test that security/observability modules can be imported"""
import sys
import os

# Add paths
sys.path.insert(0, os.path.dirname(__file__))

# Load environment
from dotenv import load_dotenv
load_dotenv()

try:
    from security import AuditLogger, AuditEventType, check_rate_limit
    print("✓ Security module imports OK")
    
    from observability import ErrorTracker, ErrorLevel, track_error
    print("✓ Observability module imports OK")
    
    # Test initialization
    audit = AuditLogger()
    print("✓ AuditLogger initialized")
    
    tracker = ErrorTracker()
    print("✓ ErrorTracker initialized")
    
    print("\n✅ All modules ready for integration")
    
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
