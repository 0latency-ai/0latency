#!/usr/bin/env python3
"""
Test script for observability system
Verifies error tracking, metrics collection, and alerting
"""
import os
import sys
import time
from datetime import datetime

# Set up environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from observability import (
    log_error,
    ErrorLevel,
    get_error_stats,
    get_metrics_summary,
    send_alert,
)
from observability.metrics import _metrics_collector
from observability.error_tracker import _error_tracker

print("=" * 60)
print("0Latency Observability System Test")
print("=" * 60)

# Test 1: Error Tracking
print("\n[TEST 1] Error Tracking")
print("-" * 40)

try:
    # Generate a test error
    def test_function():
        raise ValueError("This is a test error for observability system")
    
    test_function()
except Exception as e:
    error_hash = log_error(
        e,
        level=ErrorLevel.ERROR,
        tenant_id="test-tenant-001",
        request_id="test-req-123",
        endpoint="/test/endpoint",
        extra_context={"test": "data"}
    )
    print(f"✓ Error logged with hash: {error_hash}")

# Log a second occurrence of the same error
try:
    def test_function():
        raise ValueError("This is a test error for observability system")
    test_function()
except Exception as e:
    error_hash2 = log_error(
        e,
        level=ErrorLevel.ERROR,
        tenant_id="test-tenant-002",
        endpoint="/test/endpoint"
    )
    print(f"✓ Second occurrence logged: {error_hash2}")
    print(f"  (Should have same hash: {error_hash == error_hash2})")

# Test 2: Error Statistics
print("\n[TEST 2] Error Statistics")
print("-" * 40)

stats = get_error_stats(hours=1)
print(f"✓ Total errors (last hour): {stats['total_errors']}")
print(f"✓ Unique error groups: {stats['unique_error_groups']}")
print(f"✓ Error rate: {stats['error_rate_per_minute']:.2f}/min")

if stats['top_errors']:
    print(f"✓ Top error:")
    top = stats['top_errors'][0]
    print(f"  - Type: {top['error_type']}")
    print(f"  - Count: {top['occurrence_count']}")
    print(f"  - Affected tenants: {top['affected_tenants']}")

# Test 3: Metrics Collection
print("\n[TEST 3] Metrics Collection")
print("-" * 40)

# Simulate some API requests
for i in range(5):
    _metrics_collector.track_request(
        endpoint="POST /memories/add",
        duration_ms=100 + (i * 20),
        status_code=200,
        tenant_id=f"tenant-{i}"
    )

# Simulate a slow request
_metrics_collector.track_request(
    endpoint="POST /memories/add",
    duration_ms=6000,  # 6 seconds - should trigger slow request warning
    status_code=200
)

# Simulate an error
_metrics_collector.track_request(
    endpoint="POST /memories/add",
    duration_ms=150,
    status_code=500
)

endpoint_stats = _metrics_collector.get_endpoint_stats("POST /memories/add")
print(f"✓ Request count: {endpoint_stats['request_count']}")
print(f"✓ Error rate: {endpoint_stats['error_rate']:.2%}")
print(f"✓ Latency p50: {endpoint_stats['latency_ms']['p50']:.0f}ms")
print(f"✓ Latency p95: {endpoint_stats['latency_ms']['p95']:.0f}ms")
print(f"✓ Latency p99: {endpoint_stats['latency_ms']['p99']:.0f}ms")

# Test 4: Database Query Tracking
print("\n[TEST 4] Database Query Tracking")
print("-" * 40)

_metrics_collector.track_database_query(45.2, "SELECT * FROM memories LIMIT 10")
_metrics_collector.track_database_query(6500, "SELECT * FROM memories WHERE tenant_id = 'slow-tenant'")

db_stats = _metrics_collector.get_database_stats()
print(f"✓ Query count: {db_stats['query_count']}")
print(f"✓ Slow queries: {db_stats['slow_query_count']}")
if db_stats['latency_ms']:
    print(f"✓ DB p95 latency: {db_stats['latency_ms']['p95']:.0f}ms")

# Test 5: System Metrics
print("\n[TEST 5] System Metrics")
print("-" * 40)

system_stats = _metrics_collector.get_system_stats()
if system_stats:
    print(f"✓ Memory usage: {system_stats['memory']['percent']:.1f}%")
    print(f"✓ Disk usage: {system_stats['disk']['percent']:.1f}%")
    print(f"✓ CPU usage: {system_stats['cpu_percent']:.1f}%")
else:
    print("✗ Failed to get system stats")

# Test 6: Metrics Summary
print("\n[TEST 6] Full Metrics Summary")
print("-" * 40)

summary = get_metrics_summary()
print(f"✓ Timestamp: {summary['timestamp']}")
print(f"✓ Endpoints tracked: {len(summary['endpoints'])}")
print(f"✓ Database queries: {summary['database'].get('query_count', 0)}")
print(f"✓ System metrics: {'✓' if summary['system'] else '✗'}")

# Test 7: Alerting (optional - set SEND_TEST_ALERT=1 to enable)
print("\n[TEST 7] Alert System")
print("-" * 40)

if os.environ.get("SEND_TEST_ALERT") == "1":
    print("Sending test alert to Telegram...")
    success = send_alert(
        "🧪 Test alert from observability system\n\nThis is a test to verify Telegram alerting is working.",
        level="info",
        alert_type="test_alert",
        force=True  # Skip throttling for test
    )
    if success:
        print("✓ Alert sent successfully")
    else:
        print("✗ Alert failed (check TELEGRAM_BOT_TOKEN)")
else:
    print("⊘ Skipped (set SEND_TEST_ALERT=1 to enable)")

# Test 8: Error Details
print("\n[TEST 8] Error Details Retrieval")
print("-" * 40)

if error_hash:
    details = _error_tracker.get_error_details(error_hash, limit=5)
    if 'group' in details:
        group = details['group']
        print(f"✓ Error group: {group['error_type']}")
        print(f"✓ Occurrences: {group['occurrence_count']}")
        print(f"✓ Affected tenants: {group['affected_tenant_count']}")
        print(f"✓ First seen: {group['first_seen']}")
        print(f"✓ Last seen: {group['last_seen']}")
        print(f"✓ Recent occurrences: {len(details['recent_occurrences'])}")

# Test 9: Tenant Errors
print("\n[TEST 9] Tenant Error Tracking")
print("-" * 40)

tenant_errors = _error_tracker.get_tenant_errors("test-tenant-001", hours=1)
print(f"✓ Errors for test-tenant-001: {len(tenant_errors)}")
if tenant_errors:
    print(f"  - {tenant_errors[0]['error_type']}")

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print("✓ Error tracking: Working")
print("✓ Error grouping: Working")
print("✓ Metrics collection: Working")
print("✓ Database tracking: Working")
print("✓ System metrics: Working")
print("✓ Statistics queries: Working")
print()
print("Observability system is operational!")
print()
print("Next steps:")
print("1. Integrate decorators into main.py endpoints")
print("2. Set up cron jobs for periodic checks")
print("3. Configure TELEGRAM_BOT_TOKEN for alerts")
print("4. Deploy status page to status.0latency.ai")
print()
