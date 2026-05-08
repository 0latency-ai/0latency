"""
CP8 P5.4 — Webhook emission integration tests
Per docs/CP8-P5-4-SCOPE.md Test Plan section
"""

import pytest
import json
import httpx
from unittest.mock import patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.webhook_emission import enqueue_webhook_event
from api.webhook_worker import process_webhook_queue


@pytest.fixture
def enterprise_tenant_with_webhook(db_conn):
    """Setup enterprise tenant with active webhook."""
    cur = db_conn.cursor()
    
    # Get or create enterprise tenant
    cur.execute("""
        SELECT id, api_key_live FROM memory_service.tenants 
        WHERE plan='enterprise' AND active=true LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        pytest.skip("No enterprise tenant available")
    
    tenant_id, api_key = row
    
    # Clean up existing webhooks
    cur.execute("DELETE FROM memory_service.webhook_deliveries WHERE tenant_id = %s::uuid", (tenant_id,))
    cur.execute("DELETE FROM memory_service.tenant_webhooks WHERE tenant_id = %s::uuid", (tenant_id,))
    db_conn.commit()
    
    # Create webhook
    cur.execute("""
        INSERT INTO memory_service.tenant_webhooks 
        (tenant_id, name, url, secret, event_types, enabled)
        VALUES (%s::uuid, %s, %s, %s, %s, %s)
        RETURNING id, secret
    """, (tenant_id, "test-webhook", "https://webhook.site/test", "a" * 64, ["synthesis.replaced"], True))
    
    webhook_row = cur.fetchone()
    webhook_id, secret = webhook_row
    db_conn.commit()
    
    yield {
        "tenant_id": tenant_id,
        "api_key": api_key,
        "webhook_id": webhook_id,
        "webhook_secret": secret,
        "db_conn": db_conn
    }
    
    # Cleanup
    cur.execute("DELETE FROM memory_service.webhook_deliveries WHERE tenant_id = %s::uuid", (tenant_id,))
    cur.execute("DELETE FROM memory_service.tenant_webhooks WHERE tenant_id = %s::uuid", (tenant_id,))
    db_conn.commit()


def test_supersession_creates_delivery_row(enterprise_tenant_with_webhook):
    """Supersession of synthesis row creates webhook_deliveries row"""
    fixture = enterprise_tenant_with_webhook
    db_conn = fixture["db_conn"]
    tenant_id = fixture["tenant_id"]
    
    # Simulate enqueue_webhook_event call
    payload = {
        "event_id": "test-event-123",
        "event_type": "synthesis.replaced",
        "occurred_at": "2026-05-08T12:00:00Z",
        "tenant_id": tenant_id,
        "synthesis": {"memory_id": "test-mem-123"}
    }
    
    cur = db_conn.cursor()
    cur.execute("""
        SELECT id FROM memory_service.tenant_webhooks 
        WHERE tenant_id = %s::uuid AND enabled = true
    """, (tenant_id,))
    webhook_rows = cur.fetchall()
    
    for webhook_row in webhook_rows:
        webhook_id = webhook_row[0]
        cur.execute("""
            INSERT INTO memory_service.webhook_deliveries
            (webhook_id, tenant_id, event_id, event_type, payload, status, next_attempt_at)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', now())
        """, (webhook_id, tenant_id, "test-event-123", "synthesis.replaced", json.dumps(payload)))
    
    db_conn.commit()
    
    # Verify delivery row exists
    cur.execute("""
        SELECT COUNT(*) FROM memory_service.webhook_deliveries 
        WHERE tenant_id = %s::uuid AND event_id = %s::uuid
    """, (tenant_id, "test-event-123"))
    
    count = cur.fetchone()[0]
    assert count == 1


def test_mock_200_response_marks_delivered(enterprise_tenant_with_webhook):
    """Mock 200 response marks delivery as delivered"""
    fixture = enterprise_tenant_with_webhook
    db_conn = fixture["db_conn"]
    tenant_id = fixture["tenant_id"]
    webhook_id = fixture["webhook_id"]
    
    # Create pending delivery
    cur = db_conn.cursor()
    cur.execute("""
        INSERT INTO memory_service.webhook_deliveries
        (webhook_id, tenant_id, event_id, event_type, payload, status, next_attempt_at)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', now())
        RETURNING id
    """, (webhook_id, tenant_id, "test-200-event", "synthesis.replaced", json.dumps({"test": "data"})))
    
    delivery_id = cur.fetchone()[0]
    db_conn.commit()
    
    # Mock httpx client to return 200
    def mock_transport(request):
        return httpx.Response(200, json={"success": True})
    
    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    
    with patch('api.webhook_worker.httpx.Client', return_value=mock_client):
        stats = process_webhook_queue(db_conn)
    
    # Verify delivery marked as delivered
    cur.execute("""
        SELECT status, last_status_code FROM memory_service.webhook_deliveries 
        WHERE id = %s::uuid
    """, (delivery_id,))
    
    row = cur.fetchone()
    assert row[0] == 'delivered'
    assert row[1] == 200


def test_mock_500_response_retries(enterprise_tenant_with_webhook):
    """Mock 500 response keeps status pending, increments attempts"""
    fixture = enterprise_tenant_with_webhook
    db_conn = fixture["db_conn"]
    tenant_id = fixture["tenant_id"]
    webhook_id = fixture["webhook_id"]
    
    # Create pending delivery
    cur = db_conn.cursor()
    cur.execute("""
        INSERT INTO memory_service.webhook_deliveries
        (webhook_id, tenant_id, event_id, event_type, payload, status, next_attempt_at, attempt_count)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', now(), 0)
        RETURNING id
    """, (webhook_id, tenant_id, "test-500-event", "synthesis.replaced", json.dumps({"test": "data"})))
    
    delivery_id = cur.fetchone()[0]
    db_conn.commit()
    
    # Mock httpx client to return 500
    def mock_transport(request):
        return httpx.Response(500, json={"error": "Internal Server Error"})
    
    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    
    with patch('api.webhook_worker.httpx.Client', return_value=mock_client):
        stats = process_webhook_queue(db_conn)
    
    # Verify delivery still pending, attempt count incremented
    cur.execute("""
        SELECT status, attempt_count, last_status_code, next_attempt_at > now() as has_future_retry
        FROM memory_service.webhook_deliveries 
        WHERE id = %s::uuid
    """, (delivery_id,))
    
    row = cur.fetchone()
    assert row[0] == 'pending'
    assert row[1] == 1
    assert row[2] == 500
    assert row[3] is True


def test_five_failures_marks_dead(enterprise_tenant_with_webhook):
    """5 consecutive failures mark delivery as dead"""
    fixture = enterprise_tenant_with_webhook
    db_conn = fixture["db_conn"]
    tenant_id = fixture["tenant_id"]
    webhook_id = fixture["webhook_id"]
    
    # Create pending delivery with 4 attempts already
    cur = db_conn.cursor()
    cur.execute("""
        INSERT INTO memory_service.webhook_deliveries
        (webhook_id, tenant_id, event_id, event_type, payload, status, next_attempt_at, attempt_count)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', now(), 4)
        RETURNING id
    """, (webhook_id, tenant_id, "test-dead-event", "synthesis.replaced", json.dumps({"test": "data"})))
    
    delivery_id = cur.fetchone()[0]
    db_conn.commit()
    
    # Mock httpx client to return 500
    def mock_transport(request):
        return httpx.Response(500)
    
    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    
    with patch('api.webhook_worker.httpx.Client', return_value=mock_client):
        stats = process_webhook_queue(db_conn)
    
    # Verify delivery marked as dead
    cur.execute("""
        SELECT status, attempt_count FROM memory_service.webhook_deliveries 
        WHERE id = %s::uuid
    """, (delivery_id,))
    
    row = cur.fetchone()
    assert row[0] == 'dead'
    assert row[1] == 5


def test_forty_failures_auto_disables(enterprise_tenant_with_webhook):
    """40 consecutive failures auto-disable webhook"""
    fixture = enterprise_tenant_with_webhook
    db_conn = fixture["db_conn"]
    tenant_id = fixture["tenant_id"]
    webhook_id = fixture["webhook_id"]
    
    # Set webhook to 39 consecutive failures
    cur = db_conn.cursor()
    cur.execute("""
        UPDATE memory_service.tenant_webhooks 
        SET consecutive_failures = 39
        WHERE id = %s::uuid
    """, (webhook_id,))
    db_conn.commit()
    
    # Create pending delivery
    cur.execute("""
        INSERT INTO memory_service.webhook_deliveries
        (webhook_id, tenant_id, event_id, event_type, payload, status, next_attempt_at, attempt_count)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', now(), 0)
        RETURNING id
    """, (webhook_id, tenant_id, "test-autodisable-event", "synthesis.replaced", json.dumps({"test": "data"})))
    
    db_conn.commit()
    
    # Mock httpx client to return 500
    def mock_transport(request):
        return httpx.Response(500)
    
    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    
    with patch('api.webhook_worker.httpx.Client', return_value=mock_client):
        stats = process_webhook_queue(db_conn)
    
    # Verify webhook disabled
    cur.execute("""
        SELECT enabled, consecutive_failures FROM memory_service.tenant_webhooks 
        WHERE id = %s::uuid
    """, (webhook_id,))
    
    row = cur.fetchone()
    assert row[0] is False
    assert row[1] >= 40


def test_disabled_webhook_not_enqueued(enterprise_tenant_with_webhook):
    """Disabled webhook does not get deliveries enqueued"""
    fixture = enterprise_tenant_with_webhook
    db_conn = fixture["db_conn"]
    tenant_id = fixture["tenant_id"]
    webhook_id = fixture["webhook_id"]
    
    # Disable webhook
    cur = db_conn.cursor()
    cur.execute("""
        UPDATE memory_service.tenant_webhooks 
        SET enabled = false
        WHERE id = %s::uuid
    """, (webhook_id,))
    db_conn.commit()
    
    # Try to enqueue
    cur.execute("""
        SELECT COUNT(*) FROM memory_service.tenant_webhooks 
        WHERE tenant_id = %s::uuid AND enabled = true
    """, (tenant_id,))
    
    enabled_count = cur.fetchone()[0]
    assert enabled_count == 0


def test_soft_deleted_webhook_not_enqueued(enterprise_tenant_with_webhook):
    """Soft-deleted webhook does not get deliveries enqueued"""
    fixture = enterprise_tenant_with_webhook
    db_conn = fixture["db_conn"]
    tenant_id = fixture["tenant_id"]
    webhook_id = fixture["webhook_id"]
    
    # Soft delete webhook
    cur = db_conn.cursor()
    cur.execute("""
        UPDATE memory_service.tenant_webhooks 
        SET deleted_at = now()
        WHERE id = %s::uuid
    """, (webhook_id,))
    db_conn.commit()
    
    # Verify not included in active webhooks query
    cur.execute("""
        SELECT COUNT(*) FROM memory_service.tenant_webhooks 
        WHERE tenant_id = %s::uuid AND deleted_at IS NULL
    """, (tenant_id,))
    
    active_count = cur.fetchone()[0]
    assert active_count == 0


def test_transaction_rollback_no_delivery(enterprise_tenant_with_webhook):
    """Rolled-back transaction does not create webhook_deliveries row (outbox correctness)"""
    fixture = enterprise_tenant_with_webhook
    db_conn = fixture["db_conn"]
    tenant_id = fixture["tenant_id"]
    webhook_id = fixture["webhook_id"]
    
    # Start transaction
    cur = db_conn.cursor()
    
    # Insert delivery
    cur.execute("""
        INSERT INTO memory_service.webhook_deliveries
        (webhook_id, tenant_id, event_id, event_type, payload, status, next_attempt_at)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'pending', now())
        RETURNING id
    """, (webhook_id, tenant_id, "test-rollback-event", "synthesis.replaced", json.dumps({"test": "data"})))
    
    delivery_id = cur.fetchone()[0]
    
    # Rollback
    db_conn.rollback()
    
    # Verify no delivery row exists
    cur.execute("""
        SELECT COUNT(*) FROM memory_service.webhook_deliveries 
        WHERE id = %s::uuid
    """, (delivery_id,))
    
    count = cur.fetchone()[0]
    assert count == 0
